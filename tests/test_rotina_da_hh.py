"""A rotina da HH: a forma do ciclo, o reset e o portão do supervisor.

ESTE ARQUIVO NÃO EXERCITA MOTOR. Andar, lutar, vender e operar janela são
testados nos arquivos dos motores (`bot/navegacao.py`, `bot/combate.py`,
`bot/vendedor.py`, `bot/ui_do_jogo.py`), e agora protegem as duas caves de uma
vez. Aqui se trava o que é DA HH:

  * a ORDEM do ciclo -- preparação antes de alvo, cap antes de entrar;
  * os quatro bosses como LAÇO sobre os dados, não como estados escritos à mão;
  * o RESET, que é regra do jogo: sem desfazer e refazer o time os bosses não
    renascem, e o modo muda ONDE isso acontece;
  * o portão do supervisor, para HH e BC nunca disputarem o teclado.
"""
import ast
import inspect
import textwrap

import pytest

from blazesbot.bot.hh import mapa_hh
from blazesbot.bot.hh.routine import (
    ESTADOS_DENTRO_DA_CAVE,
    HHRoutine,
    State,
)


def _fonte(metodo) -> str:
    return textwrap.dedent(inspect.getsource(metodo))


def _chamadas(metodo) -> list[str]:
    """Os nomes chamados no corpo, NA ORDEM EM QUE APARECEM NO CÓDIGO.

    Ordenado por (linha, coluna) e não pela ordem de `ast.walk`: ela é
    largura-primeiro e devolve os nós fora da ordem do texto. Escrito assim a
    primeira vez, este helper afirmou que `apply_buffs` vinha antes de
    `ensure_pet` -- e vinha, na árvore, não no arquivo.
    """
    chamadas = [(n.lineno, n.col_offset,
                 getattr(n.func, "attr", getattr(n.func, "id", "")))
                for n in ast.walk(ast.parse(_fonte(metodo)))
                if isinstance(n, ast.Call)]
    return [nome for _linha, _col, nome in sorted(chamadas)]


# ===========================================================================
# A máquina de estados
# ===========================================================================


@pytest.mark.parametrize("estado", list(State), ids=lambda s: s.name)
def test_todo_estado_tem_handler(estado):
    """Um estado sem handler derruba a rotina com AttributeError na PRIMEIRA
    vez que ela cai nele -- e isso pode ser depois de horas rodando."""
    assert hasattr(HHRoutine, f"_do_{estado.name.lower()}")


def test_comeca_SITUANDO_e_nunca_PREPARANDO():
    """Uma conta que já está no meio da cave continua de onde estava.

    Começar preparando faria o bot tentar entrar estando dentro -- e aí o clique
    cai no chão e tira o personagem da rota. É o mesmo motivo da BC.
    """
    fonte = _fonte(HHRoutine.run)
    assert "State.SITUAR" in fonte
    assert "State.PREPARAR" not in fonte


def test_o_laco_respeita_o_should_continue_ANTES_de_agir():
    """Desligar a HH pela interface tem que devolver o controle num ponto
    seguro, entre estados, e não no meio de uma ação."""
    fonte = _fonte(HHRoutine.run)
    i_check = fonte.index("should_continue")
    i_handler = fonte.index("handler()")
    assert i_check < i_handler


def test_a_flag_farming_cai_em_QUALQUER_saida():
    """Sem o `finally`, o laço "online" seguinte re-detonaria a parada e
    derrubaria a sessão -- o oposto do desejado."""
    arvore = ast.parse(_fonte(HHRoutine.run))
    finallys = [n for n in ast.walk(arvore)
                if isinstance(n, ast.Try) and n.finalbody]
    assert finallys, "`farming` não está protegido por finally"
    corpo = " ".join(ast.unparse(n) for f in finallys for n in f.finalbody)
    assert "farming = False" in corpo


def test_a_parada_e_a_queda_respondem_ENTRE_estados():
    """`_guard` é o que faz o botão Parar e o watchdog valerem sem esperar a
    fase inteira terminar."""
    chamadas = _chamadas(HHRoutine._guard)
    assert "raise_if_stopped" in chamadas
    assert "wait_if_paused" in chamadas
    assert "check_watchdog" in chamadas


def test_dentro_da_cave_a_cadencia_e_mais_curta():
    """Lá dentro os mobs vêm atrás, e folga de tempo é dano tomado."""
    from blazesbot.bot.hh import routine

    assert routine.PASSO_DENTRO_DA_CAVE < routine.PASSO_FORA_DA_CAVE
    assert ESTADOS_DENTRO_DA_CAVE == {
        State.PREPARAR_DENTRO, State.ATE_O_BOSS, State.BOSS, State.SAIR}


# ===========================================================================
# FORA DA CAVE NÃO SE PREPARA NADA QUE EXIJA ESTAR A PÉ
# ===========================================================================
#
# Regra do usuário, 03/09/2026: *"o uso de SS, o uso de buff, o uso de poção de
# cura, qualquer coisa que precisar é só depois que entrar na cave e não fora,
# como é feito no bot BC"*. É a mesma regra que a BC segue desde 25/08/2026.
#
# Os dois motivos são medidos: montado o jogo IGNORA a tecla sem devolver erro,
# e entrar na cave é disputado -- durante a espera o personagem regenera de
# graça, então curar antes é gastar poção que a espera ia devolver.


@pytest.mark.parametrize("proibida,por_que", [
    ("apply_buffs", "buff fora da cave expira na fila da porta"),
    ("curar_ao_entrar", "a espera da porta devolve a vida de graça"),
    ("heal_to_full", "a espera da porta devolve a vida de graça"),
    ("feed_pet", "alimentar exige estar a pé, e a pé fora da cave é proibido"),
])
def test_o_preparo_de_FORA_nao_faz_o_que_e_de_dentro(proibida, por_que):
    assert proibida not in _chamadas(HHRoutine._do_preparar), por_que


def test_o_preparo_de_DENTRO_segue_a_ordem_do_BC():
    """A ordem não é preferência: cada passo depende do que o anterior deixa.

    Curar antes de buffar (buff em quem vai morrer é buff perdido), pet antes da
    comida, e montar por último -- senão os passos seguintes desfazem a montaria.
    """
    # SÓ O RAMO DO PREPARO COMPLETO. O ramo do meio da cave garante a montaria
    # e sai, então uma busca no método inteiro acharia essa montaria primeiro e
    # concluiria que a ordem quebrou. O corte é pelo AST, e não por fatia de
    # texto: fatiar a fonte no meio de um bloco indentado não volta a ser
    # Python válido.
    import ast as _ast

    arvore = _ast.parse(_fonte(HHRoutine._do_preparar_dentro))
    porta = next(n for n in _ast.walk(arvore)
                 if isinstance(n, _ast.If)
                 and "acabei_de_entrar" in _ast.unparse(n.test))
    dentro_do_desvio = {id(n) for n in _ast.walk(porta)}
    nos = [(n.lineno, n.col_offset,
            getattr(n.func, "attr", getattr(n.func, "id", "")))
           for n in _ast.walk(arvore)
           if isinstance(n, _ast.Call) and id(n) not in dentro_do_desvio]
    chamadas = [nome for _l, _c, nome in sorted(nos)]
    for antes, depois in [("curar_ao_entrar", "apply_buffs"),
                          ("apply_buffs", "ensure_pet"),
                          ("ensure_pet", "feed_pet"),
                          ("feed_pet", "garantir_montaria_para_andar")]:
        assert chamadas.index(antes) < chamadas.index(depois), (
            f"{antes} tem que vir antes de {depois}")


def test_o_PET_e_conferido_na_PORTA_e_so_uma_vez():
    """A única verificação que acontece fora da cave.

    Regra do usuário: *"o pet também pode verificar fora da cave, mas só ao
    chegar na frente da cave, antes não precisa"*. E FORA do laço de tentativas:
    a rajada pode durar uma hora com uma tentativa a cada 25 ms.
    """
    assert "pet_active" in _chamadas(HHRoutine._conferir_o_pet_na_porta)
    assert "ensure_pet" not in _chamadas(HHRoutine._do_entrar)
    # e o estado que chega na porta chama o conferidor nos DOIS caminhos
    # (já estava na porta, e viajou até ela)
    assert _chamadas(HHRoutine._do_ate_a_porta).count(
        "_conferir_o_pet_na_porta") == 2


def test_a_porta_OLHA_o_pet_mas_NAO_o_invoca():
    """Invocar exige estar a pé, e fora da cave não se desmonta.

    Relato do usuário em 13/09/2026: *"ao lado de fora da cave HH tem vezes que
    está saindo da montaria, mas no geral não deve sair... principalmente depois
    de vender os itens"*. Era este método: 17 desmontes no log de 11/09, todos
    logo depois da venda, cada um custando descer, invocar e subir.
    """
    assert "ensure_pet" not in _chamadas(HHRoutine._conferir_o_pet_na_porta), (
        "a porta voltou a invocar o pet -- e invocar é desmontar")


def test_quem_INVOCA_o_pet_e_o_preparo_de_DENTRO():
    """É o que torna a porta poder só olhar: lá dentro o desmonte já está pago
    pelos buffs, então adiar alguns segundos troca um desmonte por zero."""
    assert "ensure_pet" in _chamadas(HHRoutine._do_preparar_dentro)


def test_a_contagem_da_run_comeca_no_preparo_de_DENTRO():
    """Não na entrada: a disputa da porta pode ter levado uma hora.

    Contar a run a partir do preparo é o que torna o tempo por run comparável
    entre uma volta e outra. Mesmo desenho da BC.
    """
    assert "begin_run" in _chamadas(HHRoutine._do_preparar_dentro)
    assert "begin_run" not in _chamadas(HHRoutine._entrou)
    assert "begin_run" not in _chamadas(HHRoutine._retomar_dentro_da_cave)


def test_a_VENDA_acontece_antes_de_entrar():
    """Entrar com a bolsa cheia é fazer a run inteira e deixar o loot no chão.

    A GARANTIA MUDOU DE FORMA em 09/09/2026, e ficou mais forte. Antes era uma
    pergunta à bolsa no `PREPARAR` -- e a leitura da bolsa é instável, então na
    prática ela só disparava com 85 de 90 slots ocupados. Agora a venda da
    largada é INCONDICIONAL, na porta, antes da rajada de entrada.

    O bot em Lua não tinha nem uma nem outra: vendia toda run com 30 cliques
    cegos e transbordava sem avisar.
    """
    porta = _fonte(HHRoutine._do_ate_a_porta)
    assert "_vender_e_limpar_na_largada" in porta
    assert porta.index("_vender_e_limpar_na_largada") < porta.index(
        "State.ENTRAR")


def test_a_bolsa_ILEGIVEL_nao_manda_vender():
    """`BagConfig.precisa_vender` devolve False quando a contagem não pôde ser
    lida -- vender sem saber quantos itens existem levaria o bot a viajar sem
    motivo e a clicar na grade de uma janela talvez vazia."""
    from blazesbot.bot.hh.manutencao import ManutencaoDaHH

    # A DECISÃO subiu para `hh/manutencao.py` em 08/09/2026 -- é o que acontece
    # FORA da cave, entre uma run e a seguinte, e não fala com a máquina de
    # estados.
    assert "precisa_vender" in _fonte(ManutencaoDaHH.precisa_vender)


def test_desmonta_ANTES_de_lutar():
    """Montado o jogo recusa as skills. O bot em Lua desmonta nos quatro
    bosses, e essa parte ele acertou."""
    chamadas = _chamadas(HHRoutine._do_ate_o_boss)
    assert chamadas.index("seguir_rota") < chamadas.index("ensure_dismounted")


# ===========================================================================
# Os quatro bosses são um LAÇO sobre os dados
# ===========================================================================


def test_os_bosses_sao_dados_e_nao_estados():
    """Acrescentar um quinto boss tem que ser uma linha em `mapa_hh`.

    Se a rotina tivesse ATE_O_BOSS_1..4, cada boss novo seria dois estados e
    mais um `if` -- e cada `if` desses é uma chance de mexer num boss e quebrar
    outro.
    """
    nomes = [s.name for s in State]
    assert not [n for n in nomes if n[-1].isdigit()], nomes
    assert "TRECHOS_DOS_BOSSES" in _fonte(HHRoutine._do_ate_o_boss)


def test_o_trecho_avanca_e_o_ultimo_leva_para_a_SAIDA():
    """O avanço mora em `_avancar_o_trecho` desde 03/09/2026.

    Saiu de `_do_boss` porque passou a ter duas entradas -- o ponto que não
    engajou em 5 s e a luta vencida -- e a regra de pular os já feitos vale
    para as duas.
    """
    fonte = _fonte(HHRoutine._avancar_o_trecho)
    assert "marcar_feito_e_avancar" in fonte
    assert "State.SAIR" in fonte
    assert "State.ATE_O_BOSS" in fonte


def test_situar_DENTRO_da_cave_retoma_pelo_trecho_mais_proximo():
    """O personagem morre e revive DENTRO (o Lua confirma: respawn interno), ou
    o bot é ligado com a run em andamento. Voltar ao boss 1 seria refazer o que
    já foi feito, com a instância já gasta."""
    fonte = _fonte(HHRoutine._retomar_dentro_da_cave)
    assert "mais_proximos" in fonte
    assert "TRECHOS_DOS_BOSSES" in fonte


def test_sem_leitura_de_posicao_NAO_se_decide_nada():
    """Sem saber onde está, qualquer escolha é chute -- e chute aqui significa
    clicar no NPC errado ou andar para o lado oposto."""
    # PELO AST: a docstring desta função CITA `etapa_pelo_lugar` ao explicar
    # quem responde, e uma busca no texto acharia a explicação antes do código.
    import ast as _ast

    arvore = _ast.parse(_fonte(HHRoutine._do_situar))
    guarda = min(n.lineno for n in _ast.walk(arvore)
                 if isinstance(n, _ast.Compare)
                 and "pos is None" in _ast.unparse(n))
    consulta = min(n.lineno for n in _ast.walk(arvore)
                   if isinstance(n, _ast.Call)
                   and getattr(n.func, "attr", "") == "etapa_pelo_lugar")
    assert guarda < consulta


def test_a_etapa_sai_de_NOME_e_COORDENADA_juntos():
    """Verificação dupla, regra do usuário de 04/09/2026.

    Nenhum dos dois basta: `Memory.location()` devolve `Black Wind Camp
    Dungeon` tanto em (-343,-288) quanto em (55,33) -- medido no log de 03/09,
    673 menções e uma única string --, e a coordenada não separa as etapas de
    FORA porque o teleporte da Fay espalha o ponto de chegada.
    """
    chamadas = _chamadas(HHRoutine._do_situar)
    assert "etapa_pelo_lugar" in chamadas
    assert "location" in chamadas
    assert "position" in chamadas


def test_ja_estando_depois_do_teleporte_a_Fay_e_PULADA():
    """Refazer o teleporte do outro lado dele levaria o personagem de volta
    para Stone City, andando para LONGE da cave."""
    fonte = _fonte(HHRoutine._do_ate_a_porta)
    assert "ETAPA_NA_VIZINHANCA" in fonte
    guarda = fonte.index("ETAPA_NA_VIZINHANCA")
    assert guarda < fonte.index("viajar_para_a_hh")


def test_lugar_desconhecido_faz_a_VIAGEM_COMPLETA():
    """"Não sei" custa uma viagem, nunca um clique no lugar errado."""
    from blazesbot.bot.hh import mapa_hh

    for nome in (None, "Wei's Village", "Bothy", "Stone City"):
        assert mapa_hh.etapa_pelo_lugar(nome, (-500, -500)) == mapa_hh.ETAPA_LONGE


def test_a_COORDENADA_e_o_veto_de_dentro_e_fora():
    """Estar na caixa da instância PROVA que está dentro, e nenhum nome desmente.

    É o mesmo desenho medido da BC (`bc/localizacao._decidir_se_esta_na_cave`).
    """
    from blazesbot.bot.hh import mapa_hh

    # o nome é o mesmo dentro e fora -- só a coordenada separa
    assert mapa_hh.etapa_pelo_lugar(
        "Black Wind Camp Dungeon", (55, 33)) == mapa_hh.ETAPA_DENTRO
    assert mapa_hh.etapa_pelo_lugar(
        "Black Wind Camp Dungeon", (-343, -288)) == mapa_hh.ETAPA_NA_PORTA
    # e sem nome nenhum a coordenada ainda decide
    assert mapa_hh.etapa_pelo_lugar(None, (552, 188)) == mapa_hh.ETAPA_DENTRO
    assert mapa_hh.etapa_pelo_lugar(None, (-342, -288)) == mapa_hh.ETAPA_NA_PORTA


# ===========================================================================
# O RESET -- regra do jogo, não do bot
# ===========================================================================


def test_no_modo_SOLO_o_time_e_desfeito_ao_ENTRAR():
    """Igual à BC: a conta de reset aceita, o personagem entra, o time cai. É o
    desfazer que faz os bosses renascerem para a run seguinte."""
    fonte = _fonte(HHRoutine._entrou)
    assert "sair_do_time" in fonte
    assert "MODO_FADA_DA_HH" in fonte


def test_no_modo_FADA_o_time_SOBREVIVE_a_cave():
    """As duas atravessam juntas -- a Fada acompanha e cura. Desfazer ao entrar
    deixaria o personagem sozinho justamente onde ele precisa da cura."""
    fonte = _fonte(HHRoutine._entrou)
    i_modo = fonte.index("MODO_FADA_DA_HH")
    i_sair = fonte.index("sair_do_time")
    assert i_modo < i_sair, "o time é desfeito antes de olhar o modo"


def test_no_modo_FADA_o_ciclo_de_time_e_na_MANUTENCAO():
    """Depois de SAIR, e não antes: é lá que desfaz-refaz pode acontecer."""
    fonte = _fonte(HHRoutine._do_manutencao)
    assert "MODO_FADA_DA_HH" in fonte
    assert "_reciclar_o_time" in fonte


def test_sem_conta_de_reset_o_bot_AVISA():
    """Quem ligou a HH sem conta de reset provavelmente não sabe que os bosses
    não renascem. Aceitar em silêncio é deixar a pessoa achar que a cave está
    vazia por bug."""
    fonte = _fonte(HHRoutine._garantir_o_time)
    assert "NÃO renascem" in fonte or "não renascem" in fonte
    assert "warning" in fonte


def test_o_time_e_montado_NA_PORTA_e_nao_antes():
    """Mexer na lista no meio do caminho não adianta, e o convite podia expirar
    durante o teleporte."""
    assert "_garantir_o_time" in _fonte(HHRoutine._do_entrar)
    assert "_garantir_o_time" not in _fonte(HHRoutine._do_ate_a_porta)


# ===========================================================================
# A porta é disputada
# ===========================================================================


def test_a_rajada_de_entrada_segura_o_F12():
    """Daqui saem dois cliques por segundo na cena 3D, e um jogador parado na
    frente do NPC engole todos eles."""
    arvore = ast.parse(_fonte(HHRoutine._do_entrar))
    withs = [n for n in ast.walk(arvore) if isinstance(n, ast.With)]
    assert withs, "a rajada não segura a tecla de esconder"
    assert "segurado" in _fonte(HHRoutine._do_entrar)


def test_a_entrada_e_confirmada_pela_POSICAO():
    """Não pela imagem. O bot em Lua usa `inside.bmp` -- um casamento de
    template na tela inteira -- para saber se entrou, quando a coordenada está
    disponível e é uma leitura de struct."""
    fonte = _fonte(HHRoutine._do_entrar)
    assert "esperar_entrar" in fonte

    from blazesbot.bot.hh.entrada import EntradaDaHH

    assert "esta_dentro_da_hh" in _fonte(EntradaDaHH.esperar_entrar)


def test_a_rajada_tem_TETO():
    """Sem teto, uma porta que nunca abre prende a conta para sempre. O bot em
    Lua tem 37 laços sem teto, e cada um é um travamento permanente."""
    fonte = _fonte(HHRoutine._do_entrar)
    assert "MAX_SEGUNDOS_NA_PORTA" in fonte


# ===========================================================================
# A morte
# ===========================================================================


def test_a_morte_cai_no_RECUPERAR_e_volta_a_se_situar():
    """O personagem revive dentro ou fora da cave, e `_do_situar` distingue os
    dois pela coordenada -- exatamente o que o bot em Lua faz com
    `if ptr.getX() > 0`."""
    fonte = _fonte(HHRoutine._do_recuperar)
    assert "dead" in fonte
    assert "State.SITUAR" in fonte
    # AQUI HAVIA `assert "_trecho = 0" in fonte`, e ele estava ERRADO em dois
    # sentidos: zerar o trecho na queda foi REMOVIDO em 03/09 (quem caísse no
    # trecho 3 voltava a fazer o 1 e encontrava a sala vazia), e a asserção só
    # continuava passando porque casava com o COMENTÁRIO que explicava a
    # remoção. Quem guarda o comportamento certo é
    # `test_cair_NAO_joga_fora_o_trecho_em_andamento`, pelo AST.


# ===========================================================================
# O PORTÃO DO SUPERVISOR
# ===========================================================================


def test_a_HH_vem_antes_da_BC_no_despacho():
    """As duas são farm de cave e disputariam o teclado se rodassem juntas.

    Com ordem fixa a escolha é PREVISÍVEL -- ligar as duas roda a HH, e o log
    diz isso -- em vez de depender de qual laço chegou primeiro.
    """
    from blazesbot.bot.supervisor import AccountSupervisor

    fonte = _fonte(AccountSupervisor._operate)
    i_app = fonte.index("app.enabled")
    i_hh = fonte.index("hh_farm")
    i_bc = fonte.index("quer_farmar = self.account.bc_farm")
    assert i_app < i_hh < i_bc, "a ordem APP -> HH -> BC mudou"


def test_o_APP_continua_tendo_precedencia_sobre_as_duas():
    """O APP manda tecla em laço; qualquer farm junto seria duas mãos no mesmo
    teclado."""
    from blazesbot.bot.supervisor import AccountSupervisor

    fonte = _fonte(AccountSupervisor._operate)
    assert fonte.index("app.enabled") < fonte.index("hh_farm")


def test_ligar_a_HH_com_o_BC_rodando_devolve_o_controle():
    """No próximo ponto seguro, e não no meio de uma fase."""
    from blazesbot.bot.supervisor import AccountSupervisor

    fonte = _fonte(AccountSupervisor._operate)
    assert "not self.account.hh_farm" in fonte


def test_a_HH_nao_farma_sem_memoria():
    """O portão de memória da BC vale igual aqui: sem ler HP, posição e alvo, o
    bot passa a repetir ação no vazio -- invocar pet sete vezes, montar e
    desmontar, abrir NPC sem motivo."""
    from blazesbot.bot.supervisor import AccountSupervisor

    fonte = _fonte(AccountSupervisor._operate)
    trecho = fonte[fonte.index("hh_farm"):fonte.index("quer_farmar")]
    assert "critical_ok" in trecho


def test_a_rotina_da_HH_e_criada_UMA_vez_e_guardada():
    """O estado dela diz em que trecho dos quatro bosses a run está. Recriar a
    cada volta do laço voltaria ao primeiro boss."""
    from blazesbot.bot.supervisor import AccountSupervisor

    fonte = _fonte(AccountSupervisor._rotina_da_hh)
    assert "if self._hh is None" in fonte


def test_farms_cobre_as_DUAS_caves():
    """O painel e o laço de status perguntam "tem farm ligado". Deixar a HH de
    fora faria a conta aparecer como parada estando farmando."""
    from blazesbot.config import Account

    a = Account()
    assert a.farms is False
    a.hh_farm = True
    assert a.farms is True
    a.hh_farm, a.bc_farm = False, True
    assert a.farms is True


# ===========================================================================
# O ISOLAMENTO
# ===========================================================================


def test_a_HH_usa_o_MESMO_motor_da_BC():
    """A diretiva de reuso, verificada na identidade das peças.

    As DUAS caves derivam do mesmo motor, e cada uma só acrescenta o que é do
    mapa dela. A HH passou a derivar em 13/09/2026: usando o motor cru, o veto
    de `_preparar_para_agir` perguntava *"estou fora da cave?"*, ouvia o
    "não sei" do padrão, e deixava todo desmonte de fora da cave passar.
    """
    from blazesbot.bot.bc.combat import CombateBC
    from blazesbot.bot.combate import CombatEngine as motor
    from blazesbot.bot.hh.combate import CombateHH

    for cave in (CombateBC, CombateHH):
        assert issubclass(cave, motor)
    assert not issubclass(CombateHH, CombateBC), (
        "um ecossistema passou a herdar do outro")


def test_a_HH_SABE_provar_que_esta_fora_da_cave():
    """Sem isto o veto de desmontar fora da cave nunca disparava na HH."""
    from blazesbot.bot.combate import CombatEngine as motor
    from blazesbot.bot.hh.combate import CombateHH

    assert CombateHH._esta_fora_da_cave is not motor._esta_fora_da_cave


def test_a_prova_de_estar_fora_da_HH_NAO_e_a_negacao_de_estar_dentro():
    """`None` tem que responder False nas DUAS -- "não sei" não é "não está".

    Negar `esta_dentro_da_hh` transformaria uma leitura que falhou em prova de
    estar fora, e aí o veto bloquearia um buff DENTRO da cave.
    """
    from blazesbot.bot.hh.combate import posicao_esta_fora_da_hh

    assert posicao_esta_fora_da_hh(None) is False
    assert mapa_hh.esta_dentro_da_hh(None) is False

    for fora in (mapa_hh.PONTO_DA_ENTRADA, mapa_hh.PONTO_DA_VENDA):
        assert posicao_esta_fora_da_hh(fora), f"{fora} devia provar que é fora"
        assert not mapa_hh.esta_dentro_da_hh(fora)

    for dentro in (mapa_hh.PONTO_DA_SAIDA, mapa_hh.CHEGADA_NA_HH):
        assert not posicao_esta_fora_da_hh(dentro)
        assert mapa_hh.esta_dentro_da_hh(dentro)


def test_o_vendedor_da_HH_herda_a_MESMA_janela_de_venda():
    """A janela é uma no jogo inteiro -- confirmado nas capturas do Roaming
    Apothecary. Só o NPC muda."""
    from blazesbot.bot.bc.vendor import VendorService
    from blazesbot.bot.hh.vendedor import VendedorDaHH
    from blazesbot.bot.vendedor import JanelaDeVenda

    assert issubclass(VendedorDaHH, JanelaDeVenda)
    assert issubclass(VendorService, JanelaDeVenda)
    assert VendedorDaHH.NOME_DO_VENDEDOR == mapa_hh.NPC_VENDEDOR[1]
    assert VendorService.NOME_DO_VENDEDOR != VendedorDaHH.NOME_DO_VENDEDOR


def test_a_entrada_da_HH_herda_a_MESMA_ui_do_jogo():
    from blazesbot.bot.bc.ui_service import UIService
    from blazesbot.bot.hh.entrada import EntradaDaHH
    from blazesbot.bot.ui_do_jogo import UIDoJogo

    assert issubclass(EntradaDaHH, UIDoJogo)
    assert issubclass(UIService, UIDoJogo)


def test_a_HH_nao_tem_alvo_proibido_e_isso_e_RESPOSTA():
    """A Bewitcher Cave tem o Cemetery Guard: puxá-lo tira a run da rota. A HH
    não tem equivalente conhecido, e `None` é resposta -- não lacuna."""
    from blazesbot.bot.combate import CombatEngine

    assert CombatEngine.NOME_DO_ALVO_PROIBIDO is None


# ===========================================================================
# A RAJADA DE ENTRADA É A DO BC
# ===========================================================================
#
# Regra do usuário, 03/09/2026: *"tem que ficar fazendo as tentativas para
# entrar, como é feito em BC, pois são várias e várias tentativas até conseguir
# entrar, pois pode estar cheio a cave"*.
#
# Os números não são copiados na unha: o teste compara com os do BC, e é isso
# que impede os dois de divergirem em silêncio quando alguém ajustar um lado.


def test_o_teto_da_porta_e_o_mesmo_do_BC():
    """Uma hora, e não cinco minutos.

    Desistir devolve o personagem ao começo do ciclo sem ter feito nada -- e a
    tentativa em si custa quase zero (clique e leitura de memória).
    """
    from blazesbot.bot.bc import routine as bc
    from blazesbot.bot.hh import routine as hh

    assert hh.MAX_SEGUNDOS_NA_PORTA == bc.MAX_SEGUNDOS_ENTRADA == 3600.0


def test_o_intervalo_entre_tentativas_e_o_mesmo_do_BC():
    from blazesbot.bot.bc import routine as bc
    from blazesbot.bot.hh import routine as hh

    assert hh.ENTRE_TENTATIVAS_DE_ENTRAR == bc.ESPERA_ENTRE_TENTATIVAS


def test_a_confirmacao_de_uma_tentativa_e_CURTA():
    """Eram 2,0 s, e enquanto o bot esperava ninguém estava tentando de novo.

    A JANELA DA HH DESCOLOU DA DO BC EM 11/09/2026, e o motivo é que ela passou
    a ter medição própria. Nos logs de 09 e 10/09, das 221 entradas confirmadas
    aqui, 9 em 10 confirmam em ZERO ms -- quando a entrada pega, a troca de mapa
    já aconteceu durante os cliques. As 61.928 que não entraram pagavam a janela
    inteira: 4,3 horas na amostra.

    O BC MANTÉM 0,25 s porque lá o número não é medido, é ORÇAMENTO: seis
    tentativas em dez segundos, 1,06 s de ação mecânica, sobram 0,60 s para
    reconhecer e reagir (ver `bc/routine.JANELA_DE_RECONHECIMENTO`). Quem medir
    o BC pode encurtar lá também; até então, o que vale é a desigualdade.
    """
    from blazesbot.bot.bc import routine as bc
    from blazesbot.bot.hh import entrada

    assert entrada.TETO_DA_ENTRADA == 0.12, (
        "o teto da HH é MEDIDO; mudá-lo pede log novo, não arredondamento")
    assert entrada.TETO_DA_ENTRADA <= bc.JANELA_DE_RECONHECIMENTO, (
        "a janela da HH ficou MAIOR que a do BC, que é orçamento e não medição")
    assert entrada.PASSO_DA_ESPERA_DA_ENTRADA == bc.PASSO_DO_RECONHECIMENTO


def test_a_rajada_confere_a_POSICAO_antes_de_clicar():
    """Duas coisas, e as duas na mesma leitura.

    Já estar dentro (o servidor demorou mais que a janela) e ter DERIVADO para
    fora do ponto de conversa -- fora dele todo clique erra o NPC, e cada erro
    empurra o personagem mais para longe.
    """
    chamadas = _chamadas(HHRoutine._do_entrar)
    assert "position" in chamadas
    assert "esta_dentro_da_hh" in chamadas
    assert "garantir_coordenada_da_entrada" in chamadas
    assert chamadas.index("position") < chamadas.index("tentar_entrar_na_hh")


def test_estourar_o_teto_volta_para_a_PORTA_e_nao_para_RECUPERAR():
    """Uma hora sem entrar não é queda nem morte -- é a cave cheia.

    `RECUPERAR` é para quando algo saiu do roteiro; a resposta certa aqui é
    refazer o caminho e tentar de novo.
    """
    fonte = _fonte(HHRoutine._do_entrar)
    assert "State.ATE_A_PORTA" in fonte
    assert "State.RECUPERAR" not in fonte

# ===========================================================================
# CINCO SEGUNDOS PARA ENGAJAR, E DEPOIS SEGUE
# ===========================================================================
#
# Regra do usuário, 03/09/2026: *"sempre que tiver em um waypoint de ataque
# deve esperar no máximo 5 segundos para entrar em batalha, caso não entre em
# batalha pode continuar para os próximos waypoints"* -- e ele confirmou que
# vale no ponto do BOSS também.
#
# É o que torna barato refazer um trecho já limpo depois de uma morte.


def test_o_ponto_espera_5s_pela_flag_e_nao_mais():
    from blazesbot.bot.hh import routine as hh

    assert hh.SEGUNDOS_PARA_ENGAJAR == 5.0
    fonte = _fonte(HHRoutine._do_boss)
    assert "esperar_entrar_em_combate" in fonte
    assert "SEGUNDOS_PARA_ENGAJAR" in fonte


def test_nao_engajou_em_5s_AVANCA_o_trecho_sem_lutar():
    """O ponto está limpo; insistir seria pagar o teto da luta contra o nada."""
    chamadas = _chamadas(HHRoutine._do_boss)
    assert (chamadas.index("esperar_entrar_em_combate")
            < chamadas.index("_avancar_o_trecho"))


def test_morrer_esperando_o_engajamento_NAO_vira_ponto_limpo():
    """Silêncio porque morri é diferente de silêncio porque não tem ninguém.

    Sem esta conferência, morrer na espera faria o bot marcar o trecho como
    feito e seguir para o próximo boss -- morto.
    """
    fonte = _fonte(HHRoutine._do_boss)
    depois_da_espera = fonte[fonte.index("SEGUNDOS_PARA_ENGAJAR"):]
    assert depois_da_espera.index("dead") < depois_da_espera.index(
        "_avancar_o_trecho")


# ===========================================================================
# VOLTAR AO PONTO DEPOIS DE MATAR
# ===========================================================================


def test_a_ORDEM_e_lutar_validar_e_so_entao_creditar():
    """A validação fica ENTRE a luta e o crédito, e é o ponto todo.

    O CONTRATO mora em `hh/ponto_do_boss.py` e é testado lá. Aqui se confere a
    costura: nenhum `_avancar_o_trecho` pode acontecer antes de
    `verificar_morte_do_boss` ter respondido.
    """
    chamadas = _chamadas(HHRoutine._do_boss)

    assert (chamadas.index("_lutar_no_ponto")
            < chamadas.index("verificar_morte_do_boss"))
    assert (chamadas.index("verificar_morte_do_boss")
            < max(i for i, c in enumerate(chamadas) if c == "_catar_o_loot"))


def test_a_POSICAO_e_lida_no_instante_da_saida_de_batalha():
    """Ler depois de caminhar de volta é o que produzia a falsa vitória.

    PELO AST: a leitura tem que ser argumento da própria validação, e não uma
    variável capturada antes da luta ou depois de um deslocamento.
    """
    import ast
    import textwrap

    arvore = ast.parse(textwrap.dedent(_fonte(HHRoutine._do_boss)))
    chamadas = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)
                and ast.unparse(n.func) == "verificar_morte_do_boss"]

    assert len(chamadas) == 1
    argumentos = [ast.unparse(a) for a in chamadas[0].args]
    assert "ctx.memory.position()" in argumentos, (
        f"a posição deixou de ser lida no instante da validação: {argumentos}")


def test_o_ROLLBACK_nao_credita_e_NAO_sai_da_cave():
    """Medido em 11/09/2026: 9 falsas vitórias, 5 delas no `Purple`.

    Como o `Purple` é o último boss, creditá-lo é SAIR DA CAVE -- que é o
    relato do usuário. O ramo do rollback não pode chamar `_avancar_o_trecho`.
    """
    fonte = _fonte(HHRoutine._do_boss)
    ramo = fonte[fonte.index("veredito.creditar"):]
    ramo = ramo[ramo.index("self._vetos_de_rollback += 1"):]

    assert "_avancar_o_trecho" not in ramo, (
        "o caminho do rollback voltou a creditar o boss")
    assert "State.ATE_O_BOSS" in ramo, (
        "o rollback deixou de refazer o trecho")


def test_o_rollback_tem_TETO_e_o_estouro_nao_credita():
    """Insistir sem limite prenderia a run; creditar ao desistir reabriria o
    defeito. O desfecho é `_falhar`, que leva ao `RECUPERAR`."""
    fonte = _fonte(HHRoutine._do_boss)
    ramo = fonte[fonte.index("VETOS_ANTES_DE_DESISTIR:"):]
    corte = ramo.index("State.ATE_O_BOSS")

    assert "_falhar" in ramo[:corte]
    assert "_avancar_o_trecho" not in ramo[:corte]


def test_o_contador_de_vetos_ZERA_ao_fechar_um_trecho():
    """Senão três rollbacks espalhados pelos quatro bosses derrubariam uma run
    que está indo bem."""
    assert "_vetos_de_rollback = 0" in _fonte(HHRoutine._avancar_o_trecho)
    assert "_vetos_de_rollback = 0" in _fonte(HHRoutine.__init__)


def test_a_ancora_do_retorno_e_o_WAYPOINT_e_nao_uma_leitura():
    """Sob rollback, uma posição capturada guarda onde o rollback largou.

    No log de 05/09 a âncora era (275,138) e o ponto do boss é (271,137).
    """
    fonte = _fonte(HHRoutine._do_boss)
    assert "onde_eu_estava" not in fonte
    assert "do_trecho(self.progresso.trecho" in fonte


# ===========================================================================
# O QUE JÁ FOI FEITO NESTA IDA À CAVE
# ===========================================================================
#
# Regra do usuário, 03/09/2026: *"não precisa ser persistente, só verificar
# enquanto está com o bot aberto... e a cada vez que saiu da cave, tem que
# resetar, pois ao reentrar todos os bosses vão estar vivos novamente"*.


def test_o_progresso_e_ZERADO_ao_entrar_na_cave():
    """Instância nova, quatro bosses vivos de novo."""
    assert "progresso.entrei_na_cave()" in _fonte(HHRoutine._entrou)


def test_o_trecho_feito_e_PULADO_na_volta():
    """Depois de uma morte o bot refaz a perna; o que já limpou, ele pula."""
    # A REGRA DE PULAR mora no `ProgressoDaCave` e é testada lá
    # (`test_o_trecho_ja_feito_e_PULADO`). Aqui só se confere que a rotina
    # delega em vez de reimplementar a contagem.
    fonte = _fonte(HHRoutine._avancar_o_trecho)
    assert "marcar_feito_e_avancar" in fonte
    assert "_trechos_feitos" not in fonte


def test_a_retomada_respeita_o_trecho_em_ANDAMENTO():
    """Os quatro trechos se cruzam no mapa.

    Quem morre no trecho 3 revive no começo da cave, e dali um waypoint do
    trecho 1 fica mais perto que qualquer coisa do 3. Escolher pela distância
    refaria os bosses já mortos -- e encontraria as salas vazias, porque o reset
    só acontece na saída.
    """
    fonte = _fonte(HHRoutine._retomar_dentro_da_cave)
    assert "progresso.em_andamento" in fonte
    # a distância só decide DEPOIS, quando não há run em andamento
    assert fonte.index("progresso.em_andamento") < fonte.index("mais_proximos")


# ===========================================================================
# O PONTO ONDE OS MOBS BLOQUEIAM A PASSAGEM
# ===========================================================================
#
# O (232,188) aparece em dois arquivos do bot em Lua com a mesma instrução:
# matar os mobs que bloqueiam antes de continuar (`travel.lua`, `hh.lua`). É uma
# passagem estreita, e um mob parado nela faz a navegação bater na geometria e
# chamar o destravamento em círculo.


def test_o_mapa_declara_onde_a_passagem_e_bloqueada():
    from blazesbot.bot.hh import mapa_hh

    assert mapa_hh.WAYPOINTS_QUE_BLOQUEIAM == ((232, 188),)
    assert mapa_hh.bloqueia_a_passagem((232, 188))
    assert not mapa_hh.bloqueia_a_passagem((209, 182))


def test_e_um_conceito_DIFERENTE_de_waypoint_problematico():
    """Um é sobre GEOMETRIA (tolerância maior), o outro é sobre MOBS.

    Os dois calham de ser o mesmo ponto hoje, e é justamente por isso que
    misturá-los seria fácil e errado: o dia em que um mob bloquear um ponto de
    geometria fácil, a lista certa cresce sozinha.
    """
    import inspect

    from blazesbot.bot.hh import mapa_hh

    # Os dois calham de valer para o mesmo ponto hoje -- e o interpretador
    # chega a compartilhar a tupla, porque o conteúdo é idêntico. O que o teste
    # trava não é a identidade do objeto, e sim que as duas PERGUNTAS são
    # respondidas por listas separadas.
    assert mapa_hh.WAYPOINTS_QUE_BLOQUEIAM == ((232, 188),)
    assert mapa_hh.WAYPOINTS_PROBLEMATICOS == ((232, 188),)
    corpo = inspect.getsource(mapa_hh.bloqueia_a_passagem)
    assert "WAYPOINTS_PROBLEMATICOS" not in corpo, (
        "quem responde 'tem mob barrando?' não pode consultar a lista de "
        "geometria difícil -- são perguntas diferentes")


def test_a_rota_da_HH_leva_o_gancho():
    fonte = _fonte(HHRoutine._do_ate_o_boss)
    assert "ao_chegar=self._ao_chegar_no_waypoint" in fonte


def test_so_limpa_se_JA_estiver_em_combate_e_a_pe():
    """Numa volta em que o ponto está limpo isto não custa clique nenhum.

    A diferença contra o Lua: ele mata ali sempre que está a pé, porque não lê
    a flag de combate. Nós lemos.
    """
    chamadas = _chamadas(HHRoutine._ao_chegar_no_waypoint)
    assert "bloqueia_a_passagem" in chamadas
    assert "is_mounted" in chamadas
    assert "in_battle" in chamadas
    # O CORE LOOP DA HH desde 06/09/2026, e não mais `limpar_o_combate`: a
    # coreografia com pausa de três segundos é medição do BC.
    assert "_matar_ate_sair_de_batalha" in chamadas
    fonte = _fonte(HHRoutine._ao_chegar_no_waypoint)
    assert "in_battle() is not True" in fonte, (
        "ilegível não pode virar 'estou em combate' -- pararia por nada")


def test_o_gancho_e_OPCIONAL_no_navegador():
    """Sem gancho o comportamento é o de antes -- é o que protege a BC."""
    import inspect

    from blazesbot.bot.navegacao import Navigator

    for metodo in (Navigator.seguir_rota, Navigator.follow_path):
        assert inspect.signature(metodo).parameters["ao_chegar"].default is None


def test_o_gancho_vale_para_os_waypoints_ATRAVESSADOS():
    """A montaria cruza dois ou três waypoints numa leitura só.

    Um ponto que exige parada não pode ser pulado por causa da velocidade.
    """
    import inspect

    from blazesbot.bot.navegacao import Navigator

    fonte = inspect.getsource(Navigator.follow_path)
    assert "for alcancado in caminho[indice:novo]" in fonte


# ===========================================================================
# SAIR DA CAVE -- o estado que NÃO SAÍA
# ===========================================================================
#
# `_do_sair` andava até (529,119) e declarava a run concluída, sem falar com
# NPC nenhum. O personagem ficava dentro, e a "run seguinte" começava a tentar
# entrar numa cave em que já estava.


def test_sair_FALA_com_o_NPC_e_nao_so_anda_ate_o_ponto():
    chamadas = _chamadas(HHRoutine._do_sair)
    assert "seguir_rota" in chamadas
    assert "_falar_com_o_npc_da_saida" in chamadas
    assert (chamadas.index("seguir_rota")
            < chamadas.index("_falar_com_o_npc_da_saida"))


def test_a_run_so_e_dada_por_concluida_DEPOIS_de_sair():
    """`end_run(ok=True)` com o personagem ainda dentro seria placar mentindo."""
    fonte = _fonte(HHRoutine._do_sair)
    assert "end_run" not in fonte, (
        "o fecho da run mora em `_saiu`, que só roda depois da confirmação")
    assert "end_run" in _fonte(HHRoutine._saiu)


def test_a_saida_insiste_ate_a_POSICAO_confirmar():
    """Quem diz que saiu é a coordenada, não o clique ter saído.

    O Lua confere do mesmo jeito e refaz o diálogo quando a espera passa.
    """
    chamadas = _chamadas(HHRoutine._falar_com_o_npc_da_saida)
    assert "esta_dentro_da_hh" in chamadas
    assert "tentar_sair_da_hh" in chamadas
    assert "esperar_sair" in chamadas


def test_sair_ZERA_o_progresso_dos_bosses():
    """O desfaz-refaz do time ressuscita os quatro.

    Regra do usuário, 03/09/2026: *"a cada vez que saiu da cave, tem que
    resetar, pois ao reentrar todos os bosses vão estar vivos novamente"*.
    """
    assert "progresso.sai_da_cave()" in _fonte(HHRoutine._saiu)


def test_o_teto_para_sair_e_MENOR_que_o_de_entrar():
    """As naturezas são opostas.

    Entrar disputa vaga com outros jogadores e depende de eles saírem; sair não
    depende de ninguém -- se não sai, é o clique que está errando o NPC.
    """
    from blazesbot.bot.hh import routine as hh

    assert hh.MAX_SEGUNDOS_PARA_SAIR < hh.MAX_SEGUNDOS_NA_PORTA


# ===========================================================================
# ENTRAR E SAIR NA MESMA VOLTA
# ===========================================================================
#
# Regra do usuário, 03/09/2026: *"se for Black Wind Camp Dungeon e X acima de 0
# entrou na cave e precisa parar as tentativas na hora, pois no mesmo ângulo que
# entra, ele sai"*.
#
# O par de cliques não é atômico: entre o direito e o do link há a espera do
# diálogo. Quando uma tentativa acertava, o personagem entrava, e a tentativa
# seguinte clicava com direito no mesmo ângulo -- que dentro da cave é o NPC de
# SAÍDA. O diálogo abria (a conferência dizia "pode clicar") e o clique caía em
# "Leave Happiness Hall".


def test_o_par_de_cliques_confere_o_mundo_no_MEIO():
    """A conferência é ENTRE os dois cliques, não só antes do par."""
    import inspect

    from blazesbot.bot.hh.entrada import EntradaDaHH

    for metodo in (EntradaDaHH._entrar_rapido, EntradaDaHH._entrar_descobrindo):
        fonte = inspect.getsource(metodo)
        assert "_ainda_estou_fora" in fonte, (
            f"{metodo.__name__} pode clicar no link já estando dentro")


def test_estar_dentro_ABORTA_o_clique_no_link():
    import inspect

    from blazesbot.bot.hh.entrada import EntradaDaHH

    fonte = inspect.getsource(EntradaDaHH._ainda_estou_fora)
    assert "esta_dentro_da_hh" in fonte
    assert "return False" in fonte


def test_sem_leitura_de_posicao_a_entrada_SEGUE():
    """"Não sei" não pode bloquear a entrada -- bot mudo na porta é pior."""
    from blazesbot.bot.hh import mapa_hh

    assert mapa_hh.esta_dentro_da_hh(None) is False


def test_o_gancho_do_par_de_cliques_e_OPCIONAL():
    """Sem gancho o comportamento é o de antes -- é o que protege a BC."""
    import inspect

    from blazesbot.bot.ui_do_jogo import UIDoJogo

    for metodo in (UIDoJogo._abrir_dialogo_e_clicar,
                   UIDoJogo._clicar_no_npc_e_no_link):
        assert inspect.signature(metodo).parameters["ainda_vale"].default is None


def test_abortar_no_meio_FECHA_o_dialogo():
    """Diálogo aberto por cima da cena engole o clique da tentativa seguinte."""
    import inspect

    from blazesbot.bot.ui_do_jogo import UIDoJogo

    fonte = inspect.getsource(UIDoJogo._clicar_no_npc_e_no_link)
    trecho = fonte[fonte.index("ainda_vale is not None"):]
    assert "fechar_dialogo" in trecho.split("ctx.click")[0]


# ===========================================================================
# FORA DO PONTO E EM BATALHA -- O BECO SEM SAÍDA
# ===========================================================================


def test_fora_do_ponto_e_em_batalha_MATA_em_vez_de_andar():
    """Medido pelo usuário em 04/09/2026, e era travamento eterno.

    Chegou no ponto, o bot desmontou para lutar, o servidor lagou e devolveu o
    personagem para outro X/Y. A rotina concluía "não estou no ponto" e voltava
    para `ATE_O_BOSS`, que começa exigindo montaria -- e em batalha o jogo
    RECUSA montar. O bot apertava a tecla contra uma recusa, para sempre.
    """
    fonte = _fonte(HHRoutine._do_boss)
    trecho = fonte[fonte.index("TOLERANCIA_DO_PONTO"):]
    corte = trecho.index("State.ATE_O_BOSS")
    antes_de_voltar_a_andar = trecho[:corte]
    assert "in_battle" in antes_de_voltar_a_andar
    # PELO NOME DA CHAMADA, não pela menção: o comentário deste ramo citava
    # `limpar_o_combate` para explicar de onde a decisão veio, e a busca no
    # texto passava por causa da explicação. Hoje quem mata aqui é o laço de
    # ataque da HH, que é o mesmo dos pontos de luta -- e abre com a mira.
    assert "_matar_ate_sair_de_batalha" in antes_de_voltar_a_andar


def test_flag_ilegivel_NAO_autoriza_sair_batendo():
    """"Não sei" não pode virar "estou em combate" -- puxaria mob por nada."""
    fonte = _fonte(HHRoutine._do_boss)
    assert "in_battle() is True" in fonte


# ===========================================================================
# NO MEIO DA CAVE NÃO SE VERIFICA NADA
# ===========================================================================
#
# Regra do usuário, 04/09/2026: *"as verificações são somente na entrada da
# cave, se tiver no meio da cave não deve ser verificado nada, então só naquele
# waypoint inicial você faz as verificações e usa os buffs"*.


def test_o_preparo_completo_so_roda_no_waypoint_de_ENTRADA():
    """A pé no meio da cave é o trem de mobs encostando.

    Quem chega ao preparo sem ser pela porta é quem morreu e reviveu dentro, ou
    quem abriu o bot com a run em andamento -- e nos dois casos o que urge é
    voltar a andar, não beber poção parado.
    """
    fonte = _fonte(HHRoutine._do_preparar_dentro)
    portao = fonte.index("acabei_de_entrar")
    for depois in ("curar_ao_entrar", "apply_buffs", "ensure_pet", "feed_pet"):
        assert fonte.index(depois) > portao, (
            f"{depois} roda antes do portão de 'acabei de entrar'")


def test_a_MONTARIA_nao_e_verificacao_e_continua_no_meio_da_cave():
    """É a condição para andar: a pé o personagem não chega no boss."""
    fonte = _fonte(HHRoutine._do_preparar_dentro)
    ramo_do_meio = fonte[fonte.index("acabei_de_entrar"):fonte.index("# 1 e 2.")]
    assert "garantir_montaria_para_andar" in ramo_do_meio
    assert "begin_run" in ramo_do_meio, "a run precisa contar dos dois lados"
    assert "State.ATE_O_BOSS" in ramo_do_meio


def test_a_regua_da_chegada_e_a_do_core_e_nao_um_numero_novo():
    """(55,33) é padrão do jogo; o log leu (55,34) um segundo depois.

    O primeiro waypoint fica a 26 unidades, então qualquer régua abaixo disso
    separa "acabei de entrar" de "já estou andando" -- e `NA_ROTA` é a que o
    `core/rota.py` já usa para a mesma pergunta.
    """
    from blazesbot.bot.hh import mapa_hh
    from blazesbot.core import rota

    assert mapa_hh.TOLERANCIA_DA_CHEGADA == rota.NA_ROTA
    assert mapa_hh.acabei_de_entrar((55, 34))
    assert mapa_hh.acabei_de_entrar(mapa_hh.CHEGADA_NA_HH)
    assert not mapa_hh.acabei_de_entrar((80, 42))
    assert not mapa_hh.acabei_de_entrar(None)


# ===========================================================================
# "TODOS OS TRECHOS FEITOS" É UM ESTADO LEGÍTIMO -- 05/09/2026
# ===========================================================================
#
# A CONTAGEM em si é testada em `tests/test_progresso_da_cave.py`. Aqui fica só
# o que a ROTINA faz com a resposta dela.


def test_com_tudo_feito_SITUAR_manda_SAIR_e_nao_estoura():
    """Era `IndexError: tuple index out of range` em `_retomar_dentro_da_cave`.

    Medido no log de 05/09/2026: o usuário desligou às 20:02:14 com "os quatro
    feitos, saindo" e religou às 20:02:35 -- SITUAR estourou ONZE vezes em dez
    segundos. O progresso atravessa o desliga/liga porque a rotina é guardada
    no supervisor de propósito.
    """
    from blazesbot.bot.hh import mapa_hh
    from blazesbot.bot.hh.progresso import ProgressoDaCave

    r = HHRoutine.__new__(HHRoutine)
    r.progresso = ProgressoDaCave(len(mapa_hh.TRECHOS_DOS_BOSSES))
    r.progresso.a_run_comecou()
    r.progresso.pular_para(len(mapa_hh.TRECHOS_DOS_BOSSES))

    registrado = []
    r._ir_para = lambda estado, motivo="": registrado.append(estado)
    r._retomar_dentro_da_cave((55, 33))

    assert registrado == [State.SAIR]


def test_a_rotina_NAO_faz_a_conta_de_acabou_por_conta_propria():
    """Duas contas dessas divergiriam: IndexError num ramo, trecho refeito no
    outro."""
    fonte = _fonte(HHRoutine._retomar_dentro_da_cave)
    assert "self.progresso.acabou()" in fonte
    assert "len(mapa_hh.TRECHOS_DOS_BOSSES)" not in fonte
