"""A ida do teleporte até a porta da HH, e o que fazer quando o painel falha.

=========================================================================
AS DUAS REGRAS DO USUÁRIO (08/09/2026)
=========================================================================

1. *"O bot deve caminhar pelo minimapa até as coordenadas X: -268, Y: -488. Em
   seguida, abrir o Surroundings e selecionar Mutual."*

   O teleporte da Fay espalha o ponto de chegada, e o painel de arredores é um
   clique POSICIONAL: abrir de onde o teleporte largou dá resultado diferente a
   cada run. Andar até um ponto fixo antes é o que torna a busca repetível.

2. *"Se o bot desviar, parar no meio do caminho ou não chegar na porta de HH, o
   sistema deve abortar a espera, reabrir o Surroundings, clicar em Mutual
   novamente."*

   Antes disso `ir_para_resultado` devolvia `False` e a rotina falhava o estado
   inteiro -- voltava para `RECUPERAR`, se situava, e refazia a viagem desde
   Stone City. O laço refaz só o que falhou.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from blazesbot.bot.hh import mapa_hh
from blazesbot.bot.hh.entrada import EntradaDaHH


def _chamadas(metodo) -> list[str]:
    """Os nomes chamados, NA ORDEM DO ARQUIVO.

    Ordenado por (linha, coluna) e não pela ordem de `ast.walk`: ela é
    largura-primeiro e devolve os nós fora da ordem do texto. Escrito sem isto,
    este helper afirmou que `encostar_no_ponto` vinha antes de
    `esperar_a_chegada` -- e vinha, na árvore, não no arquivo.
    """
    arvore = ast.parse(textwrap.dedent(inspect.getsource(metodo)))
    nos = [(n.lineno, n.col_offset,
            getattr(n.func, "attr", getattr(n.func, "id", "")))
           for n in ast.walk(arvore) if isinstance(n, ast.Call)]
    return [nome for _l, _c, nome in sorted(nos)]


# ===========================================================================
# O ponto fixo de onde o painel é aberto
# ===========================================================================


def test_o_ponto_de_abrir_os_arredores_e_o_medido():
    assert mapa_hh.PONTO_PARA_ABRIR_OS_ARREDORES == (-268, -488)


def test_a_precisao_dele_e_FOLGADA_e_nao_a_da_porta():
    """Aqui o ponto protege a abertura de um PAINEL, não um clique na cena 3D.

    Apertar como a porta (1,5) custaria tentativas de reposicionamento por nada.
    """
    assert (mapa_hh.PRECISAO_PARA_ABRIR_OS_ARREDORES
            > mapa_hh.PRECISAO_NO_PONTO_DA_ENTRADA)


def test_a_ORDEM_e_minimapa_painel_minimapa():
    """Os três passos, e cada um resolve um problema diferente."""
    chamadas = _chamadas(EntradaDaHH.ir_ate_o_npc_da_hh)
    assert chamadas.index("_ir_ao_ponto_de_abrir_os_arredores") < \
        chamadas.index("_chegar_perto_da_mutual")
    assert chamadas.index("_chegar_perto_da_mutual") < \
        chamadas.index("garantir_coordenada_da_entrada")


def test_o_primeiro_passo_ESPERA_a_leitura_voltar():
    """Clique no minimapa durante a tela de carregamento é clique perdido."""
    chamadas = _chamadas(EntradaDaHH._ir_ao_ponto_de_abrir_os_arredores)
    assert chamadas.index("esperar_a_chegada") < chamadas.index(
        "encostar_no_ponto")


def test_o_primeiro_passo_anda_para_o_ponto_CERTO():
    fonte = inspect.getsource(EntradaDaHH._ir_ao_ponto_de_abrir_os_arredores)
    assert "mapa_hh.PONTO_PARA_ABRIR_OS_ARREDORES" in fonte
    assert "mapa_hh.PRECISAO_PARA_ABRIR_OS_ARREDORES" in fonte


def test_sem_leitura_de_posicao_o_passo_SEGUE():
    """"Não sei" não bloqueia: o painel ainda pode funcionar dali."""
    fonte = inspect.getsource(EntradaDaHH._ir_ao_ponto_de_abrir_os_arredores)
    depois = fonte[fonte.index("esperar_a_chegada"):]
    assert "return False" not in depois.split("encostar_no_ponto")[0]


# ===========================================================================
# O cão de guarda do destino
# ===========================================================================


def test_o_painel_e_tentado_MAIS_DE_UMA_VEZ():
    from blazesbot.bot.hh import entrada

    assert entrada.TENTATIVAS_DE_CHEGAR_PELA_MUTUAL > 1
    fonte = inspect.getsource(EntradaDaHH._chegar_perto_da_mutual)
    assert "for tentativa in range" in fonte


def test_QUEM_DECIDE_a_chegada_e_a_DISTANCIA_e_nao_o_painel():
    """O painel pode dizer que levou e largar o personagem no meio -- é o
    "desviar ou parar no meio" do relato."""
    chamadas = _chamadas(EntradaDaHH._chegar_perto_da_mutual)
    assert "position" in chamadas
    assert "distancia" in chamadas
    fonte = inspect.getsource(EntradaDaHH._chegar_perto_da_mutual)
    assert "mapa_hh.RAIO_DA_PORTA" in fonte


def test_o_painel_e_FECHADO_antes_de_reabrir():
    """Painel aberto por cima engole o clique seguinte, e o sintoma é uma busca
    que "não encontra" o NPC que está na lista."""
    fonte = inspect.getsource(EntradaDaHH._chegar_perto_da_mutual)
    trecho = fonte[fonte.index("for tentativa"):fonte.index("buscar_npc")]
    assert "fechar_dialogo" in trecho


def test_o_resultado_do_painel_NAO_aborta_mais_a_viagem():
    """`ir_para_resultado` devolvendo False agora é só mais uma volta do laço.

    Antes ele fazia `return False` na hora, e a rotina refazia a viagem desde
    Stone City.
    """
    fonte = inspect.getsource(EntradaDaHH._chegar_perto_da_mutual)
    assert "if not self.ir_para_resultado" not in fonte


def test_a_parada_responde_ENTRE_as_tentativas():
    """Três voltas de painel podem levar minutos; o Parar não pode esperar."""
    chamadas = _chamadas(EntradaDaHH._chegar_perto_da_mutual)
    assert "_guardar" in chamadas
    guarda = _chamadas(EntradaDaHH._guardar)
    assert "raise_if_stopped" in guarda
    assert "check_watchdog" in guarda


def test_tentativas_esgotadas_DEVOLVEM_False():
    """Painel que não leva a lugar nenhum não se resolve insistindo para
    sempre -- aí a rotina falha o estado, que é o certo."""
    fonte = inspect.getsource(EntradaDaHH._chegar_perto_da_mutual)
    assert fonte.rstrip().endswith("return False")
