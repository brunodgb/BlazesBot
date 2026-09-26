"""A LEITURA DO SLOT DA JANELA DE VENDA, POR IMAGEM: o slot N ficou vazio?

=========================================================================
DEPENDÊNCIA CRUZADA -- de onde veio, quem usa, o que NÃO veio
=========================================================================

Saiu de `bot/vendedor.py` em 25/09/2026 SEM MUDAR UMA LINHA DE LÓGICA: o arquivo
tinha passado do teto da catraca de tamanho (1068 contra 1028), e esta era a
parte coesa que dava para separar -- a leitura do slot por contraste de imagem,
que hoje nem roda (`vendedor.CONFERIR_SLOT_VAZIO = False`).

QUEM USA: `JanelaDeVenda`, como mixin -- e por herança a venda da BC
(`bc/vendor.py`) e a da HH (`hh/vendedor.py`). Mexer aqui mexe nas duas. O
contrato é o que a classe já tinha: quem herda fornece `ctx` e `_quadro()`.

O QUE FICOU EM `vendedor.py`, e por quê: o interruptor `CONFERIR_SLOT_VAZIO` e o
`_clicar_no_slot` que o lê. Os testes forçam o interruptor no módulo dele, e o
clique é o primitivo do laço de venda, não da leitura. As constantes daqui
continuam importáveis de `vendedor.py` pelo nome.
"""
from __future__ import annotations

import json
from itertools import pairwise
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context import BotContext

# COMO SE SABE QUE O SLOT ESTÁ VAZIO: pelo CONTRASTE DO MIOLO da célula.
#
# NÃO por casamento com um modelo de "slot vazio" -- isso foi tentado, medido e
# reprovado. O SLOT QUE O BOT CONFERE ESTÁ SEMPRE COM A BORDA AMARELA DE HOVER:
# o bot não move o cursor físico, mas `_prime_cursor` manda `WM_MOUSEMOVE` para
# a coordenada do clique antes de cada clique, então o jogo desenha a borda
# justamente no slot que se quer examinar. A borda ocupa boa parte do recorte e
# existe nos DOIS estados -- então é ELA que domina o casamento, não o conteúdo.
#
# Medido em produção (12:11 de 14/08/2026, log de dev):
#
#     slot CHEIO  -> nota 0.503     limiar 0.70
#     slot VAZIO  -> nota 0.708     margem: 0.008  <- ruído, não sinal
#
# A venda parou em 2 cliques de 66. E repetir a leitura não conserta: o 0.708 é
# ESTÁVEL, então 3, 10 ou 50 leituras seguidas dariam todas positivo.
#
# O miolo resolve porque a borda fica FORA dele. Ícone de item é colorido e
# cheio de detalhe; slot vazio é quase liso. Medido nas fotos reais deste
# cliente (24 células cheias e 24 vazias da MESMA janela, mais os dois modelos):
#
#     slot CHEIO           : 46.75 no pior caso, mediana 60.11
#     slot VAZIO com hover :  9.76
#     slot VAZIO limpo     :  3.69   (mediana das células vazias: 2.25)
#
# Vão de 37 pontos, contra os 0.008 do casamento.
#
# 24 e não 28: a 28 a borda de hover começa a entrar no recorte e o MESMO modelo
# de slot vazio salta de 9.76 para 57.80 -- voltaria a confundir tudo.
LADO_DO_MIOLO_DA_CELULA = 24

# Abaixo disto o slot está vazio. Fica a 2,5x do pior vazio (9.76) e a menos da
# metade do pior cheio (46.75) -- longe dos dois lados, que é o que faltava.
CONTRASTE_QUE_E_SLOT_VAZIO = 25.0

# Quantas leituras VAZIAS SEGUIDAS encerram a venda. **SEMPRE NO MESMO SLOT** --
# o que está sendo clicado, e nenhum outro. Qualquer leitura COM ITEM zera a
# contagem: item na grade é prova de que não acabou.
#
# TRÊS, e não uma nem duas. A leitura acontece ~30 ms depois do clique, e nesse
# instante os itens ainda estão SUBINDO para preencher o buraco: um quadro pego
# aí mostra o slot vazio sem ele estar.
LEITURAS_VAZIAS_PARA_PARAR = 6
# As leituras de confirmação são ESPAÇADAS, não coladas: veja
# `_confirmar_slot_vazio`. Sem espaço entre elas as três caem dentro do mesmo
# vão de rearranjo e a venda para no começo.
ESPERA_PARA_CONFIRMAR_VAZIO = 0.5

# ===========================================================================
# INTERRUPTOR -- A MEDIÇÃO DA ROLHA (25/09/2026). SÓ REGISTRA, não decide nada.
# ===========================================================================
#
# A ROLHA: o primeiro item INVENDÁVEL que chega ao slot N não sai do lugar, os
# cliques seguintes batem nele, e a lista da passada fica vazia. Medido em 182
# vendas da HH (23 a 25/09): 172 no padrão vende-falha-falha, NENHUMA passada
# vendeu depois de um Sell falhado 3/3, e as inúteis custaram 4,9 s por venda.
#
# A PARADA NA ROLHA vai ser decidida pelo slot N PARAR DE MUDAR -- e só depois
# de medida (pedido do usuário: *"tem que medir perfeitamente"*). O risco que a
# medição existe para pegar: itens IGUAIS em sequência deixam a imagem igual com
# a grade andando -- falso positivo, venda parada cedo.
#
# O PROTOCOLO: com isto ligado, cada passada grava a mudança do miolo a cada
# clique e quanto a bolsa baixou (a verdade, pela memória). `python -m
# blazesbot.tools.medir_a_rolha` julga: ≥ 30 vendas, ZERO falso positivo, e a
# posição da rolha batendo com a contagem em ≥ 95%. Só então entra a parada, com
# interruptor próprio. Custo enquanto mede: uma captura por clique.
MEDIR_A_ROLHA = True


class LeituraDoSlot:
    """A leitura do slot por contraste, para quem herda `JanelaDeVenda`."""

    # O CONTRATO DE QUEM HERDA, declarado para ser lido e não adivinhado: o
    # contexto da conta e a captura da janela. `JanelaDeVenda` fornece os dois.
    ctx: BotContext

    def _quadro(self):
        """A captura da janela do jogo. Quem herda substitui."""
        raise NotImplementedError("quem herda LeituraDoSlot fornece _quadro()")

    def _nota_do_slot_vazio(
        self, quadro, ponto: tuple[int, int],
    ) -> tuple[float, str] | None:
        """Quanto o slot se parece com um slot VAZIO. `(nota, qual)` ou None.

        SEMPRE NO SLOT QUE ESTÁ SENDO CLICADO, e em nenhum outro. `ponto` é o
        mesmo `alvo` que o `ctx.click` recebe -- vem do `_ponto_do_slot()`, o
        slot que o usuário configurou. A conferência é um recorte em volta dele.

        Casa numa janelinha, e não na janela inteira, exatamente por isso: a
        grade tem outros slots vazios (os de baixo, que nunca tiveram item), e
        procurar na tela toda encontraria qualquer um deles e encerraria a venda
        com item ainda no slot que interessa.

        MEDE O CONTRASTE DO MIOLO, e não a semelhança com um modelo. Casar
        modelo de "slot vazio" NÃO funcionou, e o motivo é estrutural: o slot
        que o bot confere está SEMPRE com a borda amarela de hover (o
        `_prime_cursor` manda `WM_MOUSEMOVE` para a coordenada do clique), a
        borda ocupa boa parte do recorte e ela existe nos DOIS estados -- então
        é ela que domina o casamento, não o conteúdo. Medido em produção
        (12:11 de 14/08/2026): slot CHEIO 0.503, slot vazio 0.708, com o limiar
        em 0.70. Margem de 0.008, ou seja ruído; a venda parou em 2 cliques de
        66. Repetir a leitura não conserta isso -- o 0.708 é ESTÁVEL, e 3, 10
        ou 50 leituras seguidas dariam todas positivo.

        O miolo resolve porque a borda fica FORA dele. Um ícone de item é
        colorido e cheio de detalhe; um slot vazio é quase liso. Medido nas
        fotos reais deste cliente (24 células cheias e 24 vazias da mesma
        janela, mais os dois modelos):

            slot CHEIO           : 46.75 no pior caso, mediana 60.11
            slot VAZIO com hover :  9.76
            slot VAZIO limpo     :  3.69 (mediana das células vazias: 2.25)

        Vão de 37 pontos, contra os 0.008 do casamento. `LADO_DO_MIOLO` é 24 e
        não 28 porque a 28 a borda de hover começa a entrar (o mesmo modelo
        vazio salta de 9.76 para 57.80 e voltaria a confundir tudo).

        SEMPRE NO SLOT QUE ESTÁ SENDO CLICADO, e em nenhum outro. `ponto` é o
        mesmo `alvo` que o `ctx.click` recebe -- vem do `_ponto_do_slot()`, o
        slot que o usuário configurou. A grade tem outros slots vazios (os da
        lista de venda, logo abaixo), e olhar para qualquer outro encerraria a
        venda com item ainda no slot que interessa.

        Devolve `(contraste, "miolo")`. O nome fica para o log continuar
        dizendo de onde veio a leitura.
        """
        cinza = self._miolo_do_slot(quadro, ponto)
        if cinza is None:
            return None
        # Contraste ALTO = tem ícone. A nota é invertida na comparação: quem
        # decide "vazio" é `_esta_vazio`, para o sentido ficar num lugar só.
        return (float(cinza.std()), "miolo")

    def _miolo_do_slot(self, quadro, ponto: tuple[int, int]):
        """O miolo da célula em `ponto`, em cinza -- ou None.

        UM recorte serve às duas leituras do slot: o contraste do vazio
        (`_nota_do_slot_vazio`) e a mudança clique a clique (medição da rolha).
        Centrado no ponto de clique, e em nenhum outro lugar da tela.
        """
        import cv2

        # `..` e nao `...`: este arquivo mora em `bot/`, nao mais em `bot/bc/`.
        # O nivel a mais sobreviveu a subida de `bc/vendor.py` para
        # `bot/vendedor.py` e apontava para fora do pacote. Import local,
        # entao so estouraria na primeira celula lida da bolsa. Mesmo defeito
        # de `ui_do_jogo.na_posicao_de_clicar`, travado por
        # `tests/test_ecossistemas.test_todo_import_relativo_aponta_para_algo_que_existe`.
        from ..core.vision import crop

        if quadro is None:
            return None

        meio = LADO_DO_MIOLO_DA_CELULA // 2
        janela = crop(quadro, (ponto[0] - meio, ponto[1] - meio,
                               LADO_DO_MIOLO_DA_CELULA,
                               LADO_DO_MIOLO_DA_CELULA))
        if janela is None or janela.size == 0:
            return None
        cinza = (cv2.cvtColor(janela, cv2.COLOR_BGR2GRAY)
                 if janela.ndim == 3 else janela)
        if cinza.shape[0] < LADO_DO_MIOLO_DA_CELULA // 2:
            return None
        return cinza

    # -- medição da rolha: SÓ REGISTRA -- ver `MEDIR_A_ROLHA` ---------------

    def _medir_o_slot(self, ponto: tuple[int, int]):
        """O miolo do slot AGORA, para a medição. None = desligada ou falhou.

        COMPLEMENTO: engole tudo. Instrumentação no meio da venda não pode
        custar uma passada -- a mesma regra do `_provar_o_modal`.
        """
        if not MEDIR_A_ROLHA:
            return None
        try:
            return self._miolo_do_slot(self._quadro(), ponto)
        except Exception:
            return None

    @staticmethod
    def diferenca_do_slot(anterior, atual) -> float | None:
        """Quanto o miolo mudou entre duas leituras (0 a 255). None = não dá."""
        import numpy as np

        if (anterior is None or atual is None
                or getattr(anterior, "shape", None) != getattr(atual, "shape", None)):
            return None
        return float(np.abs(atual.astype(np.int16) - anterior.astype(np.int16)).mean())

    def _registrar_a_rolha(self, passada: int, recortes: list, antes: int | None,
                           cliques: int) -> None:
        """UMA linha por passada: a mudança a cada clique e quanto a bolsa baixou.

        É a matéria-prima do `tools/medir_a_rolha.py`: a verdade é a bolsa --
        se o detector acusasse rolha no clique k, a passada tinha de ter vendido
        k - 1 itens. COMPLEMENTO: engole tudo, inclusive o próprio log.
        """
        if not MEDIR_A_ROLHA:
            return
        try:
            depois = self.ctx.memory.bag_count()
            vendidos = (antes - depois
                        if antes is not None and depois is not None else None)
            difs = [self.diferenca_do_slot(a, b) for a, b in pairwise(recortes)]
            self.ctx.log.info(
                "ROLHA/MEDIÇÃO passada=%s cliques=%s vendidos=%s difs=%s",
                passada, cliques, vendidos,
                json.dumps([None if d is None else round(d, 1) for d in difs]))
        except Exception:
            pass

    @staticmethod
    def _esta_vazio(leitura: tuple[float, str] | None) -> bool:
        """O slot está vazio? Um lugar só decide, para o sinal não inverter."""
        return leitura is not None and leitura[0] <= CONTRASTE_QUE_E_SLOT_VAZIO

    def _clicar_no_slot_antigo(
        self, alvo: tuple[int, int], sem_repetir: bool,
    ) -> tuple[bool, int]:
        """UM clique efetivo no slot. Devolve (surtiu efeito, cliques físicos).

        O "efeito esperado" de clicar num slot da grade é o slot MUDAR: o item
        sai para a lista de venda e o de trás sobe para o lugar dele. Então a
        confirmação é comparar o mesmo recorte antes e depois -- uma subtração
        de imagem, sem reconhecer item nenhum e sem limiar absoluto.

        POR QUE POR DIFERENÇA, e não por "a célula está vazia": distinguir
        célula vazia de célula cheia exigiria um limiar calibrado, e não há como
        calibrá-lo -- em todos os prints disponíveis a grade da bolsa está
        CHEIA, então não existe amostra de célula vazia para medir. Um limiar
        chutado aqui seria o mesmo erro do incidente da tolerância 3. A
        diferença dispensa a calibração: ela compara o slot com ele mesmo.

        SUBSTITUÍDO por `_clicar_no_slot`. Mantido sem uso como registro do
        raciocínio anterior; ninguém chama.
        """
        raise NotImplementedError("ver _clicar_no_slot")

    def _confirmar_slot_vazio(
        self, alvo: tuple[int, int],
    ) -> tuple[float, str] | None:
        """Relê o slot PARADO, sem clicar. `(nota, qual)` se o vazio se sustenta.

        MEDIDO na venda das 10:43 de 14/08/2026: a passada parou com 22 dos 66
        cliques, dizendo "acabaram os itens" com a grade CHEIA (foto da própria
        run em `logs/diagnostico-do-link/104345.082-...-t+750.png`, 24 itens na
        página 1/3, o slot 4 com item).

        A causa é a mecânica que o `sell_from_slot` descreve: ao tirar um item,
        os seguintes SOBEM para preencher o buraco. Entre o item sair e o
        próximo descer o slot fica **de verdade vazio** por um instante, e a
        `ESPERA_ENTRE_CLIQUES_DA_VENDA` (0,1 s) foi encurtada justamente para
        clicar mais rápido que isso. Contar leituras seguidas NAQUELA cadência
        não separa uma coisa da outra -- as três caem dentro do MESMO vão.

        Então a confirmação não clica e não corre: espera o rearranjo terminar
        entre uma leitura e a seguinte. O custo só é pago quando alguma leitura
        diz vazio, ou seja no fim da venda (uma vez) ou num vão ocasional.
        """
        ctx = self.ctx
        ultima: tuple[float, str] | None = None
        for _ in range(LEITURAS_VAZIAS_PARA_PARAR - 1):
            ctx.raise_if_stopped()
            ctx.tick(ESPERA_PARA_CONFIRMAR_VAZIO)
            leitura = self._nota_do_slot_vazio(self._quadro(), alvo)
            if not self._esta_vazio(leitura):
                # ZERA a contagem. Uma leitura com item derruba a confirmação
                # INTEIRA -- não é "a maioria venceu": item na grade é prova de
                # que não acabou, e a venda volta a clicar.
                return None
            ultima = leitura
        return ultima
