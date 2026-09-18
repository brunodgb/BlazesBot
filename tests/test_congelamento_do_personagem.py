"""O personagem congelado, e a montaria como remédio.

=========================================================================
O RELATO
=========================================================================

08/09/2026: *"dentro de HH tem lag e rollback muito forte, mas no caso de HH eu
percebi algumas vezes que o lag é tanto que chega a travar o personagem, e só
destrava se ele faz alguma ação e como está na montaria, a única ação possível é
sair da montaria... caso perceba que está mais de 20 segundos parado, sem mudar
as coordenadas e sem estar fazendo nada, o ideal é sair da montaria"*.

O número virou **15 s** na conversa de desenho, para caber dentro do teto de
30 s que já existia — sobram 15 s para a manobra provar efeito antes de o
trajeto ser abortado.

=========================================================================
O QUE ESTE ARQUIVO PROTEGE
=========================================================================

1. **O BC não muda.** O vigia nasce desligado, como os dois ganchos de
   destravamento — em 04/09/2026 o BC herdou um desmonte da HH e passou a lutar
   antes do Altar Stone.
2. **Rollback não dispara a montaria.** São fenômenos diferentes com remédios
   opostos, e a coordenada é o que os separa.
3. **O relógio atravessa os trajetos.** O congelamento medido acontece nos
   trajetos curtos de 5 s; um relógio por chamada nunca chegaria aos 15.
4. **"Não sei" não autoriza gesto.**
5. **Duas cutucadas, e não um laço.** Repetir remédio que não funciona é como o
   bot fica horas sem farmar.

Ver `docs/decisoes/hh.md` §23.
"""
from __future__ import annotations

import inspect

from blazesbot.bot import congelamento as mod
from blazesbot.bot.congelamento import VigiaDoCongelamento


class _Log:
    def __init__(self): self.linhas: list[str] = []
    def warning(self, m, *a): self.linhas.append(m % a if a else m)
    def info(self, m, *a): self.linhas.append(m % a if a else m)
    def debug(self, *a, **k): pass


class _Mem:
    def __init__(self, montado: bool | None = True):
        self.montado = montado

    def is_mounted(self): return self.montado
    def location(self): return "Black Wind Camp Dungeon"


class _Ctx:
    def __init__(self, montado: bool | None = True):
        self.log = _Log()
        self.memory = _Mem(montado)
        self.account_login = "conta"


# O maior intervalo legítimo entre duas leituras. Em produção quem passa é o
# `Navigator`, com o teto do portão da montaria.
MAXIMO_SEM_LEITURA = 6.0


def _vigia(montado: bool | None = True, ligado: bool = True):
    """Um vigia com o relógio sob controle do teste, sem esperar de verdade."""
    desmontes = []
    v = VigiaDoCongelamento(_Ctx(montado), lambda: desmontes.append(1) or True,
                            MAXIMO_SEM_LEITURA)
    v.ligado = ligado
    v.desmontes = desmontes
    return v


def _envelhecer(v: VigiaDoCongelamento, segundos: float) -> None:
    """Faz o relógio do vigia parecer mais velho, sem dormir."""
    v._desde -= segundos


# ===========================================================================
# 1. O BC não muda
# ===========================================================================


def test_DESLIGADO_nao_faz_absolutamente_nada():
    v = _vigia(ligado=False)
    for _ in range(3):
        assert v.olhar((100, 100), "andar") is False
    _envelhecer_seguro = getattr(v, "_desde", 0.0)

    assert _envelhecer_seguro == 0.0, "o relógio nem começou, e é isso mesmo"
    assert v.desmontes == []
    assert v.ctx.log.linhas == []


def test_o_vigia_do_Navigator_NASCE_desligado():
    from blazesbot.bot.navegacao import Navigator

    fonte = inspect.getsource(Navigator.__init__)
    assert "VigiaDoCongelamento(" in fonte, (
        "o Navigator deixou de ter o vigia")
    assert "ligado = True" not in fonte, (
        "o vigia passou a nascer LIGADO, e com isso o BC herdaria o desmonte")


def test_so_a_HH_liga():
    from blazesbot.bot.bc.routine import BossRushRoutine
    from blazesbot.bot.hh.routine import HHRoutine

    assert "congelamento.ligado = True" in inspect.getsource(
        HHRoutine.__init__), "a HH deixou de ligar o vigia"
    assert "congelamento" not in inspect.getsource(BossRushRoutine), (
        "o BC passou a mexer no vigia do congelamento")


# ===========================================================================
# 2. Rollback não é congelamento
# ===========================================================================


def test_coordenada_que_MUDA_zera_o_relogio():
    v = _vigia()
    v.olhar((100, 100), "andar")
    _envelhecer(v, 14.0)

    v.olhar((100, 107), "andar")            # rollback: mudou de lugar

    assert v.segundos_congelado < 1.0, "o relógio não zerou na mudança"
    assert v.desmontes == []


def test_rollback_NAO_desmonta_nem_depois_do_limite():
    """Rollback se conserta reancorando a rota, não mexendo na montaria."""
    v = _vigia()
    for passo in range(6):
        v.olhar((100, 100 + passo * 7), "andar")
        _envelhecer(v, 20.0)                # cada leitura "envelhece" muito

    assert v.desmontes == [], (
        "a montaria foi cutucada num personagem que estava se movendo")


def test_UM_pixel_de_diferenca_ja_zera():
    v = _vigia()
    v.olhar((100, 100), "andar")
    _envelhecer(v, 14.9)
    v.olhar((101, 100), "andar")
    _envelhecer(v, 14.9)

    assert v.olhar((101, 100), "andar") is False, (
        "somou dois intervalos de coordenadas diferentes")


# ===========================================================================
# 3. O relógio e o limite
# ===========================================================================


def test_ANTES_dos_15s_nao_cutuca():
    v = _vigia()
    v.olhar((100, 100), "andar")
    _envelhecer(v, mod.SEGUNDOS_PARA_CUTUCAR - 0.1)

    assert v.olhar((100, 100), "andar") is False
    assert v.desmontes == []


def test_NOS_15s_desmonta():
    v = _vigia(montado=True)
    v.olhar((100, 100), "andar")
    _envelhecer(v, mod.SEGUNDOS_PARA_CUTUCAR)

    assert v.olhar((100, 100), "andar") is True
    assert v.desmontes == [1], "não desmontou no limite"
    assert any("CONGELADO" in linha for linha in v.ctx.log.linhas)


def test_o_relogio_ATRAVESSA_as_leituras_de_trajetos_diferentes():
    """O congelamento medido acontece nos trajetos de 5 s.

    Cada `follow_path` daqueles dura 5 s; um relógio por chamada nunca somaria
    15. Aqui se prova que três janelas de 5 s na MESMA coordenada cutucam.
    """
    v = _vigia()
    v.olhar((272, 136), "andar até (272, 136)")
    for _ in range(3):                      # três "trajetos" de 5 s
        _envelhecer(v, 5.0)
        cutucou = v.olhar((272, 136), "andar até (272, 136)")

    assert cutucou is True, "somou 15s em três trajetos e não cutucou"


def test_esquecer_zera_para_quem_moveu_o_personagem_de_proposito():
    v = _vigia()
    v.olhar((100, 100), "andar")
    _envelhecer(v, 14.0)

    v.esquecer()

    assert v.segundos_congelado == 0.0
    assert v.olhar((100, 100), "andar") is False


# ===========================================================================
# 4. "Não sei" não autoriza
# ===========================================================================


def test_montaria_ILEGIVEL_nao_desmonta():
    v = _vigia(montado=None)
    v.olhar((100, 100), "andar")
    _envelhecer(v, 30.0)

    assert v.olhar((100, 100), "andar") is False
    assert v.desmontes == []


def test_A_PE_registra_mas_nao_tem_gesto_novo():
    """A tecla de montar já sai a cada volta do laço (`_manter_montaria`)."""
    v = _vigia(montado=False)
    v.olhar((100, 100), "andar")
    _envelhecer(v, mod.SEGUNDOS_PARA_CUTUCAR)

    assert v.olhar((100, 100), "andar") is True
    assert v.desmontes == [], "desmontou um personagem que já estava a pé"
    assert any("A PÉ" in linha for linha in v.ctx.log.linhas)


# ===========================================================================
# 5. Duas cutucadas, e não um laço
# ===========================================================================


def test_a_segunda_cutucada_vem_no_MEIO_do_que_resta():
    from blazesbot.bot.navegacao import TETO_PRESO_NO_MESMO_PONTO

    esperado = (mod.SEGUNDOS_PARA_CUTUCAR + TETO_PRESO_NO_MESMO_PONTO) / 2
    assert mod.SEGUNDOS_PARA_A_SEGUNDA == esperado, (
        f"a segunda cutucada ({mod.SEGUNDOS_PARA_A_SEGUNDA}s) deixou de ser "
        f"derivada dos dois números do usuário ({esperado}s)")
    assert mod.SEGUNDOS_PARA_A_SEGUNDA < TETO_PRESO_NO_MESMO_PONTO, (
        "a segunda cutucada cairia depois de o trajeto já ter sido abortado")


def test_duas_cutucadas_e_para():
    v = _vigia()
    v.olhar((100, 100), "andar")

    dadas = 0
    for _ in range(40):                     # muito tempo congelado
        _envelhecer(v, 5.0)
        if v.olhar((100, 100), "andar"):
            dadas += 1

    assert dadas == mod.CUTUCADAS, (
        f"deu {dadas} cutucadas; o remédio que não funcionou foi repetido em "
        f"laço, que é como o bot fica horas sem farmar")


def test_destravar_devolve_o_direito_a_duas():
    """Congelou, destravou, congelou de novo: é outro episódio."""
    v = _vigia()
    v.olhar((100, 100), "andar")
    _envelhecer(v, 30.0)
    v.olhar((100, 100), "andar")
    _envelhecer(v, 30.0)
    v.olhar((100, 100), "andar")
    assert len(v.desmontes) == mod.CUTUCADAS

    v.olhar((140, 160), "andar")            # destravou (com rollback)
    _envelhecer(v, mod.SEGUNDOS_PARA_CUTUCAR)

    assert v.olhar((140, 160), "andar") is True
    assert len(v.desmontes) == mod.CUTUCADAS + 1


# ===========================================================================
# A ligação com o laço de deslocamento
# ===========================================================================


def test_o_laco_de_deslocamento_CHAMA_o_vigia():
    from blazesbot.bot.navegacao import Navigator

    fonte = inspect.getsource(Navigator.follow_path)
    assert "self.congelamento.olhar(" in fonte, (
        "o laço deixou de olhar o congelamento -- o vigia existe e não roda")


def test_o_vigia_olha_ANTES_do_rollback():
    """Rollback mexe no índice; o vigia precisa da coordenada de hoje."""
    from blazesbot.bot.navegacao import Navigator

    fonte = inspect.getsource(Navigator.follow_path)
    assert fonte.index("congelamento.olhar(") < fonte.index("houve_rollback(")


def test_o_desmonte_injetado_PERMITE_batalha():
    """Congelado em batalha é o caso que o escudo da montaria protegia sem
    querer: ele existe para o personagem não PARAR de andar."""
    from blazesbot.bot.navegacao import Navigator

    fonte = inspect.getsource(Navigator.__init__)
    inicio = fonte.index("VigiaDoCongelamento(")
    trecho = fonte[inicio:inicio + 220]
    assert "permitir_em_batalha=True" in trecho, (
        "o desmonte do congelamento voltou a respeitar o escudo, e com isso "
        "não acontece justamente quando o personagem está preso em combate")


def test_o_evento_do_diario_e_PROPRIO():
    """`"travado"` já existe e é do teto de insistência. Confundir os dois
    apagaria a medida que diz se 15 s é o número certo.

    PELO AST, e pelos ARGUMENTOS da chamada: o comentário do código cita
    `"travado"` justamente para dizer que não é ele, e uma busca no texto
    acharia a explicação e reprovaria o código certo.
    """
    import ast
    import textwrap

    arvore = ast.parse(textwrap.dedent(
        inspect.getsource(mod.VigiaDoCongelamento.olhar)))
    eventos = [
        arg.value
        for n in ast.walk(arvore)
        if isinstance(n, ast.Call)
        and getattr(n.func, "attr", "") == "registrar_evento"
        for arg in n.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    ]
    assert "congelado" in eventos, f"eventos gravados: {eventos}"
    assert "travado" not in eventos, (
        "o congelamento passou a gravar no mesmo evento do teto de "
        "insistência, e as duas medidas viraram uma")


# ===========================================================================
# PARADO DE PROPÓSITO NÃO É CONGELADO -- 18/09/2026
# ===========================================================================
#
# Relato do usuário: *"fora de HH ainda tem acontecido de sair da montaria...
# as coisas que precisam desmontar são feitos dentro da cave e não fora, então
# não faz sentido acontecer casos do personagem desmontar estando fora da
# cave"*.
#
# ERAM TODAS FALSAS. As 51 cutucadas fora da cave medidas em 17-18/09 são o
# MESMO caso: o personagem parado no ponto de venda (-343,-294) enquanto vende e
# apaga lixo, mandado depois a andar 6 unidades até a porta (-342,-288). O
# relógio do vigia nunca tinha sido zerado, então a PRIMEIRA leitura do trajeto
# novo já trazia "congelado há 15-23 s" -- uma delas marcou 2034 s, o ciclo
# inteiro de uma run.


def test_a_pausa_para_VENDER_nao_conta_como_congelamento():
    """O caso medido, ponto por ponto: mesma coordenada, mas o bot passou o
    intervalo inteiro fora do laço de andar."""
    v = _vigia()
    v.olhar((-343, -294), "andar até (-343, -294)")

    # a venda: nenhuma leitura por 19 s
    v._visto_em -= 19.0
    v._desde -= 19.0

    assert v.olhar((-343, -294), "andar até (-342, -288)") is False
    assert v.desmontes == [], "cutucou por causa de uma pausa de propósito"
    assert v.segundos_congelado < 1.0, (
        "o relógio manteve o tempo da venda em vez de recomeçar")


def test_o_congelamento_de_VERDADE_continua_pego():
    """O conserto não pode ter desligado a detecção.

    Aqui as leituras chegam sem parar -- é o laço de andar rodando contra um
    personagem que não sai do lugar.
    """
    v = _vigia()
    v.olhar((300, 140), "andar até (318, 140)")
    _envelhecer(v, 16.0)

    assert v.olhar((300, 140), "andar até (318, 140)") is True
    assert v.desmontes == [1]


def test_o_destravamento_troca_o_ALVO_e_isso_NAO_zera():
    """A manobra de destravar chama o trajeto de novo com OUTRO waypoint
    enquanto o personagem segue congelado no mesmo lugar.

    Zerar por troca de alvo apagaria justamente os congelamentos verdadeiros de
    dentro da cave -- foi por isso que o discriminador é o INTERVALO ENTRE
    LEITURAS, e não o destino.
    """
    v = _vigia()
    v.olhar((449, 206), "andar até (516, 212)")
    _envelhecer(v, 16.0)

    assert v.olhar((449, 206), "andar até (462, 170)") is True, (
        "trocar o waypoint durante o destravamento apagou o congelamento")


def test_o_intervalo_maximo_vem_de_QUEM_ANDA():
    """`congelamento.py` não pode importar de `navegacao.py` (a navegação é que
    importa dele), então o número é injetado -- e é o teto do portão da
    montaria, o maior intervalo legítimo entre duas leituras do trajeto."""
    import inspect

    from blazesbot.bot import navegacao

    fonte = inspect.getsource(navegacao.Navigator.__init__)
    assert "TETO_DO_PORTAO)" in fonte, (
        "o vigia deixou de receber o intervalo máximo do portão da montaria")
    assert navegacao.TETO_DO_PORTAO == MAXIMO_SEM_LEITURA
