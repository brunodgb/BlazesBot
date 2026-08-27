"""O TAB DO APP: só conta quando o ID MUDA.

Duas mudanças do usuário em 25/08/2026, e a segunda conserta a primeira.

**Primeira:** *"na macro não vai mais precisar que o usuário cadastre o TAB como
primeira linha; você irá dar o TAB e rodar a macro quando identificar que o
target é diferente de 0 pela memória"*.

Como linha 1, o TAB era apertado **toda volta, inclusive no meio de uma luta** --
e aí trocava de alvo, largava o mob machucado e recomeçava outro do zero.
Apertar TAB sem enxergar o alvo é apostar.

**Segunda:** *"os tabs não estão funcionando direito; tem que perceber que o
value do alvo alterou para confirmar se trocou, aí sim pode começar a rodar a
macro"*.

A primeira versão perguntava só **"tem id?"** depois do TAB -- e tinha: o
**CADÁVER continua selecionado, com o MESMO id**, por 7 a 13 s depois da morte
(medido em 20/08/2026). O bot dava a troca por feita e rodava a macro contra um
corpo.
"""
from types import SimpleNamespace

import pytest

from blazesbot.bot.app import executor as mod


def _mob(ident, hp=100, nome="Gun Witch"):
    """Um mob. O padrão é INTEIRO (100/100), que é o único que o bot engaja.

    Mob pela metade ou é luta de outro jogador ou é cadáver de daqui a pouco --
    ver `EXIGIR_ALVO_INTEIRO`.
    """
    # `pct` entra porque `Memory.alvo_atual()` devolve ele -- a fixture tem que
    # parecer com o que o jogo devolve, senao ela testa outra coisa.
    return {"id": ident, "nome": nome, "nivel": 50, "hp": hp, "max_hp": 100,
            "pct": hp / 100 if hp is not None else None}


class _Roda:
    """A roda do TAB do jogo: uma lista de entidades, e um índice.

    Modela o que importa e que a versão anterior deste arquivo não modelava: o
    TAB CICLA, e **o cadáver continua na roda** -- ele não sai dela quando morre.
    """

    def __init__(self, entidades, indice=0):
        self.entidades = list(entidades)
        self.indice = indice

    @property
    def atual(self):
        if not self.entidades:
            return None
        return self.entidades[self.indice % len(self.entidades)]

    def tab(self):
        if self.entidades:
            self.indice += 1


def _executor(roda=None, tecla="TAB", sem_leitura=False, em_batalha=None):
    """Um `ExecutorDeMacro` sem construtor -- não há jogo no teste."""
    e = mod.ExecutorDeMacro.__new__(mod.ExecutorDeMacro)
    e.teclas: list[str] = []
    e.linhas: list[tuple[str, str]] = []
    e.roda = roda

    def apertar(t):
        e.teclas.append(t)
        if t == tecla and roda is not None:
            roda.tab()

    e.input = SimpleNamespace(key=apertar)
    e.log = SimpleNamespace(
        info=lambda f, *a: e.linhas.append(("INFO", f % a if a else f)),
        warning=lambda f, *a: e.linhas.append(("WARNING", f % a if a else f)),
        debug=lambda *a, **k: None)

    if sem_leitura:
        e._id_do_alvo = None
        e._alvo_atual = None
    else:
        e._id_do_alvo = lambda: (roda.atual or {}).get("id", 0) if roda else 0
        e._alvo_atual = lambda: (roda.atual if roda else None)

    e._tecla_de_alvo = (lambda: tecla)
    e._continuar = lambda: True
    e.tabs_dados = 0
    e.mortes_vistas = 0
    e.alvos_inalcancaveis = 0
    e.voltas_abortadas = 0
    e.voltas = 0
    e._avisou_sem_tecla_de_alvo = False
    e._tabs_sem_resposta = 0
    e._avisou_tecla_morta = False
    # A régua do alvo inalcançável.
    e._alvo_da_regua = None
    e._hp_de_referencia = None
    e._linhas_sem_dano = 0
    e._ja_tirou_vida = False
    e._alvo_sumiu_avisado = False
    # A reserva pela flag de combate.
    e._alvo_da_reserva = None
    e._morto_pela_reserva = None
    e._morte_do_alvo = mod.MorteDoAlvo()
    e._em_batalha = em_batalha
    e._estava_em_batalha = False
    e._vida_pct = None
    e._urgencia = False
    e.urgencias = 0
    e._espera_depois_do_tab_ms = None
    # A SEGUNDA PORTA (a barra desenhada) e a cadencia dela. `None` = APP
    # sem tela, que e o padrao desta suite: quem quiser exercita-la injeta.
    e._vida_do_alvo_pela_tela = None
    e._linha_da_rotacao = 0
    e._ultima_olhada_na_tela = 0.0
    e._linha_da_ultima_olhada = -1
    e._linhas_cegas = 0
    e.mortes_pela_tela = 0
    # O escape do alvo ILEGÍVEL.
    e._alvo_ilegivel_id = None
    e._voltas_ilegiveis = 0
    e._inalcancavel_id = None
    return e


# OS VALORES DE VERDADE, capturados no import -- a fixture abaixo zera os dois
# para a suite nao dormir, e ai `mod.X` deixa de servir para travar o NUMERO.
# A REFERENCIA DA REGUA virou FRACAO (0..1) em 26/08/2026: ela le pela cascata
# memoria -> tela, e a barra desenhada so sabe responder em fracao. Por isso as
# assercoes deste arquivo comparam com `1.0` e `0.8` em vez de `100` e `80`.
RESPIRO_ANTES = mod.ESPERA_ANTES_DO_TAB
RESPIRO_DEPOIS = mod.ESPERA_DEPOIS_DO_TAB
ESPACO_ENTRE_TABS = mod.ESPERA_ENTRE_TABS
OBSERVACAO_DA_MORTE = mod.SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE
PAUSA_DA_RODA = mod.SEGUNDOS_PARA_A_RODA_REINICIAR
PASSO_DA_BASE = mod.PASSO_DA_ESPERA_DA_BASE


def _relogio_falso(monkeypatch):
    """RELOGIO FALSO, e nao `sleep` neutralizado.

    Neutralizar o `sleep` NAO faz o tempo passar: os lacos com teto saem por
    `time.time() >= fim`, entao eles girariam em vazio pelos 3 s de verdade.
    Aqui cada `sleep` ADIANTA o relogio, e o teto resolve em algumas voltas.
    Devolve a lista das dormidas, para quem quiser somar.
    """
    agora = [1000.0]
    dormidas: list[float] = []

    def dormir(segundos):
        dormidas.append(segundos)
        agora[0] += max(float(segundos), 0.01)

    monkeypatch.setattr(mod.time, "time", lambda: agora[0])
    monkeypatch.setattr(mod.time, "sleep", dormir)
    return dormidas


@pytest.fixture(autouse=True)
def _o_laco_antigo(monkeypatch):
    """ESTE ARQUIVO TESTA O LACO PARADO -- ver `LACO_SIMPLES` no executor.

    Em 26/08/2026 o usuario mandou voltar ao simples e deixar "as funcoes que
    fizemos ai paradas sem uso, para testar outra hora". Elas nao foram
    apagadas: viraram interruptor, que e a regra do projeto.

    Manter a suite delas viva e o que torna o religamento barato -- no dia em
    que `LACO_SIMPLES` virar `False`, o codigo que volta a rodar ja chega com
    134 testes atras dele, cada um citando a medicao que o justificou. Apagar os
    testes junto seria jogar fora o aprendizado e manter so o codigo.
    """
    monkeypatch.setattr(mod, "LACO_SIMPLES", False)


@pytest.fixture(autouse=True)
def _rapido(monkeypatch):
    monkeypatch.setattr(mod, "SEGUNDOS_PARA_O_ALVO_APARECER", 0.05)
    monkeypatch.setattr(mod, "PASSO_DA_ESPERA_DA_BASE", 0.0)
    monkeypatch.setattr(mod, "ESPERA_ANTES_DO_TAB", 0.0)
    monkeypatch.setattr(mod, "ESPERA_DEPOIS_DO_TAB", 0.0)
    monkeypatch.setattr(mod, "ESPERA_ENTRE_TABS", 0.0)
    monkeypatch.setattr(mod, "SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE", 0.0)
    monkeypatch.setattr(mod, "SEGUNDOS_PARA_A_RODA_REINICIAR", 0.0)


# ===========================================================================
# ALVO VIVO: NÃO SE MEXE
# ===========================================================================

def test_COM_alvo_vivo_a_tecla_nem_sai():
    """O defeito que a linha 1 tinha: apertar TAB no meio da luta LARGA o mob
    machucado e recomeça outro do zero."""
    e = _executor(_Roda([_mob(0x111, hp=45)]))

    e._garantir_alvo()

    assert e.teclas == [], "trocou de alvo com uma luta em andamento"
    assert e.tabs_dados == 0


def test_NAO_SEI_a_vida_nao_libera_o_TAB():
    """Sem leitura, dizer que morreu faria o bot largar um mob VIVO e sair
    procurando outro -- e o largado continua batendo."""
    e = _executor(_Roda([{"id": 0x111, "hp": None, "max_hp": 100}]))
    e._garantir_alvo()
    assert e.teclas == []


# ===========================================================================
# O TAB SÓ CONTA QUANDO O ID MUDA
# ===========================================================================

def test_CADAVER_nao_conta_como_alvo_e_o_TAB_insiste_ate_trocar():
    """O CORAÇÃO DO CONSERTO.

    O corpo fica selecionado, com o MESMO id, por 7 a 13 s. Perguntar "tem id?"
    depois do TAB respondia SIM -- o id do cadáver -- e o bot rodava a macro
    contra um corpo.
    """
    roda = _Roda([_mob(0x111, hp=0), _mob(0x222)])
    e = _executor(roda)

    e._garantir_alvo()

    assert e.teclas == ["TAB"], e.teclas
    assert roda.atual["id"] == 0x222, "não saiu do cadáver"


def test_TAB_que_cai_NOUTRO_cadaver_DESISTE(monkeypatch):
    """O TAB é cíclico e o corpo entra na roda tanto quanto um mob vivo — mas
    insistir levaria a um mob mais longe, e a roda é ordenada por distância.

    Com `TENTATIVAS_DE_TAB = 2` (interruptor) ele volta a insistir uma vez.
    """
    roda = _Roda([_mob(0x111, hp=0), _mob(0x222, hp=0), _mob(0x333)])
    e = _executor(roda)
    assert e._garantir_alvo() is False
    assert e.teclas == ["TAB"], e.teclas

    monkeypatch.setattr(mod, "TENTATIVAS_DE_TAB", 2)
    roda2 = _Roda([_mob(0x111, hp=0), _mob(0x222, hp=0), _mob(0x333)])
    e2 = _executor(roda2)
    assert e2._garantir_alvo() is True
    assert e2.teclas == ["TAB", "TAB"], e2.teclas
    assert roda2.atual["id"] == 0x333


def test_TECLA_QUE_NAO_PEGA_desiste_rapido():
    """Fracasso diferente de "caiu noutro cadáver": aqui CADA tentativa paga o
    teto inteiro, então o corte é mais curto.

    Sem essa separação, uma tecla mal configurada custaria
    `TENTATIVAS_DE_TAB * SEGUNDOS_PARA_O_ALVO_APARECER` por volta, para sempre.
    """
    roda = _Roda([_mob(0x111, hp=0)])
    roda.tab = lambda: None          # a tecla sai, o jogo ignora
    e = _executor(roda)

    # COM UM SALTO POR AQUISIÇÃO, o contador vive entre VOLTAS. Um contador
    # local nunca chegaria a dois, e a tecla morta seria relatada como "só
    # cadáver por aqui" para sempre — o diagnóstico errado.
    for _ in range(mod.TABS_SEM_RESPOSTA_PARA_DESISTIR):
        e._garantir_alvo()

    assert any("não está pegando" in t for _n, t in e.linhas), e.linhas
    assert not any("roda voltar ao começo" in t for _n, t in e.linhas), (
        "confundiu tecla morta com falta de mob perto")


def test_o_aviso_de_tecla_morta_sai_UMA_vez_e_REARMA():
    """Uma sessão de APP roda por horas; um aviso por volta afogaria o log. Mas
    consertar a tecla tem que voltar a valer."""
    roda = _Roda([_mob(0x111, hp=0), _mob(0x222)])
    pegando = [False]
    original = roda.tab
    roda.tab = lambda: original() if pegando[0] else None
    e = _executor(roda)

    for _ in range(6):
        e._garantir_alvo()
    avisos = [t for _n, t in e.linhas if "não está pegando" in t]
    assert len(avisos) == 1, avisos

    pegando[0] = True
    assert e._garantir_alvo() is True
    assert e._tabs_sem_resposta == 0


def test_UM_TAB_POR_AQUISICAO_e_mais_nenhum():
    """A VIRADA DE 26/08/2026, em duas etapas.

    Primeiro: *"o ideal é tentar manter só no PRIMEIRO tab, para evitar ficar
    indo em mobs muito longes, pq o tab vai primeiro no mob MAIS PERTO e
    conforme vai clicando ele vai indo nos mobs mais LONGES."*

    Depois, cortando o meio-termo de dois saltos: *"eu quero que seja apenas 1
    único tab por vez, pois com essa questão de GARANTIR o tab, está fazendo ir
    em outro mob e não no mais perto."*

    A versão de oito saltos media o custo em milissegundos. O custo nunca foi
    tempo: **cada salto é um mob mais longe**.
    """
    assert mod.TENTATIVAS_DE_TAB == 1

    mortos = [_mob(0x100 + i, hp=0) for i in range(5)]
    roda = _Roda([*mortos, _mob(0x999)])
    e = _executor(roda)

    assert e._garantir_alvo() is False, "insistiu para garantir um alvo"
    assert e.tabs_dados == 1, f"deu mais de um TAB: {e.tabs_dados}"


def test_MELHOR_sem_alvo_do_que_com_o_alvo_ERRADO():
    """O cadáver do mob recém-morto está encostado no personagem, então um
    salto pode não bastar. A resposta NÃO é dar outro salto — é desistir desta
    volta e tentar de novo, de novo no mais perto."""
    roda = _Roda([_mob(0x111, hp=0), _mob(0x222, hp=0), _mob(0x999, hp=80)])
    e = _executor(roda)

    assert e._garantir_alvo() is False
    assert e.tabs_dados == 1
    assert roda.atual["id"] == 0x222, "continuou girando até achar"
    assert any("NO MAIS PRÓXIMO" in t for _n, t in e.linhas), e.linhas


def test_desistir_ESPERA_a_roda_voltar_ao_comeco(monkeypatch):
    """Tentar de novo PERTO é sempre melhor que continuar LONGE.

    Sem a pausa, a volta seguinte apertaria o TAB com a roda ainda adiantada e
    pegaria um mob mais longe ainda -- exatamente o que os dois saltos existem
    para impedir.
    """
    dormidas: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", dormidas.append)
    monkeypatch.setattr(mod, "SEGUNDOS_PARA_A_RODA_REINICIAR", PAUSA_DA_RODA)

    e = _executor(_Roda([_mob(0x100 + i, hp=0) for i in range(5)]))
    e._garantir_alvo()

    assert sum(dormidas) == pytest.approx(PAUSA_DA_RODA)
    assert any("roda voltar ao começo" in t for _n, t in e.linhas), e.linhas


def test_SEM_alvo_nenhum_o_TAB_traz_um():
    roda = _Roda([{"id": 0}, _mob(0x222)])
    e = _executor(roda)

    e._garantir_alvo()

    assert e.teclas == ["TAB"]
    assert roda.atual["id"] == 0x222


def test_selecionar_NADA_nao_conta_como_troca(monkeypatch):
    monkeypatch.setattr(mod, "TENTATIVAS_DE_TAB", 3)
    """`id == 0` mudou, mas não para um alvo."""
    roda = _Roda([_mob(0x111, hp=0), {"id": 0}])
    e = _executor(roda)

    e._garantir_alvo()

    assert len(e.teclas) >= 2, (
        f"aceitou 'nada selecionado' como troca: {e.teclas}")


def test_sai_no_INSTANTE_em_que_o_alvo_troca():
    """O teto é aviso: o id muda numa leitura de microssegundos assim que o
    cliente processa a tecla."""
    roda = _Roda([_mob(0x111, hp=0), _mob(0x222)])
    e = _executor(roda)

    e._garantir_alvo()

    assert e.tabs_dados == 1


# ===========================================================================
# O QUE NÃO PODE PARAR A MACRO
# ===========================================================================

def test_sem_leitura_de_memoria_NADA_muda():
    """Cliente onde a memória não responde continua rodando a macro exatamente
    como antes -- mesmo contrato do pet e da trava de posição."""
    e = _executor(sem_leitura=True)
    e._garantir_alvo()
    assert e.teclas == []


def test_sem_tecla_configurada_avisa_UMA_vez_e_segue():
    e = _executor(_Roda([{"id": 0}]), tecla="")

    e._garantir_alvo()
    e._garantir_alvo()

    assert e.teclas == []
    avisos = [t for n, t in e.linhas if n == "WARNING"]
    assert len(avisos) == 1, avisos
    assert "próximo alvo" in avisos[0]


def test_leitura_que_EXPLODE_nao_derruba_a_volta():
    """Memória é leitura de processo alheio: pode falhar a qualquer instante, e
    a macro não pode cair junto."""
    def explode():
        raise RuntimeError("processo sumiu")

    e = _executor(_Roda([{"id": 0}]))
    e._id_do_alvo = explode
    e._garantir_alvo()

    assert e.teclas == []


def test_SEM_alvo_vivo_a_macro_NAO_roda():
    """DECISÃO REVERTIDA pelo usuário em 25/08/2026.

    A versão anterior deixava a macro rodar sem alvo, argumentando que macro de
    buff ou de pesca não poderia parar. Ele respondeu que **a macro do APP é só
    ataque**:

        *"Caso o mob esteja morto não faz sentido rodar a macro, tem que ir para
         o próximo MOB; só vale a pena rodar macro em mob vivo."*

    E rodar sem alvo é o que produz a mensagem de **skill inválida** na tela.
    """
    so_cadaveres = _Roda([_mob(0x100 + i, hp=0) for i in range(20)])
    assert _executor(so_cadaveres)._garantir_alvo() is False

    vivo = _Roda([_mob(0x111, hp=50)])
    assert _executor(vivo)._garantir_alvo() is True


def test_sem_leitura_de_memoria_o_alvo_e_dado_por_BOM():
    """Não há como PROVAR que não há alvo, e travar a macro por isso deixaria o
    APP mudo em cliente onde a memória não responde."""
    assert _executor(sem_leitura=True)._garantir_alvo() is True


def test_o_respiro_so_e_pago_quando_um_TAB_SAIU(monkeypatch):
    """*"Dá uns 500ms depois do TAB para começar a rodar a macro... às vezes
    está sendo muito rápido."*

    Alvo que já estava vivo não paga nada: não houve tecla, não há o que
    assentar. É isso que torna o respiro barato — ele custa uma vez por mob
    morto, não uma vez por volta da macro.

    O TESTE LÊ A CONSTANTE em vez de repetir o número: assim ele trava o
    COMPORTAMENTO (quem paga e quem não paga) e não o valor, que é observação de
    campo e já mudou uma vez.
    """
    dormidas: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", dormidas.append)
    monkeypatch.setattr(mod, "ESPERA_ANTES_DO_TAB", RESPIRO_ANTES)
    monkeypatch.setattr(mod, "ESPERA_DEPOIS_DO_TAB", RESPIRO_DEPOIS)

    _executor(_Roda([_mob(0x111, hp=50)]))._garantir_alvo()
    assert sum(dormidas) == 0, "pagou respiro sem ter apertado TAB"

    dormidas.clear()
    _executor(_Roda([_mob(0x111, hp=0), _mob(0x222)]))._garantir_alvo()
    total = RESPIRO_ANTES + RESPIRO_DEPOIS
    assert sum(dormidas) == pytest.approx(total), (
        f"os dois respiros do TAB deveriam somar {total}s: {sum(dormidas)}")


def test_o_respiro_DEPOIS_do_TAB_e_de_UM_SEGUNDO():
    """Dobrado em 26/08/2026: *"após o tab em vez de 500ms pode colocar 1
    segundo inteiro"*. Meio segundo não estava assentando."""
    assert RESPIRO_DEPOIS == 1.0


def test_o_respiro_ANTES_do_TAB_e_de_600ms():
    """*"E adiciona 600ms antes do tab"* (usuário, 26/08/2026).

    Gêmeo do de baixo: a volta acabou de mandar a última linha da rotação e o
    TAB que chega em cima se perde. O que se perde aqui é a PRÓPRIA AQUISIÇÃO,
    e um TAB engolido custa uma volta inteira contra o cadáver.
    """
    assert RESPIRO_ANTES == 0.6


def test_o_respiro_ANTES_e_pago_UMA_VEZ_por_aquisicao_e_nao_por_tecla(
        monkeypatch):
    """A roda pode girar até `TENTATIVAS_DE_TAB` vezes, e cobrar 0,6 s em cada
    salto somaria ~4,8 s por volta num ponto cheio de cadáveres -- sem comprar
    nada.

    O que o respiro resolve é a colisão com as teclas da MACRO, e essas só
    existem antes do PRIMEIRO salto. Entre saltos, `_esperar_o_alvo_trocar` só
    devolve com o id JÁ trocado -- um TAB nunca chega em cima de outro pendente.
    """
    dormidas: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", dormidas.append)
    monkeypatch.setattr(mod, "ESPERA_ANTES_DO_TAB", RESPIRO_ANTES)
    monkeypatch.setattr(mod, "ESPERA_DEPOIS_DO_TAB", RESPIRO_DEPOIS)
    monkeypatch.setattr(mod, "ESPERA_ENTRE_TABS", ESPACO_ENTRE_TABS)
    monkeypatch.setattr(mod, "TENTATIVAS_DE_TAB", 2)

    roda = _Roda([_mob(0x111, hp=0), _mob(0x222, hp=0), _mob(0x999, hp=70)])
    e = _executor(roda)
    e._garantir_alvo()

    assert e.tabs_dados == 2, f"a roda nem girou: {e.tabs_dados} TAB(s)"
    # A CONTA, aberta: o respiro de cima UMA vez, o espaçamento ENTRE saltos
    # (um a menos que o número de saltos) e o respiro de baixo UMA vez.
    total = (RESPIRO_ANTES
             + ESPACO_ENTRE_TABS * (e.tabs_dados - 1)
             + RESPIRO_DEPOIS)
    assert sum(dormidas) == pytest.approx(total), (
        f"pagou o respiro de cima por tecla ({e.tabs_dados} TABs): "
        f"{sum(dormidas)} contra {total}")


def test_os_respiros_do_TAB_RESPONDEM_ao_Parar():
    """1,6 s de bot mudo por mob morto é espera cega, e a regra do projeto é
    que o Parar responda na hora.

    NÃO dá para usar `_esperar` aqui: ele confere a MORTE DO ALVO lá dentro, e
    durante a aquisição o alvo selecionado é justamente o cadáver que se está
    tentando largar -- ele devolveria "pare" no primeiro décimo de segundo.
    """
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(
        inspect.getsource(mod.ExecutorDeMacro._garantir_alvo))
    chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "sleep" not in chamadas, "voltou a espera cega em volta do TAB"
    assert "_dormir" in chamadas

    e = _executor(_Roda([_mob(0x111, hp=0), _mob(0x222)]))
    e._continuar = lambda: False
    assert e._dormir(10.0) is False


def test_desistir_AVISA_e_diz_QUAL_foi_o_motivo():
    """Dois fracassos diferentes pedem dois avisos diferentes: quem lê o log
    precisa saber se o problema é a tecla ou é não ter mob."""
    so_cadaveres = _Roda([_mob(0x100 + i, hp=0) for i in range(20)])
    e1 = _executor(so_cadaveres)
    e1._garantir_alvo()
    assert any("só cadáver por aqui" in t for _n, t in e1.linhas), e1.linhas
    assert not any("não está pegando" in t for _n, t in e1.linhas), e1.linhas

    travada = _Roda([_mob(0x111, hp=0)])
    travada.tab = lambda: None
    e2 = _executor(travada)
    for _ in range(mod.TABS_SEM_RESPOSTA_PARA_DESISTIR):
        e2._garantir_alvo()
    assert any("não está pegando" in t for _n, t in e2.linhas), e2.linhas


def test_a_ORDEM_da_volta_e_confere_voltar_TAB_macro():
    """*"As conferências têm que ser antes do TAB, então verifica primeiro, TAB
    depois; o TAB tem que vir logo antes da macro."*

    Antes o TAB era a PRIMEIRA coisa da volta, e o bot adquiria o alvo para só
    então gastar tempo com pet e caminhada -- com o mob novo batendo de graça
    nesse meio-tempo. Era o sintoma relatado.
    """
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(mod.ExecutorDeMacro.uma_volta))

    # A PRIMEIRA ocorrência de cada uma, não a última: `_garantir_alvo` aparece
    # duas vezes (a segunda é a régua do inalcançável), e um dicionário simples
    # guardaria só a de baixo.
    primeira: dict[str, int] = {}
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            primeira.setdefault(no.func.attr, no.lineno)
            primeira[no.func.attr] = min(primeira[no.func.attr], no.lineno)

    for antes, depois in (("garantir_pet", "_travar_posicao_se_preciso"),
                          ("_travar_posicao_se_preciso", "_garantir_alvo"),
                          ("_garantir_alvo", "_registrar_o_alvo")):
        assert primeira[antes] < primeira[depois], (
            f"`{antes}` deveria vir antes de `{depois}`")


# ===========================================================================
# A MACRO PARA NO MEIO QUANDO O MOB CAI
# ===========================================================================

def test_alvo_morreu_responde_pela_VIDA_e_nao_pelo_id():
    assert _executor(_Roda([_mob(0x111, hp=0)]))._alvo_morreu() is True
    assert _executor(_Roda([_mob(0x111, hp=1)]))._alvo_morreu() is False


def test_leitura_do_alvo_que_EXPLODE_nao_derruba_nada():
    e = _executor(_Roda([_mob(0x111)]))

    def explode():
        raise RuntimeError("processo sumiu")

    e._alvo_atual = explode
    assert e._alvo_morreu() is False


def test_cortar_a_volta_avisa_e_conta():
    """*"Caso o mob morra antes de acabar a macro inteira, pode ir para o
    próximo mob sem terminar a macro."*"""
    e = _executor(_Roda([_mob(0x111, hp=0)]))

    assert e._cortar_a_volta() is True
    assert e.mortes_vistas == 1
    assert any("corto a rotação" in t for _n, t in e.linhas), e.linhas


def test_com_o_alvo_VIVO_a_volta_NAO_e_cortada():
    """*"Caso não morra, você não aperta TAB: você recomeça a macro até garantir
    que ele morreu."*"""
    assert _executor(_Roda([_mob(0x111, hp=45)]))._cortar_a_volta() is False


def test_com_o_interruptor_DESLIGADO_a_macro_vai_ate_o_fim(monkeypatch):
    monkeypatch.setattr(mod, "INTERROMPER_A_MACRO_QUANDO_O_ALVO_MORRE", False)
    assert _executor(_Roda([_mob(0x111, hp=0)]))._cortar_a_volta() is False


def test_o_interruptor_esta_LIGADO():
    assert mod.INTERROMPER_A_MACRO_QUANDO_O_ALVO_MORRE is True


def test_a_espera_de_UMA_LINHA_tambem_confere_a_morte():
    """Uma linha de 3000 ms sem isso faria o bot bater num cadáver por até três
    segundos."""
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(mod.ExecutorDeMacro._esperar))
    chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "_cortar_a_volta" in chamadas


def test_a_conferencia_e_mais_fina_que_a_linha_mais_curta():
    assert mod.PASSO_DA_CONFERENCIA_DO_ALVO <= 0.25


# ===========================================================================
# A RÉGUA DO ALVO INALCANÇÁVEL -- o mob do penhasco
# ===========================================================================

def _com_regua(alvos, ident=0x111):
    """Um executor com a régua JÁ NASCIDA, como fica depois de um TAB.

    A referência é fixada na AQUISIÇÃO -- se ela nascesse na primeira
    conferência, consumiria a primeira linha da macro e a regra do usuário
    viraria três linhas na prática.

    ATENÇÃO ao montar a lista: o nascimento da régua CONSOME a primeira leitura
    (é dela que sai a referência). O que vem depois são as linhas da macro.
    """
    e = _executor(_Roda([_mob(ident, hp=100)]))
    seq = list(alvos)
    e._alvo_atual = lambda: seq.pop(0) if len(seq) > 1 else seq[0]
    e._comecar_a_regua(ident)
    return e


def test_TRES_linhas_sem_tirar_vida_TROCAM_de_alvo():
    """*"A primeira leitura do target é 100/100 HP e a vida não saiu disso
    depois da primeira e segunda linha — já não alterou, então vai para o
    próximo mob."*

    O mob do penhasco: existe, está vivo, e o jogo não deixa acertar.
    """
    e = _com_regua([_mob(0x111, hp=100)] * 6)

    assert e._alvo_intocavel() is False, "trocou na primeira linha"
    assert e._alvo_intocavel() is False, "trocou na segunda linha"
    assert e._alvo_intocavel() is True, "não percebeu em 3 linhas"
    assert any("não estou alcançando" in t for _n, t in e.linhas), e.linhas


def test_tirar_UM_ponto_de_vida_ja_zera_a_regua():
    """Se está tirando vida, está alcançando. Um ponto basta."""
    e = _com_regua([_mob(0x111, hp=100),     # a régua nasce com 100
                    _mob(0x111, hp=99),      # tirou 1 de vida
                    _mob(0x111, hp=99),
                    _mob(0x111, hp=99),
                    _mob(0x111, hp=99)])

    assert e._hp_de_referencia == 1.0
    # DEPOIS DE TIRAR UM PONTO, A RÉGUA CALA PARA SEMPRE NESTE ALVO.
    # Foi ela que largou um mob em luta e matou o personagem: se dá para
    # machucar, dá para acertar, e o que está acontecendo é outra coisa.
    for _ in range(4):
        assert e._alvo_intocavel() is False


def test_a_referencia_e_o_PRIMEIRO_HP_e_regeneracao_nao_engana():
    """Se a referência fosse o golpe anterior, um mob regenerando pareceria
    estar sendo acertado a cada leitura.

    A pergunta certa é "eu ALGUMA VEZ tirei vida dele?".
    """
    e = _com_regua([_mob(0x111, hp=100)] * 4)
    assert e._hp_de_referencia == 1.0

    # o mob regenera ACIMA da referência: continua sendo "não tirei nada"
    e._alvo_atual = lambda: _mob(0x111, hp=120)   # regenera acima do teto
    assert e._alvo_intocavel() is False
    assert e._alvo_intocavel() is False
    assert e._alvo_intocavel() is True


def test_HP_ilegivel_NAO_conta_nem_a_favor_nem_contra():
    """"Não sei" nunca larga alvo -- mesma regra da régua da barra e da trava
    da janela."""
    e = _com_regua([{"id": 0x111, "hp": None}] * 4)

    for _ in range(4):
        assert e._alvo_intocavel() is False


def test_alvo_NOVO_recomeca_a_regua():
    """O contador é do ALVO, não da volta."""
    e = _com_regua([_mob(0x111, hp=100),     # a régua nasce
                    _mob(0x111, hp=100),     # 1ª linha sem dano
                    _mob(0x111, hp=100),     # 2ª linha sem dano
                    _mob(0x111, hp=100),     # 3ª linha sem dano
                    _mob(0x222, hp=80),      # TAB: alvo novo
                    _mob(0x222, hp=80)])

    assert e._alvo_intocavel() is False
    assert e._alvo_intocavel() is False
    assert e._alvo_intocavel() is True       # o 0x111 é inalcançável

    assert e._alvo_intocavel() is False, "não zerou no alvo novo"
    assert e._alvo_da_regua == 0x222
    assert e._hp_de_referencia == 0.8


def test_o_TAB_do_inalcancavel_e_FORCADO():
    """O mob está VIVO, então o atalho "alvo vivo, não mexe" impediria a troca.
    `forcar=True` é o que larga um alvo que não dá para acertar."""
    roda = _Roda([_mob(0x111), _mob(0x222)])
    e = _executor(roda)

    assert e._garantir_alvo() is True         # alvo vivo: não mexe
    assert e.teclas == []

    assert e._garantir_alvo(forcar=True) is True
    assert e.teclas == ["TAB"]
    assert roda.atual["id"] == 0x222


def test_NAO_guarda_lista_de_inalcancaveis():
    """*"Caso volte é só identificar novamente depois da segunda linha; não
    precisa guardar nada, pois os IDs podem mudar e acabar percebendo errado."*

    Uma lista velha faria o bot pular mob bom.
    """
    import ast
    import inspect

    fonte = ast.parse(inspect.getsource(mod))
    nomes = {no.attr for no in ast.walk(fonte)
             if isinstance(no, ast.Attribute)}
    proibidos = {n for n in nomes
                 if "intocav" in n.lower() or "inalcanc" in n.lower()}
    # O que está proibido é uma COLEÇÃO de ids largados. São permitidos:
    # `_alvo_intocavel` (o veredito), `_largar_o_alvo_inalcancavel` (marca),
    # `alvos_inalcancaveis` (um INTEIRO de estatística) e `_inalcancavel_id`
    # (UM id, gasto na volta seguinte e apagado -- ver o teste de comportamento
    # `test_o_inalcancavel_que_VOLTA_ganha_avaliacao_nova`).
    assert proibidos <= {"_alvo_intocavel", "_largar_o_alvo_inalcancavel",
                         "alvos_inalcancaveis", "_inalcancavel_id"}, (
        f"apareceu memória de alvos inalcançáveis: {proibidos}")


def test_o_inalcancavel_que_VOLTA_ganha_avaliacao_nova():
    """A marca é UM id GASTO, e não memória permanente.

    *"Caso volte é só identificar novamente depois da segunda linha; não
    precisa guardar nada, pois os IDs podem mudar e acabar percebendo errado."*
    """
    roda = _Roda([_mob(0x111, hp=100), _mob(0x222, hp=100)])
    e = _executor(roda)

    # A régua largou o 0x111.
    e._largar_o_alvo_inalcancavel()
    assert e._inalcancavel_id == 0x111

    # A volta seguinte GASTA a marca: o TAB sai mesmo com o mob vivo.
    assert e._garantir_alvo() is True
    assert e.teclas == ["TAB"]
    assert e._inalcancavel_id is None, "a marca virou memória permanente"

    # O TAB volta a cair no 0x111: ele é aceito, e a régua o avalia de novo.
    roda.indice = 0
    e.teclas.clear()
    assert e._garantir_alvo() is True
    assert e.teclas == [], "pulou um mob só porque ele já tinha sido largado"


def test_o_largado_NAO_aperta_tecla_nenhuma():
    """Existe UM só lugar que adquire alvo, e é o passo 4 da volta -- com a
    conferência de id novo, o respiro do TAB e a régua recomeçada. Apertar o
    TAB no abandono entregaria à volta seguinte um alvo que ninguém conferiu."""
    e = _executor(_Roda([_mob(0x111, hp=100), _mob(0x222, hp=100)]))

    e._largar_o_alvo_inalcancavel()

    assert e.teclas == []
    assert e.tabs_dados == 0


def test_a_regua_roda_DEPOIS_de_cada_linha():
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(mod.ExecutorDeMacro.uma_volta))
    chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "_alvo_intocavel" in chamadas


def test_TRES_linhas_e_nao_duas():
    """Decisão do usuário em 26/08/2026: *"LINHAS_SEM_DANO_PARA_TROCAR = 2
    coloca em 3, acho que vai ser melhor"*.

    Com 1, uma skill que erra ou de recarga longa trocaria alvo à toa. Com 2, a
    margem contra o atraso do servidor ficou apertada demais depois que o
    portão `hp >= max_hp` saiu (ver `EXIGIR_ALVO_INTEIRO`).
    """
    assert mod.LINHAS_SEM_DANO_PARA_TROCAR == 3


def test_alvo_que_SUMIU_do_array_deixa_rastro_no_log():
    """SUSPEITA EM INVESTIGAÇÃO, e por isso ela LOGA em vez de decidir.

    O id responde mas nenhuma entidade tem esse id. Duas explicações opostas:
    a entidade ainda não entrou no array (medido: 1 leitura em ~45, logo depois
    de selecionar), ou ela SAI do array quando o mob morre.

    A segunda faria o bot bater no cadáver até o TAB — o sintoma que o usuário
    relatou. Enquanto não há medição, a resposta segura é "não morreu", e o que
    se faz é deixar rastro.
    """
    e = _executor(_Roda([_mob(0x111, hp=50)]))
    e._alvo_atual = lambda: None

    assert e._alvo_morreu() is False
    assert e._alvo_morreu() is False

    avisos = [t for _n, t in e.linhas if "NENHUMA entidade" in t]
    assert len(avisos) == 1, f"o rastro repetiu ou sumiu: {e.linhas}"


def test_o_rastro_REARMA_quando_a_entidade_volta():
    """Uma ocorrência nova precisa aparecer no log; senão a segunda vez fica
    invisível e o padrão não dá para ver."""
    e = _executor(_Roda([_mob(0x111, hp=50)]))
    sumido = [True]
    e._alvo_atual = lambda: None if sumido[0] else _mob(0x111, hp=50)

    e._alvo_morreu()
    sumido[0] = False
    e._alvo_morreu()
    sumido[0] = True
    e._alvo_morreu()

    avisos = [t for _n, t in e.linhas if "NENHUMA entidade" in t]
    assert len(avisos) == 2, e.linhas


# ===========================================================================
# SÓ SE ENGAJA ALVO INTEIRO — e não se LARGA alvo machucado
# ===========================================================================

def test_o_TAB_ACEITA_mob_pela_metade():
    """REVOGAÇÃO de 26/08/2026 -- ver `EXIGIR_ALVO_INTEIRO`.

    Recusar mob machucado parecia proteger contra herdar a luta de outro
    jogador. Na prática, num ponto de farm movimentado quase todo mob da roda
    está machucado: o bot recusava TODOS, girava a roda inteira, não engajava
    nada, e a volta seguinte recomeçava. TAB contínuo, e cada TAB é um mob a
    mais olhando para o personagem.
    """
    roda = _Roda([_mob(0x111, hp=0), _mob(0x222, hp=30)])
    e = _executor(roda)

    assert e._garantir_alvo() is True
    assert roda.atual["id"] == 0x222
    assert e.tabs_dados == 1, "girou a roda à toa num mob perfeitamente válido"


def test_alvo_JA_NA_MIRA_e_machucado_NAO_e_largado():
    """A regra do 100/100 vale só para AQUISIÇÃO.

    Largar mob no meio da luta é o defeito que matou o personagem: o mob
    largado continua batendo.
    """
    e = _executor(_Roda([_mob(0x111, hp=35)]))

    assert e._garantir_alvo() is True
    assert e.teclas == [], "largou um mob que estava sendo morto"


def test_a_regua_do_inalcancavel_NAO_dispara_em_alvo_machucado():
    """O CONSERTO DO DEFEITO QUE MATOU O PERSONAGEM.

    *"Eu acompanhei que trocou de target sem ter matado o target, agora nessa
    última versão, fazendo que o personagem morresse."*

    Numa macro de linhas curtas, duas linhas passam em menos de um segundo --
    antes de o servidor registrar o primeiro golpe. A régua largava um mob que
    ESTAVA sendo morto, e o mob largado continuava batendo.

    Se o alvo já perdeu vida, dá para acertar: a régua cala.
    """
    e = _com_regua([_mob(0x111, hp=100),     # a régua nasce
                    _mob(0x111, hp=97),      # já machucou
                    _mob(0x111, hp=97),
                    _mob(0x111, hp=97),
                    _mob(0x111, hp=97)])

    for _ in range(4):
        assert e._alvo_intocavel() is False, (
            "largou um alvo que já estava machucado")


def test_a_regua_AINDA_dispara_no_mob_INTEIRO():
    """A trava não pode matar a regra: o mob do penhasco continua sendo
    largado, porque ele fica em 100/100 para sempre."""
    e = _com_regua([_mob(0x111, hp=100)] * 6)

    assert e._alvo_intocavel() is False
    assert e._alvo_intocavel() is False
    assert e._alvo_intocavel() is True


def test_a_regua_dispara_TAMBEM_no_mob_do_penhasco_JA_MACHUCADO():
    """O QUE O PORTÃO `hp >= max_hp` IMPEDIA -- e por isso ele saiu.

    Com a exigência de alvo inteiro revogada, o bot adquire mobs machucados.
    Um mob a 60/100 do outro lado do penhasco ficava imune à régua para
    sempre, porque ele nunca voltaria a 100/100.

    A pergunta certa é sobre a AQUISIÇÃO, não sobre o máximo: adquirido a 60
    e ainda em 60 depois de três linhas é alcance.
    """
    e = _com_regua([_mob(0x111, hp=60)] * 6)

    assert e._alvo_intocavel() is False
    assert e._alvo_intocavel() is False
    assert e._alvo_intocavel() is True


def test_machucar_DEPOIS_de_adquirir_cala_a_regua_para_sempre():
    """O CONSERTO DO DEFEITO QUE MATOU O PERSONAGEM, ancorado no lugar certo.

    Adquirido a 100, machucado para 97, e o servidor para de registrar dano:
    isso é LUTA, e largar aqui é largar mob no meio dela. A régua cala para
    sempre neste alvo, por mais linhas que passem.
    """
    e = _com_regua([_mob(0x111, hp=100),     # a régua nasce
                    _mob(0x111, hp=97)] + [_mob(0x111, hp=97)] * 8)

    for _ in range(8):
        assert e._alvo_intocavel() is False, (
            "largou um alvo que ELE MESMO machucou")


def test_a_regua_le_a_memoria_UMA_VEZ_por_linha():
    """Duas fotos de instantes diferentes respondendo à mesma pergunta é como
    nascem as decisões que ninguém consegue reproduzir."""
    leituras = [0]
    e = _com_regua([_mob(0x111, hp=100)] * 6)

    original = e._alvo_atual

    def contando():
        leituras[0] += 1
        return original()

    e._alvo_atual = contando
    e._alvo_intocavel()

    assert leituras[0] == 1, f"leu {leituras[0]} vezes numa linha só"


def test_o_interruptor_do_alvo_inteiro_esta_DESLIGADO():
    """REVOGADO pelo usuário em 26/08/2026: *"anteriormente em outra sessão eu
    tinha falado que precisava estar com a vida 100/100, mas não precisa, pode
    ser qualquer vida, o importante é ser um alvo DIFERENTE"*.

    Ligado, ele produziu o defeito relatado no mesmo dia -- *"começou a ficar
    andando e dando tab, chamou vários mobs e morreu"*: num ponto de farm
    movimentado quase todo mob da roda está machucado, então `_garantir_alvo`
    recusava TODOS, girava a roda inteira e a volta seguinte recomeçava.
    """
    assert mod.EXIGIR_ALVO_INTEIRO is False


def test_qualquer_vida_serve_desde_que_o_ALVO_seja_outro():
    """O critério de aquisição é ESTAR VIVO; quem garante que é outro mob é a
    IDENTIDADE, não o HP."""
    roda = _Roda([_mob(0x111, hp=0), _mob(0x222, hp=60)])
    e = _executor(roda)

    assert e._garantir_alvo() is True
    assert roda.atual["id"] == 0x222, "recusou um mob vivo por estar machucado"


def test_LIGADO_de_volta_o_bot_recusa_mob_pela_metade(monkeypatch):
    """O interruptor continua de pé -- mas religá-lo exige medir antes: ele já
    matou o personagem uma vez."""
    monkeypatch.setattr(mod, "EXIGIR_ALVO_INTEIRO", True)
    monkeypatch.setattr(mod, "TENTATIVAS_DE_TAB", 3)
    roda = _Roda([_mob(0x111, hp=0), _mob(0x222, hp=60), _mob(0x333, hp=100)])
    e = _executor(roda)

    assert e._garantir_alvo() is True
    assert roda.atual["id"] == 0x333


# ===========================================================================
# A RESERVA: HP ILEGÍVEL DECIDIDO PELA FLAG DE COMBATE
# ===========================================================================
#
# Decisão do usuário em 26/08/2026: *"caso não consiga identificar a vida você
# deve usar o `em combate = False`. Caso saia do True e fique False, é pq saiu
# de batalha e o mob já está morto. Caso não saia, ou não está morto ou tem
# outro mob batendo no personagem."*

def _ilegivel(em_batalha):
    """Um executor com alvo SELECIONADO e entidade ausente do array."""
    e = _executor(_Roda([_mob(0x111, hp=50)]), em_batalha=em_batalha)
    e._alvo_atual = lambda: None
    return e


def test_a_batalha_que_ACABA_com_o_alvo_selecionado_prova_a_morte():
    """O ESCAPE DO ESTADO ABSORVENTE.

    Com o HP ilegível, `_alvo_morreu()` respondia False para sempre e
    `_garantir_alvo` lia isso como "alvo vivo, não mexe" -- TAB nunca, macro
    contra o corpo até o usuário parar o bot na mão.
    """
    estados = iter([True, False, False])
    e = _ilegivel(lambda: next(estados))

    assert e._alvo_morreu() is False, "declarou morte antes de ver a transição"
    assert e._alvo_morreu() is True, "não viu a batalha acabar"
    assert any("a batalha ACABOU" in t for _n, t in e.linhas), e.linhas


def test_a_flag_PRESA_em_True_nao_prova_nada():
    """*"Caso não saia, ou não está morto ou tem outro mob batendo no
    personagem."* Nos dois casos o certo é continuar batendo."""
    e = _ilegivel(lambda: True)

    for _ in range(5):
        assert e._alvo_morreu() is False


def test_a_reserva_so_sabe_dizer_MORREU():
    """Fora de batalha o tempo todo (entre um mob e outro) não é morte de
    ninguém: o que prova é a TRANSIÇÃO, não o nível."""
    e = _ilegivel(lambda: False)

    for _ in range(5):
        assert e._alvo_morreu() is False


def test_o_veredito_da_reserva_e_LATCH_por_identidade():
    """A transição True -> False acontece UMA vez. Sem guardar o veredito, a
    pergunta seguinte voltaria a "não sei" -- devolvendo o bot exatamente ao
    estado absorvente que a reserva veio desfazer."""
    estados = iter([True, False, False, False, False])
    e = _ilegivel(lambda: next(estados))

    e._alvo_morreu()
    assert e._alvo_morreu() is True
    for _ in range(3):
        assert e._alvo_morreu() is True, "esqueceu o veredito"


def test_UM_PONTO_DE_VIDA_derruba_o_veredito_da_reserva():
    """Se ele aparece vivo, ele está vivo -- e o que a flag disse antes não
    importa mais."""
    estados = iter([True, False])
    e = _ilegivel(lambda: next(estados))
    e._alvo_morreu()
    assert e._alvo_morreu() is True

    e._alvo_atual = lambda: _mob(0x111, hp=40)
    assert e._alvo_morreu() is False
    assert e._morto_pela_reserva is None


def test_a_leitura_ILEGIVEL_da_flag_nao_apaga_a_memoria_da_batalha():
    """`None` de uma leitura falha não pode apagar que o personagem ESTAVA em
    batalha, senão a reserva perde justamente o sinal que ela existe para ver."""
    estados = iter([True, None, False])
    e = _ilegivel(lambda: next(estados))

    assert e._alvo_morreu() is False    # True
    assert e._alvo_morreu() is False    # None: não decide
    assert e._alvo_morreu() is True     # False: a transição sobreviveu


def test_SEM_reserva_o_HP_ilegivel_volta_a_ser_nao_sei():
    """`em_batalha=None` (sem leitura) devolve o contrato antigo: continua
    batendo, porque não há como provar a morte."""
    e = _ilegivel(None)

    for _ in range(5):
        assert e._alvo_morreu() is False


# ===========================================================================
# O ESCAPE DO ALVO ILEGÍVEL: "NÃO SEI" NÃO BLOQUEIA O TAB PARA SEMPRE
# ===========================================================================

def test_alvo_ilegivel_por_voltas_demais_LIBERA_o_TAB():
    """Com OUTRO mob batendo, a flag de combate nunca baixa e a reserva não tem
    o que dizer. Um alvo que não dá para enxergar também não dá para saber que
    está sendo morto."""
    roda = _Roda([_mob(0x111, hp=50), _mob(0x222, hp=80)])
    e = _executor(roda, em_batalha=lambda: True)
    # SÓ O 0x111 está ilegível; o vizinho da roda lê normalmente.
    e._alvo_atual = lambda: (None if (roda.atual or {}).get("id") == 0x111
                             else roda.atual)

    assert e._garantir_alvo() is True
    assert e.teclas == [], "largou na primeira volta ilegível"

    assert e._garantir_alvo() is True
    assert e.teclas == ["TAB"], "ficou preso no alvo ilegível"
    assert roda.atual["id"] == 0x222
    assert any("ILEGÍVEL" in t for _n, t in e.linhas), e.linhas


def test_UMA_leitura_boa_zera_o_escape():
    """Flicker de uma amostra não conta: a entidade some do array por 1 leitura
    em ~45 com o mob VIVO (medido em 25/08/2026)."""
    sumido = [True]
    roda = _Roda([_mob(0x111, hp=50)])
    e = _executor(roda, em_batalha=lambda: True)
    e._alvo_atual = lambda: None if sumido[0] else _mob(0x111, hp=50)

    e._garantir_alvo()
    sumido[0] = False
    e._garantir_alvo()
    sumido[0] = True
    e._garantir_alvo()

    assert e.teclas == [], "a leitura boa não zerou o contador"


# ===========================================================================
# A MESMA MORTE NÃO SAI DUAS VEZES
# ===========================================================================

def test_a_mesma_morte_nao_conta_duas_vezes():
    """O cadáver fica selecionável de 7 a 13 s. Uma volta que recomece em cima
    dele voltaria a contar o mesmo óbito e a repetir a mesma linha de log."""
    e = _executor(_Roda([_mob(0x111, hp=0)]))

    assert e._cortar_a_volta() is True
    assert e._cortar_a_volta() is True, "parou de cortar a volta no cadáver"
    assert e.mortes_vistas == 1, "contou o mesmo óbito duas vezes"
    assert len([t for _n, t in e.linhas if "caiu no meio" in t]) == 1


def test_a_trava_e_por_IDENTIDADE_e_deixa_a_morte_SEGUINTE_passar():
    """Uma trava de RELÓGIO ou contaria duas vezes ou engoliria a próxima."""
    roda = _Roda([_mob(0x111, hp=0), _mob(0x222, hp=0)])
    e = _executor(roda)

    e._cortar_a_volta()
    roda.tab()
    assert e._cortar_a_volta() is True
    assert e.mortes_vistas == 2


# ===========================================================================
# SEM TECLA DE ALVO: NÃO RODA A MACRO CONTRA O NADA
# ===========================================================================

def test_sem_tecla_e_com_o_alvo_MORTO_a_volta_NAO_roda():
    """Devolver True aqui mandava a macro rodar contra um cadáver -- e a volta
    era cortada na primeira linha sem enviar tecla e sem pagar espera nenhuma,
    o que fazia `rodar()` girar com a CPU em 100%."""
    e = _executor(_Roda([_mob(0x111, hp=0)]), tecla="")

    assert e._garantir_alvo() is False


# ===========================================================================
# CONTADORES: SÓ A VOLTA COMPLETA CONTA COMO VOLTA
# ===========================================================================
#
# Decisão do usuário em 26/08/2026: *"a contagem de voltas não deve levar em
# consideração os mobs que não conseguir atacar como os do penhasco"*.
#
# `self.voltas` alimenta a limpeza de bolsa (`voltas % a_cada`) e o shuffle
# anti-AFK. Contar aborto contamina os dois: num ponto de farm com muita morte
# eles passam a disparar cedo demais.

def _volta(alvos, passos=3, tecla="TAB"):
    """Um executor pronto para `uma_volta()`, com uma sequência de leituras.

    A sequência é consumida SÓ por `_alvo_atual`; `_id_do_alvo` espia a leitura
    corrente sem gastar. É o que reproduz o que o jogo faz: o id é estável e o
    HP muda por baixo dele.
    """
    fila = list(alvos)
    passo = [0]

    def atual():
        i = min(passo[0], len(fila) - 1)
        return fila[i] if fila else None

    def ler():
        alvo = atual()
        passo[0] += 1
        return alvo

    e = _executor(_Roda([fila[0]] if fila else []), tecla=tecla)
    e._alvo_atual = ler
    e._id_do_alvo = lambda: (atual() or {}).get("id", 0)
    e._fonte = lambda: [SimpleNamespace(key="1", delay_ms=0)] * passos
    e._pausado = None
    e._pet_ativo = None
    e._tecla_do_pet = ""
    e._tecla_do_pet_food = ""
    e._travar_posicao = False
    e.teclas_enviadas = 0
    e._ultimo_alvo_dito = object()
    return e


def test_a_volta_COMPLETA_conta():
    e = _volta([_mob(0x111, hp=90)] * 30)

    assert e.uma_volta() is True
    assert e.voltas == 1
    assert e.voltas_abortadas == 0
    assert e.teclas_enviadas == 3


def test_a_volta_CORTADA_pela_morte_NAO_conta():
    """Vivo na largada, morre no meio da rotação -- que é o caso real."""
    e = _volta([_mob(0x111, hp=90)] * 2 + [_mob(0x111, hp=0)] * 30)

    assert e.uma_volta() is True
    assert e.voltas == 0, "corte por morte contou como volta de macro"
    assert e.voltas_abortadas == 1
    assert e.mortes_vistas == 1


def test_a_volta_ABANDONADA_pelo_inalcancavel_NAO_conta():
    """É o caso que o usuário nomeou: *"os mobs que não conseguir atacar como
    os do penhasco"*."""
    e = _volta([_mob(0x111, hp=100)] * 30, passos=6)

    assert e.uma_volta() is True
    assert e.voltas == 0, "o mob do penhasco contou como volta de macro"
    assert e.voltas_abortadas == 1
    assert e.alvos_inalcancaveis == 1
    assert e._inalcancavel_id == 0x111


def test_a_regua_NAO_adquire_alvo_de_dentro_do_laco_das_linhas():
    """EXISTE UM SÓ LUGAR QUE ADQUIRE ALVO, e é o passo 4 da volta.

    A régua chamava `_garantir_alvo(forcar=True)` de dentro do laço das linhas:
    o alvo novo era adquirido no meio da volta e só então a volta seguinte
    gastava pet, comida e até 2 s de caminhada antes da linha 1 -- com o mob
    recém-chamado batendo de graça o tempo todo.
    """
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(mod.ExecutorDeMacro.uma_volta))
    chamadas = [n for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "_garantir_alvo"]

    assert len(chamadas) == 1, "a volta adquire alvo em mais de um lugar"
    # `urgente=` é permitido (só pula os respiros); `forcar=` não é -- era ele
    # que largava o alvo e adquiria outro de dentro do laço das linhas.
    passados = {k.arg for k in chamadas[0].keywords}
    assert "forcar" not in passados, "ainda existe um `forcar=True` na volta"
    assert passados <= {"urgente"}, passados


# ===========================================================================
# O SHUFFLE ANTI-AFK NÃO SAI ANDANDO COM MOB EM CIMA
# ===========================================================================
#
# Ele saía a cada `shuffle_apos_n_voltas` voltas paradas, sem perguntar o que
# estava acontecendo. Bate com o relato do usuário em 26/08/2026 -- *"começou a
# ficar andando e dando tab, chamou vários mobs e morreu"*.

def _shuffle(em_batalha=None, alvo=None):
    e = _executor(em_batalha=em_batalha)
    e._base_pos = (10, 10)
    e._minimap_center = (100, 100)
    e._alvo_atual = lambda: alvo
    e._id_do_alvo = lambda: (alvo or {}).get("id", 0)
    e.voltas = 30
    e.input.right_click = lambda *a, **k: e.teclas.append("CLIQUE")
    return e


def test_o_shuffle_NAO_sai_em_combate():
    e = _shuffle(em_batalha=lambda: True)

    assert e._fazer_shuffle_anti_afk() is False
    assert e.teclas == [], "saiu andando com o personagem em combate"


def test_o_shuffle_NAO_sai_com_alvo_VIVO():
    e = _shuffle(em_batalha=lambda: False, alvo=_mob(0x111, hp=50))

    assert e._fazer_shuffle_anti_afk() is False
    assert e.teclas == []


def test_o_shuffle_SAI_quando_esta_tudo_parado():
    e = _shuffle(em_batalha=lambda: False)
    e._esperar = lambda ms: True

    assert e._fazer_shuffle_anti_afk() is True
    assert e.teclas == ["CLIQUE", "CLIQUE"]


def test_o_shuffle_deixou_de_ser_espera_CEGA():
    """Eram dois `time.sleep(1.0)` que não olhavam o botão de parar e não
    conferiam nada -- 2 s em que o bot ficava mudo."""
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(
        inspect.getsource(mod.ExecutorDeMacro._fazer_shuffle_anti_afk))
    chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}

    assert "sleep" not in chamadas, "voltou a espera cega no shuffle"
    assert "_esperar" in chamadas


# ===========================================================================
# O LOG DO ALVO NÃO REPETE A MESMA LINHA POR CAUSA DO FLICKER
# ===========================================================================

def test_a_leitura_ilegivel_NAO_reabre_a_linha_do_alvo():
    """No log de 25/08/2026 a entidade do cadáver sumia e voltava do array, a
    chave alternava `(id, hp) -> None -> (id, hp)`, e a MESMA linha saía a cada
    volta: 1251 linhas idênticas de "Rose Snake 0/100" contra 5 de alvo novo.

    O log ficou ilegível justamente na sessão em que era mais preciso lê-lo.
    """
    sumido = [False]
    e = _executor(_Roda([_mob(0x111, hp=40)]))
    e._alvo_atual = lambda: None if sumido[0] else _mob(0x111, hp=40)
    e._ultimo_alvo_dito = object()

    e._registrar_o_alvo()
    for _ in range(5):
        sumido[0] = True
        e._registrar_o_alvo()
        sumido[0] = False
        e._registrar_o_alvo()

    linhas = [t for _n, t in e.linhas if t.startswith("APP alvo:")]
    assert len(linhas) == 1, f"a mesma linha repetiu {len(linhas)} vezes"


# ===========================================================================
# EM BATALHA NÃO SE ANDA — 26/08/2026
# ===========================================================================
#
# *"É bom ter essas delays e deixar os 2 segundos de retorno para o lugar, A
# MENOS QUE ESTEJA EM BATALHA é claro (...) é bom ter mais cuidado para não sair
# puxando os outros mobs e fazer ele morrer."*
#
# Os 2 s de `SEGUNDOS_PARA_A_TRAVA_DEVOLVER` FICAM. O pedido não é andar menos,
# é não andar NA HORA ERRADA: atravessar o ponto de farm com um mob em cima faz
# ele acompanhar e passar por outros.

def _com_trava(em_batalha=None, alvo=None, longe=True):
    e = _executor(em_batalha=em_batalha)
    e._travar_posicao = True
    e._base_pos = (10, 10)
    e._minimap_center = (100, 100)
    e._posicao_atual = lambda: (40, 40) if longe else (10, 10)
    e._ultima_posicao_conhecida = None
    e._voltas_sem_movimento = 0
    e._shuffle_apos_n_voltas = 30
    e._alvo_atual = lambda: alvo
    e._id_do_alvo = lambda: (alvo or {}).get("id", 0)
    e.input.right_click = lambda *a, **k: e.teclas.append("CLIQUE")
    return e


def test_os_2_SEGUNDOS_do_retorno_continuam_de_pe():
    """O pedido foi MANTER o retorno, não encurtá-lo."""
    assert mod.SEGUNDOS_PARA_A_TRAVA_DEVOLVER == 2.0


def test_EM_BATALHA_o_personagem_NAO_volta_andando():
    e = _com_trava(em_batalha=lambda: True)

    assert e._travar_posicao_se_preciso() is False
    assert e.teclas == [], "saiu andando com o personagem em combate"


def test_COM_ALVO_VIVO_o_personagem_NAO_volta_andando():
    """A flag demora a subir no primeiro golpe; o alvo com vida cobre esse
    buraco. Basta UMA das duas fontes dizer que há luta."""
    e = _com_trava(em_batalha=lambda: False, alvo=_mob(0x111, hp=50))

    assert e._travar_posicao_se_preciso() is False
    assert e.teclas == []


def test_FORA_de_batalha_ele_volta_normalmente():
    """A trava de posição continua sendo o que impede a deriva pelo mapa."""
    e = _com_trava(em_batalha=lambda: False)
    e._esperar_chegar_na_base = lambda teto: True

    assert e._travar_posicao_se_preciso() is True
    assert e.teclas == ["CLIQUE"]
    assert any("mandando voltar andando" in t for _n, t in e.linhas), e.linhas


def test_SEM_leitura_de_batalha_ele_volta_como_antes():
    """"Não sei" NÃO suprime a caminhada: um cliente sem leitura de memória
    nunca voltaria ao ponto e derivaria pelo mapa — pior que voltar na hora
    errada."""
    e = _com_trava(em_batalha=None)
    e._esperar_chegar_na_base = lambda teto: True

    assert e._travar_posicao_se_preciso() is True
    assert e.teclas == ["CLIQUE"]


def test_o_interruptor_de_andar_so_fora_de_batalha_esta_LIGADO():
    assert mod.ANDAR_SO_FORA_DE_BATALHA is True


def test_DESLIGADO_a_caminhada_volta_a_ignorar_a_batalha(monkeypatch):
    monkeypatch.setattr(mod, "ANDAR_SO_FORA_DE_BATALHA", False)
    e = _com_trava(em_batalha=lambda: True)
    e._esperar_chegar_na_base = lambda teto: True

    assert e._travar_posicao_se_preciso() is True
    assert e.teclas == ["CLIQUE"]


def test_a_MESMA_guarda_serve_a_caminhada_e_ao_shuffle():
    """Duas ações que tiram o personagem do lugar, uma pergunta só. Se cada uma
    tivesse a própria régua, uma delas ficaria para trás no conserto seguinte."""
    import ast
    import inspect
    import textwrap

    for metodo in (mod.ExecutorDeMacro._travar_posicao_se_preciso,
                   mod.ExecutorDeMacro._fazer_shuffle_anti_afk):
        fonte = textwrap.dedent(inspect.getsource(metodo))
        chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)}
        assert "_lutando" in chamadas, f"{metodo.__name__} não pergunta"


# ===========================================================================
# RESPIRO DEPOIS DA MORTE — a flag de combate precisa de um instante
# ===========================================================================

def test_a_volta_cortada_pela_MORTE_abre_a_OBSERVACAO(monkeypatch):
    """*"Zerou a vida, analisa por 3 segundos: se não saiu, pode dar tab e
    recomeçar a macro, pois tem alguém batendo."*"""
    monkeypatch.setattr(mod, "SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE",
                        OBSERVACAO_DA_MORTE)
    _relogio_falso(monkeypatch)
    vistos = []

    e = _executor(em_batalha=lambda: (vistos.append(1), True)[1])
    e._estava_em_batalha = True
    e._abortar_a_volta(morreu=True)

    assert e._urgencia is True, "não percebeu o segundo mob"
    assert len(vistos) > 5, "observou uma vez só em vez de perguntar"

    e2 = _executor(em_batalha=lambda: False)
    e2._abortar_a_volta(morreu=True)
    assert e2._urgencia is False, "inventou urgência numa morte limpa"


def test_a_morte_NAO_conta_como_volta():
    e = _executor()
    e.voltas = 0
    e.voltas_abortadas = 0

    e._abortar_a_volta(morreu=True)

    assert e.voltas == 0
    assert e.voltas_abortadas == 1


# ===========================================================================
# A RODA DO TAB DEIXOU DE SER VARRIDA EM RAJADA
# ===========================================================================

def test_a_roda_de_cadaveres_e_ESPACADA(monkeypatch):
    """`_esperar_o_alvo_trocar` devolve NO INSTANTE em que o id muda, então a
    roda inteira era varrida em menos de meio segundo."""
    dormidas: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", dormidas.append)
    monkeypatch.setattr(mod, "ESPERA_ENTRE_TABS", ESPACO_ENTRE_TABS)
    # O ESPAÇAMENTO É O INTERRUPTOR: com um salto só ele não é alcançado, e o
    # caminho de dois saltos continua inteiro para quem subir a constante.
    monkeypatch.setattr(mod, "TENTATIVAS_DE_TAB", 2)

    roda = _Roda([_mob(0x111, hp=0), _mob(0x222, hp=0), _mob(0x999)])
    e = _executor(roda)
    e._garantir_alvo()

    assert e.tabs_dados == 2
    assert sum(dormidas) == pytest.approx(ESPACO_ENTRE_TABS), (
        "os saltos da roda saíram em rajada")


def test_o_espacamento_entre_TABs_cabe_dentro_do_reinicio_da_roda():
    """O INVARIANTE QUE IMPORTA, e ele não é sobre ser "pequeno".

    Com `TENTATIVAS_DE_TAB = 1` esta constante fica INERTE — só volta a ser
    alcançada por quem subir o teto de saltos (ela é o interruptor do caminho de
    vários saltos). Comparar com o respiro de entrada era arbitrário: são
    propósitos diferentes e nada obriga um a ser menor que o outro.

    O que NÃO pode acontecer é o espaçamento passar do tempo de reinício da roda
    do jogo: nesse caso o segundo salto voltaria ao PRIMEIRO mob em vez de
    avançar, e a aquisição depois de uma morte pararia no próprio cadáver.
    """
    assert ESPACO_ENTRE_TABS > 0
    assert ESPACO_ENTRE_TABS < PAUSA_DA_RODA


def test_UM_TAB_so_nao_paga_espacamento_nenhum(monkeypatch):
    """O caminho feliz — cadáver na mira, mob vivo no salto seguinte — não
    ganhou custo nenhum."""
    dormidas: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", dormidas.append)
    monkeypatch.setattr(mod, "ESPERA_ENTRE_TABS", ESPACO_ENTRE_TABS)

    e = _executor(_Roda([_mob(0x111, hp=0), _mob(0x222)]))
    e._garantir_alvo()

    assert e.tabs_dados == 1
    assert sum(dormidas) == 0


# ===========================================================================
# DUAS PERGUNTAS QUE ESTAVAM GRUDADAS — 26/08/2026
# ===========================================================================
#
# *"Vamos usar a flag se está em batalha para, na hora que sair de batalha,
# poder PARAR A MACRO NO MEIO e seguir com o resto. A vida ir a zero nós usamos
# para ANALISAR O MOB e saber se já matamos ele (...) então zerou a vida,
# analisa por 3 segundos: se não saiu, pode dar tab e recomeçar a macro, POIS
# TEM ALGUÉM BATENDO."*
#
#   "aquele mob morreu?"  -> responde o HP DELE
#   "a luta acabou?"      -> responde a FLAG DE COMBATE

def test_SAIR_de_batalha_corta_a_macro_no_meio():
    """A segunda fonte de "o mob caiu", e ela vale onde a primeira falha: com o
    HP do alvo ILEGÍVEL, a flag continua respondendo."""
    estados = iter([True, False])
    e = _executor(_Roda([_mob(0x111, hp=50)]), em_batalha=lambda: next(estados))
    e._alvo_atual = lambda: None          # HP ilegível
    e._ler_em_batalha()                   # a luta começou

    assert e._cortar_a_volta() is True
    assert e.mortes_vistas == 1


def test_o_que_corta_e_a_TRANSICAO_e_nunca_o_NIVEL():
    """O bot passa a maior parte do tempo fora de combate, entre um mob e o
    outro. Fora de batalha o tempo todo não é morte de ninguém."""
    e = _executor(_Roda([_mob(0x111, hp=50)]), em_batalha=lambda: False)

    for _ in range(5):
        assert e._cortar_a_volta() is False


def test_a_saida_de_batalha_ANOTA_o_veredito_na_reserva():
    """A transição acontece UMA vez e é consumida no corte. Sem anotar,
    `_garantir_alvo` ouviria "não sei" e o portão "alvo vivo, não mexe"
    bloquearia o TAB no próprio cadáver."""
    estados = iter([True, False, False, False])
    roda = _Roda([_mob(0x111, hp=50), _mob(0x222, hp=80)])
    e = _executor(roda, em_batalha=lambda: next(estados))
    e._alvo_atual = lambda: (None if (roda.atual or {}).get("id") == 0x111
                             else roda.atual)
    e._ler_em_batalha()

    assert e._cortar_a_volta() is True
    assert e._morto_pela_reserva == 0x111

    assert e._garantir_alvo() is True
    assert e.teclas == ["TAB"], "ficou preso no cadáver depois do corte"


def test_matar_E_SAIR_de_batalha_e_o_ciclo_CALMO(monkeypatch):
    monkeypatch.setattr(mod, "SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE",
                        OBSERVACAO_DA_MORTE)
    e = _executor(em_batalha=lambda: False)
    e._estava_em_batalha = True

    assert e._observar_depois_da_morte() is False
    assert e._urgencia is False
    assert e.urgencias == 0


def test_matar_e_CONTINUAR_em_batalha_e_URGENCIA(monkeypatch):
    monkeypatch.setattr(mod, "SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE",
                        OBSERVACAO_DA_MORTE)
    _relogio_falso(monkeypatch)
    e = _executor(em_batalha=lambda: True)
    e._estava_em_batalha = True

    assert e._observar_depois_da_morte() is True
    assert e._urgencia is True
    assert e.urgencias == 1
    assert any("OUTRO mob batendo" in t for _n, t in e.linhas), e.linhas


def test_a_VIDA_CAINDO_encerra_a_observacao_ANTES_do_teto(monkeypatch):
    """*"Dá para conferir pela vida atual do personagem, que vai estar descendo
    também."* É prova POSITIVA de dano entrando — a flag só sabe dizer "ainda
    em batalha"."""
    monkeypatch.setattr(mod, "SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE", 30.0)
    _relogio_falso(monkeypatch)
    vidas = iter([80.0, 80.0, 71.0])

    e = _executor(em_batalha=lambda: True)
    e._estava_em_batalha = True
    e._vida_pct = lambda: next(vidas)

    assert e._observar_depois_da_morte() is True
    assert any("minha vida caiu" in t for _n, t in e.linhas), e.linhas


def test_SEM_leitura_de_batalha_a_morte_NAO_vira_urgencia(monkeypatch):
    """Inventar urgência aqui faria o bot pular pet, comida e caminhada em TODA
    morte, num cliente que nunca soube se estava em batalha."""
    monkeypatch.setattr(mod, "SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE",
                        OBSERVACAO_DA_MORTE)
    _relogio_falso(monkeypatch)
    e = _executor(em_batalha=None)
    e._estava_em_batalha = True

    assert e._observar_depois_da_morte() is False
    assert e._urgencia is False


def test_o_teto_da_observacao_e_AVISO_e_nao_gasto(monkeypatch):
    """A morte limpa — que é a maioria — sai no instante em que a flag baixa."""
    monkeypatch.setattr(mod, "SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE", 30.0)
    dormidas = _relogio_falso(monkeypatch)

    e = _executor(em_batalha=lambda: False)
    e._estava_em_batalha = True
    e._observar_depois_da_morte()

    assert sum(dormidas) == 0, "pagou o teto numa morte limpa"


# ===========================================================================
# A VOLTA URGENTE PULA O CICLO CALMO
# ===========================================================================

def _com_conferencias(alvos, em_batalha=None):
    e = _volta(alvos)
    e._em_batalha = em_batalha
    e.feitos: list[str] = []
    e.garantir_pet = lambda: e.feitos.append("pet")
    e.feed_pet = lambda force=False: e.feitos.append("comida")
    e._travar_posicao_se_preciso = lambda: e.feitos.append("andar")
    return e


def test_FORA_de_batalha_a_volta_faz_as_conferencias_na_ORDEM():
    """*"Saiu de batalha → pet → comida → voltar ao ponto → TAB → e por assim
    vai."*"""
    e = _com_conferencias([_mob(0x111, hp=0)] + [_mob(0x222, hp=90)] * 30,
                          em_batalha=lambda: False)

    e.uma_volta()

    assert e.feitos == ["pet", "comida", "andar"], e.feitos


def test_EM_BATALHA_a_volta_NAO_confere_nada():
    """REGRA GERAL, e não só na urgência. A tecla de comida é IGNORADA pelo
    jogo em combate, mas o `PetFeeder` registrava a refeição assim mesmo — o
    pet passava fome com o cronômetro dizendo que tinha comido."""
    e = _com_conferencias([_mob(0x111, hp=90)] * 30, em_batalha=lambda: True)

    e.uma_volta()

    assert e.feitos == [], f"conferiu no meio da luta: {e.feitos}"


def test_ALVO_VIVO_ja_e_batalha_para_as_conferencias():
    """A flag demora a subir no primeiro golpe; o alvo com vida cobre isso."""
    e = _com_conferencias([_mob(0x111, hp=90)] * 30, em_batalha=lambda: False)

    e.uma_volta()

    assert e.feitos == []


def test_a_volta_URGENTE_nao_gasta_pet_comida_nem_caminhada():
    """*"Pode dar tab e recomeçar a macro, pois tem alguém batendo."*

    Pet, comida e caminhada são cuidados de quem está tranquilo. Com um mob em
    cima eles são segundos de dano de graça — e a caminhada ainda arrastaria o
    mob pelo ponto de farm.
    """
    e = _com_conferencias([_mob(0x111, hp=0)] + [_mob(0x222, hp=90)] * 30,
                          em_batalha=lambda: False)
    e._urgencia = True

    e.uma_volta()

    assert e.feitos == [], f"gastou o ciclo calmo com um mob batendo: {e.feitos}"


def test_a_urgencia_vale_UMA_volta_so():
    """Nada é perdido: a volta seguinte, já sem urgência, faz tudo."""
    e = _volta([_mob(0x111, hp=90)] * 30)
    e._urgencia = True

    e.uma_volta()
    assert e._urgencia is False


def test_a_volta_URGENTE_nao_paga_o_respiro_de_entrada_do_TAB(monkeypatch):
    """O respiro existe para o TAB não chegar em cima das teclas da macro. Na
    urgência a macro foi CORTADA e a observação já gastou até 3 s — as teclas
    assentaram, e o que sobra é um mob batendo."""
    dormidas: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", dormidas.append)
    monkeypatch.setattr(mod, "ESPERA_ANTES_DO_TAB", RESPIRO_ANTES)
    monkeypatch.setattr(mod, "ESPERA_DEPOIS_DO_TAB", RESPIRO_DEPOIS)

    e = _executor(_Roda([_mob(0x111, hp=0), _mob(0x222)]))
    e._garantir_alvo(urgente=True)

    assert sum(dormidas) == pytest.approx(RESPIRO_DEPOIS), (
        f"pagou o respiro de entrada com um mob batendo: {sum(dormidas)}")


# ===========================================================================
# A LINHA 0 DA MACRO — o tempo depois do TAB virou configuração
# ===========================================================================
#
# *"Como a macro 0, mas sem poder editar o botão e não pode colocar em outro
# lugar, sempre será a primeira, e o tempo sim será editável; aquele 1 segundo
# após o tab será isso."*

def test_o_respiro_depois_do_TAB_vem_da_CONFIGURACAO(monkeypatch):
    dormidas: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", dormidas.append)
    monkeypatch.setattr(mod, "ESPERA_ANTES_DO_TAB", 0.0)

    e = _executor(_Roda([_mob(0x111, hp=0), _mob(0x222)]))
    e._espera_depois_do_tab_ms = lambda: 2500
    e._garantir_alvo()

    assert sum(dormidas) == pytest.approx(2.5)


def test_o_valor_da_tela_vale_na_VOLTA_SEGUINTE_sem_religar(monkeypatch):
    """Chega como FUNÇÃO pelo mesmo motivo que `fonte_dos_passos` chega."""
    dormidas: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", dormidas.append)
    monkeypatch.setattr(mod, "ESPERA_ANTES_DO_TAB", 0.0)
    valor = [1000]

    e = _executor(_Roda([_mob(0x111, hp=0), _mob(0x333)]))
    e._espera_depois_do_tab_ms = lambda: valor[0]
    e._garantir_alvo()
    assert sum(dormidas) == pytest.approx(1.0)

    valor[0] = 300
    dormidas.clear()
    e2 = _executor(_Roda([_mob(0x444, hp=0), _mob(0x555)]))
    e2._espera_depois_do_tab_ms = lambda: valor[0]
    e2._garantir_alvo()
    assert sum(dormidas) == pytest.approx(0.3)


def test_o_PISO_de_100ms_vale_tambem_para_a_linha_0(monkeypatch):
    dormidas: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", dormidas.append)
    monkeypatch.setattr(mod, "ESPERA_ANTES_DO_TAB", 0.0)

    e = _executor(_Roda([_mob(0x111, hp=0), _mob(0x222)]))
    e._espera_depois_do_tab_ms = lambda: 0
    e._garantir_alvo()

    assert sum(dormidas) == pytest.approx(mod.MINIMO_DE_ESPERA_DO_APP_MS / 1000)


def test_o_piso_do_executor_e_o_MESMO_da_config():
    """A duplicata é deliberada — o executor do APP não importa
    `blazesbot.config` (isolamento travado por teste). Este confere que os dois
    números batem, que é o único jeito de a cópia não apodrecer."""
    from blazesbot.config import MINIMO_DE_ESPERA_DO_APP_MS

    assert mod.MINIMO_DE_ESPERA_DO_APP_MS == MINIMO_DE_ESPERA_DO_APP_MS


def test_SEM_configuracao_o_executor_usa_a_CONSTANTE(monkeypatch):
    """`ESPERA_DEPOIS_DO_TAB` deixou de ser o valor e virou o PADRÃO de quem
    roda sem configuração."""
    dormidas: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", dormidas.append)
    monkeypatch.setattr(mod, "ESPERA_ANTES_DO_TAB", 0.0)
    monkeypatch.setattr(mod, "ESPERA_DEPOIS_DO_TAB", RESPIRO_DEPOIS)

    e = _executor(_Roda([_mob(0x111, hp=0), _mob(0x222)]))
    e._garantir_alvo()

    assert sum(dormidas) == pytest.approx(RESPIRO_DEPOIS)


def test_leitura_que_EXPLODE_cai_no_padrao(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(mod, "ESPERA_DEPOIS_DO_TAB", 0.42)

    e = _executor()

    def explode():
        raise RuntimeError("boom")

    e._espera_depois_do_tab_ms = explode
    assert e._respiro_depois_do_tab() == 0.42


# ===========================================================================
# URGÊNCIA E A PAUSA DA RODA
# ===========================================================================

def test_a_urgencia_NAO_paga_a_pausa_da_roda(monkeypatch):
    """A pausa existe para a roda voltar ao mob mais perto — otimização de
    MIRA. Com um mob batendo, tentar de novo já vale mais que tentar melhor."""
    dormidas = _relogio_falso(monkeypatch)
    monkeypatch.setattr(mod, "SEGUNDOS_PARA_A_RODA_REINICIAR", PAUSA_DA_RODA)
    monkeypatch.setattr(mod, "ESPERA_ENTRE_TABS", 0.0)
    monkeypatch.setattr(mod, "ESPERA_ANTES_DO_TAB", 0.0)

    e = _executor(_Roda([_mob(0x100 + i, hp=0) for i in range(5)]))
    e._garantir_alvo(urgente=True)

    assert sum(dormidas) == 0, f"ficou parado apanhando: {sum(dormidas)}s"


def test_a_urgencia_NAO_afrouxa_o_teto_de_saltos():
    """*"A ideia não é ter 2 alvos, é ter sempre 1 por vez."* A urgência mexe
    na ESPERA entre tentativas, nunca em quantos mobs o bot chama."""
    e = _executor(_Roda([_mob(0x100 + i, hp=0) for i in range(5)]))
    e._garantir_alvo(urgente=True)

    assert e.tabs_dados == mod.TENTATIVAS_DE_TAB == 1


# ===========================================================================
# QUEM JÁ ESTÁ NO PONTO NÃO RECEBE ORDEM DE ANDAR — 26/08/2026
# ===========================================================================
#
# *"O primeiro uso da poção está gerando algum problema; ele clica na poção,
# CONSOME ela, mas CANCELA logo em seguida."*
#
# Um clique direito no minimapa é uma ORDEM DE ANDAR, e uma ordem pendente
# cancela a bebida no instante seguinte.

def _na_base(distancia):
    e = _executor()
    e._base_pos = (10, 10)
    e._minimap_center = (100, 100)
    e._posicao_atual = lambda: (10, 10)
    e._ultima_posicao_conhecida = (10, 10)
    e.distancia_da_base = lambda: distancia
    e.input.right_click = lambda *a, **k: e.teclas.append("CLIQUE")
    return e


def test_parado_na_base_NAO_manda_andar():
    e = _na_base(0.0)

    assert e.mandar_voltar_para_base() is True, (
        '"já estou lá" é sucesso, não falha')
    assert e.teclas == [], "mandou andar quem já estava no ponto"


def test_dentro_da_tolerancia_tambem_NAO_manda_andar():
    e = _na_base(float(mod.TOLERANCIA_POSICAO))
    e.mandar_voltar_para_base()
    assert e.teclas == []


def test_LONGE_da_base_manda_andar_normalmente():
    e = _na_base(9.0)
    assert e.mandar_voltar_para_base() is True
    assert e.teclas == ["CLIQUE"]


def test_SEM_leitura_de_posicao_manda_andar():
    """"Não sei" clica: sem provar que ele está no ponto, curar longe da base é
    pior que um passo a mais."""
    e = _na_base(None)
    assert e.mandar_voltar_para_base() is True
    assert e.teclas == ["CLIQUE"]


# ===========================================================================
# O ATRASO ENTRE O TAB E A LINHA 1
# ===========================================================================

def test_a_confirmacao_do_TAB_tem_cadencia_PROPRIA_e_fina():
    """*"Às vezes está existindo alguma delay entre o clicar o TAB e começar a
    macro, e NÃO é a configuração nova."*

    A confirmação reusava `PASSO_DA_ESPERA_DA_BASE` (0,1 s), que é a cadência
    de "já cheguei na base?" — pensada para CAMINHADA. Custava até 100 ms
    mortos por aquisição.
    """
    assert mod.PASSO_DA_CONFIRMACAO_DO_TAB == 0.01
    # A fixture zera `PASSO_DA_ESPERA_DA_BASE`; o valor de verdade foi
    # capturado no import.
    assert mod.PASSO_DA_CONFIRMACAO_DO_TAB < PASSO_DA_BASE

    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(
        inspect.getsource(mod.ExecutorDeMacro._esperar_o_alvo_trocar))
    nomes = {n.id for n in ast.walk(ast.parse(fonte)) if isinstance(n, ast.Name)}
    assert "PASSO_DA_CONFIRMACAO_DO_TAB" in nomes
    assert "PASSO_DA_ESPERA_DA_BASE" not in nomes


def test_o_RESPIRO_e_a_ULTIMA_coisa_antes_da_macro():
    """*"Nós desenhamos a ordem para o TAB ser o ÚLTIMO e logo em seguida rodar
    a macro."*

    A régua e o log ficavam DEPOIS do respiro — entre o fim da espera e a
    primeira tecla. O log escreve em disco.
    """
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(
        inspect.getsource(mod.ExecutorDeMacro._garantir_alvo))
    arvore = ast.parse(fonte)

    def linhas_de(nome):
        return [n.lineno for n in ast.walk(arvore)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == nome]

    respiro = max(linhas_de("_respiro_depois_do_tab"))
    assert max(linhas_de("_comecar_a_regua")) < respiro, (
        "a régua ficou entre a espera e a primeira tecla")

    # A linha "alvo novo ..." é a que saía depois do respiro. Procurada pelo
    # TEXTO, e não por "o último `log.info`": há outros avisos mais abaixo no
    # método, e eles não estão no caminho da macro.
    avisos = [n.lineno for n in ast.walk(arvore)
              if isinstance(n, ast.Call) and n.args
              and isinstance(n.args[0], ast.Constant)
              and isinstance(n.args[0].value, str)
              and "alvo novo" in n.args[0].value]
    assert avisos and max(avisos) < respiro, (
        "o log ficou entre a espera e a primeira tecla")


def test_a_regua_usa_o_alvo_JA_LIDO_e_nao_le_de_novo():
    """Duas fotos de instantes diferentes respondendo à mesma pergunta é como
    nascem as decisões que ninguém consegue reproduzir."""
    leituras = [0]
    e = _executor()

    def contando():
        leituras[0] += 1
        return _mob(0x111, hp=80)

    e._alvo_atual = contando
    e._comecar_a_regua(0x111, _mob(0x111, hp=80))

    assert leituras[0] == 0, "releu o alvo tendo a leitura na mão"
    assert e._hp_de_referencia == 0.8


def test_a_linha_do_alvo_NAO_sai_duas_vezes_na_aquisicao():
    """`_registrar_o_alvo` roda logo depois e diria a MESMA coisa — uma leitura
    e uma escrita em disco a mais no trecho mais sensível do laço."""
    e = _executor(_Roda([_mob(0x111, hp=0), _mob(0x222, hp=70)]))
    e._ultimo_alvo_dito = object()

    e._garantir_alvo()
    e._registrar_o_alvo()

    linhas = [t for _n, t in e.linhas if t.startswith("APP alvo:")]
    assert linhas == [], f"repetiu a linha do alvo: {linhas}"
    assert any("alvo novo" in t for _n, t in e.linhas)


def test_a_janela_de_observacao_e_de_TRES_segundos():
    """*"Após notar a morte do mob ficando com 0 de HP, dá 2 segundos para sair
    de batalha."*"""
    assert OBSERVACAO_DA_MORTE == 3.0


# ===========================================================================
# A SEGUNDA PORTA: A VIDA PELA TELA — 26/08/2026
# ===========================================================================
#
# *"Mantém como primeira porta o HP pela memória; caso não ache, usa a vida
# pela tela — no `target_hybrid` tem uma função para isso também. Caso for pela
# tela, sempre deixa rodar mais 3 linhas depois de confirmar a morte, só para
# garantir por causa do falso positivo da morte."*
#
# Medição que abriu esta porta: três mobs VIVOS, `Rose Snake nv61 100/100`,
# existiam na memória e não eram alcançáveis pela janela varrida.

def _com_tela(vida_na_tela, alvo=None, linha=9):
    e = _executor(_Roda([_mob(0x111, hp=50)]))
    e._alvo_atual = lambda: alvo
    e._vida_do_alvo_pela_tela = lambda: vida_na_tela
    e._linha_da_rotacao = linha
    return e


def test_a_MEMORIA_e_a_primeira_porta_e_a_tela_nem_e_olhada():
    olhadas = [0]
    e = _com_tela(0.0, alvo=_mob(0x111, hp=50))

    def contando():
        olhadas[0] += 1
        return 0.0

    e._vida_do_alvo_pela_tela = contando
    vida, fonte, _ = e._vida_do_alvo()

    assert (vida, fonte) == (0.5, "memoria")
    assert olhadas[0] == 0, "pagou uma captura com a memória respondendo"


def test_SEM_a_memoria_a_TELA_responde():
    vida, fonte, _ = _com_tela(0.42)._vida_do_alvo()
    assert (vida, fonte) == (0.42, "tela")


def test_SEM_as_duas_continua_NAO_SEI():
    vida, fonte, _ = _com_tela(None)._vida_do_alvo()
    assert (vida, fonte) == (None, "nada")


def test_a_tela_NAO_e_olhada_antes_da_TERCEIRA_linha():
    """*"Só vai começar a ler a partir da segunda linha, no caso antes de
    começar a terceira linha."*

    Logo depois do TAB a entidade pode simplesmente ainda não ter entrado no
    array — pagar uma captura para descobrir isso seria caro.
    """
    for linha in (1, 2):
        assert _com_tela(0.5, linha=linha)._olhar_a_tela() is None, linha
    assert _com_tela(0.5, linha=3)._olhar_a_tela() == 0.5


def test_a_tela_NAO_e_olhada_DUAS_VEZES_na_mesma_linha():
    e = _com_tela(0.5)
    assert e._olhar_a_tela() == 0.5
    assert e._olhar_a_tela() is None, "capturou duas vezes na mesma linha"


def test_entre_capturas_ha_no_MINIMO_meio_segundo(monkeypatch):
    """*"A cada 500ms ou a cada linha, o que for MAIOR."* As duas condições
    valem juntas: numa macro de linhas longas manda a linha, numa de linhas
    curtas manda o meio segundo."""
    agora = [1000.0]
    monkeypatch.setattr(mod.time, "time", lambda: agora[0])

    e = _com_tela(0.5, linha=3)
    assert e._olhar_a_tela() == 0.5

    e._linha_da_rotacao = 4                     # linha nova, mas cedo demais
    agora[0] += mod.INTERVALO_MINIMO_DA_TELA / 2
    assert e._olhar_a_tela() is None

    agora[0] += mod.INTERVALO_MINIMO_DA_TELA
    assert e._olhar_a_tela() == 0.5


def test_o_intervalo_da_tela_e_MUITO_maior_que_a_conferencia_do_alvo():
    """A conferência roda a cada 0,1 s dentro da espera de cada linha. Se a
    tela entrasse ali seriam 10 capturas por segundo POR CONTA."""
    assert mod.INTERVALO_MINIMO_DA_TELA >= 5 * mod.PASSO_DA_CONFERENCIA_DO_ALVO


def test_o_limiar_de_morte_na_tela_e_o_MESMO_do_core():
    """A cópia é deliberada (o executor não importa o `target_hybrid` inteiro),
    e este teste é o único jeito de ela não apodrecer."""
    from blazesbot.core.target_hybrid import LIMIAR_VIDA_TELA

    assert mod.LIMIAR_DE_MORTE_NA_TELA == LIMIAR_VIDA_TELA


# -- o pedágio das 3 linhas ------------------------------------------------

def test_a_TELA_nao_declara_morte_na_hora_e_abre_o_PEDAGIO():
    """`SO_A_MEMORIA_DECLARA_MORTE` do BC vale lá; aqui a tela PODE declarar,
    e o pedágio é o preço."""
    e = _com_tela(0.0)

    assert e._alvo_morreu() is False, "a tela declarou morte na hora"
    assert e._linhas_cegas == mod.LINHAS_BATENDO_CEGO_DEPOIS_DA_TELA
    assert e.mortes_pela_tela == 1
    assert any("no escuro" in t for _n, t in e.linhas), e.linhas


def test_o_pedagio_e_aberto_UMA_VEZ_e_nao_reiniciado():
    e = _com_tela(0.0)
    e._alvo_morreu()
    e._linhas_cegas = 1
    e._alvo_morreu()

    assert e._linhas_cegas == 1, "o pedágio foi reiniciado e nunca acabaria"
    assert e.mortes_pela_tela == 1


def test_a_MEMORIA_voltando_com_vida_CANCELA_o_pedagio():
    """Um ponto de vida derruba toda suspeita — inclusive a da tela."""
    e = _com_tela(0.0)
    e._alvo_morreu()
    assert e._linhas_cegas > 0

    e._alvo_atual = lambda: _mob(0x111, hp=40)
    assert e._alvo_morreu() is False
    assert e._linhas_cegas == 0, "continuou pagando pedágio num mob vivo"


def test_as_TRES_linhas_sao_o_numero_do_usuario():
    assert mod.LINHAS_BATENDO_CEGO_DEPOIS_DA_TELA == 3


def test_a_espera_CEGA_nao_confere_o_alvo():
    """*"Continua batendo, SEM PERGUNTAR MAIS."* A irmã dela (`_esperar`)
    pergunta a cada 0,1 s; esta não pergunta nada."""
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(mod.ExecutorDeMacro._esperar_cego))
    chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}

    assert "_cortar_a_volta" not in chamadas
    assert "_dormir" in chamadas


def test_SAIR_de_batalha_corta_o_pedagio_no_meio():
    """*"Se saiu de batalha, é garantido que matou e não tem outro mob
    batendo."* As linhas que sobram não compram mais nada."""
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(mod.ExecutorDeMacro.uma_volta))
    arvore = ast.parse(fonte)
    dentro = [n for n in ast.walk(arvore)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == "_a_batalha_acabou"]

    assert dentro, "o pedágio não olha a saída de batalha"
    assert "self._linhas_cegas = 0" in fonte
