"""F1 + TAB para abrir a luta, e F1 + TAB de novo quando o alvo não apanha.

=========================================================================
A REGRA
=========================================================================

Usuário, 08/09/2026: *"dentro de HH tem vezes que o personagem acaba se auto
selecionando ou seleciona o pet e quando isso acontece, ele nao seleciona
automaticamente outro mob automaticamente"*, e a solução que ele mesmo indicou:
*"pressionar F1 que é a tecla de auto seleçao e depois dar TAB, assim garante
que vai selecionar o mob mais perto"*. Depois, sobre o começo da luta:
*"apertar F1 e depois dar o primeiro TAB vai ser o mais eficiente para atacar
os mobs corretos"*.

=========================================================================
O QUE ESTE ARQUIVO PROTEGE
=========================================================================

1. O gesto é DOIS toques na ordem certa -- só o TAB é cíclico e pode voltar
   para o pet.
2. Conta sem a tecla de auto-seleção continua funcionando (TAB sozinho).
3. A ABERTURA de toda luta da HH é esse gesto, sem condição.
4. O detector de meio de luta é OPT-IN -- é assim que a BC não muda.

Ver `docs/decisoes/hh.md` §14.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from blazesbot.bot import combate as motor
from blazesbot.bot.hh.routine import HHRoutine


def _chamadas(metodo) -> list[str]:
    """Os nomes CHAMADOS no corpo, na ORDEM das linhas -- pelo AST.

    `ast.walk` é em LARGURA, então a ordem de visita não é a ordem do arquivo:
    o `sorted` por `lineno` é o que faz este teste falar sobre ordem.
    """
    arvore = ast.parse(textwrap.dedent(inspect.getsource(metodo)))
    nos = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)]
    return [getattr(n.func, "attr", getattr(n.func, "id", ""))
            for n in sorted(nos, key=lambda n: (n.lineno, n.col_offset))]


# ===========================================================================
# O gesto
# ===========================================================================


class _Teclas:
    def __init__(self, self_target: str = "f1"):
        self.self_target = self_target
        self.tab = "tab"


class _Log:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def debug(self, *a, **k): pass


class _Memoria:
    """Responde o que a confirmação do F1 pergunta.

    `virar_para_mim` é o que o F1 de mentira faz: a partir dali o alvo passa a
    ser o próprio personagem, que é como o gesto se confirma no jogo.
    """

    def __init__(self, meu: str = "Eu", alvo: str | None = "MobQualquer"):
        self.meu = meu
        self.alvo = alvo
        self.leituras = 0

    def char_name(self):
        return self.meu

    def alvo_atual(self):
        self.leituras += 1
        return None if self.alvo is None else {"nome": self.alvo}

    def virar_para_mim(self):
        self.alvo = self.meu


class _Ctx:
    """O mínimo que `reancorar_o_alvo` toca. Registra o que foi apertado."""

    def __init__(self, self_target: str = "f1", memoria=None):
        self.apertadas: list[str] = []
        self.log = _Log()
        self.memory = memoria if memoria is not None else _Memoria()

        class _S:
            keys = _Teclas(self_target)
        self.settings = _S()

    def press(self, tecla, *a, **k):
        self.apertadas.append(tecla)
        # O F1 do jogo seleciona o próprio personagem.
        if tecla == self.settings.keys.self_target:
            self.memory.virar_para_mim()

    def tick(self, *a, **k): pass


def _motor_de_mentira(self_target: str = "f1", memoria=None):
    """Um `CombatEngine` com o `ctx` de mentira, sem passar pelo `__init__`."""
    combate = object.__new__(motor.CombatEngine)
    combate.ctx = _Ctx(self_target, memoria)
    return combate


def test_o_gesto_e_a_tecla_de_auto_selecao_e_DEPOIS_o_TAB():
    combate = _motor_de_mentira("f1")
    combate._trocar_de_alvo = lambda *a, **k: combate.ctx.press("tab")

    combate.reancorar_o_alvo("teste")

    assert combate.ctx.apertadas == ["f1", "tab"], (
        "A ordem é F1 e depois TAB. Só o TAB é cíclico: da mira presa no pet "
        "ele avança para 'o seguinte naquele ciclo', que pode ser o pet de "
        "novo -- que é exatamente o sintoma relatado.")


def test_sem_a_tecla_de_auto_selecao_o_TAB_sai_sozinho():
    for vazia in ("", "   ", None):
        combate = _motor_de_mentira(vazia)
        combate._trocar_de_alvo = lambda *a, **k: combate.ctx.press("tab")

        combate.reancorar_o_alvo("teste")

        assert combate.ctx.apertadas == ["tab"], (
            f"Com `self_target`={vazia!r} o bot tem que continuar tentando: um "
            f"TAB ainda pode acertar o mob. Pior, mas funcionando.")


def test_a_auto_selecao_e_CONFERIDA_antes_do_TAB():
    """Um F1 que se confirma não é repetido: o segundo toque seria desperdício."""
    memoria = _Memoria()
    combate = _motor_de_mentira("f1", memoria)
    combate._trocar_de_alvo = lambda *a, **k: combate.ctx.press("tab")

    combate.reancorar_o_alvo("teste")

    assert combate.ctx.apertadas == ["f1", "tab"]
    assert memoria.leituras == 1, (
        "a confirmação é UMA leitura de memória -- sem captura de tela")


def test_F1_que_NAO_pega_e_apertado_nas_DUAS_tentativas():
    """Regra do usuário: *"se precisar para garantir aperta 2x o F1"*.

    Apertar de novo é seguro porque o gesto é IDEMPOTENTE -- selecionar a si
    mesmo duas vezes dá o mesmo que uma. É o oposto do TAB, que é cíclico.
    """
    class _Teimosa(_Memoria):
        def virar_para_mim(self):
            pass                    # o F1 não pega, nunca

    memoria = _Teimosa()
    combate = _motor_de_mentira("f1", memoria)
    combate._trocar_de_alvo = lambda *a, **k: combate.ctx.press("tab")

    combate.reancorar_o_alvo("teste")

    assert combate.ctx.apertadas == ["f1", "f1", "tab"], (
        "sem confirmação o F1 tem que sair de novo -- e o TAB tem que sair de "
        "qualquer forma no fim")
    assert combate.ctx.apertadas.count("f1") == (
        motor.TENTATIVAS_DE_AUTO_SELECAO)


def test_NAO_CONFIRMAR_nao_bloqueia_o_TAB():
    """"Não sei" não bloqueia: bot mudo é pior que o defeito."""
    class _Ilegivel(_Memoria):
        def char_name(self):
            return None             # nome corrompido, como o `yXe City`

        def virar_para_mim(self):
            pass

    combate = _motor_de_mentira("f1", _Ilegivel())
    combate._trocar_de_alvo = lambda *a, **k: combate.ctx.press("tab")

    combate.reancorar_o_alvo("teste")

    assert "tab" in combate.ctx.apertadas


def test_MIRA_VAZIA_conta_como_F1_que_nao_pegou():
    combate = _motor_de_mentira("f1", _Memoria(alvo=None))
    assert combate._estou_na_minha_propria_mira() is False


def test_NOME_ILEGIVEL_nao_e_NAO():
    """`None` é "não deu para comparar", e não "não sou eu"."""
    class _SemNome(_Memoria):
        def char_name(self):
            return "  "

    combate = _motor_de_mentira("f1", _SemNome())
    assert combate._estou_na_minha_propria_mira() is None


def test_a_comparacao_IGNORA_caixa_e_espaco():
    combate = _motor_de_mentira("f1", _Memoria(meu="BlazesOfGamer",
                                               alvo=" blazesofgamer "))
    assert combate._estou_na_minha_propria_mira() is True


# ===========================================================================
# A abertura de toda luta da HH
# ===========================================================================


def test_o_core_loop_MIRA_antes_de_qualquer_outra_coisa():
    chamadas = _chamadas(HHRoutine._matar_ate_sair_de_batalha)

    assert "_mirar_o_primeiro_mob" in chamadas, (
        "A luta da HH abre com F1 + TAB. Sem isso a rotação gira contra o "
        "próprio personagem ou contra o pet, e o bot bate em nada.")
    assert chamadas.index("_mirar_o_primeiro_mob") < chamadas.index(
        "atacar_ate_sair_de_combate"), (
        "Mirar DEPOIS de começar a bater é bater no alvo errado primeiro.")


def test_a_abertura_NAO_TEM_CONDICAO():
    """Nenhum `if` antes do gesto: perguntar custa leitura e acerta menos."""
    corpo = textwrap.dedent(inspect.getsource(HHRoutine._mirar_o_primeiro_mob))
    arvore = ast.parse(corpo)
    metodo = arvore.body[0]

    assert not [n for n in ast.walk(metodo) if isinstance(n, ast.If)], (
        "O gesto é barato (duas teclas) e o resultado é sempre o mesmo -- o "
        "mob mais perto. Conferir cada caso possível antes é o que a regra do "
        "usuário substituiu.")


def test_NENHUM_combate_da_HH_escapa_da_mira():
    """*"todo e qualquer combate dentro de HH precisa clicar o F1 e depois o
    TAB"* -- usuário, 08/09/2026.

    Eram TRÊS entradas de combate e só uma passava pela mira. As outras duas
    foram relatadas por ele: *"vi aqui que alguns casos esta ocorrendo de não
    fazer isso"*.

    | entrada | quem ataca | tinha mira? |
    |---|---|---|
    | pontos de pacote | `_matar_ate_sair_de_batalha` | sim |
    | bosses 2 e 4 | `lutar_contra_um_boss` | **não** |
    | portão da montaria | `limpar_o_combate` | **não** |
    """
    import ast
    import textwrap

    from blazesbot.bot.hh import routine as mod

    # Quem CHAMA o motor de combate, e quem chama a mira, por método.
    arvore = ast.parse(inspect.getsource(mod))
    classe = next(n for n in arvore.body
                  if isinstance(n, ast.ClassDef) and n.name == "HHRoutine")

    ATAQUES = {"atacar_ate_sair_de_combate", "lutar_contra_um_boss",
               "limpar_o_combate"}
    for metodo in [n for n in classe.body if isinstance(n, ast.FunctionDef)]:
        chamadas = {getattr(n.func, "attr", getattr(n.func, "id", ""))
                    for n in ast.walk(metodo) if isinstance(n, ast.Call)}
        if not (chamadas & ATAQUES):
            continue
        assert "_mirar_o_primeiro_mob" in chamadas, (
            f"HHRoutine.{metodo.name} ataca sem passar pela mira "
            f"(chama {sorted(chamadas & ATAQUES)})")

    # E A ORDEM: mirar antes de bater.
    #
    # PELO LINENO DAS CHAMADAS, nunca por posição de texto: a docstring de
    # `_lutar_no_ponto` cita `_matar_ate_sair_de_batalha` para explicar os dois
    # caminhos, e uma busca no texto acharia a explicação antes da mira e
    # reprovaria um método correto.
    for nome in ("_lutar_no_ponto", "_matar_ate_sair_de_batalha",
                 "_destravar_o_combate"):
        corpo = ast.parse(textwrap.dedent(
            inspect.getsource(getattr(HHRoutine, nome)))).body[0]
        linhas = {}
        for n in ast.walk(corpo):
            if not isinstance(n, ast.Call):
                continue
            alvo = getattr(n.func, "attr", getattr(n.func, "id", ""))
            if alvo == "_mirar_o_primeiro_mob" or alvo in ATAQUES:
                linhas.setdefault(alvo, n.lineno)
        assert "_mirar_o_primeiro_mob" in linhas, nome
        ataques = [linha for alvo, linha in linhas.items() if alvo in ATAQUES]
        if ataques:
            assert linhas["_mirar_o_primeiro_mob"] < min(ataques), (
                f"{nome} bate antes de mirar")


def test_a_luta_NAO_TEM_PERGUNTA_NENHUMA_no_meio():
    """O F1+TAB é SÓ a abertura. Depois dela a luta é fluida.

    Regra do usuário, 08/09/2026: *"o F1 + TAB e apenas para evitar problemas no
    incio da batalha, mas as batalhas devem ser fluidas como exemplifiquei no
    Boss 2"*.

    Um detector de "alvo que não apanha" foi construído e SAIU por isto: ele
    lia o HP a cada volta para decidir se reancorava, e essa é uma pergunta no
    meio do caminho. O modelo é a luta do boss 2 -- morreu, TAB, continua
    batendo.
    """
    assinatura = inspect.signature(motor.CombatEngine.atacar_ate_sair_de_combate)

    assert "reancorar_alvo_travado" not in assinatura.parameters, (
        "O laço de ataque voltou a ter uma pergunta no meio: aquele detector "
        "lia o HP a cada volta para DECIDIR se trocava de alvo.")

    # E A DIFERENÇA ENTRE PERGUNTA E REAÇÃO, que é o que este teste protege.
    #
    # `ao_falhar_o_tab` existe e é chamado no meio da luta -- mas só quando o
    # TAB da morte NÃO trocou o alvo, e isso o laço já sabia: `trocou` vem da
    # confirmação por id, que existia antes. Zero leituras a mais, zero
    # condições novas no caminho normal.
    fonte = inspect.getsource(motor.CombatEngine.atacar_ate_sair_de_combate)
    assert "if ao_falhar_o_tab is not None and not trocou:" in fonte, (
        "a reancoragem do meio da luta deixou de ser condicionada à FALHA do "
        "TAB -- sem esse `not trocou` ela viraria pergunta")


def test_quem_troca_de_alvo_no_MEIO_e_a_MORTE_do_alvo():
    """E o TAB é imediato -- sem espera entre a morte e a troca."""
    fonte = inspect.getsource(motor.CombatEngine.atacar_ate_sair_de_combate)

    assert "ESPERA_APOS_A_MORTE_ANTES_DO_TAB" not in fonte, (
        "Os 3s de pausa depois da morte são a coreografia da BC "
        "(`limpar_o_combate`). Na HH os mobs do ponto PRECISAM morrer: puxar o "
        "seguinte é o objetivo.")
    assert "_trocar_de_alvo" in fonte


# ===========================================================================
# A BC não muda
# ===========================================================================


def test_a_BC_nao_reancora_alvo():
    from blazesbot.bot.bc.routine import BossRushRoutine

    fonte = inspect.getsource(BossRushRoutine)
    assert "reancorar_o_alvo" not in fonte, (
        "Decisão de cave não mora em código compartilhado, e esta é da HH: "
        "no BC quem abre a luta é o clique no boss, não o TAB.")


# ===========================================================================
# A regra "F1 nunca sai em batalha" e esta exceção
# ===========================================================================


def test_a_excecao_a_regra_do_F1_esta_ESCRITA_onde_ela_acontece():
    """`combate.py` tem a regra no alto: F1 LARGA o alvo, então nunca em luta.

    A abertura da luta a viola de propósito -- ali largar o alvo é o objetivo,
    e o TAB seguinte é o que fecha o gesto. Quem lê `reancorar_o_alvo` depois
    de ler a regra tem que encontrar o porquê no lugar, e não deduzir.
    """
    fonte = inspect.getsource(motor.CombatEngine.reancorar_o_alvo)

    assert "EXCEÇÃO" in fonte.upper(), (
        "Sem isto escrito, a próxima leitura da regra vai concluir que este "
        "F1 é o defeito que a regra proíbe.")


def test_o_F1_da_CURA_continua_proibido_em_batalha():
    """A exceção é só da abertura de luta. A cura não ganhou nada."""
    from blazesbot.bot.combate import CombatEngine

    fonte = inspect.getsource(CombatEngine.maintain)
    assert "reancorar_o_alvo" not in fonte
