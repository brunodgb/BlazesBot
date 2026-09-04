"""O combate da HH no nível do BC — e nenhuma chamada em colaborador que não existe.

=========================================================================
OS DEFEITOS QUE ESTE ARQUIVO IMPEDE DE VOLTAR
=========================================================================

**1. O portão de nome zerava a luta.** A HH passava `alvo_esperado=rotulo` com os
rótulos de comentário do bot em Lua ("Fa-Yuan", "Dupla", "Green Robmaster",
"Purple") — nomes que nunca foram medidos no jogo. O portão devolve `acabaram`
para qualquer nome diferente do esperado, o que é o desfecho CERTO numa fase de
vários mobs (os guardas do BC) e errado num boss único. Resultado medido em
03/09/2026: a luta terminava na primeira leitura de nome, **sem um golpe**, e
reportava VITÓRIA. Os quatro bosses "morriam" em segundos.

**2. O desfecho era descartado.** `_do_boss` avançava o trecho sempre. Morrer no
boss 2 fazia o bot seguir para o boss 3 — morto, sem vida, sem pet.

**3. A luta era uma fração da do BC.** Sem desmontar, sem conferir morte, sem
TAB de aquisição quando o boss não vem, sem `exige_ter_entrado`, sem golpe
durante a confirmação de saída, sem gravar o placar.

**4. `curar_antes_do_boss` não existia no `self.combat` da HH.** Ela mora(va) em
`bc/combat.py`, e o `self.combat` da HH é a classe base — `AttributeError` no
primeiro boss. A suíte inteira passava, porque nenhum teste executa `_do_boss`.
É a quarta vez que um defeito desta família aparece nesta integração
(`Api.alternar_hh`, a Fada que não curava, o `_open_npc` órfão): **suíte verde
não prova que as peças estão ligadas.**
"""
from __future__ import annotations

import ast
import inspect
import itertools
import textwrap

import pytest

from blazesbot.bot import combate as motor
from blazesbot.bot.hh import mapa_hh
from blazesbot.bot.hh.routine import HHRoutine


def _fonte(alvo) -> str:
    return textwrap.dedent(inspect.getsource(alvo))


def _linha_de(metodo, nome: str) -> int:
    """A primeira linha de CÓDIGO que menciona `nome`, pelo AST.

    NÃO por `str.index`: a docstring destes métodos cita os nomes justamente
    para explicar a ordem, e comparar posições de texto encontrava a explicação
    antes do código. Errei isso quatro vezes escrevendo este arquivo -- o helper
    existe para não haver uma quinta.
    """
    arvore = ast.parse(_fonte(metodo))
    linhas = [
        no.lineno
        for no in ast.walk(arvore)
        if (isinstance(no, ast.Attribute) and no.attr == nome)
        or (isinstance(no, ast.Name) and no.id == nome)
        or (isinstance(no, ast.keyword) and no.arg == nome)
    ]
    assert linhas, f"`{nome}` não aparece no código de {metodo.__name__}"
    return min(linhas)


def _em_ordem(metodo, *nomes: str) -> None:
    """Cada nome aparece no código antes do seguinte."""
    posicoes = [(n, _linha_de(metodo, n)) for n in nomes]
    for (a, la), (b, lb) in itertools.pairwise(posicoes):
        assert la < lb, (
            f"em {metodo.__name__}: `{a}` (linha {la}) tem que vir antes de "
            f"`{b}` (linha {lb}) -- ordem atual: {posicoes}")


# ===========================================================================
# 1) NENHUMA CHAMADA EM COLABORADOR QUE NÃO EXISTE
# ===========================================================================

# (o atributo da rotina, a classe que ele guarda). É a lista dos colaboradores
# injetados -- `test_sem_chamada_orfa.py` cobre `self.<nome>`, e este cobre
# `self.<colaborador>.<nome>`, que é onde o defeito 4 se esconde.
COLABORADORES = {
    "combat": "blazesbot.bot.combate:CombatEngine",
    "nav": "blazesbot.bot.navegacao:Navigator",
    "ui": "blazesbot.bot.hh.entrada:EntradaDaHH",
    "vendedor": "blazesbot.bot.hh.vendedor:VendedorDaHH",
    "team": "blazesbot.bot.team:TeamService",
}


def _classe(caminho: str):
    import importlib

    modulo, nome = caminho.split(":")
    return getattr(importlib.import_module(modulo), nome)


def _chamadas_em(rotina, colaborador: str) -> set[str]:
    """Os nomes chamados como `self.<colaborador>.<nome>(...)`."""
    achados: set[str] = set()
    for metodo in vars(rotina).values():
        if not callable(metodo) or not hasattr(metodo, "__code__"):
            continue
        try:
            arvore = ast.parse(_fonte(metodo))
        except (OSError, SyntaxError):  # pragma: no cover
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Attribute):
                continue
            dono = no.value
            if (isinstance(dono, ast.Attribute) and dono.attr == colaborador
                    and isinstance(dono.value, ast.Name)
                    and dono.value.id == "self"):
                achados.add(no.attr)
    return achados


@pytest.mark.parametrize("atributo,caminho", sorted(COLABORADORES.items()))
def test_toda_chamada_em_colaborador_da_HH_existe(atributo: str, caminho: str):
    """`self.combat.curar_antes_do_boss()` era `AttributeError` no primeiro boss.

    Nenhum teste executa `_do_boss`, então a chamada errada passava por toda a
    suíte. Este teste lê o AST da rotina e confere cada nome contra a classe
    real do colaborador.
    """
    classe = _classe(caminho)
    faltando = sorted(n for n in _chamadas_em(HHRoutine, atributo)
                      if not hasattr(classe, n))
    assert not faltando, (
        f"a rotina da HH chama `self.{atributo}.{{{', '.join(faltando)}}}` e "
        f"{classe.__name__} não tem. Isso é AttributeError com o jogo aberto.")


def test_a_mesma_conferencia_vale_para_a_Fada_da_HH():
    from blazesbot.bot.hh.fada import FadaDaHH

    for atributo, caminho in (("nav", COLABORADORES["nav"]),
                              ("ui", COLABORADORES["ui"])):
        classe = _classe(caminho)
        faltando = sorted(n for n in _chamadas_em(FadaDaHH, atributo)
                          if not hasattr(classe, n))
        assert not faltando, f"FadaDaHH.{atributo}: {faltando}"


# ===========================================================================
# 2) O PORTÃO DE NOME NÃO ENTRA NUMA LUTA DE BOSS
# ===========================================================================


def test_a_HH_NAO_passa_alvo_esperado():
    """Nome nunca medido + semântica de fase multi-mob = luta encerrada sem um
    golpe, reportando vitória."""
    from blazesbot.bot.hh import routine as mod

    arvore = ast.parse(inspect.getsource(mod))
    usos = [no.lineno for no in ast.walk(arvore)
            if isinstance(no, ast.Call)
            and any(kw.arg == "alvo_esperado" for kw in no.keywords)]
    assert not usos, (
        f"a HH voltou a passar `alvo_esperado` (linhas {usos}). Os rótulos dela "
        f"são comentário do bot em Lua, não nome medido -- e portão de nome é "
        f"para fase de VÁRIOS mobs, não para boss único.")


def test_o_ritual_do_boss_NAO_aceita_alvo_esperado():
    """A ausência do parâmetro é a decisão, e ela fica no motor.

    Se `lutar_contra_um_boss` aceitasse o portão, a próxima cave repetiria o
    erro -- o parâmetro existir é um convite a usá-lo.
    """
    params = inspect.signature(motor.CombatEngine.lutar_contra_um_boss).parameters
    assert "alvo_esperado" not in params


def test_o_BC_continua_usando_o_portao_ONDE_ele_esta_certo():
    """Na fase dos guardas: quatro Gun Witch, e "o nome mudou" É o sinal de que
    acabaram. Tirar de lá seria consertar o que não está quebrado."""
    from blazesbot.bot.bc import combat

    arvore = ast.parse(inspect.getsource(combat))
    com_portao = [no for no in ast.walk(arvore)
                  if isinstance(no, ast.Call)
                  and any(kw.arg == "alvo_esperado" for kw in no.keywords)]
    assert com_portao, "o BC parou de usar o portão de nome nos guardas"


# ===========================================================================
# 3) O RITUAL DA LUTA É O DO BC
# ===========================================================================

# O que a luta de boss tem que fazer, e o que cada item evita. Absorvido de
# `bc/combat.fase_do_boss_por_combate`.
O_RITUAL = [
    ("_descer_para_lutar", "montado o jogo recusa as skills"),
    ("esperar_entrar_em_combate", "a flag de combate é quem diz que a luta começou"),
    ("snapshot", "conferir MORTE antes de bater no vazio"),
    ("press", "TAB de aquisição quando o boss não vem sozinho"),
    ("atacar_ate_sair_de_combate", "a rotação em si"),
    ("salvar", "o placar vai para o disco no fim da luta"),
]


@pytest.mark.parametrize("chamada,por_que", O_RITUAL,
                         ids=lambda v: v if " " not in str(v) else "")
def test_o_ritual_do_boss_faz_cada_passo(chamada: str, por_que: str):
    fonte = _fonte(motor.CombatEngine.lutar_contra_um_boss)
    assert chamada in fonte, f"falta `{chamada}` -- {por_que}"


def test_o_ritual_espera_com_prazo_CURTO_e_sem_pocao():
    """Na frente do boss não se bebe poção: ele encosta e o efeito para na hora.

    E o prazo curto não é desistência -- estourá-lo dispara o TAB de aquisição.
    """
    fonte = _fonte(motor.CombatEngine.lutar_contra_um_boss)
    assert "pocao_na_espera=False" in fonte
    assert "SEGUNDOS_ANTES_DO_TAB_NO_BOSS" in fonte


def test_o_ritual_protege_a_luta_forcada():
    """`exige_ter_entrado`: com a luta forçada a flag ainda está baixa quando a
    rotação começa, e sem o portão a confirmação declararia vitória em 1,5 s."""
    fonte = _fonte(motor.CombatEngine.lutar_contra_um_boss)
    assert "exige_ter_entrado=forcado" in fonte


def test_o_ritual_insiste_no_golpe_durante_a_confirmacao():
    """A virada de fase derruba a flag por um instante, e quem reengaja é o
    golpe -- parado, o bot confirmava vitória com o boss de pé."""
    fonte = _fonte(motor.CombatEngine.lutar_contra_um_boss)
    assert "atacar_na_confirmacao=True" in fonte


def test_a_HH_usa_o_ritual_e_nao_uma_versao_propria():
    fonte = _fonte(HHRoutine._do_boss)
    assert "lutar_contra_um_boss" in fonte
    assert "atacar_ate_sair_de_combate" not in fonte, (
        "a HH voltou a chamar a rotação direto, pulando o ritual")


def test_o_BC_tambem_delega_o_ritual():
    """Uma implementação só. Duas divergem na primeira manutenção, e a que fica
    para trás é a que ninguém está olhando."""
    from blazesbot.bot.bc.combat import CombateBC

    fonte = _fonte(CombateBC.fase_do_boss_por_combate)
    assert "lutar_contra_um_boss" in fonte


# ===========================================================================
# 4) O DESFECHO É HONRADO
# ===========================================================================


def test_derrota_no_boss_manda_RECUPERAR_e_NAO_avanca_o_trecho():
    """Morrer no boss 2 fazia o bot seguir para o boss 3 -- morto."""
    # A LUTA E O AVANÇO SÃO FUNÇÕES SEPARADAS desde 03/09/2026, e o portão
    # entre elas é o `if not self._lutar_no_ponto(...)`: derrota devolve False
    # e a função sai ANTES de qualquer avanço.
    # HÁ DOIS AVANÇOS na função, e é de propósito: um quando o ponto não
    # engaja em 5 s (nada a lutar) e outro depois da luta vencida. O que não
    # pode existir é um avanço que ignore uma DERROTA -- por isso a comparação
    # é com o ÚLTIMO, o que fecha o caminho da luta.
    import ast as _ast
    arvore = _ast.parse(_fonte(HHRoutine._do_boss))
    avancos = [n.lineno for n in _ast.walk(arvore)
               if isinstance(n, _ast.Call)
               and getattr(n.func, "attr", "") == "_avancar_o_trecho"]
    assert avancos, "a função deixou de avançar o trecho"
    assert max(avancos) > _linha_de(HHRoutine._do_boss, "_lutar_no_ponto")

    fonte = _fonte(HHRoutine._do_boss)
    assert "if not self._lutar_no_ponto" in fonte, (
        "o avanço deixou de depender do desfecho da luta")
    assert "_falhar" in _fonte(HHRoutine._lutar_no_ponto)


def test_a_vitoria_e_lida_do_MESMO_campo_que_o_BC_le():
    """`venceu = fim.saiu_de_combate`. Um segundo critério de vitória seria uma
    segunda definição de "o boss morreu"."""
    from blazesbot.bot.bc.routine import BossRushRoutine

    assert "fim.saiu_de_combate" in _fonte(BossRushRoutine._do_boss)
    assert "fim.saiu_de_combate" in _fonte(HHRoutine._lutar_no_ponto)


def test_morrer_ANTES_de_encostar_tambem_para():
    """`curar_antes_do_boss` fica 15 s parado; um mob do trajeto pode matar
    ali."""
    _em_ordem(HHRoutine._do_boss,
              "curar_antes_do_boss", "dead", "_lutar_no_ponto")


def test_a_morte_conta_UMA_run_perdida():
    """`_do_recuperar` volta a cada 2 s enquanto morto; chamar `end_run` em
    todas fazia uma morte aparecer como dezenas de runs perdidas."""
    _em_ordem(HHRoutine._do_recuperar, "_contou_a_morte", "end_run")


# ===========================================================================
# 5) CURA E RECUPERAÇÃO — "quando e como se curar", absorvido
# ===========================================================================


def test_curar_antes_do_boss_mora_no_MOTOR():
    """É conhecimento do jogo, e as duas caves precisam do mesmo."""
    assert hasattr(motor.CombatEngine, "curar_antes_do_boss")


def test_a_cura_vem_ANTES_de_encostar_e_nao_depois_da_luta():
    """Na frente do boss a poção não vale: ele encosta e o efeito para."""
    _em_ordem(HHRoutine._do_boss, "curar_antes_do_boss", "_lutar_no_ponto")


def test_a_HH_senta_entre_os_bosses_SE_precisar():
    """O BC senta depois dos guardas; na HH o equivalente é o intervalo entre
    os quatro bosses. `precisa_curar` é o portão -- sentar com a vida cheia
    seria pagar segundos por nada em toda run saudável."""
    _em_ordem(HHRoutine._recuperar_entre_os_bosses,
              "precisa_curar", "sentar_para_recuperar")


# ===========================================================================
# 6) DOIS BOSSES NO MESMO PONTO — a "Dupla"
# ===========================================================================


def test_o_mapa_diz_quantos_alvos_tem_cada_ponto():
    """Três naturezas, e o mapa é quem declara qual é qual.

    Medido pelo usuário no jogo em 03/09/2026: os pontos 1 e 3 são PACOTES de
    mobs ranged (número indeterminado), o 2 é a dupla de bosses, e o 4 é um
    boss só.
    """
    assert mapa_hh.ALVOS_POR_PONTO[mapa_hh.BOSS_2] == 2
    assert mapa_hh.ALVOS_POR_PONTO[mapa_hh.BOSS_4] == 1
    for rotulo in (mapa_hh.BOSS_1, mapa_hh.BOSS_3):
        assert mapa_hh.ALVOS_POR_PONTO[rotulo] == mapa_hh.VARIOS
        assert mapa_hh.e_pacote_de_mobs(rotulo)
    for rotulo in (mapa_hh.BOSS_2, mapa_hh.BOSS_4):
        assert not mapa_hh.e_pacote_de_mobs(rotulo)


def test_a_AoE_e_desligada_onde_os_mobs_sao_RANGED():
    """A skill de área é de curta distância.

    Mob ranged fica parado longe atirando, e a área passa embaixo dele sem
    tocar em nada -- girar AoE ali é gastar o tempo da rotação sem dano, e a
    luta se arrasta até o teto. Regra do usuário, 03/09/2026.
    """
    assert not mapa_hh.usa_aoe(mapa_hh.BOSS_1)
    assert not mapa_hh.usa_aoe(mapa_hh.BOSS_3)
    assert mapa_hh.usa_aoe(mapa_hh.BOSS_2)
    assert mapa_hh.usa_aoe(mapa_hh.BOSS_4)


def test_a_luta_pergunta_ao_MAPA_se_usa_AoE():
    """O dado mora no mapa, e a rotina obedece -- não há `if rotulo ==` solto."""
    fonte = _fonte(HHRoutine._lutar_no_ponto)
    assert "mapa_hh.usa_aoe(rotulo)" in fonte
    assert "mapa_hh.e_pacote_de_mobs(rotulo)" in fonte


def test_o_PACOTE_usa_o_ritual_de_matar_ate_sair_de_batalha():
    """Mata um, PARA e olha a flag, e só então TAB para o próximo.

    É a coreografia de `limpar_o_combate`, que é a mesma do bot em Lua neste
    ponto (`hh.killAtPosition`). Existe porque o que encerra a luta é a lista
    acabar: cada morte pode ou não ser a última, e a pausa é como se descobre
    sem puxar mob novo.
    """
    fonte = _fonte(HHRoutine._lutar_no_ponto)
    assert "limpar_o_combate" in fonte
    assert hasattr(motor.CombatEngine, "limpar_o_combate")


def test_o_ponto_de_DOIS_alvos_pede_TAB_e_o_de_um_nao():
    """Sem TAB depois da morte, o segundo boss da Dupla nunca é adquirido.

    E com TAB num ponto de alvo único, o bot trocaria de alvo no meio da luta
    do boss -- perdendo dano.
    """
    assert mapa_hh.tabs_ao_morrer(mapa_hh.BOSS_2) > 0
    # E ZERO NOS PACOTES por motivo OPOSTO: lá quem dá o TAB é
    # `limpar_o_combate`, depois de parar e conferir a flag. Dois donos do mesmo
    # TAB gastariam dois por morte, e o segundo miraria quem está FORA do
    # combate -- que é como se puxa mob novo.
    for rotulo in (mapa_hh.BOSS_1, mapa_hh.BOSS_3, mapa_hh.BOSS_4):
        assert mapa_hh.tabs_ao_morrer(rotulo) == 0


def test_rotulo_desconhecido_NAO_gasta_TAB():
    """Um boss novo entra com um alvo até alguém medir o contrário."""
    assert mapa_hh.tabs_ao_morrer("BossQueNinguemMediu") == 0


def test_a_luta_recebe_o_numero_de_TABS_do_mapa():
    assert "tabs_ao_morrer" in _fonte(HHRoutine._lutar_no_ponto)


def test_todo_ponto_de_boss_esta_declarado():
    """Um boss fora da tabela cai no padrão sem ninguém decidir."""
    for rotulo, _caminho, _ponto in mapa_hh.TRECHOS_DOS_BOSSES:
        assert rotulo in mapa_hh.ALVOS_POR_PONTO, rotulo


# ===========================================================================
# 7) NÃO SE ESPERA COMBATE DE LONGE
# ===========================================================================


def test_a_HH_confere_a_POSICAO_antes_de_esperar_o_combate():
    """Absorvido do `BossRushRoutine._do_boss`: fora do ponto, o bot volta a
    andar em vez de ficar parado esperando uma flag que não vai ligar."""
    _em_ordem(HHRoutine._do_boss, "position", "_lutar_no_ponto")
    assert "State.ATE_O_BOSS" in _fonte(HHRoutine._do_boss)


def test_sem_leitura_de_posicao_a_luta_SEGUE():
    """Recusar aqui travaria a run; quem decide então é a flag ligar ou não."""
    fonte = _fonte(HHRoutine._do_boss)
    assert "pos is not None" in fonte


# ===========================================================================
# Chamar uma PROPRIEDADE é TypeError, e o nome existe
# ===========================================================================


def _chamadas_de_verdade_em(rotina, colaborador: str) -> set[str]:
    """Os nomes usados como `self.<colaborador>.<nome>(...)` -- COM parênteses.

    Diferente de `_chamadas_em`, que pega qualquer acesso: aqui só entra o que
    o código de fato CHAMA, porque é só isso que quebra quando o nome é uma
    propriedade.
    """
    achados: set[str] = set()
    for metodo in vars(rotina).values():
        if not callable(metodo) or not hasattr(metodo, "__code__"):
            continue
        try:
            arvore = ast.parse(_fonte(metodo))
        except (OSError, SyntaxError):  # pragma: no cover
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            alvo = no.func
            if not isinstance(alvo, ast.Attribute):
                continue
            dono = alvo.value
            if (isinstance(dono, ast.Attribute) and dono.attr == colaborador
                    and isinstance(dono.value, ast.Name)
                    and dono.value.id == "self"):
                achados.add(alvo.attr)
    return achados


@pytest.mark.parametrize("atributo,caminho", sorted(COLABORADORES.items()))
def test_a_HH_nao_CHAMA_propriedade_de_colaborador(atributo: str, caminho: str):
    """`self.team.in_team()` derrubou o bot inteiro, e a suíte não viu.

    `in_team` é `@property` em `bot/team.py`. Com parênteses vira
    `TypeError: 'bool' object is not callable`, que estoura a sessão -- o
    supervisor solta o controle e recomeça, e o bot fica reiniciando na porta da
    cave a cada 5 s. Medido no log de 03/09/2026, 19:02.

    O teste irmão (`test_toda_chamada_em_colaborador_da_HH_existe`) não pegava:
    o nome EXISTE na classe. O que não existe é o direito de chamá-lo.
    """
    classe = _classe(caminho)
    propriedades = sorted(
        n for n in _chamadas_de_verdade_em(HHRoutine, atributo)
        if isinstance(getattr(classe, n, None), property))
    assert not propriedades, (
        f"a rotina da HH chama `self.{atributo}.{{{', '.join(propriedades)}}}()` "
        f"com parênteses, e em {classe.__name__} isso é `@property`. "
        f"Com o jogo aberto vira TypeError e a sessão inteira cai.")
