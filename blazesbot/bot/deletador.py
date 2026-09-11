"""Deletar itens de lixo da bolsa, por reconhecimento de imagem.

Pertence ao ecossistema **APP** (ver `blazesbot/bot/app/__init__.py`): é o
módulo APP que o usa, porque ele roda longe de vendedor e deletar é a única
saída para bolsa cheia ali. O BC continua vendendo.

===========================================================================
O FLUXO, MEDIDO NOS PRINTS DO USUÁRIO
===========================================================================

    1. o inventário já está aberto (a macro apertou `KeyBinds.inventory`)
    2. clique ESQUERDO no item que casou com um template
    3. clique no ÍCONE DE DELETAR, na fileira de baixo do inventário
    4. aparece "Are you sure to delete [nome do item]?"
    5. clique em Ok

O passo 3 mudou tudo em relação à primeira versão deste arquivo, que apertava
uma tecla de apagar. Não existe tecla: é um ícone, e ele foi recortado do print
(`btn_delete_item.png`, 27x27, casa a **0.992** contra a captura do usuário).

===========================================================================
UMA FOTO SÓ, E POR QUE ISSO É SEGURO AQUI
===========================================================================

Uma captura serve para achar TODOS os alvos e o ícone; as exclusões saem
todas dela, sem refotografar. Isso só é seguro por um fato confirmado pelo
usuário: **a bolsa NUNCA reorganiza os slots sozinha.** O buraco deixado por
um item apagado permanece (é por isso que existe o botão "Arrange", separado).
Se ela compactasse, as coordenadas dos alvos 2..N passariam a apontar para
itens diferentes depois da primeira exclusão -- e apagar o item errado não tem
desfazer.

O ÍCONE também é localizado UMA vez e reusado. Medido: com a caixa de
confirmação na tela, o ícone cai para 0.423 porque a barra de progresso passa
por cima dele. Procurá-lo de novo a cada exclusão falharia por isso.

===========================================================================
POR QUE ELE É PERIGOSO, E O QUE O SEGURA
===========================================================================

Deletar é IRREVERSÍVEL. Um falso positivo não custa tempo, custa item:

  * CASAMENTO EM COR e limiar próprio. Em cinza, ícones de MESMA FORMA e cor
    diferente marcam 0.93 a 0.99 contra o template errado (medido no
    `package_courage`); em cor caem para 0.58-0.88.
  * LISTA BRANCA POR PASTA. Só apaga o que tem template. Não existe "apaga o
    que não reconheço" -- o padrão é PRESERVAR.
  * LADO MÍNIMO de template: pedaço de ícone casa com muito mais coisa.
  * TETO DE EXCLUSÕES por chamada.
  * A CAIXA DE CONFIRMAÇÃO É CONFERIDA por imagem antes do clique no Ok. Sem
    ela na tela o clique cairia dentro do inventário e poderia mover ou usar um
    item -- é a mesma lição do `_abrir_dialogo_e_clicar` do BC.
  * FERRAMENTA DE AFERIÇÃO (`conferir`): fotografa e DESENHA o que casaria, sem
    clicar em nada. É o jeito de validar os templates contra o NOSSO cliente
    antes de confiar neles -- eles vieram do ver.6139 de outro bot.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core import teclado_mudo, vision
from ..core.coords import TEMPLATE_ANCHORS

if TYPE_CHECKING:
    from .context import BotContext

# ===========================================================================
# INTERRUPTOR
# ===========================================================================
# O caminho continua inteiro com ele em False -- desligado não é apagado.
ATIVADO = True

# ===========================================================================
# A FILA QUE RETOMA DE ONDE PAROU (Isolada por Conta)
# ===========================================================================
#
# O teto de 10 s pode acabar antes de todos os templates serem verificados. O
# que sobrou vai PRIMEIRO na chamada seguinte -- senão os últimos da lista
# nunca seriam olhados, e o lixo que eles pegam ficaria na bolsa para sempre.
#
# Usa um dicionário mapeado pelo login da conta para que threads simultâneas
# (múltiplas contas rodando) não atropelem a fila umas das outras.
_estado_das_filas: dict[str, int] = {}

# Pasta com um PNG por item que PODE ser deletado. TODOS entram, sem peneira.
#
# É LISTA BRANCA e é a única: o que não tem modelo aqui nunca é apagado. Pôr um
# PNG nesta pasta é autorizar o bot a apagar aquele item; tirar é revogar.
PASTA_DO_LIXO = Path("data") / "templates" / "deletar"

# A PASTA DA HH -- lista SEPARADA, e a separacao e o ponto.
#
# Regra do usuario, 08/09/2026: *"o HH dropa lixo que nao pode ser vendido no
# NPC... para o ecossistema HH, ele deve ler a lista de imagens/itens a serem
# deletados de uma PASTA ESPECIFICA DE HH (diferente da lista global/BC)"*.
#
# POR QUE NAO DA PARA SER UMA LISTA SO: o que e lixo numa cave e mercadoria na
# outra. Um PNG na lista global apaga o item em TODA conta e TODO ecossistema --
# e apagar e irreversivel. Duas pastas e a unica forma de "lixo de HH" nao
# significar "lixo em todo lugar".
PASTA_DO_LIXO_DA_HH = Path("data") / "templates" / "deletar_hh"

# ===========================================================================
# NÃO EXISTE MAIS PENEIRA POR TAMANHO — decisão do usuário, com o porquê
# ===========================================================================
#
# Havia um `LADO_MINIMO_DO_TEMPLATE = 24` que rejeitava modelo com lado menor
# que 24 px, sob o argumento de que os pequenos eram PEDAÇOS de ícone e
# casariam com coisa demais. Medido, o argumento não se sustentou:
#
#   * dos 125 rejeitados, **93 eram o ÚNICO modelo daquele item** -- ou seja, a
#     peneira não removia redundância, removia COBERTURA;
#   * vários rejeitados são ícone inteiro, só que recortado justo e não
#     quadrado (`ApoCharm` 30x20, `BambShoot` 20x29, `BariteOre` 26x17). O
#     corte pelo LADO MENOR derrubava esses junto com os pedaços de verdade.
#
# A decisão do usuário é usar TODOS: se o outro bot os usava, eles funcionam.
#
# O RISCO MEDIDO, registrado para não se perder: contra o print da bolsa real
# do usuário, os modelos casaram itens que podem não ser lixo (`Sin48`,
# `Fada48`, `Monk48`, `Tamer48`, `dip`). Quem decide isso é o olho humano, e é
# exatamente para isso que existe o botão "Conferir Modelos de Exclusão": ele
# desenha o que seria apagado, sem apagar. **Rodar a conferência antes de ligar
# a limpeza continua sendo a única proteção que não depende de palpite.**

# Limiar do casamento EM COR dos itens. Vem do `package_courage`, que mediu o
# vão entre item verdadeiro (0.971-0.999) e distrator de mesma forma
# (0.583-0.878). PRECISA SER REMEDIDO com os templates de lixo -- é para isso
# que existe a `conferir`.
LIMIAR_EM_COR = 0.92

# Teto de exclusões por chamada. Um template ruim não pode esvaziar a bolsa.
MAXIMO_DE_EXCLUSOES = 20

# Dois casamentos a menos de tanto um do outro são o MESMO item, contado duas
# vezes por templates parecidos. Clicar duas vezes no mesmo slot apagaria o que
# entrou no lugar do primeiro.
DISTANCIA_QUE_E_O_MESMO_ITEM = 12

# ===========================================================================
# TEMPO
# ===========================================================================

# Teto do passo inteiro (verificar + apagar), pedido do usuário.
#
# O teto é conferido ENTRE templates e ENTRE exclusões, nunca no meio de uma:
# cortar depois do clique no ícone deixaria a caixa aberta na tela, e a macro
# voltaria a mandar tecla por cima dela. Uma exclusão que COMEÇA dentro do
# prazo termina — o estouro é de no máximo uma.
#
# A VARREDURA DEIXOU DE SER O GARGALO quando o casamento passou a ser feito só
# DENTRO da região da bolsa (ver `REGIOES_DA_BOLSA`). Medido nos prints do
# usuário, por modelo: **31,6 ms na janela inteira contra 2,86 ms na região**,
# 11x. Os 81 modelos caíram de 2,6 s para **0,23 s** -- ou seja, praticamente
# todo o orçamento agora é gasto apagando, que é o que se queria.
TETO_DE_SEGUNDOS = 10.0

# Espera pela caixa de confirmação aparecer, depois do clique no ícone.
TETO_DA_CAIXA = 1.2
PASSO_DA_ESPERA = 0.08

# Assentamento depois do Ok, para o item sumir antes do clique seguinte.
DEPOIS_DO_OK = 0.18

# A janela do inventário terminar de pintar depois da tecla.
#
# QUEM AINDA USA: o FECHAR (`_fechar_a_bolsa`, que aperta e depois confere) e a
# aferição. O ABRIR deixou de usar em 07/09/2026 -- lá se pergunta pelo ícone
# em laço, ver `TETO_DA_BOLSA_ABRIR`.
ESPERA_DA_BOLSA_ABRIR = 0.58

# Teto da espera pela bolsa APARECER depois da tecla -- 07/09/2026.
#
# ERA UMA ESPERA CEGA de 0,58 s, e ela custou 268 limpezas seguidas perdidas em
# duas contas, por horas, com ZERO itens apagados: quando a tela demorava mais
# que isso para pintar, `deletar_lixo` não achava o ícone, concluía "a bolsa não
# está aberta" e desistia -- e o `finally` apertava a tecla de novo.
#
# Agora se PERGUNTA (`_esperar_a_bolsa_abrir`), saindo no instante em que o
# ícone aparece. 2 s é teto, não gasto: no caso comum a bolsa aparece em bem
# menos, e o que era 0,58 s fixo virou ~0,1 s típico.
TETO_DA_BOLSA_ABRIR = 2.0

# Passo entre duas perguntas pelo ícone. Cada uma custa uma captura de janela,
# então não pode ser fino demais; 0,15 s dá ~13 amostras dentro do teto.
PASSO_DA_BOLSA_ABRIR = 0.15

# Quantas vezes insistir para FECHAR a bolsa. Duas, porque a tecla é síncrona:
# se a segunda não fechou, o problema não é o toque ter se perdido.
TENTATIVAS_DE_FECHAR_A_BOLSA = 2

LIMIAR_DO_ICONE = 0.80
LIMIAR_DA_CAIXA = 0.80

TEMPLATE_DO_ICONE = "btn_delete_item.png"

# ===========================================================================
# ONDE PODE DELETAR — e só ali
# ===========================================================================
#
# A REGRA, dada pelo usuário com prints: só os itens ABAIXO da linha de abas
# "Item | Quest | Arrange | Ext.". O que está acima é o EQUIPAMENTO que o
# personagem está usando.
#
# O jogo não deixaria apagar equipamento de qualquer forma -- mas tentar custa
# o clique, o clique no ícone e a espera da caixa que nunca vem, tudo dentro de
# um orçamento de 10 segundos. Tempo gasto ali é item de lixo que ficou na
# bolsa.
#
# E TEM UM GANHO QUE NÃO ERA O OBJETIVO: casar dentro de um retângulo de
# ~245x170 em vez da janela inteira de 1024x768 é ~24x menos área por modelo.
# A varredura dos 81 modelos, que custava 2,6 s, passa a caber com folga.
#
# Cada região é ancorada num template e definida por um retângulo RELATIVO ao
# CENTRO dele (a convenção do `find_template`). Medido no print do usuário: a
# linha de abas fica centrada em (665,466) e a grade vai de (542,483) a
# (780,648) -- logo (-123,+17) a (+115,+182), com uma folga de 2 px.


@dataclass(frozen=True)
class RegiaoDaBolsa:
    """Um retângulo de slots deletáveis, ancorado num template."""

    template: str
    dx0: int
    dy0: int
    dx1: int
    dy1: int
    rotulo: str = ""


REGIOES_DA_BOLSA: tuple[RegiaoDaBolsa, ...] = (
    # A bolsa principal, abaixo das abas. A folga de ~5 px em volta do medido
    # não é capricho: `matchTemplate` exige o modelo INTEIRO dentro do recorte,
    # então um ícone encostado na borda não casaria se o retângulo fechasse
    # exatamente nele.
    # A ÚLTIMA LINHA CABE -- e não cabia até 10/09/2026, quando o retângulo
    # terminava em +186 e a grade termina em +190. As cinco linhas ficam entre
    # +13 e +190, de 35 em 35 px (medido no print de referência). Faltavam
    # QUATRO pixels, e `matchTemplate` quer o modelo INTEIRO dentro do recorte:
    # item na 5ª linha não era reconhecido. Ver `docs/decisoes/deletador.md`.
    RegiaoDaBolsa("state_bag_tabs.png", -130, 12, 125, 195, "bolsa principal"),
    # AS BOLSAS EXTRAS ("Expand Bag 1" e "Expand Bag 2"), ancoradas na ETIQUETA
    # e não no título -- e essa escolha é a regra inteira.
    #
    # Uma bag extra pode estar `Permanent`, `Limited Time`, `Expired` ou
    # `Unactivated`. Só as duas primeiras são acessíveis. A `Expired` **continua
    # mostrando os itens** (medido no print do usuário: a Expand Bag 1 aparece
    # cheia e vermelha), então sem olhar a etiqueta o bot gastaria clique e
    # espera numa bag onde nada acontece -- dentro de um teto de 10 s.
    #
    # PROCURAR SÓ AS ETIQUETAS BOAS, e não reconhecer a ruim, faz o padrão ser
    # PRESERVAR: uma etiqueta que eu não conheça (a `Unactivated`, ou uma que o
    # jogo invente amanhã) simplesmente não casa, e a bag fica de fora sozinha.
    # Reconhecer `Expired` para excluir teria a falha oposta -- o que não
    # estivesse na lista de exclusão seria varrido.
    #
    # Medido nos prints: a etiqueta fica no alto à DIREITA do painel, e a grade
    # desce à esquerda dela. Como as duas etiquetas têm larguras diferentes
    # (74 e 94 px) e é a borda DIREITA delas que se alinha ao painel, cada uma
    # tem o seu retângulo -- os números não podem ser compartilhados.
    RegiaoDaBolsa("state_bag_permanent.png", -196, 13, 50, 193, "bag Permanent"),
    RegiaoDaBolsa("state_bag_limited.png", -186, 13, 60, 193, "bag Limited Time"),
)

LIMIAR_DA_REGIAO = 0.80

# ===========================================================================
# A FILA QUE RETOMA DE ONDE PAROU
# ===========================================================================
#
# O teto de 10 s pode acabar antes de todos os templates serem verificados. O
# que sobrou vai PRIMEIRO na chamada seguinte -- senão os últimos da lista
# nunca seriam olhados, e o lixo que eles pegam ficaria na bolsa para sempre.
#
# Mora no módulo (e não na instância) porque quem chama é uma função injetada
# pelo supervisor, recriada a cada volta.
_proximo_da_fila = 0


def ordem_da_fila(nomes: list[str], comeca_em: int) -> list[str]:
    """Os templates na ordem em que devem ser verificados agora.

    Lógica pura, para o teste não precisar do jogo: roda a lista de forma que o
    primeiro não-verificado da vez passada venha na frente.
    """
    if not nomes:
        return []
    inicio = comeca_em % len(nomes)
    return nomes[inicio:] + nomes[:inicio]


def _sao_o_mesmo_item(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return (abs(a[0] - b[0]) <= DISTANCIA_QUE_E_O_MESMO_ITEM
            and abs(a[1] - b[1]) <= DISTANCIA_QUE_E_O_MESMO_ITEM)


def modelos_na_pasta(pasta: Path | None = None) -> list[Path]:
    """Todo PNG da pasta, RELIDO a cada chamada.

    Reler é de propósito e é requisito: acrescentar um modelo na pasta tem que
    passar a valer sem reiniciar o bot. O custo é um `glob` (~1 ms) -- as
    IMAGENS em si continuam em cache no `TemplateLibrary`, que é onde o custo
    real estaria.

    A versão anterior guardava a lista para sempre, porque precisava abrir cada
    arquivo para medir o lado. Sem a peneira, não há mais o que medir.

    `pasta=None` é a lista GLOBAL (`PASTA_DO_LIXO`). Quem passa outra é o
    ecossistema que tem lixo próprio -- ver `PASTA_DO_LIXO_DA_HH`.
    """
    return sorted((pasta or PASTA_DO_LIXO).glob("*.png"))


def _carregar(ctx: BotContext, pasta: Path | None = None) -> dict[str, Any]:
    """Templates EM COR. Em cinza não se pode deletar (ver o cabeçalho).

    A CHAVE DO CACHE CARREGA O NOME DA PASTA, e isso não é detalhe: o
    `TemplateLibrary` guarda por chave, e duas pastas com um arquivo de mesmo
    nome (`bag.png` na global e `bag.png` na da HH) devolveriam a MESMA imagem
    -- a primeira que fosse carregada. O bot apagaria o item errado, e a
    exclusão é irreversível.
    """
    pasta = pasta or PASTA_DO_LIXO
    saida: dict[str, Any] = {}
    for arquivo in modelos_na_pasta(pasta):
        img = ctx.templates.load_color(f"{pasta.name}/{arquivo.name}")
        if img is not None:
            saida[arquivo.stem] = img
    return saida


def regioes_visiveis(ctx: BotContext, quadro) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Os retângulos de slots deletáveis que estão na tela AGORA.

    Devolve `[(rótulo, (x, y, largura, altura)), ...]`, já em coordenadas da
    janela. Lista vazia significa "não achei bolsa nenhuma" -- e aí não se
    deleta nada, que é o desfecho seguro.

    O retângulo é derivado do template a cada chamada, e não fixo: a janela do
    inventário pode ser arrastada para qualquer canto, e foi por isso que o
    `package_courage` varria a tela inteira.
    """
    altura_da_tela, largura_da_tela = quadro.shape[:2]
    achadas: list[tuple[str, tuple[int, int, int, int]]] = []
    for regiao in REGIOES_DA_BOLSA:
        tpl = ctx.templates.load(regiao.template)
        if tpl is None:
            continue
        # TODAS as ocorrências, e não a melhor: a MESMA etiqueta aparece em
        # mais de uma bag ao mesmo tempo (medido: `Permanent` nas duas Expand
        # Bags do print do usuário). Com `find_template` só a primeira delas
        # seria varrida, e a outra nunca seria limpa.
        for centro in vision.find_all_templates(quadro, tpl,
                                                threshold=LIMIAR_DA_REGIAO):
            x0 = max(0, centro[0] + regiao.dx0)
            y0 = max(0, centro[1] + regiao.dy0)
            x1 = min(largura_da_tela, centro[0] + regiao.dx1)
            y1 = min(altura_da_tela, centro[1] + regiao.dy1)
            if x1 > x0 and y1 > y0:
                achadas.append((regiao.rotulo or regiao.template,
                                (x0, y0, x1 - x0, y1 - y0)))
    return achadas


def _casamentos_nas_regioes(quadro, template, regioes,
                            placar: list[float] | None = None,
                            ) -> list[tuple[int, int]]:
    """Casa o modelo SÓ dentro das regiões, e devolve em coordenada da janela.

    Recortar antes de casar não é só o filtro pedido -- é o que torna a
    varredura barata: ~245x170 por região contra 1024x768 da janela inteira.

    `placar`, se dado, recebe o MAIOR valor de correlação visto em qualquer
    região -- DE GRAÇA, porque o `matchTemplate` já roda e antes esse número era
    descartado. É ele que separa "não tem esse item na tela" de "tem, e o modelo
    quase bate" -- ver `_quem_nao_casou`.
    """
    centros: list[tuple[int, int]] = []
    for _rotulo, (x, y, larg, alt) in regioes:
        recorte = vision.crop(quadro, (x, y, larg, alt))
        if recorte is None or recorte.size == 0:
            continue
        if (recorte.shape[0] < template.shape[0]
                or recorte.shape[1] < template.shape[1]):
            continue
        for cx, cy in vision.find_all_templates(
                recorte, template, threshold=LIMIAR_EM_COR, colorido=True,
                placar=placar):
            centros.append((cx + x, cy + y))
    return centros


def _achar_icone(ctx: BotContext, quadro) -> tuple[int, int] | None:
    """O ícone de deletar na fileira de baixo do inventário.

    É também o SINAL DE QUE O INVENTÁRIO ESTÁ ABERTO. Isso não é economia: a
    leitura de estado de UI por memória (`bag_open()`) falhou em 5 de 5 runs
    medidas, e o ícone só existe com a bolsa na tela.
    """
    tpl = ctx.templates.load(TEMPLATE_DO_ICONE)
    if tpl is None:
        ctx.log.warning("Sem o template %s; não sei onde clicar para deletar.",
                        TEMPLATE_DO_ICONE)
        return None
    return vision.find_template(quadro, tpl, threshold=LIMIAR_DO_ICONE)


def _esperar_a_caixa(ctx: BotContext) -> tuple[int, int] | None:
    """Espera "Are you sure to delete...?" e devolve o ponto do Ok.

    O Ok é DERIVADO do texto, nunca uma coordenada fixa: a caixa pode mudar de
    lugar com a resolução, e os botões Ok e Cancel são idênticos em forma --
    um template de botão casaria nos dois.
    """
    nome, deslocamentos = TEMPLATE_ANCHORS["delete_confirm"]
    tpl = ctx.templates.load(nome)
    if tpl is None:
        return None
    limite = time.perf_counter() + TETO_DA_CAIXA
    while True:
        quadro = vision.capture_window(ctx.hwnd)
        if quadro is not None and not vision.frame_is_blank(quadro):
            base = vision.find_template(quadro, tpl, threshold=LIMIAR_DA_CAIXA)
            if base is not None:
                dx, dy = deslocamentos["ok"]
                return (base[0] + dx, base[1] + dy)
        if time.perf_counter() >= limite:
            return None
        ctx.tick(PASSO_DA_ESPERA)


def _apagar_um(ctx: BotContext, item: tuple[int, int],
               icone: tuple[int, int]) -> bool:
    """Uma exclusão completa: item -> ícone -> Ok.

    Devolve se o Ok chegou a ser clicado. NÃO confere que o item sumiu da
    bolsa: refotografar por item custaria mais que o teto de 10 s permite, e a
    própria caixa de confirmação já nomeia o item que vai embora.
    """
    ctx.click(item)
    ctx.tick(0.05)
    ctx.click(icone)
    ponto_do_ok = _esperar_a_caixa(ctx)
    if ponto_do_ok is None:
        ctx.log.warning(
            "Cliquei no ícone de deletar em %s e a confirmação não apareceu. "
            "NÃO vou clicar no Ok às cegas -- o clique cairia dentro do "
            "inventário.", icone)
        return False
    ctx.click(ponto_do_ok)
    ctx.tick(DEPOIS_DO_OK)
    return True


def deletar_lixo(ctx: BotContext,
                 teto_segundos: float = TETO_DE_SEGUNDOS,
                 pasta: Path | None = None) -> int:
    """Apaga da bolsa os itens com template na `pasta`.

    Pressupõe o inventário JÁ ABERTO. Devolve quantos foram apagados.

    `pasta=None` é a lista GLOBAL (`PASTA_DO_LIXO`), que é o que o APP e a BC
    usam. A HH passa a sua (`PASTA_DO_LIXO_DA_HH`): o que é lixo numa cave é
    mercadoria na outra, e apagar é irreversível.

    Nunca levanta e nunca demora mais que `teto_segundos`: é um complemento da
    macro do APP, que roda por horas sozinha e não pode parar por causa dele.
    """
    global _estado_das_filas

    pasta = pasta or PASTA_DO_LIXO
    if not ATIVADO:
        return 0
    if not pasta.is_dir():
        ctx.log.warning("Deletador ligado mas %s não existe.", pasta)
        return 0

    comeco = time.perf_counter()
    limite = comeco + teto_segundos

    quadro = vision.capture_window(ctx.hwnd)
    if quadro is None or vision.frame_is_blank(quadro):
        ctx.log.warning("Sem captura da tela; não dá para deletar por imagem.")
        return 0

    icone = _achar_icone(ctx, quadro)
    if icone is None:
        ctx.log.info(
            "Não achei o ícone de deletar na tela — o inventário não está "
            "aberto. Pulando a limpeza desta volta.")
        return 0

    regioes = regioes_visiveis(ctx, quadro)
    # QUAIS regiões, e não só quantas. Uma bolsa extra FECHADA não tem etiqueta
    # na tela, então ela simplesmente não entra nesta lista -- e o item que
    # estiver dentro dela é invisível para a varredura, sem nenhum aviso. Era
    # exatamente esse estado que não aparecia em log nenhum.
    if regioes:
        ctx.log.info("Bolsas visíveis para a limpeza: %s.",
                     ", ".join(r for r, _ in regioes))
    if not regioes:
        ctx.log.info(
            "Não achei a grade da bolsa na tela (a linha de abas "
            "Item/Quest/Arrange/Ext.). Não vou deletar nada.")
        return 0

    templates = _carregar(ctx, pasta)
    if not templates:
        ctx.log.warning("Nenhum template em %s.", pasta)
        return 0

    # Busca a posição da fila específica desta conta
    login_da_conta = (ctx.account.login or "").strip().lower()
    proximo_da_fila = _estado_das_filas.get(login_da_conta, 0)

    nomes = ordem_da_fila(sorted(templates), proximo_da_fila)
    apagados = 0
    verificados = 0
    ja_clicados: list[tuple[int, int]] = []
    # QUEM NÃO CASOU, e o quanto faltou. Ver `_quem_nao_casou` no fim.
    nao_casaram: dict[str, float] = {}

    for nome in nomes:
        if time.perf_counter() >= limite or apagados >= MAXIMO_DE_EXCLUSOES:
            break
        ctx.raise_if_stopped()
        verificados += 1

        pontuacoes: list[float] = []
        centros = _casamentos_nas_regioes(
            quadro, templates[nome], regioes, placar=pontuacoes)
        if not centros and pontuacoes:
            nao_casaram[nome] = max(pontuacoes)
        for centro in centros:
            if time.perf_counter() >= limite or apagados >= MAXIMO_DE_EXCLUSOES:
                break
            if any(_sao_o_mesmo_item(centro, p) for p in ja_clicados):
                continue
            ja_clicados.append(centro)
            if _apagar_um(ctx, centro, icone):
                apagados += 1
                ctx.log.info("Item deletado: %s em %s", nome, centro)

    # Atualiza a fila apenas para esta conta
    _estado_das_filas[login_da_conta] = (proximo_da_fila + verificados) % max(1, len(templates))

    gasto = time.perf_counter() - comeco
    ctx.log.info(
        "Limpeza da bolsa: %s item(ns) deletado(s) | %s de %s modelos "
        "verificados em %.1f s%s", apagados, verificados, len(templates),
        gasto, " (teto atingido)" if gasto >= teto_segundos else "")

    _quem_nao_casou(ctx, nao_casaram)
    return apagados


def _quem_nao_casou(ctx: BotContext, placar: dict[str, float]) -> None:
    """Diz quanto FALTOU para cada modelo que não casou nesta passada.

    =======================================================================
    POR QUE ISTO EXISTE
    =======================================================================

    Um modelo que NUNCA casa é invisível: a passada apaga os outros, o log diz
    "7 item(ns) deletado(s)" e parece tudo certo. Relato do usuário em
    11/09/2026 sobre o `Trap-Meshwork`: *"agora adicionei de volta, porém não
    está deletando os itens que são iguais"* -- e o log da época não tinha como
    responder, porque o diagnóstico só rodava quando a passada apagava ZERO.

    =======================================================================
    E O NÚMERO SEPARA DUAS CAUSAS OPOSTAS
    =======================================================================

      * **0,30-0,60** -- o item não está na tela agora, ou o modelo é de outro
        item. Nada a consertar no limiar;
      * **0,80-0,91** -- o item ESTÁ lá e o modelo quase bate: recorte ruim
        (zoom, fundo diferente, número de pilha por cima). Refazer o PNG.

    CUSTO ZERO: o valor vem do `matchTemplate` que já rodava, por `placar`.
    Antes eu pagava uma segunda varredura para isso (`_explicar_o_zero`), e ela
    foi embora junto.
    """
    if not placar:
        return
    piores = sorted(placar.items(), key=lambda kv: kv[1], reverse=True)[:6]
    ctx.log.info(
        "Não casaram (limiar %.2f): %s. Acima de ~0,80 o item está na tela e o "
        "recorte é que não bate; abaixo de ~0,60 o item não está lá.",
        LIMIAR_EM_COR,
        ", ".join(f"{nome} {valor:.2f}" for nome, valor in piores))


def esquecer_a_fila() -> None:
    """Volta a fila para o começo. Usado pelos testes."""
    global _estado_das_filas
    _estado_das_filas.clear()


def _esperar_a_bolsa_abrir(ctx: BotContext) -> bool:
    """Espera o ícone de deletar APARECER. `True` = a bolsa está na tela.

    Substituiu a espera cega de 0,58 s -- ver `TETO_DA_BOLSA_ABRIR` para o que
    ela custou em campo.

    O QUE ESTA FUNÇÃO DEVOLVE VALE OURO PARA QUEM CHAMA: `False` significa
    "a bolsa NÃO está na tela", e é isso que autoriza não apertar a tecla de
    novo. A tecla é interruptor: apertar sem saber o estado é a diferença entre
    fechar o que abriu e abrir o que estava fechado.
    """
    fim = time.perf_counter() + TETO_DA_BOLSA_ABRIR
    while True:
        if inventario_esta_aberto(ctx) is True:
            return True
        if time.perf_counter() >= fim:
            return False
        ctx.tick(PASSO_DA_BOLSA_ABRIR)


def inventario_esta_aberto(ctx: BotContext) -> bool | None:
    """A bolsa está na tela? `True`, `False` ou `None` (não dá para saber).

    O sinal é o ÍCONE DE DELETAR: ele só existe com o inventário aberto. Não é
    economia de template -- a leitura de estado de UI por memória (`bag_open()`)
    falhou em 5 de 5 runs medidas, e o ícone é a evidência que a tela dá.

    As três respostas são distintas de propósito. Tratar `None` como `False`
    faria o bot apertar a tecla sem saber, e num inventário que JÁ estava aberto
    isso o FECHA -- aí nada é apagado e, pior, o "fechar" do fim o reabre e
    deixa a bolsa aberta engolindo as teclas da macro pelo resto da noite.
    """
    quadro = vision.capture_window(ctx.hwnd)
    if quadro is None or vision.frame_is_blank(quadro):
        return None
    return _achar_icone(ctx, quadro) is not None


def limpar_a_bolsa(ctx: BotContext, tecla_do_inventario: str,
                   teto_segundos: float = TETO_DE_SEGUNDOS,
                   pasta: Path | None = None) -> int:
    """Abre a bolsa SE precisar, apaga o lixo, e fecha SÓ se foi este passo
    que abriu.

    =======================================================================
    POR QUE OLHAR ANTES DE APERTAR
    =======================================================================

    A tecla do inventário é um INTERRUPTOR: ela abre se estiver fechado e fecha
    se estiver aberto. Apertar às cegas numa bolsa já aberta a fecha -- e aí não
    há o que apagar, e o "fechar" do fim REABRE e deixa a bolsa aberta. Com o
    inventário aberto a macro do APP perde toda tecla que manda, pelas horas
    seguintes, sem nada no log dizendo por quê.

    Por isso o estado inicial é LIDO, e o fim RESTAURA o que se encontrou:
    aberto continua aberto, fechado volta a fechado.
    """
    if not ATIVADO or not tecla_do_inventario:
        return 0

    aberto_antes = inventario_esta_aberto(ctx)
    eu_abri = False
    try:
        if aberto_antes is not True:
            # Inclui o caso `None`: sem leitura, o desfecho seguro é abrir e
            # devolver ao fechado -- é o comportamento que existia antes de
            # haver conferência nenhuma.
            ctx.press(tecla_do_inventario)
            eu_abri = True
            if not _esperar_a_bolsa_abrir(ctx):
                # DESISTE DA LIMPEZA, MAS NÃO DO FECHAMENTO -- e a diferença é
                # do Codex, na revisão de 07/09/2026.
                #
                # A primeira versão zerava `eu_abri` aqui, "para não apertar a
                # tecla sem saber o estado". Isso jogava fora exatamente o
                # mecanismo que resolve o caso restante: se a bolsa abrir DEPOIS
                # do teto, ela ficaria aberta -- e bolsa aberta atrapalha as
                # voltas seguintes.
                #
                # `eu_abri` continua `True` porque é verdade: a tecla saiu. Quem
                # decide se aperta de novo é o `finally`, e ele decide OLHANDO
                # (fecha só o que a tela diz estar aberto). Intenção não fecha
                # bolsa; observação fecha.
                ctx.log.warning(
                    "A bolsa não apareceu em %.1fs depois da tecla %r. Desisto "
                    "da limpeza desta volta; se ela abrir atrasada, o "
                    "fechamento a encontra.",
                    TETO_DA_BOLSA_ABRIR, tecla_do_inventario)
                return teclado_mudo.BOLSA_NAO_ABRIU
        else:
            ctx.log.debug("Inventário já estava aberto; não vou mexer na tecla.")
        return deletar_lixo(ctx, teto_segundos, pasta)
    finally:
        # FECHA SÓ O QUE ESTÁ OBSERVADAMENTE ABERTO. `eu_abri` diz o que eu
        # tentei; a tela diz o que É. Entre os dois, manda a tela.
        if eu_abri and inventario_esta_aberto(ctx) is True:
            _fechar_a_bolsa(ctx, tecla_do_inventario)


def _fechar_a_bolsa(ctx: BotContext, tecla: str) -> None:
    """Fecha, e CONFERE que fechou.

    Um "fechar" que não pegou custa caro e em silêncio: a macro do APP roda por
    horas mandando tecla para uma bolsa aberta que engole tudo. Conferir custa
    uma captura; não conferir custa a noite.
    """
    for tentativa in range(1, TENTATIVAS_DE_FECHAR_A_BOLSA + 1):
        ctx.press(tecla)
        ctx.tick(ESPERA_DA_BOLSA_ABRIR)
        if inventario_esta_aberto(ctx) is not True:
            return
        ctx.log.debug("A bolsa não fechou na tentativa %s; repetindo.",
                      tentativa)
    ctx.log.warning(
        "Não consegui FECHAR o inventário. A macro vai mandar tecla com a "
        "bolsa aberta, e ela engole tudo — confira a tela.")


# ===========================================================================
# AFERIÇÃO — vê o que casaria, SEM apagar nada
# ===========================================================================


def conferir(ctx: BotContext, destino: Path | None = None) -> dict[str, Any]:
    """Fotografa a bolsa e DESENHA o que os templates reconheceriam.

    Não clica, não manda tecla, não apaga. Existe porque os 81 templates vieram
    do ver.6139 de OUTRO bot e nunca foram medidos contra o nosso cliente --
    e o custo de descobrir um falso positivo apagando é um item perdido, sem
    desfazer.

    Devolve `{"ok", "erro", "achados", "arquivo"}`; a imagem tem um retângulo
    por casamento, com o nome do modelo e a nota.
    """
    import cv2

    if not PASTA_DO_LIXO.is_dir():
        return {"ok": False, "erro": f"A pasta {PASTA_DO_LIXO} não existe.",
                "achados": [], "arquivo": ""}

    quadro = vision.capture_window(ctx.hwnd)
    if quadro is None or vision.frame_is_blank(quadro):
        return {"ok": False, "erro": "Não consegui capturar a tela do jogo.",
                "achados": [], "arquivo": ""}

    templates = _carregar(ctx)
    if not templates:
        return {"ok": False, "erro": f"Nenhum modelo em {PASTA_DO_LIXO}.",
                "achados": [], "arquivo": ""}

    regioes = regioes_visiveis(ctx, quadro)
    marcado = quadro.copy()
    # Desenha a REGIÃO antes dos itens: é o que mostra, de relance, que o
    # equipamento ficou de fora da conta.
    for rotulo, (x, y, larg_r, alt_r) in regioes:
        cv2.rectangle(marcado, (x, y), (x + larg_r, y + alt_r), (255, 200, 0), 2)
        cv2.putText(marcado, rotulo, (x, max(10, y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1)

    achados: list[dict[str, Any]] = []
    for nome, tpl in templates.items():
        alt, larg = tpl.shape[:2]
        for centro in _casamentos_nas_regioes(quadro, tpl, regioes):
            achados.append({"modelo": nome, "x": centro[0], "y": centro[1]})
            x0, y0 = centro[0] - larg // 2, centro[1] - alt // 2
            cv2.rectangle(marcado, (x0, y0), (x0 + larg, y0 + alt),
                          (0, 0, 255), 2)
            cv2.putText(marcado, nome, (x0, max(10, y0 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

    icone = _achar_icone(ctx, quadro)
    if icone is not None:
        cv2.circle(marcado, icone, 16, (0, 255, 0), 2)
        cv2.putText(marcado, "deletar", (icone[0] - 24, icone[1] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

    caminho = destino or (Path("logs") / "afericao-do-deletador.png")
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(caminho), marcado)
    except OSError as exc:
        return {"ok": False, "erro": f"Não consegui salvar: {exc}",
                "achados": achados, "arquivo": ""}

    return {"ok": True, "erro": "", "achados": achados,
            "arquivo": str(caminho), "modelos": len(templates),
            "inventario_aberto": icone is not None}
