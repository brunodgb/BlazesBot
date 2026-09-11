"""A saída da HH mira o ponto EXATO -- uma unidade de folga custa 86% de falha.

=========================================================================
O RELATO
=========================================================================

Usuário, 11/09/2026:

> *"No waypoint de saída da HH está falhando às vezes, no caso nem sempre está
> abrindo o diálogo com o NPC, pois está variando a posição, é importante
> aumentar a precisão do X e Y do último waypoint pois assim ajuda a garantir
> que vai sair da cave, isso é um ponto crucial não ficar travado."*

=========================================================================
A MEDIÇÃO QUE LHE DEU RAZÃO -- 122 SAÍDAS DE PRODUÇÃO
=========================================================================

Cruzando a posição em que a perna fina parou com o desfecho da tentativa:

    posição fina    saiu   falhou   % de falha
    (527, 124)        50        0          0%   <- o ponto medido
    (527, 125)         8        1         11%
    (526, 123)         1        4         80%
    (527, 123)         8       48         86%   <- UMA unidade de folga

Uma unidade em Y multiplica a falha por oitenta. E (527,123) está a distância
1,0 do alvo, ou seja DENTRO da folga de 1,5 -- a navegação parava ali e
declarava chegada.

O preço disso no log: entre 01h e 04h do dia 11/09 foram **29 runs seguidas sem
sair da cave**, cada uma gastando 5 minutos e 18 tentativas de 18 segundos.

=========================================================================
O QUE ESTE ARQUIVO PROTEGE
=========================================================================

1. A CAMINHADA mira o ponto exato; QUEM CLICA continua com a folga de 1,5.
   São duas perguntas diferentes e não podem voltar a ser o mesmo número.
2. A mira é menor que 1,0 -- com posição inteira, é isso que significa "o
   ponto, e nenhum vizinho".
3. Falhar em encostar NÃO impede o clique: o pior caso novo é o antigo.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from blazesbot.bot.hh import entrada, mapa_hh
from blazesbot.core.rota import distancia

# O que foi medido em produção em 11/09/2026, para o teste falar em números.
MEDIDO = {
    (527, 124): (50, 0),
    (527, 125): (8, 1),
    (526, 123): (1, 4),
    (527, 123): (8, 48),
}


# ===========================================================================
# 1. Duas réguas, duas perguntas
# ===========================================================================


def test_a_mira_e_MAIS_APERTADA_que_a_regua_de_quem_clica():
    """*"onde eu quero parar?"* não é *"posso clicar daqui?"*.

    A de clicar protege do outro NPC que mora perto (medido em 04/09/2026) e
    por isso é generosa. A de andar decide de onde o clique sai, e ali só o
    ponto medido funciona.
    """
    assert entrada.MIRA_NO_PONTO_DA_SAIDA < mapa_hh.PRECISAO_NO_PONTO_DA_SAIDA


def test_a_mira_exclui_TODO_vizinho_de_uma_unidade():
    """Com posição inteira, qualquer valor abaixo de 1,0 quer dizer o mesmo.

    E é preciso que queira: (527,123) está a exatamente 1,0 do alvo e é a
    posição que falhou 48 de 56 vezes.
    """
    alvo = mapa_hh.PONTO_DA_SAIDA
    for pos, (saiu, falhou) in MEDIDO.items():
        dentro = distancia(pos, alvo) <= entrada.MIRA_NO_PONTO_DA_SAIDA
        if pos == alvo:
            assert dentro, "a mira rejeitou o próprio ponto medido"
            continue
        assert not dentro, (
            f"a mira ({entrada.MIRA_NO_PONTO_DA_SAIDA}) aceita {pos}, que em "
            f"produção falhou {falhou} de {saiu + falhou} vezes")


def test_a_folga_ANTIGA_aceitava_a_posicao_que_falhava():
    """O teste de regressão propriamente dito: é isto que mudou."""
    ruim = (527, 123)
    assert distancia(ruim, mapa_hh.PONTO_DA_SAIDA) <= (
        mapa_hh.PRECISAO_NO_PONTO_DA_SAIDA), (
        "a folga de clicar deixou de conter (527,123) -- então este teste "
        "perdeu o sentido e a medição de 11/09/2026 precisa ser refeita")


def test_a_posicao_pior_e_a_que_a_mira_agora_rejeita():
    pior = max(MEDIDO, key=lambda p: MEDIDO[p][1] / sum(MEDIDO[p]))
    assert pior == (527, 123)
    assert distancia(pior, mapa_hh.PONTO_DA_SAIDA) > (
        entrada.MIRA_NO_PONTO_DA_SAIDA)


# ===========================================================================
# 2. A caminhada usa a mira; o clique usa a folga
# ===========================================================================


def _reguas_lidas(func) -> set[str]:
    """As réguas citadas no CÓDIGO -- pelo AST, nunca pelo texto.

    A docstring de `garantir_coordenada_da_saida` cita as duas para explicar a
    diferença entre elas, então contar no texto acharia as duas em qualquer um
    dos dois caminhos.

    Uma mora em `mapa_hh` (`Attribute`) e a outra no próprio `entrada`
    (`Name`), então as duas formas entram.
    """
    arvore = ast.parse(textwrap.dedent(inspect.getsource(func)))
    nomes = {n.attr for n in ast.walk(arvore)
             if isinstance(n, ast.Attribute)
             and getattr(n.value, "id", "") == "mapa_hh"}
    nomes |= {n.id for n in ast.walk(arvore) if isinstance(n, ast.Name)}
    return nomes


def test_a_mira_mora_junto_dos_irmaos_de_posicionamento():
    """`mapa_hh` diz ONDE o ponto fica; `entrada` diz QUANTO se insiste nele.

    É onde já moram `TENTATIVAS_DE_POSICIONAR` e
    `SEGUNDOS_POR_TENTATIVA_DE_ENCOSTAR`, os outros dois knobs da mesma volta.
    """
    assert not hasattr(mapa_hh, "MIRA_NO_PONTO_DA_SAIDA")
    for irmao in ("TENTATIVAS_DE_POSICIONAR",
                  "SEGUNDOS_POR_TENTATIVA_DE_ENCOSTAR"):
        assert hasattr(entrada, irmao)


def test_a_caminhada_da_saida_mira_o_ponto_exato():
    lidas = _reguas_lidas(entrada.EntradaDaHH.garantir_coordenada_da_saida)

    assert "MIRA_NO_PONTO_DA_SAIDA" in lidas, (
        "a caminhada voltou a parar na folga de quem clica")
    assert "PRECISAO_NO_PONTO_DA_SAIDA" not in lidas


def test_QUEM_CLICA_continua_com_a_folga_de_um_e_meio():
    """Apertar aqui seria pior que o defeito: das 17 saídas que aconteceram de
    (527,123) e (527,125), nenhuma teria sido tentada."""
    lidas = _reguas_lidas(entrada.EntradaDaHH.tentar_sair_da_hh)

    assert "PRECISAO_NO_PONTO_DA_SAIDA" in lidas
    assert "MIRA_NO_PONTO_DA_SAIDA" not in lidas, (
        "a régua de clicar apertou junto -- e aí a tentativa é PULADA em vez "
        "de acontecer de um ponto pior")


def test_nao_encostar_NAO_impede_o_clique():
    """`encostar_no_ponto` devolve False e a vida segue.

    É o que garante que o pior caso novo é o comportamento antigo, e não uma
    run presa esperando uma casa decimal.
    """
    arvore = ast.parse(textwrap.dedent(
        inspect.getsource(entrada.EntradaDaHH.garantir_coordenada_da_saida)))
    metodo = arvore.body[0]

    assert isinstance(metodo.body[-1], ast.Return), (
        "o método deixou de apenas devolver o resultado de encostar")

    from blazesbot.bot.hh.routine import HHRoutine
    fonte = inspect.getsource(HHRoutine._falar_com_o_npc_da_saida)
    laco = ast.parse(textwrap.dedent(fonte)).body[0]
    ifs = [n for n in ast.walk(laco) if isinstance(n, ast.If)
           and "garantir_coordenada_da_saida" in ast.unparse(n.test)]
    assert not ifs, (
        "a rotina passou a abortar a tentativa quando não consegue encostar -- "
        "e clicar de (527,123) ainda saiu 8 vezes, contra 0 de não clicar")


# ===========================================================================
# 3. O ponto medido não se move sozinho
# ===========================================================================


def test_o_ponto_da_saida_continua_sendo_o_medido():
    """A mira só vale enquanto o alvo for o ponto de onde o NPC foi medido."""
    assert mapa_hh.PONTO_DA_SAIDA == (527, 124)
    assert mapa_hh.CAMINHO_ATE_A_SAIDA[-1].x == 527
    assert mapa_hh.CAMINHO_ATE_A_SAIDA[-1].y == 124
