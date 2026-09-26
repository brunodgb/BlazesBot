"""A CATRACA DA ESPERA CEGA: o número de `FIXO` pode cair, nunca subir.

=============================================================================
POR QUE UMA CATRACA, E NÃO UMA PROIBIÇÃO
=============================================================================

Proibir espera cega quebraria o bot: existem esperas que **não têm o que
perguntar** -- o `hold` entre o KEYDOWN e o KEYUP (o jogo ignora tecla de
duração zero), o respiro antes do botão Sell (o cliente ainda está digerindo 24
cliques), a cadência de uma skill. Essas são exceções justificadas, e cada uma
tem a justificativa escrita no código.

O que não pode acontecer é a lista CRESCER sem ninguém perceber. Espera cega
nova é a forma mais fácil de "resolver" um defeito de sincronismo, e a mais cara
de descobrir depois: ela não dá erro, só come APM para sempre.

Então a catraca: mexeu e o número caiu, o teste atualiza o piso (e a próxima
pessoa não pode voltar atrás). Mexeu e subiu, o teste reprova e pergunta o que
foi que não deu para perguntar.

=============================================================================
A SAÍDA QUANDO A ESPERA É INEVITÁVEL
=============================================================================

Não é burlar o teste -- é ler `core/espera.py`. Se existe QUALQUER observável
(memória, template, posição, o campo mexer), a espera vira `espera.ate(...)` e
some daqui sozinha, porque deixa de ser FIXO. Se não existe mesmo, suba o número
NESTE arquivo, no mesmo commit, com a justificativa na mensagem.

O catálogo completo, com a natureza de cada tempo, é `docs/TEMPOS.md` (gerado).
"""
from __future__ import annotations

from collections import Counter

import pytest

from blazesbot.core.indice_de_tempos import extrair

# QUANTAS ESPERAS CEGAS CADA MÓDULO TINHA EM 11/09/2026, medido pelo mesmo
# extrator que gera o `docs/TEMPOS.md`. Só entram os módulos do caminho quente
# -- onde espera cega custa APM; o resto do projeto (ferramentas, GUI) não
# entra na catraca porque ali o relógio não disputa com o jogo.
TETO_DE_ESPERAS_CEGAS = {
    "blazesbot/bot/combate.py": 36,
    "blazesbot/bot/navegacao.py": 28,
    "blazesbot/bot/app/executor.py": 16,
    "blazesbot/bot/ui_do_jogo.py": 14,
    # 8 -> 7 + 1 em 25/09/2026: a confirmação espaçada do slot vazio mudou de
    # arquivo junto com a leitura (`bot/leitura_do_slot.py`); o total não mudou.
    "blazesbot/bot/vendedor.py": 7,
    "blazesbot/bot/leitura_do_slot.py": 1,
    "blazesbot/core/inputs.py": 7,
    "blazesbot/bot/bc/routine.py": 7,
    "blazesbot/bot/bc/vendor.py": 6,
    "blazesbot/bot/hh/routine.py": 3,
    "blazesbot/bot/hh/entrada.py": 1,
}

# O TOTAL do projeto inteiro, incluindo o que não está na tabela acima.
#
# 250 -> 251 em 19/09/2026, e a subida tem nome: `tools/empacotar.py` espera 3 s
# entre as tentativas de apagar a pasta da entrega anterior. Ela é cega só para
# o extrator, que enxerga o `time.sleep` e não o laço em volta: a PERGUNTA é o
# próprio `shutil.rmtree` da volta seguinte, e o que se espera é o Windows
# soltar o handle do `.exe` de 9 MB que o antivírus está varrendo -- evento sem
# observável nenhum do lado de cá. E é ferramenta de empacotar, não caminho
# quente: ali o relógio não disputa com o jogo.
# 251 -> 252 em 22/09/2026: `login.ESPERA_PELO_SERVIDOR_FORA_DO_AR`, os 30 s
# entre uma ida à lista de servidores e a seguinte quando o servidor da conta
# não está nela.
#
# NÃO TEM OBSERVÁVEL, e é por isso que ela é cega de verdade: durante a espera a
# tela é a de LOGIN, e a única forma de saber se o servidor voltou é autenticar
# de novo e abrir a lista -- que é exatamente o custo que a espera existe para
# não pagar. Sem ela o laço deu 854 idas em 9 minutos, sete contas
# reautenticando duas vezes por segundo contra um servidor fora do ar.
TETO_GERAL = 252


def _por_arquivo() -> Counter:
    contagem: Counter = Counter()
    for tempo in extrair():
        if tempo.natureza == "FIXO":
            contagem[tempo.arquivo] += 1
    return contagem


@pytest.mark.parametrize("arquivo,teto", sorted(TETO_DE_ESPERAS_CEGAS.items()))
def test_o_modulo_nao_ganhou_espera_cega_nova(arquivo, teto):
    """Subiu? Diga o que não deu para perguntar -- ver `core/espera.py`."""
    atual = _por_arquivo()[arquivo]
    assert atual <= teto, (
        f"{arquivo}: {atual} esperas CEGAS, contra {teto} em 11/09/2026. "
        f"Toda espera com observável deve virar `espera.ate(...)`; se esta não "
        f"tem observável nenhum, suba o número em "
        f"`tests/test_catraca_da_espera_cega.py` no mesmo commit, com o porquê "
        f"na mensagem.")


def test_o_projeto_inteiro_nao_ganhou_espera_cega_nova():
    atual = sum(_por_arquivo().values())
    assert atual <= TETO_GERAL, (
        f"{atual} esperas cegas no projeto, contra {TETO_GERAL} em "
        f"11/09/2026. A conta subiu em algum módulo fora da tabela.")


def test_a_catraca_APERTA_quando_o_numero_cai():
    """O piso não pode ficar folgado: quem converteu uma espera trava o ganho.

    Este teste é o que impede a catraca de virar enfeite. Ele reprova quando um
    módulo tem MENOS espera cega do que a tabela diz -- e o conserto é baixar o
    número, no mesmo commit da conversão.
    """
    contagem = _por_arquivo()
    folgados = {arq: (teto, contagem[arq])
                for arq, teto in TETO_DE_ESPERAS_CEGAS.items()
                if contagem[arq] < teto}
    assert not folgados, (
        "estes módulos têm MENOS espera cega que a tabela: "
        + ", ".join(f"{arq} (tabela {teto}, real {real})"
                    for arq, (teto, real) in folgados.items())
        + ". Baixe os números — o ganho só fica travado depois disso.")
