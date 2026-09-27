"""O destravamento não pode repetir o waypoint que o jogo já recusou.

=========================================================================
O DEFEITO, RELATADO E MEDIDO EM 18/08/2026
=========================================================================

O usuário mandou a foto do chat do jogo (`data/templates/entrada/
erro-repeticao.png`) com a MESMA linha repetida muitas vezes:

    Failed to auto-path [Secret Altar(203,30)->Secret Altar(216,43)]

Ou seja: o jogo dizendo, dezenas de vezes, que aquele trajeto não existe de onde
o personagem está -- e o bot pedindo de novo.

DUAS CAUSAS, e as duas estão cobertas aqui.

1. O ORÇAMENTO TINHA SIDO CORTADO 5,3x. `SEGUNDOS_POR_TENTATIVA_DE_DESTRAVAR`
   estava em 1,5 s e `PASSADAS_DO_DESTRAVAMENTO` em 1, enquanto o
   `docs/decisoes/navegacao.md` registra **4 s e 2 passadas** com medição
   explícita ("dos 18 candidatos alcançados no log, 16 chegaram em ≤4 s"). Os
   comentários do próprio arquivo descreviam 4 s ao lado do valor 1,5. Confirmado
   no log de produção de 03:21: cada tentativa durou ~1,7 s e todas falharam.
   Candidato que chegaria em 2-4 s era abandonado antes de chegar.

2. NÃO HAVIA MEMÓRIA DE CANDIDATO QUE FALHOU. A manobra escolhe os candidatos a
   partir da POSIÇÃO ATUAL; se ela não muda, a escolha não muda. Cada nova
   chamada recomeçava com os mesmos três vizinhos -- o laço que o usuário viu.

A simulação abaixo roda a manobra com um jogo dublado em que UM waypoint é
intransitável, exatamente como o `Failed to auto-path` descreve.
"""
from __future__ import annotations

import pytest

from blazesbot.bot import navegacao as nav
from blazesbot.bot.bc import mapa_bc


class RotaFalsa(tuple):
    """Uma rota é uma tupla de waypoints; aqui basta ter `.pos`."""


class Waypoint:
    """O mínimo que a manobra e a tolerância do mapa injetado leem."""

    def __init__(self, pos):
        self.pos = pos
        self.area = "Secret Altar"
        self.tricky = False


def _rota(n=8):
    # Waypoints em linha, 10 unidades entre eles: vizinhos imediatos são
    # sempre os índices coladas, como na rota real.
    return RotaFalsa(Waypoint((200 + 10 * i, 30)) for i in range(n))


def _navegador(monkeypatch, rota, intransitaveis, posicao=(203, 30)):
    """Um `Navigator` com o mundo dublado no nível do próprio objeto."""
    servico = nav.Navigator.__new__(nav.Navigator)
    # O MAPA É INJETADO desde 01/09/2026: o navegador mora em `bot/` e serve os
    # dois ecossistemas, então quem responde "quanta folga neste waypoint" é o
    # mapa da cave, não um import fixo da BC. Como este dublê constrói o objeto
    # por `__new__`, o campo tem que ser posto à mão.
    servico.mapa = mapa_bc
    servico._retrocessos_feitos = set()
    servico._candidatos_que_falharam = set()
    servico._retrocesso_bloqueado = False
    servico._indice_do_retrocesso = None

    tentativas: list[tuple] = []

    class Log:
        def info(self, *a, **k): ...
        def debug(self, *a, **k): ...
        def warning(self, *a, **k): ...

    class Memoria:
        @staticmethod
        def location(): return "Secret Altar"

    class Ctx:
        log = Log()
        account_login = "simulacao"
        memory = Memoria()

        def raise_if_stopped(self): ...

    servico.ctx = Ctx()
    monkeypatch.setattr(servico, "position", lambda: posicao, raising=False)

    def follow_path(alvos, tolerance=None, max_seconds=None, **kw):
        alvo = alvos[0]
        tentativas.append(alvo)
        # O jogo RECUSA o trajeto para os pontos intransitáveis -- é o
        # `Failed to auto-path` da foto.
        return alvo not in intransitaveis

    monkeypatch.setattr(servico, "follow_path", follow_path, raising=False)
    return servico, tentativas


# =====================================================================
# O orçamento medido
# =====================================================================

def test_o_orcamento_medido_nao_foi_cortado_de_novo():
    """4 s e 2 passadas — os números do `docs/decisoes/navegacao.md`.

    Eles têm medição explícita e escaparam para 1,5 s / 1 passada no halvamento
    geral, cuja própria regra excluía thresholds medidos. Se caírem de novo, o
    laço volta: candidato que chegaria em 2-4 s é abandonado antes.
    """
    assert nav.SEGUNDOS_POR_TENTATIVA_DE_DESTRAVAR >= 4.0
    assert nav.PASSADAS_DO_DESTRAVAMENTO >= 2


# =====================================================================
# A memória de candidato que falhou
# =====================================================================

def test_o_candidato_que_falhou_NAO_e_tentado_de_novo(monkeypatch):
    """O laço da foto: mesma posição, mesma escolha, mesmo pedido recusado."""
    rota = _rota()
    base = 0
    # Tudo intransitável: a manobra falha e anota todos os candidatos.
    servico, tentativas = _navegador(monkeypatch, rota,
                                     intransitaveis={w.pos for w in rota})
    monkeypatch.setattr(nav, "vizinhos_na_rota",
                        lambda *a, **k: (None, base, base + 1))

    assert servico.destravar_pelos_vizinhos(rota) is None
    assert servico._candidatos_que_falharam, (
        "a manobra não anotou nenhum candidato como ruim — a próxima chamada "
        "vai repetir os mesmos, que é o laço relatado")


def test_a_manobra_se_AFASTA_quando_os_imediatos_falham(monkeypatch):
    """Pedido do usuário: "testar os outros para ver se destrava".

    Com os imediatos intransitáveis e um waypoint mais adiante livre, a manobra
    tem que ALCANÇAR o de adiante em vez de insistir.
    """
    rota = _rota()
    base = 3
    # Intransitáveis: o próprio, o seguinte e o anterior. Livre: base+2.
    ruins = {rota[base].pos, rota[base + 1].pos, rota[base - 1].pos}
    servico, tentativas = _navegador(monkeypatch, rota, intransitaveis=ruins)
    monkeypatch.setattr(nav, "vizinhos_na_rota",
                        lambda *a, **k: (base - 1, base, base + 1))
    monkeypatch.setattr(mapa_bc, "tolerancia_do_waypoint",
                        lambda *a, **k: 8)
    monkeypatch.setattr(nav, "distancia", lambda a, b: 50.0)

    alcancado = servico.destravar_pelos_vizinhos(rota)
    assert alcancado is not None, (
        "a manobra desistiu sem tentar nenhum waypoint além dos imediatos")
    assert alcancado not in (base, base + 1, base - 1)
    assert rota[alcancado].pos in tentativas


def test_a_expansao_segue_a_ORDEM_DA_ROTA_e_nao_a_distancia(monkeypatch):
    """A regra que custou uma run continua valendo.

    "A rota é um CAMINHO, e pular waypoint é atravessar parede." A expansão se
    afasta de um em um NA LISTA — base+2, base-2, base+3 — e nunca escolhe por
    proximidade em linha reta. O que mudou é só ATÉ ONDE ela vai depois de os
    imediatos terem falhado de verdade.
    """
    rota = _rota(10)
    base = 5
    servico, tentativas = _navegador(monkeypatch, rota,
                                     intransitaveis={w.pos for w in rota})
    monkeypatch.setattr(nav, "vizinhos_na_rota",
                        lambda *a, **k: (base - 1, base, base + 1))
    monkeypatch.setattr(mapa_bc, "tolerancia_do_waypoint",
                        lambda *a, **k: 8)
    monkeypatch.setattr(nav, "distancia", lambda a, b: 50.0)

    servico.destravar_pelos_vizinhos(rota)
    indices = [next(i for i, w in enumerate(rota) if w.pos == p)
               for p in tentativas]
    # A primeira volta tem que ir do mais perto ao mais longe NA LISTA.
    primeira_volta = indices[:len(set(indices))]
    distancias = [abs(i - base) for i in primeira_volta]
    assert distancias == sorted(distancias), (
        f"a ordem de tentativa não é do mais perto ao mais longe na rota: "
        f"{primeira_volta} (base {base})")
    assert max(distancias) <= nav.ALCANCE_DA_EXPANSAO


def test_chegar_ESQUECE_as_falhas(monkeypatch):
    """A lista de ruins era sobre uma posição em que o personagem não está mais.

    Mantê-la depois de chegar envenenaria o próximo episódio, recusando
    candidatos que agora podem funcionar.
    """
    rota = _rota()
    base = 2
    servico, _ = _navegador(monkeypatch, rota, intransitaveis=set())
    servico._candidatos_que_falharam = {0, 1, 7}
    monkeypatch.setattr(nav, "vizinhos_na_rota",
                        lambda *a, **k: (None, base, base + 1))
    monkeypatch.setattr(mapa_bc, "tolerancia_do_waypoint",
                        lambda *a, **k: 8)
    monkeypatch.setattr(nav, "distancia", lambda a, b: 50.0)

    assert servico.destravar_pelos_vizinhos(rota) is not None
    assert servico._candidatos_que_falharam == set(), (
        "a memória sobreviveu à chegada e vai recusar candidatos bons depois")


def test_todos_ruins_NAO_devolve_None_para_sempre(monkeypatch):
    """Esgotada a lista, a memória morre e a manobra recomeça.

    Sem isso a correção trocaria um laço por uma paralisia: a manobra devolveria
    `None` para sempre, sem nunca mais tentar nada.
    """
    rota = _rota()
    base = 3
    servico, tentativas = _navegador(monkeypatch, rota, intransitaveis=set())
    servico._candidatos_que_falharam = set(range(len(rota)))
    monkeypatch.setattr(nav, "vizinhos_na_rota",
                        lambda *a, **k: (base - 1, base, base + 1))
    monkeypatch.setattr(mapa_bc, "tolerancia_do_waypoint",
                        lambda *a, **k: 8)
    monkeypatch.setattr(nav, "distancia", lambda a, b: 50.0)

    assert servico.destravar_pelos_vizinhos(rota) is not None
    assert tentativas, "não tentou nada; a manobra ficou paralisada"


# =====================================================================
# DENTE — reintroduz o defeito e exige reprovação
# =====================================================================

def test_DENTE_sem_a_memoria_a_manobra_repete_o_mesmo_candidato(monkeypatch):
    """Sem anotar as falhas, duas chamadas seguidas pedem o MESMO trajeto.

    É o laço da foto. Se este teste parar de reproduzi-lo, a simulação deixou de
    ter o que os outros testes provam evitar.
    """
    rota = _rota()
    base = 0
    servico, tentativas = _navegador(monkeypatch, rota,
                                     intransitaveis={w.pos for w in rota})
    monkeypatch.setattr(nav, "vizinhos_na_rota",
                        lambda *a, **k: (None, base, base + 1))

    servico.destravar_pelos_vizinhos(rota)
    primeira = list(tentativas)
    # A VERSÃO ANTIGA: sem memória entre chamadas.
    servico._candidatos_que_falharam = set()
    tentativas.clear()
    servico.destravar_pelos_vizinhos(rota)
    assert tentativas == primeira, (
        "sem a memória as duas chamadas deveriam ser idênticas — se não são, "
        "a simulação não reproduz mais o laço relatado")


if __name__ == "__main__":
    pytest.main([__file__, "-q"])


# =====================================================================
# ANDAR ZERO UNIDADE NÃO DESTRAVA NADA -- 04/09/2026
# =====================================================================
#
# Medido no log: parado em (282,139), com o waypoint 21 exatamente em
# (282,139), o bot deu ~180 voltas em 4 min 10 s -- "Destravando pelo waypoint
# 21 (tolerância 2)", "alcançado em 0.0s", "a rota continua do 22", e de novo.
#
# O `follow_path` de um ponto que já foi alcançado devolve True SEMPRE, em zero
# segundo, com qualquer tolerância. A manobra declarava sucesso, quem chamou
# zerava o contador de travas, e a situação voltava idêntica.
#
# A memória de falhas (`_candidatos_que_falharam`) não pegava: ela guarda quem
# FALHOU, e este candidato tem sucesso -- um sucesso que não serve para nada.


def test_o_candidato_onde_o_personagem_JA_esta_NAO_e_tentado(monkeypatch):
    """Parado EM CIMA do waypoint 1: a manobra tem de oferecer outro ponto."""
    rota = _rota()
    servico, tentativas = _navegador(
        monkeypatch, rota, intransitaveis=set(), posicao=(200, 30))

    servico.destravar_pelos_vizinhos(rota)

    assert (200, 30) not in tentativas, (
        "tentou andar até onde o personagem já estava -- é o laço de 4 minutos")
    assert tentativas, "não ofereceu manobra nenhuma tendo vizinhos válidos"


def test_todos_os_vizinhos_no_MESMO_ponto_devolve_None(monkeypatch):
    """Sem manobra a oferecer, o certo é DIZER isso.

    Fingir sucesso é o que fazia `follow_path` zerar as travas e reinsistir para
    sempre. Devolvendo `None`, quem chamou devolve o controle para a rotina --
    que sabe matar, refazer o trecho ou falhar, e que passa pelo `_guard()`.
    """
    rota = RotaFalsa(Waypoint((200, 30)) for _ in range(3))
    servico, tentativas = _navegador(
        monkeypatch, rota, intransitaveis=set(), posicao=(200, 30))

    assert servico.destravar_pelos_vizinhos(rota) is None
    assert not tentativas, "não deveria ter tentado andar para lugar nenhum"


def test_a_regua_do_filtro_e_a_MESMA_da_tentativa(monkeypatch):
    """Duas cópias dessa conta divergiriam em silêncio.

    O sintoma seria um candidato descartado com uma régua e tentado com outra --
    ou o contrário, que traz o laço de volta.
    """
    # PELO AST: o comentário que explica o filtro cita a função pelo nome, e
    # `str.count` no texto contava a explicação junto com as chamadas.
    import ast
    import inspect
    import textwrap

    arvore = ast.parse(textwrap.dedent(
        inspect.getsource(nav.Navigator.destravar_pelos_vizinhos)))
    chamadas = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)
                and getattr(n.func, "attr", "") == "_tolerancia_do_candidato"]
    assert len(chamadas) == 2, (
        "o filtro e a tentativa têm que usar a mesma função de tolerância, e "
        f"cada um chamá-la uma vez -- achei {len(chamadas)} chamada(s)")


def test_a_manobra_respeita_o_TETO_DE_PRESO_no_mesmo_ponto(monkeypatch):
    """Até 9 candidatos x 2 passadas x 4 s, sem teto total: o teto do usuário
    ("30 segundos sem fazer nada já é bastante") só era conferido ENTRE uma
    manobra e outra, e uma só chegou a 91 s (26/09/2026). Achado A7 da
    auditoria de 27/09/2026: estourado o teto, a manobra devolve o controle."""
    rota = _rota(20)
    servico, tentativas = _navegador(
        monkeypatch, rota, intransitaveis={w.pos for w in rota}, posicao=(300, 30))
    relogio = [1_000.0]
    monkeypatch.setattr(nav.time, "time", lambda: relogio[0])
    chamar = servico.follow_path

    def cada_tentativa_custa_12s(alvos, **kw):
        relogio[0] += 12.0
        return chamar(alvos, **kw)

    monkeypatch.setattr(servico, "follow_path", cada_tentativa_custa_12s)
    assert servico.destravar_pelos_vizinhos(rota) is None
    assert len(tentativas) == 3, (
        f"{len(tentativas)} tentativas: o teto de "
        f"{nav.TETO_PRESO_NO_MESMO_PONTO:.0f} s não segurou a manobra")
