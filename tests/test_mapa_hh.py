"""O mapa da HH: os dados que vieram do bot em Lua não podem se degradar.

ESTE TESTE EXISTE PORQUE OS WAYPOINTS SÃO O ÚNICO ATIVO INSUBSTITUÍVEL da
integração. Combate, navegação e venda o BlazesBot já sabe fazer melhor que o bot
original; os 66 pontos medidos passo a passo, não -- remedir custa horas de jogo.

Então aqui se trava o que não pode mudar por acidente: a contagem, a ordem, a
continuidade dos trechos e o clique calibrado de cada ponto. Também se trava a
HONESTIDADE do que ainda não foi medido: a área interna é um marcador, e o dia em
que alguém a preencher com palpite, este teste avisa.
"""
import itertools

import pytest

from blazesbot.bot.hh import mapa_hh as m
from blazesbot.core.rota import (
    Waypoint,
    distancia_ao_trecho,
    houve_rollback,
    montar,
)

# ===========================================================================
# Os waypoints vindos do Lua
# ===========================================================================

# Contagem por trecho, conforme `hh.lua`: position_1, position_boss_2,
# position_boss_3, position_boss_4 e position_exit.
CONTAGEM_DO_LUA = {
    "CAMINHO_ATE_O_BOSS_1": 22,
    "CAMINHO_ATE_O_BOSS_2": 16,
    "CAMINHO_ATE_O_BOSS_3": 12,
    "CAMINHO_ATE_O_BOSS_4": 15,
    "CAMINHO_ATE_A_SAIDA": 1,
}


@pytest.mark.parametrize("nome,esperado", sorted(CONTAGEM_DO_LUA.items()))
def test_cada_trecho_tem_a_contagem_medida(nome, esperado):
    """Waypoint que desaparece não dá erro: o bot só passa a bater na parede."""
    assert len(getattr(m, nome)) == esperado


def test_o_total_e_66():
    """65 nos quatro trechos dos bosses, 1 no de saída."""
    assert len(m.TODOS_OS_WAYPOINTS) == sum(CONTAGEM_DO_LUA.values()) == 66
    assert sum(CONTAGEM_DO_LUA[k] for k in CONTAGEM_DO_LUA
               if k != "CAMINHO_ATE_A_SAIDA") == 65


def test_todo_waypoint_tem_o_clique_calibrado():
    """O `via` é a RESERVA para quando o motor de navegação desistir.

    Perder um significa perder a única prova de que aquele trecho tem uma
    passagem que o cálculo não encontra sozinho.
    """
    sem_via = [wp.pos for wp in m.TODOS_OS_WAYPOINTS if wp.via is None]
    assert not sem_via, f"waypoints sem clique calibrado: {sem_via}"


def test_o_clique_calibrado_quase_sempre_cai_nos_limites_do_lua():
    """Os limites do `travel.lua:37` valem para o clique CALCULADO, não para o `via`.

    Dois dos 66 fogem da caixa, ambos no começo do trecho do boss 4, e não são
    erro: aquele trecho anda PARA TRÁS sobre o caminho do boss 3, e um passo para
    trás no minimapa cai à esquerda do centro.

    Este teste trava a exceção em DOIS. Se aparecer um terceiro, alguém digitou
    errado -- e se algum dia o `via` passar pelo corte do clique calculado, estes
    dois deixam de apontar para onde foram calibrados.
    """
    (xmin, xmax), (ymin, ymax) = m.LIMITES_DO_MINIMAPA
    fora = [wp.via for wp in m.TODOS_OS_WAYPOINTS
            if not (xmin <= wp.via[0] <= xmax and ymin <= wp.via[1] <= ymax)]
    assert sorted(fora) == sorted(m.VIA_FORA_DOS_LIMITES), (
        f"a lista de exceções mudou: {fora}")


def test_a_via_fora_dos_limites_esta_no_trecho_do_boss_4():
    """A explicação da exceção é o trecho que anda para trás. Se elas
    aparecerem em outro trecho, a explicação deixou de valer."""
    do_boss_4 = {wp.via for wp in m.CAMINHO_ATE_O_BOSS_4}
    for via in m.VIA_FORA_DOS_LIMITES:
        assert via in do_boss_4, f"{via} não é do trecho do boss 4"


def test_cada_trecho_termina_no_ponto_de_luta():
    """O ponto de luta É o último waypoint do trecho, sempre.

    Se divergirem, a rotina anda até o fim da rota e procura alvo em outro
    lugar -- sem erro nenhum aparecer.
    """
    for rotulo, caminho, posicao in m.TRECHOS_DOS_BOSSES:
        assert caminho[-1].pos == posicao, (
            f"o trecho do {rotulo} termina em {caminho[-1].pos}, "
            f"mas o ponto de luta é {posicao}")


def test_a_anotacao_do_lua_fica_perto_do_ponto_de_luta():
    """Nos bosses 1 e 2 a anotação do `hh.lua` está 2,24 à frente do waypoint.

    QUEM MANDA É O WAYPOINT: a anotação é onde o boss ESTÁ, e o waypoint é de
    onde se bate nele. Usar a anotação como destino mandaria o bot tentar andar
    para dentro do boss -- clique que não produz movimento, e que acorda o
    detector de travamento sem haver trava.

    O teto de 3 é o que separa "de onde se bate" de "outro lugar da cave".
    """
    for rotulo, _, posicao in m.TRECHOS_DOS_BOSSES:
        anotada = m.COORDENADA_ANOTADA_NO_LUA[rotulo]
        assert m.distancia(posicao, anotada) <= 3, (
            f"{rotulo}: ponto de luta {posicao} vs anotacao {anotada}")


def test_os_trechos_sao_continuos():
    """O começo de um trecho tem de estar PERTO do fim do anterior.

    O caminho do boss 4 anda para trás sobre o do boss 3 -- isso é medição, não
    erro --, então o critério é distância e não igualdade. O que este teste
    barra é um trecho começar do outro lado da cave, que é o sintoma de alguém
    ter colado a lista errada.
    """
    trechos = [c for _, c, _ in m.TRECHOS_DOS_BOSSES] + [m.CAMINHO_ATE_A_SAIDA]
    for anterior, seguinte in itertools.pairwise(trechos):
        salto = m.distancia(anterior[-1].pos, seguinte[0].pos)
        assert salto <= 40, (
            f"salto de {salto:.0f} entre {anterior[-1].pos} e "
            f"{seguinte[0].pos}: trechos descontínuos")


def test_o_ponto_de_mobs_esta_na_rota():
    """(232, 188) é caso especial em dois lugares do Lua; some da rota, some a
    razão de o tratamento existir."""
    pontos = {wp.pos for wp in m.TODOS_OS_WAYPOINTS}
    for ponto in m.WAYPOINTS_PROBLEMATICOS:
        assert ponto in pontos, f"{ponto} não está em nenhum trecho"


# ===========================================================================
# A honestidade do que NÃO foi medido
# ===========================================================================


def test_a_area_interna_continua_marcada_como_nao_medida():
    """ESTE TESTE VAI FALHAR DE PROPÓSITO quando a área for medida.

    Quando isso acontecer, o certo é apagar este teste e ligar o de baixo -- não
    afrouxar este. O marcador existe para que ninguém confunda "não sei" com
    "sei que é isto", e a hora de trocar é quando houver medição, não quando o
    teste incomodar.
    """
    assert not m.area_medida(), (
        "TODAS as áreas internas da HH aparecem como medidas. Se foram medidas "
        "de verdade, apague este teste e atualize docs/decisoes/hh.md seção 9.")

    # O INVENTÁRIO DO QUE JÁ FOI MEDIDO É EXPLÍCITO, e é ele que impede o
    # afrouxamento: um nome novo aqui só entra junto com a linha que diz de que
    # print ele saiu. Medidos em 03/09/2026, nos prints do usuário.
    assert m.areas_medidas() == {(527, 124): "Happiness Hall Main Hall"}, (
        "alguém nomeou uma área da HH sem registrar a medição -- ver o "
        "cabeçalho de mapa_hh.py e docs/decisoes/hh.md seção 9")
    assert all(wp.area == m.AREA_INTERNA_NAO_MEDIDA
               for wp in m.TODOS_OS_WAYPOINTS
               if wp.pos not in m.areas_medidas())


def test_o_interior_da_HH_tem_MAIS_DE_UMA_area():
    """Os dois nomes medidos são diferentes, e isso descarta uma hipótese.

    Se a instância inteira tivesse um nome só, dava para confirmar "estou
    dentro" pelo nome. Ela não tem: a chegada é `Happiness Hall Dungeon` e a
    saída é `Happiness Hall Main Hall`. Por isso quem responde "estou dentro" é
    a COORDENADA (`esta_dentro_da_hh`), como o bot em Lua já fazia.
    """
    assert m.ROTULO_DE_TELA_DA_CHEGADA != m.AREA_DA_SAIDA
    assert m.ROTULO_DE_TELA_DA_CHEGADA != m.LUGAR_FORA_DA_HH
    assert m.AREA_DA_SAIDA != m.LUGAR_FORA_DA_HH


def test_os_nomes_de_Happiness_Hall_sao_da_TELA_e_nao_do_PONTEIRO():
    """Registrado porque foi tratado errado uma vez, em 03/09/2026.

    O ponteiro devolve `Black Wind Camp Dungeon` DENTRO e FORA da cave -- a
    linha do log que confirma a entrada diz *"(55, 33) | local Black Wind Camp
    Dungeon"*. Os nomes `Happiness Hall *` são o rótulo do canto da TELA.

    A consequência é a regra: quem responde "dentro ou fora" é a COORDENADA.
    """
    assert m.LUGAR_FORA_DA_HH == "Black Wind Camp Dungeon"
    # o nome NÃO decide -- o mesmo nome com coordenadas opostas dá etapas
    # opostas
    assert m.etapa_pelo_lugar(m.LUGAR_FORA_DA_HH, (55, 33)) == m.ETAPA_DENTRO
    assert (m.etapa_pelo_lugar(m.LUGAR_FORA_DA_HH, (-343, -288))
            == m.ETAPA_NA_PORTA)
    # e nenhum `Happiness Hall *` participa da decisão
    import inspect

    corpo = inspect.getsource(m.etapa_pelo_lugar)
    assert "Happiness" not in corpo


def test_o_marcador_e_visivel():
    """Marcador que parece nome de lugar de verdade não avisa ninguém."""
    assert "não medida" in m.AREA_INTERNA_NAO_MEDIDA


# ===========================================================================
# A caixa da cave
# ===========================================================================


def test_a_caixa_vem_dos_waypoints_e_nao_da_mao():
    xs = [wp.x for wp in m.TODOS_OS_WAYPOINTS]
    ys = [wp.y for wp in m.TODOS_OS_WAYPOINTS]
    assert m.CAIXA_DA_HH == (
        (min(xs) - m.FOLGA_DA_CAIXA, min(ys) - m.FOLGA_DA_CAIXA),
        (max(xs) + m.FOLGA_DA_CAIXA, max(ys) + m.FOLGA_DA_CAIXA))


def test_todo_waypoint_cabe_na_caixa():
    for wp in m.TODOS_OS_WAYPOINTS:
        assert m.posicao_esta_na_caixa_da_hh(wp.pos), f"{wp.pos} fora da caixa"


def test_a_entrada_esta_fora_da_caixa():
    """A entrada é FORA da cave. Se caísse na caixa, o bot não distinguiria
    'estou na porta' de 'estou dentro'."""
    assert not m.posicao_esta_na_caixa_da_hh(m.PONTO_DA_ENTRADA)


# ===========================================================================
# Dentro vs fora, pelo sinal da coordenada
# ===========================================================================


@pytest.mark.parametrize("pos,dentro", [
    (m.CHEGADA_NA_HH, True),
    (m.POSICAO_DO_BOSS_1, True),
    (m.POSICAO_DO_BOSS_4, True),
    (m.PONTO_DA_ENTRADA, False),
    (m.POSICAO_DA_MUTUAL, False),
    ((-344, -297), False),      # o ponto do vendedor no bot Lua
    (None, False),
])
def test_dentro_da_hh_pelo_sinal(pos, dentro):
    assert m.esta_dentro_da_hh(pos) is dentro


def test_a_posicao_da_fada_e_dentro_da_cave():
    """A Fada acompanha o personagem DENTRO da cave no modo HH+Fada."""
    assert m.esta_dentro_da_hh(m.POSICAO_DA_FADA_NO_BOSS)


# ===========================================================================
# A rota de chegada
# ===========================================================================


def test_a_entrada_bate_com_a_ancora_do_bot_lua():
    """O bot Lua entra de (-342, -286) e roda hoje em produção.

    A coordenada do usuário e a dele concordam, e é essa a confirmação mais
    forte disponível sem remedir. Divergir muito daqui significa que alguém
    trocou o ponto sem medir.
    """
    assert m.distancia(m.PONTO_DA_ENTRADA, (-342, -286)) <= 4


def test_o_ponto_de_conversa_nao_e_o_do_npc():
    """Não se clica de fora do ponto -- mas também não se fica em cima do NPC.

    O painel de arredores caminha até PERTO da Mutual; o ponto de conversa é
    outro, e a diferença entre os dois é o motivo de existir um passo de
    encostar.
    """
    assert m.PONTO_DA_ENTRADA != m.POSICAO_DA_MUTUAL
    assert m.distancia(m.PONTO_DA_ENTRADA, m.POSICAO_DA_MUTUAL) > \
        m.PRECISAO_NO_PONTO_DA_ENTRADA


def test_o_destino_do_transporte_e_o_que_precisa_rolar():
    """`West Suburb of Stone City` só aparece rolando a lista do Fay.

    Trocar isto por um destino da parte visível da lista (como o Ghost Din Woods
    da BC) mandaria as contas da HH para a cave errada.
    """
    assert m.DESTINO_DO_TRANSPORTE == "West Suburb of Stone City"
    assert m.NPC_DE_TRANSPORTE[1] == "Transport Fay"


def test_o_vendedor_nao_e_o_da_bc():
    """A HH vende no Roaming Apothecary, fora da cave -- não no Rich Man."""
    assert m.NPC_VENDEDOR[1] == "Roaming Apothecary"
    assert "Rich" not in m.NPC_VENDEDOR[0]


# ===========================================================================
# O modelo compartilhado com a BC (`core/rota.py`)
# ===========================================================================


def test_a_hh_usa_o_MESMO_waypoint_da_bc():
    """Duas classes Waypoint seriam duas noções de rota, e a navegação
    promovida ao core precisa de UMA."""
    from blazesbot.bot.bc import mapa_bc

    assert m.Waypoint is Waypoint is mapa_bc.Waypoint


def test_o_montar_remove_repeticao_consecutiva():
    """A medição da BC produziu (156,-406) duas vezes seguidas: o bot considera
    o primeiro alcançado, clica no segundo, não há movimento para observar e o
    detector de travamento dispara sem haver trava."""
    feito = montar([(1, 1, "a"), (1, 1, "a"), (2, 2, "a"), (1, 1, "a")])
    assert [wp.pos for wp in feito] == [(1, 1), (2, 2), (1, 1)]


def test_o_montar_aceita_com_e_sem_via():
    """A BC não tem clique calibrado; a HH tem em todos. O mesmo `montar`
    atende os dois, e ausência de `via` é ausência, não erro."""
    feito = montar([(1, 1, "a"), (2, 2, "a", (900, 100))])
    assert feito[0].via is None
    assert feito[1].via == (900, 100)


# ===========================================================================
# O MOTOR DE ROTA É UM SÓ (`core/rota.py`), os DADOS são de cada cave
# ===========================================================================


def test_as_duas_caves_chamam_o_mesmo_motor():
    """Duas implementações da retomada seriam duas chances de só uma ser
    corrigida. A regra mora no core; `mapa_bc` e `mapa_hh` só injetam dados."""
    from blazesbot.bot.bc import mapa_bc
    from blazesbot.core import rota

    for nome in ("mais_proximos", "vizinhos_na_rota", "distancia",
                 "Retomada", "Waypoint"):
        assert getattr(mapa_bc, nome) is getattr(rota, nome)
        assert getattr(m, nome) is getattr(rota, nome)


def test_a_retomada_da_hh_nao_recua_para_o_inicio_da_area():
    """A HH NÃO passa `areas_apertadas`, e isso é deliberado.

    O recuo "volte ao início da área" só faz sentido quando se sabe onde a área
    começa. Aqui a área é um MARCADOR: todos os waypoints têm o mesmo texto, e
    passá-lo como apertado mandaria o bot de volta ao waypoint 1 da cave inteira
    sempre que ele escorregasse -- desfazendo a run.
    """
    caminho = m.CAMINHO_ATE_O_BOSS_1
    # Fora da rota, no fim dela. A cave é sinuosa, então o waypoint mais próximo
    # de um ponto qualquer não é necessariamente o último -- o que se exige aqui
    # é que a retomada escolha O MAIS PRÓXIMO e não volte ao começo.
    longe = (caminho[-1].x + 30, caminho[-1].y + 30)
    r = m.onde_retomar(longe, caminho)

    esperado, _ = m.mais_proximos(longe, caminho)[0]
    assert r.indice in (esperado, esperado + 1), (
        f"retomou no waypoint {r.indice + 1}/{len(caminho)}, e o mais próximo "
        f"é o {esperado + 1}")
    assert r.indice > 0, "recuou para o começo da cave"
    assert "apertada" not in r.motivo


def test_a_retomada_da_bc_continua_recuando_na_area_apertada():
    """O contrário do teste acima, no mesmo motor: a BC injeta as áreas e o
    recuo do Secret Altar continua valendo. Se este quebrar, a promoção levou
    embora um comportamento medido."""
    from blazesbot.bot.bc import mapa_bc

    rota_altar = mapa_bc.CAMINHO_ATE_O_ALTAR
    primeiro_altar = next(i for i, wp in enumerate(rota_altar)
                          if wp.area == "Secret Altar")
    # Fora da rota, mas mais perto de um waypoint do meio do Secret Altar.
    meio = rota_altar[primeiro_altar + 4]
    fora = (meio.x + 20, meio.y + 20)
    r = mapa_bc.onde_retomar(fora, rota_altar)
    assert r.indice == primeiro_altar, (
        f"retomou em {r.indice}, esperado o início do Secret Altar "
        f"({primeiro_altar})")
    assert "apertada" in r.motivo


def test_a_tolerancia_da_hh_sobe_no_ponto_de_mobs():
    """(232, 188) é onde os mobs seguram o personagem: chegar ali exige folga."""
    ponto = m.WAYPOINTS_PROBLEMATICOS[0]
    problematico = next(wp for wp in m.TODOS_OS_WAYPOINTS if wp.pos == ponto)
    outro = next(wp for wp in m.TODOS_OS_WAYPOINTS if wp.pos != ponto)

    assert m.tolerancia_do_waypoint(problematico, 3, 8) == 8
    assert m.tolerancia_do_waypoint(outro, 3, 8) == 3


def test_o_rollback_vale_igual_nas_duas():
    """Mesma função, mesma folga: voltar 2+ waypoints é rollback."""
    caminho = m.CAMINHO_ATE_O_BOSS_1
    assert m.houve_rollback(10, caminho[5].pos, caminho) == 5
    assert m.houve_rollback(10, caminho[10].pos, caminho) is None
    assert m.houve_rollback(10, caminho[9].pos, caminho) is None   # folga
    assert m.houve_rollback(10, None, caminho) is None


# ===========================================================================
# Os dois LOOPS INFINITOS de 03/09/2026
# ===========================================================================
#
# Os dois foram o MESMO defeito, em duas geometrias diferentes: `houve_rollback`
# perguntava "qual waypoint está mais perto" quando a pergunta é "o personagem
# foi jogado para trás". Ver a explicação inteira em `core/rota.houve_rollback`.
#
# O teste usa a rota REAL da HH de propósito: o defeito era do encontro entre a
# régua e ESTES pontos, e um caminho sintético não guardaria isso.

def _indice_do(caminho, ponto):
    for i, w in enumerate(caminho):
        if w.pos == ponto:
            return i
    raise AssertionError(f"{ponto} não está mais na rota; o teste ficou velho")


@pytest.mark.parametrize("trecho,anterior,alvo,posicao,por_que", [
    # Trecho 1: wp10 e wp11 estão a 4,5 unidades -- menos que a tolerância de
    # chegada (7). O bot cruza os dois de uma vez e o mais próximo continua
    # sendo o 10, com o índice já no 12.
    (0, (207, 186), (232, 188), (211, 184),
     "wp10 e wp11 cabem no mesmo raio de tolerância"),
    # Trecho 4: wp13 é uma ESPORA -- desce 19 para subir 33. Voltando por cima
    # do corredor, o wp12 vira o mais próximo.
    (3, (510, 126), (509, 93), (509, 115),
     "a rota volta pelo mesmo corredor da espora do wp13"),
])
def test_andar_no_rumo_certo_NAO_e_rollback(trecho, anterior, alvo, posicao,
                                            por_que):
    """O bot ia e voltava para sempre nestes dois pontos. Medido no log.

    Em ambos o personagem estava indo para onde mandaram -- em cima da reta que
    liga o waypoint anterior ao alvo. O que estava errado era a régua.
    """
    caminho = m.TRECHOS_DOS_BOSSES[trecho][1]
    i_alvo = _indice_do(caminho, alvo)
    assert caminho[i_alvo - 1].pos == anterior, (
        "a ordem da rota mudou; conferir se o loop volta com ela")

    assert distancia_ao_trecho(posicao, anterior, alvo) <= 12.0, (
        f"{posicao} deveria estar EM CIMA do trecho {anterior}->{alvo}")
    assert houve_rollback(i_alvo, posicao, caminho) is None, (
        f"loop infinito de volta: {por_que}")


def test_rollback_DE_VERDADE_continua_sendo_pego():
    """O conserto não pode ter desligado a detecção.

    Personagem no meio do trecho 1 e jogado de volta para um waypoint bem
    anterior: longe do trecho atual E perto de um índice de trás. As duas
    coisas, que é o que o teleporte tem e o andar normal não.
    """
    caminho = m.TRECHOS_DOS_BOSSES[0][1]
    i_alvo = _indice_do(caminho, (232, 188))
    atras = caminho[i_alvo - 4].pos
    assert houve_rollback(i_alvo, atras, caminho) == i_alvo - 4


def test_nenhum_par_da_rota_e_uma_ESPORA_sem_aviso():
    """Inventário dos pontos que a régua nova protege.

    Não reprova a espora -- ela é legítima, o bot em Lua usa os mesmos pontos e
    o `via` de cada um é diferente (o ponto existe para virar a direção do
    clique, não para andar). O que o teste faz é manter o inventário à vista:
    se um trecho novo trouxer outro, o número aqui muda e quem mexeu vê por quê.
    """
    apertados = [
        (rotulo, c[i - 1].pos, c[i].pos)
        for rotulo, c, _p in m.TRECHOS_DOS_BOSSES
        for i in range(1, len(c))
        if m.distancia(c[i - 1].pos, c[i].pos) < 7
    ]
    assert apertados == [("Fa-Yuan", (209, 182), (207, 186))], (
        f"o inventário de pares apertados mudou: {apertados}")
