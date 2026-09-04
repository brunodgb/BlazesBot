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
    chamadas = _chamadas(HHRoutine._do_preparar_dentro)
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
    assert "ensure_pet" in _chamadas(HHRoutine._conferir_o_pet_na_porta)
    assert "ensure_pet" not in _chamadas(HHRoutine._do_entrar)
    # e o estado que chega na porta chama o conferidor nos DOIS caminhos
    # (já estava na porta, e viajou até ela)
    assert _chamadas(HHRoutine._do_ate_a_porta).count(
        "_conferir_o_pet_na_porta") == 2


def test_a_contagem_da_run_comeca_no_preparo_de_DENTRO():
    """Não na entrada: a disputa da porta pode ter levado uma hora.

    Contar a run a partir do preparo é o que torna o tempo por run comparável
    entre uma volta e outra. Mesmo desenho da BC.
    """
    assert "begin_run" in _chamadas(HHRoutine._do_preparar_dentro)
    assert "begin_run" not in _chamadas(HHRoutine._entrou)
    assert "begin_run" not in _chamadas(HHRoutine._retomar_dentro_da_cave)


def test_o_CAP_e_conferido_ANTES_de_entrar():
    """A capacidade que o bot em Lua NÃO tem.

    Ele vende toda run com 30 cliques cegos e transborda sem avisar -- e
    `getBagItems` está implementado no `pointers.lua` e nunca é chamado.

    Entrar com a bolsa cheia é fazer a run inteira e deixar o loot no chão.
    """
    fonte = _fonte(HHRoutine._do_preparar)
    i_bolsa = fonte.index("_precisa_vender")
    i_porta = fonte.index("State.ATE_A_PORTA")
    assert i_bolsa < i_porta


def test_a_bolsa_ILEGIVEL_nao_manda_vender():
    """`BagConfig.precisa_vender` devolve False quando a contagem não pôde ser
    lida -- vender sem saber quantos itens existem levaria o bot a viajar sem
    motivo e a clicar na grade de uma janela talvez vazia."""
    assert "precisa_vender" in _fonte(HHRoutine._precisa_vender)


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
    fonte = _fonte(HHRoutine._do_boss)
    assert "_trecho += 1" in fonte
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
    fonte = _fonte(HHRoutine._do_situar)
    i_none = fonte.index("if pos is None")
    i_dentro = fonte.index("esta_dentro_da_hh")
    assert i_none < i_dentro


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
    assert "_trecho = 0" in fonte


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
    """A diretiva de reuso, verificada na identidade das peças."""
    from blazesbot.bot.bc.combat import CombatEngine as combate_bc
    from blazesbot.bot.combate import CombatEngine as motor
    from blazesbot.bot.hh.routine import CombatEngine as combate_hh

    assert combate_hh is motor
    assert issubclass(combate_bc, motor)


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

    A janela do BC é 0,25 s porque perguntar é uma leitura de memória: dá para
    perguntar várias vezes dentro dela em vez de esperar cego.
    """
    from blazesbot.bot.bc import routine as bc
    from blazesbot.bot.hh import entrada

    assert entrada.TETO_DA_ENTRADA == bc.JANELA_DE_RECONHECIMENTO
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
