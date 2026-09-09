"""A JANELA DE VENDA do jogo: abrir, vender slot a slot, confirmar vazio.

=========================================================================
O QUE ESTE MÓDULO É
=========================================================================

A janela de venda é UMA no jogo inteiro -- mesma moldura, mesma grade de slots,
mesma paginação 1/3, mesmo par Sell/Cancel. Confirmado nas capturas do
`Roaming Apothecary` da HH em 01/09/2026: é a mesma do Rich Man de Stone City.

Então a MÁQUINA sobe e serve os dois ecossistemas:

    abrir o diálogo do NPC e achar o link de vender
    achar a âncora da janela e derivar o ponto do slot
    clicar no slot, CONFERIR que ele ficou vazio, avançar
    fechar a caixa de confirmação quando ela aparece

O que fica no ecossistema é QUEM é o vendedor e COMO se chega nele:

    bot/bc/vendor.py     o Rich Man em Stone City, a volta pela pedra ou pelo
                         token de guilda, a compra de suprimentos
    bot/hh/vendedor.py   o `Roaming Apothecary`, do lado de fora da cave -- não
                         precisa de viagem nenhuma, ele fica ali

**DEPENDÊNCIA CRUZADA: mexer aqui mexe nos dois.** `bc/vendor.py` herda desta
classe, então tudo que a rotina da BC já chamava continua no mesmo objeto e com
o mesmo nome.

=========================================================================
POR QUE A CONFERÊNCIA DE SLOT VAZIO EXISTE
=========================================================================

O bot em Lua da HH vende com **30 cliques fixos** num slot literal, 100 ms entre
eles, sem saber se vendeu alguma coisa. Isso falha de duas formas: para de
vender antes de acabar (bolsa maior que 30 itens) e continua clicando depois de
acabar (bolsa menor), e em nenhum dos dois casos alguém sabe.

Aqui cada clique é seguido de uma leitura do slot. Vazio, avança; ainda com
item, insiste. É a diferença entre vender e clicar.
"""
from __future__ import annotations

from ..config import CLIQUES_POR_PASSADA
from ..core import calibracao, diario, esconder_jogadores
from ..core.coords import TEMPLATE_ANCHORS
from ..core.vision import (
    capture_window,
    find_template,
)
from .context import BotContext
from .navegacao import Navigator
from .ui_do_jogo import UIDoJogo

# ===========================================================================
# O RICH É PROCURADO NA TELA, NÃO DECORADO NUMA COORDENADA
# ===========================================================================
#
# `coords.vendor_npc` (284,336) foi medida com o personagem parado EXATAMENTE em
# (158,-494), e o comentário dela conta o porquê da fragilidade: quando o ponto
# de parada mudou de (153,-492) para (158,-494) -- **cinco unidades de mundo** --,
# o NPC saiu de (464,377) para (172,301) na tela. **Quase 300 px por cinco
# passos.**
#
# `PRECISAO_NO_PONTO_DO_VENDEDOR = 0.9` limita o erro, mas não o elimina: dentro
# da tolerância o NPC ainda passeia dezenas de pixels, e o clique direito que
# erra o Rich cai na cena 3D.
#
# Achar o Rich POR IMAGEM tira essa dependência. A coordenada continua existindo
# como RESERVA -- se o template não casar, o comportamento é o de sempre, e o log
# diz qual dos dois foi usado. Nunca ficar pior que hoje.
TEMPLATE_VENDEDOR = "vendedor.png"

# Onde procurar: um retângulo em volta de onde ele DEVERIA estar. Não é a posição
# dele -- é o limite da busca, e por isso é generoso.
#
# 200 px de raio contra os ~54 px que a tolerância de 0,9 unidade permite (pela
# régua dos 300 px por 5 unidades). Sobra folga de três vezes, e ainda assim a
# busca não varre a tela inteira -- o que importa, porque um casamento de sprite
# de NPC do outro lado do cenário seria um clique direito no lugar errado.
RAIO_DA_BUSCA_DO_VENDEDOR = 200

# Limiar do casamento. Sprite de NPC contra cenário 3D é mais difícil que ícone
# de UI, então não é 0.90. Erra para MENOS de propósito: falso negativo cai na
# coordenada de reserva (o comportamento de hoje), falso positivo manda o clique
# direito para o lugar errado.
LIMIAR_DO_VENDEDOR = 0.80

# Recarga do Guild Token, em segundos. Valor do jogo.
RECARGA_GUILD_TOKEN = 10 * 60

# TETO da espera do teleporte -- não é mais o tempo gasto, é o limite.
#
# Eram 6,0 s CEGOS em toda ida ao vendedor: o bot apertava a tecla, dormia seis
# segundos e só então olhava a posição. Mas o que confirma o teleporte já é uma
# leitura -- o salto de posição, abaixo --, então dá para PERGUNTAR: o laço sai
# no instante em que o personagem aparece na cidade. O teto só é pago quando o
# teleporte realmente não acontece (item sem estoque, tecla errada), que é
# justamente o caso em que se quer ter certeza antes de desistir.
ESPERA_DO_TELEPORTE = 5.0

# Entre leituras. A posição vem da memória e custa microssegundos; o passo é
# curto porque o ganho aqui é exatamente o que se corta do fim da espera.
PASSO_DA_ESPERA_DO_TELEPORTE = 0.12

# Salto de posição que confirma o teleporte para a cidade.
#
# NÃO É MAIS O QUE CONFIRMA A CHEGADA -- ver `voltar_para_a_cidade`. Salto de
# posição prova que ALGO aconteceu, não que o destino é Stone City, e devolver
# True para qualquer salto era o que deixava o bot procurando o Rich em outra
# localização, andando em laço. Quem confirma agora é
# `mapa_bc.esta_em_stone_city`.
SALTO_QUE_CONFIRMA = 200.0

# ==========================================================================
# CHEGAR A STONE CITY -- números do usuário (18/08/2026)
# ==========================================================================
#
# "são 10 tentativas de usar o guild token e depois vem 3 tentativas de usar a
# pedra de retorno, sendo cada tentativa a cada 10 segundos, caso alguma das
# teclas não esteja configurada então tem que ignorar a parte referente àquela
# tecla, e a cada vez você confere se está em stone city após o uso."
#
# O Token vem primeiro e é tentado 10 vezes porque NÃO GASTA ITEM -- tentar é
# barato. A recarga interna do bot NÃO barra a tentativa: decisão do usuário,
# "às vezes pode ter ocorrido uma falha na contagem". Apertar na recarga não faz
# nada além de gastar o tempo da tentativa.
#
# A pedra vem depois e são só 3, porque ela GASTA. E o usuário explicou por que
# 3 bastam: "é garantido que vai usar, pq não tem recarga, é só o usuário ter
# comprado anteriormente". Usar a pedra e não chegar tem duas explicações --
# estoque zerado ou TECLA ERRADA --, e as duas exigem intervenção. Repetir mais
# que isso só queimaria estoque escondendo um erro de configuração.
TENTATIVAS_DO_TOKEN = 10
TENTATIVAS_DA_PEDRA = 3
ESPERA_ENTRE_TENTATIVAS_DE_RETORNO = 8.0

# Folga da CAMINHADA até o vendedor. O painel de arredores caminha até perto e
# aceita folga por construção; quem fecha o último passo é o ajuste apertado.
TOLERANCIA_DA_CAMINHADA_ATE_O_VENDEDOR = 2

# Orçamento do ajuste fino no ponto do vendedor. Pequeno porque o passo real é
# de poucas unidades -- mesmo desenho do patamar do Altar Stone.
TENTATIVAS_DE_ENCOSTAR_NO_VENDEDOR = 6
SEGUNDOS_POR_TENTATIVA_NO_VENDEDOR = 4

# Quantos CICLOS COMPLETOS de venda (reposicionar -> abrir diálogo -> vender)
# antes de desistir.
#
# Dez, por pedido do usuário. A insistência é o ponto: bolsa cheia trava o bot e
# faz o usuário perder item, então não vender não pode ser um desfecho silencioso.
#
# Esgotando os dez, o BC farm daquela conta é DESLIGADO (e salvo): a conta fica
# online, logada, com o relogin ativo, e o checkbox desmarca na interface -- que
# é o sinal de que precisa de intervenção. Não fecha nada, não desliga o bot
# inteiro, e não volta a tentar vender. Mesmo desfecho que já existe para "sem
# tecla de retorno configurada".
CICLOS_DE_VENDA = 10

# Quantas vezes reclicar o Ok da caixa "It's precious item" antes de desistir.
# Três porque o clique é síncrono (SendMessage): se três não fecharam, o
# problema não é o clique ter se perdido.
TENTATIVAS_NO_OK = 3

# Limiar do template do TEXTO da caixa "It's precious item, please confirm!".
# Medido nos quatro prints do processo de venda: 1.000 com a caixa na tela,
# 0.454 a 0.483 nos três sem ela. 0.80 fica no meio de um vão enorme.
LIMIAR_DA_CAIXA_PRECIOSA = 0.80

# ===========================================================================
# CANDIDATOS DO `ADDR_MODAL`, para a calibração
# ===========================================================================
#
# `ADDR_MODAL` está SABIDAMENTE ERRADO nesta versão do cliente: ele guarda um
# ponteiro, então `modal_open()` é sempre `False` (está no `CLAUDE.md`). O
# candidato `+0x60` é o deslocamento MEDIDO entre a 6139 e a 6400
# (`core/rebase.py`), e é o padrão que já explicou três endereços "quebrados".
#
# O gabarito é a caixa "It's precious item" vista na tela -- ver
# `_provar_o_modal`, que roda logo abaixo, no método que substituiu o
# `modal_open()`.
CANDIDATOS_DO_MODAL = (0x012CE35C, 0x012CE3BC)

# ===========================================================================
# VELOCIDADE DA VENDA -- o que saiu, e por quê
# ===========================================================================
#
# A venda confirmava CADA clique por diferença de imagem: recorte do slot
# antes, clique, `tick(0.20)`, recorte depois, subtração. Três capturas e 200 ms
# por clique -- ~300 ms cada, ~7 s por passada de 24, quase tudo espera.
#
# Aquilo existia para responder UMA pergunta: "acabaram os itens deste slot?".
# E existia naquela forma indireta por uma limitação que o `CLAUDE.md`
# registrava: *"em todos os prints disponíveis a grade está CHEIA, então não
# existe amostra de célula vazia para medir"* -- sem amostra, não havia como
# calibrar um limiar de "vazio", e a diferença dispensava calibração.
#
# ESSA LIMITAÇÃO ACABOU: o usuário recortou `state_slot_vazio.png`. Medido
# contra a grade real, o slot vazio marca **0.966** e o segundo maior pico
# (célula com item) marca **0.368** -- vão de 0.598. A pergunta passou a ter
# resposta direta, e ela custa ~0 ms.
#
# Com isso saíram `TENTATIVAS_POR_SLOT`, `TETO_DE_CLIQUES_FISICOS`,
# `MUDANCA_MINIMA_NO_SLOT` e a `_cauda_vazia`: os quatro eram a resposta
# indireta para a mesma pergunta. O teto de cliques físicos, em particular, não
# foi "jogado fora" -- sem repetição, físico e efetivo são 1:1 e ele deixa de
# existir por construção.

# Espera entre um clique e o seguinte na grade. Era 200 ms.
#
# Não é zero de propósito: o clique na grade tem efeito de ESTADO -- o item sai
# e os de trás sobem --, e colar os cliques arriscaria clicar durante o
# rearranjo. 30 ms cortam 85% da espera e ainda dão respiro.
ESPERA_ENTRE_CLIQUES_DA_VENDA = 0.065

# ==========================================================================
# INTERRUPTOR -- A CONFERÊNCIA DE SLOT VAZIO ESTÁ DESLIGADA (decisão do usuário,
# 14/08/2026: "comenta por hora essa verificação de slot vazio e deixa clicar a
# quantidade total de vezes que o usuário configurou como estava antes").
#
# DESLIGADA, a venda faz exatamente o que fazia antes de a conferência existir:
# clica as `settings.sell_clicks` vezes configuradas, em passadas de 24, e
# clica em Sell no fim de cada uma. Nada mais.
#
# Não foi APAGADA porque as duas tentativas de conferir custaram medição de
# produção que não se recupera de graça, e as duas estão registradas no
# `CLAUDE.md`: o casamento por modelo (reprovado -- a borda de hover domina o
# recorte e a margem virou 0.008) e o contraste do miolo (calibrado nas fotos
# reais, vão de 37 pontos, mas ainda sem uma venda inteira que o confirme).
# Ligar de novo é trocar False por True; os testes do caminho continuam rodando
# com o interruptor forçado, para ele não apodrecer desligado.
#
# DESLIGADA ela também é mais RÁPIDA: some uma captura de tela por clique. A
# conferência da caixa "It's precious item" NÃO é afetada -- ela continua a cada
# clique, com interruptor ou sem, porque com a caixa aberta a passada inteira
# vende zero.
CONFERIR_SLOT_VAZIO = False

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
# O RESPIRO EM VOLTA DO BOTÃO "SELL"
# ===========================================================================
#
# Relato do usuário em 25/08/2026:
#
#     *"na hora de vender os itens, tem vezes que ao tentar clicar no botão
#      'Sell' está tudo tão rápido que acaba não clicando... criar uma pequena
#      delayzinha para garantir o clique e não atropelar funções. De resto está
#      perfeito, é só nesse momento mesmo."*
#
# POR QUE JUSTO AQUI, e não em qualquer clique. O Sell é o único clique do bot
# que chega na cola de uma RAJADA: até `CLIQUES_POR_PASSADA` (24) cliques nos
# slots a `ESPERA_ENTRE_CLIQUES_DA_VENDA` (0,065 s) cada, um atrás do outro. O
# cliente ainda está digerindo a lista quando o Sell bate na fila -- e um Sell
# engolido marca a passada inteira como vendida sem ter vendido nada.
#
# O "DEPOIS" JÁ EXISTIA, com o número solto no meio do código. Ganhou nome para
# aparecer no `docs/INTERRUPTORES.md` e poder ser ajustado sem caçar a linha.
#
# ESTES DOIS SÃO ESPERA CEGA, E É DE PROPÓSITO -- a exceção à regra do projeto.
# Antes do clique não existe o que perguntar: "o cliente terminou de digerir 24
# cliques" não tem observável. Perguntar exigiria reprocurar a âncora do Sell
# por template a cada passada, que custa uma captura para responder algo que um
# terço de segundo resolve.
#
# NÚMERO DE OBSERVAÇÃO DE CAMPO, não de medição instrumentada: é o usuário
# vendo o clique se perder. Foi escolhido para ficar confortavelmente acima da
# cadência da rajada (0,065) e na mesma ordem do respiro que já existia depois
# (0,5). Se ainda escapar, é aqui que se mexe.
ESPERA_ANTES_DO_SELL = 0.40
ESPERA_DEPOIS_DO_SELL = 0.60


class JanelaDeVenda:
    def __init__(self, ctx: BotContext, navigator: Navigator | None = None) -> None:
        self.ctx = ctx
        self.nav = navigator or Navigator(ctx)
        self._guild_token_usado_em = 0.0
        self._pedras_gastas = 0
        # A `_cauda_vazia` SAIU: ela era a resposta indireta para "acabaram os
        # itens", descoberta por tentativa e erro. Hoje o `state_slot_vazio.png`
        # responde direto e por venda (ver `sell_from_slot`).

    # ==================================================================
    # Voltar para a cidade
    # ==================================================================

    # ==================================================================
    # QUEM É O VENDEDOR -- o que cada ecossistema preenche
    # ==================================================================
    #
    # A janela de venda é a mesma no jogo inteiro; o NPC não. Estes três pontos
    # são tudo o que a máquina precisa saber, e todos têm resposta neutra --
    # uma `JanelaDeVenda` sem ecossistema vende no NPC que estiver na frente.

    # Só para o log dizer com quem se está falando.
    NOME_DO_VENDEDOR = "vendedor"

    def _config_da_venda(self):
        """De QUAL cave saem o slot inicial e o teto de passadas.

        =================================================================
        POR QUE ISTO É GANCHO, E NÃO `ctx.settings.vendor` DIRETO
        =================================================================

        `AccountSettings.vendor` é uma propriedade de compatibilidade: ela
        devolve `bc.vendor`, SEMPRE. Enquanto só a Bewitcher Cave vendia, isso
        era invisível; com a HH, a venda dela passou a ser feita com o slot da
        BC -- e a conta `gamerblazes`, com BC em 1 e HH em 3, venderia a partir
        do slot 1, que é EQUIPAMENTO. A proteção dos itens bons é geométrica
        (`sell_from_slot`), então o número errado aqui não vende de menos:
        vende o que não podia.

        Medido em `data/config.json` em 09/09/2026: 1 das 7 contas tinha os
        dois números diferentes, e `creubo` (slot 4 nos dois) escondia o
        defeito por coincidência.

        O PADRÃO CONTINUA SENDO O DA BC para não mudar o comportamento de quem
        já usava a classe base; quem tem configuração própria sobrescreve (ver
        `hh/vendedor.VendedorDaHH`).
        """
        return self.ctx.settings.vendor

    def _ui_do_jogo(self) -> UIDoJogo:
        """A máquina de operar janela do jogo, com o navegador COMPARTILHADO.

        Um navegador novo teria cronômetro de montaria próprio, cego para os
        toques deste -- e dois cronômetros de montaria significam remontar e
        desmontar em seguida.
        """
        return UIDoJogo(self.ctx, self.nav)

    def _no_ponto_do_vendedor(self) -> bool:
        """Estou de onde os cliques no vendedor funcionam?

        Padrão `True`: sem ponto medido não há o que conferir, e recusar aqui
        travaria a venda num laço sem saída.

        A Bewitcher Cave sobrescreve, porque lá o Rich Man exige a coordenada: de
        fora dela o clique direito cai no chão e ANDA com o personagem -- e a
        volta seguinte parte de um lugar pior.
        """
        return True

    def _onde_clicar_no_vendedor(self) -> tuple[int, int]:
        """Onde clicar com o direito para abrir o diálogo do NPC.

        Padrão: o ponto genérico de NPC da cena, o mesmo que a entrada da cave
        usa. Quem tem coordenada medida (o Rich Man) sobrescreve.
        """
        return self._ui_do_jogo()._ponto_padrao_do_npc()

    def _onde_clicar_no_link_de_vender(self) -> tuple[int, int] | None:
        """Onde está o link "Sell Item" DENTRO do diálogo já aberto.

        =================================================================
        POR QUE ISTO É GANCHO E NÃO UMA CONSTANTE
        =================================================================

        A coordenada da Bewitcher Cave NÃO TRANSFERE para outro NPC, e isso foi
        medido em 03/09/2026, não suposto:

            primeiro link do diálogo, no NPC da HH ....... cliente (302, 361)
            `vendor_purchase_tab` da BC .................. cliente (282, 395)
            `vendor_sell_tab` da BC ..................... cliente (266, 430)

        Os links do diálogo ficam a ~34 px um do outro, e a posição do PRIMEIRO
        depende de quantas linhas de texto o NPC escreve antes deles. O
        `Roaming Apothecary` da HH escreve duas linhas e tem dois links, então o
        "Sell Item" dele cai por volta de (302, 395) -- 35 px acima e 36 px à
        esquerda de onde a BC clica.

        É exatamente o que `clicar_link` já documenta: *"os links do diálogo
        mudam de posição conforme o texto do NPC, por isso são localizados por
        imagem e não por deslocamento fixo"*. Este caso é a prova disso.

        UM ERRO AQUI NÃO FAZ O PERSONAGEM ANDAR -- o ponto errado cai DENTRO da
        janela do diálogo, não na cena 3D. Mas a venda não abre, e a bolsa
        continua cheia; `_tentar_abrir_a_venda` confere a abertura pela âncora e
        tenta de novo.

        `None` = não sei onde é. Quem chama NÃO clica.
        """
        return self.ctx.coords.vendor_sell_tab

    def _open_npc(self, attempts: int = 4) -> bool:
        """Abre a janela de venda do NPC: clique direito, depois o link.

        Dois cliques, medidos com o personagem na coordenada (153,-492):

            clique DIREITO em (467,377)   -> abre o diálogo do NPC
            clique  esquerdo em (267,430) -> "Sell Item", dentro do diálogo

        O View Reset antes é obrigatório: são cliques na cena 3D e na janela do
        diálogo, e com a câmera fora do padrão o primeiro deles cai no chão.

        =================================================================
        O SEGUNDO CLIQUE NÃO SAI MAIS ÀS CEGAS
        =================================================================

        Esta função disparava os dois cliques em sequência e só conferia o
        resultado DEPOIS dos dois. Quando o clique direito não abria o diálogo,
        o clique no link caía na cena 3D -- e no Talisman isso FAZ O PERSONAGEM
        ANDAR. Como havia até 4 voltas, cada uma empurrava o personagem mais
        para longe da coordenada onde os cliques funcionam, e a venda inteira
        ia junto. Era o "o personagem começa a andar sozinho para o lado".

        As duas coordenadas foram CONFERIDAS contra prints do usuário: o clique
        do link cai exatamente sobre "Sell Item". O problema nunca foi onde se
        clica -- era clicar sem saber se havia diálogo.

        Agora usa `_abrir_dialogo_e_clicar`, que já existia para exatamente
        isto (é o que o Altar Stone e a saída da cave usam): clica no NPC,
        CONFERE que o diálogo abriu, e só então clica no link. Sem diálogo, não
        clica -- e o personagem fica onde está para a volta seguinte tentar.
        """
        ctx = self.ctx
        # Passa o navegador adiante: o serviço de UI também anda (o painel de
        # arredores caminha até o NPC), e um navegador novo teria cronômetro de
        # montaria próprio, cego para os toques deste.
        ui = self._ui_do_jogo()

        # F12 PRESO DURANTE AS TENTATIVAS INTEIRAS, não em volta de cada clique.
        # Ver `UIService.tentar_entrar_na_cave` para o mecanismo: as mensagens da
        # tecla entram na mesma fila POSTADA do clique e o estragam quando estão
        # encostadas nele. `segurado` conta aninhamento, então o `with` de dentro
        # de `_abrir_dialogo_e_clicar` não solta a tecla aqui.
        with esconder_jogadores.segurado(
                tecla=ctx.settings.keys.hide_players,
                segurar=ctx.key_down, soltar=ctx.key_up, log=ctx.log):
            return self._tentar_abrir_a_venda(ctx, ui, attempts)

    def _tentar_abrir_a_venda(self, ctx, ui, attempts: int) -> bool:
        ui.resetar_visao(forcar=True)

        for volta in range(1, attempts + 1):
            ctx.raise_if_stopped()
            # De fora do ponto o clique direito cai no chão e ANDA com o
            # personagem -- e aí a volta seguinte parte de um lugar pior. A
            # precisão é a MESMA que `travel_to_vendor` usa para andar até aqui.
            if not self._no_ponto_do_vendedor():
                ctx.log.warning(
                    "Saí do ponto do vendedor (estou em %s); não clico daqui",
                    ctx.memory.position())
                return False
            # O LINK VAI COMO FUNÇÃO, e não resolvido aqui.
            #
            # ERA RESOLVIDO ANTES DO CLIQUE DIREITO, e isso matava a venda de
            # quem acha o link POR IMAGEM: o texto "Sell Item" só aparece na
            # tela DEPOIS de o diálogo abrir. Medido na HH em 09/09/2026 -- a
            # tentativa morria em ~200 ms sem clicar em nada.
            #
            # Coordenada fixa (o caso da BC) passa por aqui sem mudar nada:
            # `_abrir_dialogo_e_clicar` aceita as duas formas.
            if ui._abrir_dialogo_e_clicar(
                    self._onde_clicar_no_vendedor(),
                    self._onde_clicar_no_link_de_vender,
                    f"abrir a venda do {self.NOME_DO_VENDEDOR}"):
                ctx.tick(0.3)
                if self._sell_anchor() is not None:
                    ctx.log.debug("Janela de venda aberta (tentativa %s)", volta)
                    return True
                # Sem template não há como confirmar. Segue: o diálogo abriu e o
                # link foi clicado, que é o que importa.
                if ctx.templates.load(TEMPLATE_ANCHORS["sell"][0]) is None:
                    return True
        ctx.log.warning("Não confirmei a abertura da janela de venda")
        return False

    def _sell_anchor(self) -> dict[str, tuple[int, int]] | None:
        """Localiza a janela de venda e devolve os pontos dela.

        A janela de venda NÃO aparece centralizada, então derivar a posição dela
        do tamanho da tela não funciona. Localizar o título por imagem e calcular
        o resto a partir dele resolve, e vale em qualquer resolução porque a UI
        do jogo tem tamanho fixo.
        """
        ctx = self.ctx
        template_nome, deslocamentos = TEMPLATE_ANCHORS["sell"]
        template = ctx.templates.load(template_nome)
        if template is None:
            return None
        quadro = capture_window(ctx.hwnd)
        if quadro is None:
            return None
        base = find_template(quadro, template, threshold=0.80)
        if base is None:
            return None
        return {
            nome: (base[0] + dx, base[1] + dy)
            for nome, (dx, dy) in deslocamentos.items()
        }

    def _dismiss_confirm(self) -> bool:
        """Fecha a caixa "It's precious item, please confirm!", se aberta.

        Pode clicar em Ok sempre: esses itens não são realmente valiosos, é só um
        aviso do cliente. O que não pode é deixar a caixa aberta -- com ela na
        tela, TODO clique seguinte na grade é engolido e a passada inteira vende
        zero item.

        CONFIRMA que fechou, e é por isso que existe o laço: um Ok que não pegou
        custa a passada INTEIRA, e sem conferir o bot seguiria clicando 24 vezes
        atrás de uma caixa, achando que estava vendendo.
        """
        ctx = self.ctx
        ok = self._ponto_do_ok(self._quadro())
        if ok is None:
            return False

        for tentativa in range(1, TENTATIVAS_NO_OK + 1):
            ctx.click(ok)
            ctx.tick(0.125)
            depois = self._ponto_do_ok(self._quadro())
            if depois is None:
                if tentativa > 1:
                    ctx.log.debug("Caixa de confirmação fechou no %sº Ok",
                                  tentativa)
                return True
            ok = depois          # a caixa pode ter sido redesenhada

        ctx.log.warning(
            "A caixa de item precioso não fechou depois de %s clique(s) em Ok "
            "(%s). Os cliques seguintes na grade vão ser engolidos por ela.",
            TENTATIVAS_NO_OK, ok)
        return True

    def _quadro(self):
        """Uma captura da janela, ou None. Atalho com nome curto: este arquivo
        passou a olhar a tela em vários pontos."""
        return capture_window(self.ctx.hwnd)

    def _ponto_do_ok(self, quadro) -> tuple[int, int] | None:
        """Onde está o Ok da caixa "It's precious item", ou None se ela não está.

        O template é SÓ O TEXTO da caixa, e o Ok é derivado dele por
        deslocamento medido (ver `TEMPLATE_ANCHORS["precious"]`). Duas razões
        para não usar a coordenada fixa `confirm_ok`:

          * a caixa é desenhada por cima da janela de venda, que NÃO aparece
            sempre no mesmo lugar -- é por isso que existe o `_sell_anchor`;
          * derivando, o mesmo achado responde "a caixa está aberta?" e "onde
            clicar", sem chance de as duas respostas discordarem.

        SUBSTITUIU `ctx.memory.modal_open()`. A leitura de memória era um flag
        genérico (servia também para DC e erro de login) e, pelo que o log
        mostra das leituras irmãs de UI (`bag_open` nunca respondeu True em 5 de
        5 runs), não é confiável neste cliente. Sem ela o Ok simplesmente nunca
        era clicado, e a passada inteira ficava marcada sem vender.
        """
        ctx = self.ctx
        nome, deslocamentos = TEMPLATE_ANCHORS["precious"]
        template = ctx.templates.load(nome)
        if template is None or quadro is None:
            return None
        base = find_template(quadro, template, threshold=LIMIAR_DA_CAIXA_PRECIOSA)

        # ==============================================================
        # A PROVA DO `ADDR_MODAL` PEGA CARONA AQUI, e o lugar não é acidente
        # ==============================================================
        #
        # Este método SUBSTITUIU o `modal_open()` -- está escrito acima. Então é
        # exatamente aqui que existe, no mesmo instante, a resposta certa
        # ("a caixa está na tela") e a chance de perguntar à memória a mesma
        # coisa. Se algum candidato de `ADDR_MODAL` gabaritar contra este
        # gabarito, aquele caminho pode voltar; enquanto não gabaritar, não pode.
        #
        # Recorrência alta de graça: isto roda a cada clique de venda, e a
        # captura já foi feita por quem chamou.
        self._provar_o_modal(base is not None)

        if base is None:
            return None
        dx, dy = deslocamentos["ok"]
        return (base[0] + dx, base[1] + dy)

    def _provar_o_modal(self, caixa_na_tela: bool) -> None:
        """Pontua os candidatos de `ADDR_MODAL` contra a caixa vista na tela.

        COMPLEMENTO: engole tudo, inclusive o próprio log. Instrumentação no meio
        da venda não pode custar uma passada.
        """
        if not calibracao.ATIVADA:
            return
        try:
            ctx = self.ctx
            # Ver `calibracao.quem_esta_medindo`: o `BotContext` não tem
            # `id_run`, e pedir com default zerava a contagem de runs.
            conta, id_run = calibracao.quem_esta_medindo()
            for endereco in CANDIDATOS_DO_MODAL:
                rotulo = f"{endereco:#010x}"
                if not calibracao.deve_amostrar("modal", rotulo):
                    continue
                calibracao.registrar(calibracao.julgar_booleano(
                    prova="modal", candidato=rotulo,
                    lido=ctx.memory.candidato_de_endereco_booleano(endereco),
                    na_tela=caixa_na_tela, conta=conta, id_run=id_run))
        except Exception as exc:
            try:
                self.ctx.log.debug("Prova do modal falhou: %s", exc)
            except Exception:
                pass

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
        # Contraste ALTO = tem ícone. A nota é invertida na comparação: quem
        # decide "vazio" é `_esta_vazio`, para o sentido ficar num lugar só.
        return (float(cinza.std()), "miolo")

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

    def _clicar_no_slot(
        self, alvo: tuple[int, int],
    ) -> tuple[float, str] | None:
        """UM clique no slot. Devolve a nota de "slot vazio" DEPOIS do clique.

        UMA captura serve às DUAS perguntas do ciclo, e é por isso que a
        conferência do slot é praticamente de graça:

          1. a caixa "It's precious item" está aberta? (ela engole todo clique
             seguinte -- com ela na tela os itens param de subir e a passada
             inteira vende zero);
          2. o slot ficou vazio? (não há mais item de N para frente)

        A caixa é conferida a CADA clique, e não a cada 10: ela aparece com
        MUITA frequência na venda, às vezes em sequência, e cada clique gasto
        atrás dela é um item que não subiu.
        """
        ctx = self.ctx
        # ANTES do clique: a caixa aberta engoliria exatamente este clique.
        # Isto roda com o interruptor ligado OU desligado -- é a caixa, não o
        # slot vazio, e sem ela a passada inteira vende zero.
        self._dismiss_confirm()
        ctx.click(alvo)
        ctx.tick(ESPERA_ENTRE_CLIQUES_DA_VENDA)
        if not CONFERIR_SLOT_VAZIO:
            # Desligada, nem a captura é paga: a venda clica o total configurado.
            return None
        return self._nota_do_slot_vazio(self._quadro(), alvo)

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

    def _ponto_do_slot(
            self) -> tuple[tuple[int, int], tuple[int, int], str] | None:
        """Onde clicar para vender e onde está o botão Sell.

        Prefere a janela localizada por imagem; cai para as coordenadas
        calculadas quando NÃO HÁ COMO PERGUNTAR -- e só nesse caso.

        =================================================================
        `None` = A JANELA DE VENDA NÃO ESTÁ NA TELA. NÃO CLIQUE.
        =================================================================

        Tendo o template da âncora e não o achando no quadro, a janela não está
        aberta -- e a grade não existe onde a conta calculada diz. Clicar ali é
        clicar na CENA 3D, e no Talisman isso faz o personagem ANDAR: sai do
        ponto de onde os cliques no vendedor funcionam, e a passada seguinte
        parte de um lugar pior. É o mesmo defeito que `_open_npc` já conserta
        no clique do link, um passo adiante.

        SEM O TEMPLATE segue pelas coordenadas calculadas: aí não existe
        pergunta a fazer, e recusar deixaria a venda impossível em cliente sem
        captura -- a mesma escolha de `_tentar_abrir_a_venda`.
        """
        ctx = self.ctx
        cfg = self._config_da_venda()
        pontos = self._sell_anchor()
        if pontos:
            slot1 = pontos["slot1"]
            botao = pontos["sell_button"]
            origem = "janela localizada"
        elif ctx.templates.load(TEMPLATE_ANCHORS["sell"][0]) is not None:
            ctx.log.warning(
                "A janela de venda não está na tela; não clico na grade "
                "calculada -- isso cairia na cena 3D e faria o personagem "
                "andar para longe do vendedor.")
            return None
        else:
            slot1 = ctx.coords.sell_slot_xy(1)
            botao = ctx.coords.vendor_sell_button
            origem = "coordenadas calculadas"

        grade = ctx.coords.sell_grid
        indice = max(1, cfg.sell_start_slot) - 1
        linha, coluna = divmod(indice, grade.columns)
        alvo = (slot1[0] + coluna * grade.cell_w,
                slot1[1] + linha * grade.cell_h)
        return alvo, botao, origem

    def sell_from_slot(self) -> int:
        """Vende a partir do slot configurado, em passadas de 24.

        MECÂNICA: a grade tem 6 colunas por 4 linhas (24 slots). Ao tirar um item
        de um slot, os seguintes SOBEM para preencher o buraco. Então clicar
        repetidamente na MESMA posição N esvazia tudo de N para frente, e os slots
        1..N-1 nunca se movem -- portanto nunca são vendidos. A proteção dos itens
        bons é geométrica, não uma lista de exceções que pode estar incompleta.

        Devolve quantos itens saíram das bolsas, medido por memória.
        """
        ctx = self.ctx
        # A CONFIGURAÇÃO É DA CAVE QUE ESTÁ VENDENDO -- ver `_config_da_venda`.
        cfg = self._config_da_venda()

        # "Acabaram os itens" é POR VENDA: a bolsa desta ida não diz nada sobre
        # a próxima.
        acabou = False
        antes = ctx.memory.bag_count()
        # O TOTAL É DO PERSONAGEM desde 09/09/2026 -- uma bolsa, um número,
        # valendo para toda cave. O TETO de passadas continua sendo da cave.
        total_de_cliques = max(1, ctx.settings.sell_clicks)
        passadas = cfg.passadas_para(total_de_cliques)
        restantes = total_de_cliques

        ctx.log.info(
            "Venda: %s clique(s) no total, em até %s passada(s) de %s "
            "(protegidos: slots 1..%s) | bolsa com %s item(ns) | "
            "conferência de slot vazio: %s",
            restantes, passadas, CLIQUES_POR_PASSADA,
            max(0, cfg.sell_start_slot - 1), antes,
            "ligada" if CONFERIR_SLOT_VAZIO else "DESLIGADA (clica o total)",
        )

        for passada in range(1, passadas + 1):
            ctx.raise_if_stopped()
            if restantes <= 0:
                break

            if not self._open_npc():
                break

            ponto = self._ponto_do_slot()
            if ponto is None:
                # A janela sumiu entre abrir e mirar. Encerra a venda: insistir
                # aqui é clicar no chão. A run seguinte tenta de novo.
                break
            alvo, botao_vender, origem = ponto
            nesta = min(CLIQUES_POR_PASSADA, restantes)
            ctx.log.info("Passada %s/%s: %s cliques em %s [%s]",
                         passada, passadas, nesta, alvo, origem)

            dados = 0
            for _ in range(nesta):
                ctx.raise_if_stopped()
                leitura = self._clicar_no_slot(alvo)
                dados += 1

                if leitura is None:
                    # Sem imagem não se julga: segue clicando. Recusar aqui
                    # deixaria a venda impossível em cliente sem captura.
                    continue

                nota, qual = leitura
                if not self._esta_vazio(leitura):
                    # A leitura de TODO clique vai para o log de dev: é ela que
                    # mostra, numa venda real, se o corte de contraste está no
                    # lugar. Cheio fica perto de 60, vazio perto de 3.
                    ctx.log.debug("Slot %s com item (contraste %.1f, corte %.1f)",
                                  alvo, nota, CONTRASTE_QUE_E_SLOT_VAZIO)
                    continue

                # Parece vazio. Antes de encerrar a venda inteira, CONFIRMA com
                # a grade parada -- a esta cadência o vazio quase sempre é o
                # rearranjo, não o fim.
                firme = self._confirmar_slot_vazio(alvo)
                if firme is None:
                    ctx.log.debug(
                        "Slot %s parecia vazio (contraste %.1f), mas voltou a "
                        "ter item: era o rearranjo, não o fim — contagem zerada",
                        alvo, nota)
                    continue

                # Slot N vazio quer dizer que não há mais nada de N para
                # frente: os itens SOBEM para preencher o buraco. Clicar
                # mais é clicar no nada, e as passadas seguintes também.
                acabou = True
                ctx.log.info(
                    "O slot %s está vazio (contraste %.1f, corte %.1f; %s "
                    "leituras seguidas espaçadas de %.2f s): acabaram os "
                    "itens. Encerrando a venda depois de %s clique(s) nesta "
                    "passada.",
                    alvo, firme[0], CONTRASTE_QUE_E_SLOT_VAZIO,
                    LEITURAS_VAZIAS_PARA_PARAR, ESPERA_PARA_CONFIRMAR_VAZIO,
                    dados)
                break

            restantes -= dados
            # Uma caixa aberta engoliria o clique em Sell, e a passada inteira
            # ficaria marcada sem nunca ser vendida.
            self._dismiss_confirm()
            # VENDE O QUE JÁ SUBIU, mesmo tendo parado cedo: o que está na lista
            # tem que virar dinheiro.
            #
            # RESPIRO ANTES E DEPOIS -- ver `ESPERA_ANTES_DO_SELL`. O de antes é
            # o que faltava: o Sell chegava na cola de até 24 cliques a 0,065 s,
            # com o cliente ainda digerindo a lista, e um Sell engolido marca a
            # passada como vendida sem ter vendido nada.
            ctx.tick(ESPERA_ANTES_DO_SELL)
            ctx.click(botao_vender)
            ctx.tick(ESPERA_DEPOIS_DO_SELL)
            self._dismiss_confirm()
            ctx.log.info("Passada %s: %s clique(s) no slot", passada, dados)
            if acabou:
                break

        depois = ctx.memory.bag_count()
        if antes is not None and depois is not None:
            vendidos = max(0, antes - depois)
            ctx.log.info("Venda concluída: %s itens vendidos (%s -> %s)",
                         vendidos, antes, depois)
            if vendidos == 0:
                diario.registrar_evento(
                    ctx.account_login, "acao-sem-efeito",
                    f"venda não tirou item nenhum da bolsa ({antes} itens); "
                    f"slot inicial {cfg.sell_start_slot}",
                    ctx.memory.position(), ctx.memory.location(),
                )
            return vendidos
        return 0

    # ==================================================================
    # Compra
    # ==================================================================

