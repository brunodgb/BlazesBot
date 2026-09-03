"""
Configuração do BlazesBot.

TRÊS NÍVEIS, e a separação é deliberada:

  1. MÁQUINA (BotConfig) -- caminho do Client.bat, quantas contas abrir. Não faz
     sentido cada conta ter um caminho de jogo diferente.

  2. PERSONAGEM (AccountSettings) -- teclas, montaria, pet, limiares de poção.
     Vale em qualquer atividade: a tecla da poção é a mesma na BC ou em qualquer
     outra cave.

  3. ATIVIDADE (BCConfig) -- boss, rota, reset de time, venda. É específico da
     Bewitcher Cave.

O nível 3 existe separado porque o escopo vai crescer: quando entrarem outras
caves, cada uma ganha o próprio bloco (`hollow`, `dr`...) sem mexer no que é do
personagem. Assim o jogador configura as teclas uma vez e reaproveita em tudo.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .core.secrets import decrypt, encrypt

# Versão 4: o caminho da cave saiu do arquivo e passou a viver em
# `bot/mapa_bc.py`; entraram a capacidade de bolsas e a sequência do modo APP.
CONFIG_VERSION = 4
DEFAULT_CONFIG_PATH = Path("data") / "config.json"

# Gravar a configuração acontece de DUAS fontes ao mesmo tempo: a interface
# (quando você muda qualquer campo) e os supervisores em suas threads (quando
# descobrem o nick do personagem de uma conta). Duas escritas simultâneas no
# mesmo arquivo produzem JSON truncado -- e config.json truncado leva embora as
# senhas cifradas. Daí o lock e a gravação atômica em `save`.
_LOCK_ARQUIVO = threading.Lock()

# ---------------------------------------------------------------------------
# Montaria
# ---------------------------------------------------------------------------

MOUNT_SPEEDS = (90, 100, 110, 120, 130, 140, 150)
DEFAULT_MOUNT_SPEED = 90


def mount_multiplier(speed_pct: int) -> float:
    return 1.0 + max(0, int(speed_pct)) / 100.0


def travel_time_factor(speed_pct: int) -> float:
    """Escala os tempos limite de deslocamento. Referência: a montaria mais lenta."""
    return mount_multiplier(MOUNT_SPEEDS[0]) / mount_multiplier(speed_pct)


# ---------------------------------------------------------------------------
# Teclas
# ---------------------------------------------------------------------------

@dataclass
class KeyBinds:
    """Teclas que o BOT vai pressionar. É o bot que aperta; aqui só se declara.

    Os padrões são os do próprio jogo (System Interface > Keys Setting):
    Sit/Stand = X, Shift to Next Target = TAB, Item Interface = I,
    Community Interface = F.
    """

    # Combate
    attack_skills: list[str] = field(default_factory=lambda: ["1", "2", "3"])
    aoe_skill: str = ""
    super_skill: str = ""
    break_soul: str = ""
    heal_skill: str = ""
    buffs: list[str] = field(default_factory=list)
    # Consumíveis
    hp_potion: str = "9"
    battle_hp_potion: str = ""
    pet_food: str = "6"
    stone_charm: str = "7"
    # Deslocamento e utilidades
    mount: str = "SPACE"
    # Skill de velocidade da MONTARIA: +30% por 30 s, com 6 min de recarga.
    #
    # É a única skill que funciona montado -- todo o resto exige desmontar. Por
    # isso ela é usada só DENTRO da cave, onde o tempo é o que importa: gastá-la
    # andando pela cidade seria desperdiçar a recarga.
    speed_skill: str = ""
    # Guild Token: volta para a cidade SEM gastar item, com 10 min de recarga.
    # Tem preferência sobre a pedra de retorno justamente por não gastar -- a
    # pedra some de uma em uma e precisa ser recomprada.
    guild_token: str = ""
    pet_summon: str = "R"
    # Interface -- padrões do jogo
    sit: str = "X"
    # AUTO-SELEÇÃO: a tecla que seleciona o PRÓPRIO personagem.
    #
    # Medido em 28/08/2026: ela põe o id da própria conta no `TARGET_ID`, e é
    # isso que permite a cada conta publicar "eu sou o <id>" no mural. Sem esse
    # id a Fada não tem como confirmar em quem clicou -- e o invariante é que id
    # que não bate não cura. Ou seja: conta sem esta tecla NÃO é curável.
    #
    # Serve também para a auto-cura da própria Fada.
    self_target: str = "F1"
    # A tecla de SEGUIR o alvo selecionado (o "follow" do jogo).
    #
    # VAZIA POR PADRÃO, e isso é decisão: ela não tem atalho padrão no cliente,
    # e chutar uma faria a Fada apertar uma tecla que faz outra coisa. Enquanto
    # estiver vazia, a Fada da HH avisa no log e não tenta seguir.
    #
    # Quem usa: `bot/hh/fada.py`, no modo HH+Fada -- a curandeira clica no
    # retrato do líder e aperta isto, e o JOGO caminha por ela. É o que o bot em
    # Lua faz (`keys.follow = "p"`), e é muito melhor que a Fada refazer os 66
    # waypoints por conta própria: seguir não tem como sair da rota.
    follow: str = ""
    next_target: str = "TAB"
    inventory: str = "I"
    friend_list: str = "F"
    # Tecla que vai DIRETO para a página 1 da barra de atalhos.
    #
    # VAZIO por padrão, e isso importa: sem tecla o bot continua fazendo o que
    # sempre fez -- dois cliques no botão de subir, que sobe e PARA no 1. A
    # tecla é um atalho, não um requisito.
    #
    # O jogo deixa configurar uma tecla por página; aqui só interessa a da
    # página 1, porque é a que resolve com UM toque. E ela é melhor que o clique
    # por ir direto ao destino: o clique precisa de dois toques justamente
    # porque só sabe subir um degrau por vez.
    hotbar_page_1: str = ""
    # Esconder os outros jogadores. Vazio = o bot não mexe nisso.
    #
    # Não é só conveniência visual: o catador de loot clica no CHÃO, e outro
    # personagem em cima do cadáver muda o que o clique acerta. O truque que faz
    # o esconder GRUDAR está em `core/esconder_jogadores.py`.
    hide_players: str = "F12"

    def validate(self) -> list[str]:
        from .core.inputs import VK_CODES

        problemas: list[str] = []

        def checar(rotulo: str, valor: str, obrigatorio: bool) -> None:
            if not valor:
                if obrigatorio:
                    problemas.append(f"{rotulo}: tecla obrigatória não definida.")
                return
            if str(valor).upper() not in VK_CODES:
                problemas.append(f"{rotulo}: tecla '{valor}' não reconhecida.")

        if not [k for k in self.attack_skills if k]:
            problemas.append("Skills de ataque: defina ao menos uma.")

        # A POÇÃO DE HP DEIXOU DE SER OBRIGATÓRIA quando há skill de cura.
        # Uma Fairy cura com mana e recarga; exigir que ela cadastre uma poção
        # que nunca vai usar é pedir configuração falsa. Mas UMA das duas tem que
        # existir, senão não há como recuperar vida em lugar nenhum.
        if not self.hp_potion and not self.heal_skill:
            problemas.append(
                "Recuperar vida: defina a tecla de Poção de HP ou a de Cura — "
                "sem nenhuma das duas o bot não tem como se curar."
            )
        checar("Poção de HP", self.hp_potion, False)
        checar("Montaria", self.mount, True)
        checar("Próximo alvo", self.next_target, True)
        checar("Inventário", self.inventory, True)
        checar("Lista de amigos", self.friend_list, False)

        opcionais = [
            ("AoE", self.aoe_skill), ("Super Skill", self.super_skill),
            ("Break Soul", self.break_soul), ("Cura", self.heal_skill),
            ("HP de batalha", self.battle_hp_potion),
            ("Comida de pet", self.pet_food),
            ("Pedra de retorno", self.stone_charm),
            ("Guild Token", self.guild_token),
            ("Skill de velocidade", self.speed_skill),
            ("Invocar pet", self.pet_summon),
            ("Sentar", self.sit),
            ("Barra de atalhos p.1", self.hotbar_page_1),
            ("Esconder jogadores", self.hide_players),
        ]
        for rotulo, valor in opcionais:
            checar(rotulo, valor, False)
        for i, k in enumerate(self.attack_skills, 1):
            checar(f"Skill de ataque {i}", k, False)
        for i, k in enumerate(self.buffs, 1):
            checar(f"Buff {i}", k, False)
        problemas += self.teclas_repetidas()
        return problemas

    def teclas_repetidas(self) -> list[str]:
        """A MESMA tecla em duas funções diferentes.

        O jogo não permite -- cada tecla tem um destino só no Keys Setting --,
        então uma configuração com repetição descreve algo que não existe: o bot
        acha que trocou de barra e na verdade disparou uma skill, e nunca
        percebe. O erro é silencioso, e é por isso que ele é barrado aqui e
        também na hora de digitar, nas duas interfaces.
        """
        usos: dict[str, list[str]] = {}

        def anotar(rotulo: str, valor: str) -> None:
            if valor:
                usos.setdefault(str(valor).upper(), []).append(rotulo)

        for i, k in enumerate(self.attack_skills, 1):
            anotar(f"Ataque {i}", k)
        for i, k in enumerate(self.buffs, 1):
            anotar(f"Buff {i}", k)
        for rotulo, valor in (
            ("AoE", self.aoe_skill), ("Super Skill", self.super_skill),
            ("Break Soul", self.break_soul), ("Cura", self.heal_skill),
            ("Poção HP", self.hp_potion),
            ("Poção HP em batalha", self.battle_hp_potion),
            ("Comida Pet", self.pet_food), ("Retorno", self.stone_charm),
            ("Montaria", self.mount),
            ("Skill de velocidade", self.speed_skill),
            ("Guild Token", self.guild_token),
            ("Pet Invoc", self.pet_summon), ("Sentar", self.sit),
            ("Prox Alvo", self.next_target), ("Inventário", self.inventory),
            ("Amigos", self.friend_list),
            ("Barra de atalhos p.1", self.hotbar_page_1),
            ("Esconder jogadores", self.hide_players),
        ):
            anotar(rotulo, valor)

        return [f"A tecla '{tecla}' está em mais de uma função: "
                f"{', '.join(onde)}."
                for tecla, onde in sorted(usos.items()) if len(onde) > 1]

    @property
    def has_aoe(self) -> bool:
        """AoE só existe se houver tecla. Sem tecla, a opção não faz sentido."""
        return bool(self.aoe_skill)


# ---------------------------------------------------------------------------
# Personagem: pet e poções
# ---------------------------------------------------------------------------

# Cada comida de pet dá 5 de felicidade, o máximo é 100, e o pet perde 1 a cada
# 10 minutos. Ou seja: uma comida cobre 50 minutos. Alimentar nesse intervalo
# mantém o pet sem desperdiçar item.
PET_FEED_MINUTES = 50

# FAIXA FECHADA DO INTERVALO DE COMIDA (26/08/2026, decisão do usuário).
#
# Fora dela a conta acima deixa de fechar: abaixo de 40 min o item é desperdiçado
# (o pet ainda não gastou 5 de felicidade), acima de 60 o pet passa fome entre
# refeições. Este campo é o ÚNICO campo de tempo da interface que continua em
# MINUTOS: em milissegundos ele pediria 7 dígitos para um valor que se ajusta de
# 5 em 5 minutos, e não é delay de mecânica, é grade de longo prazo.
PET_FEED_MINUTOS_MIN = 40
PET_FEED_MINUTOS_MAX = 60


def pet_feed_na_faixa(minutos: object) -> int:
    """Grampeia o intervalo na faixa. Aplicado na LEITURA e na TELA.

    Grampeia em vez de RECUSAR de propósito: `config.json` salvo por versão
    antiga (o combo da GUI oferecia 10, 20 e 30 minutos) sobe corrigido em vez de
    fazer o bot recusar a configuração inteira. É o mesmo contrato do piso de
    `MINIMO_DELAY_MS`.
    """
    try:
        valor = int(minutos or PET_FEED_MINUTES)
    except (TypeError, ValueError):
        valor = PET_FEED_MINUTES
    return max(PET_FEED_MINUTOS_MIN, min(PET_FEED_MINUTOS_MAX, valor))


@dataclass
class PetConfig:
    """Cuidado do pet.

    Pet sem comida DESAPARECE, e um pet que sumiu no meio da cave estraga a run
    sem avisar. Por isso não existe liga/desliga: com o farm ativo o pet é
    obrigatório, e o bot alimenta sempre.
    """

    feed_every_minutes: int = PET_FEED_MINUTES
    feed_on_start: bool = False   # útil se você não acabou de alimentar à mão
    summon_on_login: bool = True

    # ESTADO, NÃO CONFIGURAÇÃO -- e por isso não aparece em tela nenhuma.
    #
    # É o instante (epoch) em que a próxima refeição vence. Mora aqui pelo mesmo
    # motivo que `last_hwnd`/`last_pid`: é estado por conta que precisa
    # SOBREVIVER A REINÍCIO.
    #
    # Sem ele, a grade da comida nasce de novo a cada restart -- e a garantia de
    # N refeições por dia (28,8 com o intervalo de 50 min) se perde justamente
    # nas sessões em que o bot é reiniciado. Pet sem comida DESAPARECE, então o
    # custo de perder a grade é perder o pet no meio de uma run.
    #
    # `0.0` = grade ainda não iniciada, e é diferente de um instante no passado
    # (que significaria "venceu, alimente agora").
    proxima_comida_em: float = 0.0


@dataclass
class PotionConfig:
    """Limiares de poção e cura. Valem em qualquer atividade."""

    # MÍNIMO DE HP PARA INICIAR A CAVE.
    #
    # É o único limiar de cura que existe, e ele é ALVO, não gatilho: o bot se
    # cura até chegar aqui e só então começa a travessia. Abaixo disso ele não
    # sai do lugar.
    #
    # ANTES ERAM TRÊS NÚMEROS para a mesma decisão -- este, um "não curar acima
    # de" e um "só Super Skill acima de" --, e eles se contradiziam com facilidade:
    # bastava o terceiro ficar maior que o segundo para a poção nunca ser usada, e
    # a janela precisava de um aviso em vermelho explicando isso. Um alvo só não
    # tem como se contradizer.
    hp_pct: int = 85
    # EM BATALHA SÓ A POÇÃO DE BATALHA AGE, e ela é RESERVA, não manutenção.
    #
    # Era 90%, ou seja: o bot bebia poção de batalha quase o tempo todo durante a
    # luta. Passou a 15% por decisão do usuário em 19/08/2026, junto com a regra
    # de que em batalha o personagem não se cura -- durante a luta o bot luta, e
    # a poção de batalha existe para o susto, não para manutenção.
    #
    # ATENÇÃO À VIZINHANÇA: `emergency_pct` (25%) aborta a luta. Com os dois nos
    # valores de fábrica, a abortagem chega ANTES da poção -- o que é o desfecho
    # certo, e faz a poção ser mesmo último recurso. Subir este número acima de
    # `emergency_pct` faz a poção sair antes do aborto; é escolha legítima, mas é
    # escolha, e o padrão não a assume.
    battle_hp_pct: int = 15
    emergency_pct: int = 25       # abaixo disso, aborta a luta
    # Teto da recuperação. Não é editável: é rede de segurança contra ficar sem
    # poção na bolsa, não estratégia. Cada poção leva 15 s, então isto dá oito.
    max_heal_seconds: int = 120
    # `prefer_heal_skill` SAIU em 19/08/2026. Era um segundo lugar para dizer o
    # que a tecla já diz: quem configura a tecla de cura quer usar a cura -- a
    # mesma regra que o `combat.py` já escrevia ("Sem perfil de classe: quem tem
    # tecla de cura tem cura. A configuração é a declaração"). Dois lugares
    # dizendo a mesma coisa acabam discordando, e aí o usuário tem uma tecla
    # configurada que não é usada e nenhuma pista do porquê.
    #
    # Config antigo com a chave é lido e IGNORADO, como os limiares de mana.


# ---------------------------------------------------------------------------
# Atividade: Bewitcher Cave
# ---------------------------------------------------------------------------

@dataclass
class BCRoute:
    """Ajustes da rota. O CAMINHO em si não mora aqui.

    Os waypoints ficam em `bot/mapa_bc.py`, no código. A separação é deliberada
    e vem de um problema real: enquanto o caminho era gravado no `config.json`,
    um caminho antigo de uma execução anterior continuava valendo depois de o
    caminho certo ser medido no jogo -- e não havia como perceber, porque tudo
    parecia configurado. O `config.json` chegou a guardar os 38 waypoints
    herdados do T-R0XX enquanto os 57 medidos até então estavam só na
    documentação.

    Caminho de cave é propriedade do JOGO, não preferência de quem usa. O que
    sobra aqui é o que realmente varia: o modo da rota e os textos de busca.
    """

    # ROTA: sempre direto ao boss. Deixou de ser escolha do usuário.
    #
    # O modo "safe" limpava as Gun Witches do caminho antes de encostar no boss.
    # Ele saía do desenho do bot -- que é ignorar todo mob de trajeto -- e o
    # caminho dele já estava desligado no código (ver `routine._do_ate_o_boss`),
    # porque mirava por nome e usava o combate por ponteiro de alvo, os dois em
    # standby. Uma opção que não muda nada é pior que nenhuma opção: ela promete.
    mode: str = "standard"
    cave_search_text: str = "Skull"
    woods_search_text: str = "Din"
    transport_search_text: str = "Fay"

    # -- caminho, vindo do código -----------------------------------------

    @property
    def cave_entrance(self) -> tuple[int, int]:
        from .bot.bc.mapa_bc import ENTRADA_EM_GHOST_DIN

        return ENTRADA_EM_GHOST_DIN

    @property
    def boss_position(self) -> tuple[int, int]:
        from .bot.bc.mapa_bc import POSICAO_DO_BOSS

        return POSICAO_DO_BOSS

    @property
    def altar_path(self) -> list[tuple[int, int]]:
        from .bot.bc import mapa_bc

        return mapa_bc.como_lista(mapa_bc.CAMINHO_ATE_O_ALTAR)

    @property
    def boss_approach(self) -> list[tuple[int, int]]:
        from .bot.bc import mapa_bc

        return mapa_bc.como_lista(mapa_bc.CAMINHO_ATE_O_BOSS)

    @property
    def tricky_waypoints(self) -> list[tuple[int, int]]:
        from .bot.bc.mapa_bc import WAYPOINTS_PROBLEMATICOS

        return list(WAYPOINTS_PROBLEMATICOS)


# ---------------------------------------------------------------------------
# Bolsas
# ---------------------------------------------------------------------------

# Cada bolsa do jogo tem 30 espaços. O personagem começa com uma e pode ter até
# três (base + duas Expand Bag).
SLOTS_POR_BOLSA = 30
MAX_BOLSAS = 3

# Espaços livres a partir dos quais já vale voltar para vender.
#
# Não é frescura: uma run derruba mais de um item, e chegar na cave com 3 espaços
# livres significa PERDER drop -- item que não cabe simplesmente não entra. Seis
# é a folga que cobre uma run inteira com margem.
FOLGA_PADRAO_DE_SLOTS = 6


@dataclass
class BagConfig:
    """Quantas bolsas o personagem tem, e quando isso obriga a ir vender.

    A quantidade é informada por quem configura, e não lida do jogo, por um
    motivo concreto: uma "Expand Bag" marcada como *Expired* continua aparecendo
    na interface mas NÃO recebe item. Deduzir a capacidade da tela erraria
    exatamente no caso que importa. Já quem joga sabe quantas bolsas válidas tem.
    """

    bolsas: int = 1
    folga_minima: int = FOLGA_PADRAO_DE_SLOTS

    @property
    def capacidade(self) -> int:
        return max(1, min(MAX_BOLSAS, self.bolsas)) * SLOTS_POR_BOLSA

    def espaco_livre(self, itens: int | None) -> int | None:
        """Espaços livres, ou None se a contagem de itens não pôde ser lida."""
        if itens is None:
            return None
        return max(0, self.capacidade - itens)

    def precisa_vender(self, itens: int | None) -> bool:
        """A bolsa está apertada o bastante para valer a viagem?

        Devolve False quando não deu para ler a contagem: vender sem saber
        quantos itens existem levaria o bot a viajar sem motivo e, pior, a clicar
        na grade de venda de uma janela que talvez esteja vazia.
        """
        livre = self.espaco_livre(itens)
        return livre is not None and livre < self.folga_minima


# ---------------------------------------------------------------------------
# Módulo APP -- macro de teclado, independente do farm da cave
# ---------------------------------------------------------------------------

# Linhas oferecidas na aba APP. Dezesseis cobre com folga a macro mais longa que
# faz sentido escrever à mão nesta tela.
PASSOS_DO_APP = 20

# Espera mínima de QUALQUER campo de tempo do APP, em milissegundos.
#
# Decisão do usuário em 26/08/2026: *"o mínimo vai ser 100ms em todos os campos
# do APP"*.
#
# Vale para as linhas da macro E para a espera da linha 0 (a do TAB). Zero
# deixava duas teclas saírem no mesmo instante, e o cliente engole a segunda —
# é o mesmo defeito do botão "Sell" da venda, só que espalhado por toda a
# sequência. O piso é aplicado na LEITURA e na TELA, nos dois lados, para que o
# arquivo salvo por uma versão antiga também suba corrigido.
# PISO DE QUALQUER DELAY DA INTERFACE, EM MILISSEGUNDOS.
#
# As duas interfaces mostram TODO campo de tempo em ms (pedido do usuário: havia
# segundos, milissegundos e minutos na mesma tela) e nenhuma delas aceita menos
# que isto. O piso saiu daqui, da espera da macro, e valia só para ela; virou o
# piso de todos porque o defeito é o mesmo em qualquer delay -- tempo perto de
# zero faz duas ações saírem no mesmo instante e o cliente engole a segunda.
MINIMO_DELAY_MS = 100

# Um número lido por dois lados mora num lugar só.
MINIMO_DE_ESPERA_DO_APP_MS = MINIMO_DELAY_MS

# ÍCONE DO APLICATIVO — UM ARQUIVO SÓ para as duas interfaces.
#
# Mora em `web/public/` porque é de lá que o Vite o copia para o `dist/`, e é o
# `dist/` que o pywebview abre. A GUI PyQt6 aponta para o MESMO arquivo: duas
# cópias divergiriam na primeira troca de arte.
#
# Antes disto, `favicon.ico` era referenciado em dois lugares do HTML e NÃO
# EXISTIA no repositório -- o que aparecia no titlebar era o placeholder de
# imagem quebrada do WebView2. E não havia `setWindowIcon` em lugar nenhum, então
# a janela e a barra de tarefas também estavam sem ícone.
ICONE_DO_APP = Path(__file__).resolve().parents[1] / "web" / "public" / "favicon.ico"


# Teto do nome de um grupo de contas (`Account.grupo`).
#
# O rótulo entra num cabeçalho que ocupa a largura da tabela: nome gigante
# empurra o layout e o usuário não vê por quê. Aplicado na LEITURA e na TELA, nos
# dois lados -- mesmo contrato do piso dos delays.
LIMITE_DO_NOME_DO_GRUPO = 40


def segundos_para_ms(segundos: float) -> int:
    """Segundos guardados no `config.json` -> milissegundos da TELA.

    `attack_delay` e `launch_delay` continuam `float` de segundos no arquivo e no
    `combat.py`: a padronização em ms é de APRESENTAÇÃO. Trocar a unidade no
    armazenamento obrigaria a migrar todo `config.json` existente e a mexer no
    laço de ataque, que é a parte mais medida do projeto, para ganhar nada.
    """
    return max(MINIMO_DELAY_MS, round(float(segundos or 0) * 1000))


def ms_para_segundos(ms: float) -> float:
    """Milissegundos da TELA -> segundos guardados. Ver `segundos_para_ms`."""
    limpo = max(MINIMO_DELAY_MS, int(ms or MINIMO_DELAY_MS))
    # 3 casas: 100 ms é 0,1 s exato e 8500 ms é 8,5 s -- sem dízima no arquivo.
    return round(limpo / 1000, 3)


@dataclass
class AppStep:
    """Uma linha da macro: uma tecla e quanto esperar depois dela.

    NÃO EXISTE MAIS UM `enabled` POR LINHA. Antes cada linha tinha a própria caixa
    "usar", e havia duas formas de a mesma linha não rodar: sem tecla, ou com
    tecla e desmarcada. Duas formas para o mesmo resultado é uma a mais do que
    precisa, e a caixa desmarcada com tecla preenchida parecia configurada sem
    estar. Agora a regra é uma só: a linha roda se tiver tecla.
    """

    key: str = ""
    delay_ms: int = 800

    def __post_init__(self) -> None:
        # O PISO MORA AQUI, no dataclass, e não em cada chamador: qualquer
        # `AppStep` construído em qualquer lugar já nasce respeitando o mínimo.
        # Ver `MINIMO_DE_ESPERA_DO_APP_MS`.
        self.delay_ms = max(MINIMO_DE_ESPERA_DO_APP_MS, int(self.delay_ms or 0))

    @property
    def valido(self) -> bool:
        return bool(self.key)


# ---------------------------------------------------------------------------
# TIME DO APP -- a mesma macro rodando em várias contas ao mesmo tempo
# ---------------------------------------------------------------------------

# Quantas contas o líder arrasta junto. Pedido do usuário em 27/08/2026:
# *"eu posso escolher até 4 outras contas cadastradas"*. O líder NÃO entra na
# conta -- são 4 seguidores, 5 janelas no total.
MAXIMO_DE_SEGUIDORES_DO_TIME = 4

# Os três modos. A diferença entre eles é O QUE fica sincronizado:
#
#   "copiar"      -- só a macro. Cada conta roda no seu ritmo, sem esperar
#                    ninguém. É o time sem sincronia, para quem só quer a mesma
#                    sequência em várias contas.
#   "largada"     -- a macro E o começo de cada volta. Todos dão o TAB e
#                    começam a sequência juntos; cada um bate no SEU mob. É o
#                    padrão, e na prática costuma dar no mesmo mob: com a trava
#                    de posição ligada os personagens ficam quase no mesmo
#                    ponto, e o TAB deste jogo pega o mais perto.
#   "mesmo_alvo"  -- a macro, a largada e o ALVO. O líder publica o id do mob e
#                    os seguidores dão TAB até o próprio alvo bater.
#
# NÃO EXISTE TECLA DE ASSIST neste jogo -- conferido campo a campo em
# `KeyBinds`. Por isso "mesmo_alvo" só tem um caminho possível: comparar o
# `TARGET_ID` lido da memória de cada conta com o do líder.
MODOS_DO_TIME = ("copiar", "largada", "mesmo_alvo")
MODO_PADRAO_DO_TIME = "largada"


def normalizar_time_logins(bruto: object) -> list[str]:
    """A lista de seguidores, sempre limpa: texto, sem vazio, sem repetido, no teto.

    A DEFESA É FEITA DUAS VEZES DE PROPÓSITO -- na leitura do `config.json`
    (`BotConfig._app_from_dict`) e na ponte web (`Api.salvar_personagem`).
    São duas portas independentes: o arquivo pode ter sido editado à mão e o
    JavaScript pode mandar qualquer coisa. É a mesma decisão do piso de 100 ms,
    que também mora nos dois lados (ver `MINIMO_DE_ESPERA_DO_APP_MS`) -- e o
    motivo é o mesmo: "a tela impõe" não é garantia, é boa vontade.
    """
    if not isinstance(bruto, (list, tuple)):
        return []
    limpos: list[str] = []
    for item in bruto:
        login = str(item or "").strip()
        # Login VAZIO é conta recém-criada que ainda não foi cadastrada. Guardar
        # isso deixaria uma vaga do time apontando para lugar nenhum -- e o time
        # ficaria esperando a largada de quem nunca vai chegar.
        if not login or login in limpos:
            continue
        limpos.append(login)
        if len(limpos) >= MAXIMO_DE_SEGUIDORES_DO_TIME:
            break
    return limpos


# Padrões das duas barras de cura do time. Pedido do usuário em 28/08/2026:
# *"duas barras em todas as contas (padrão 30% e 90%) na aba APP; e em time, a
# configuração do líder manda"*.
#
# São perguntas diferentes e por isso são dois números: `PEDIR` é "estou ferido
# o bastante para chamar a Fada (ou beber poção)"; `PARAR` é "já estou curado o
# bastante, pode ir para o próximo". A distância entre os dois é o que impede a
# Fada de ser chamada de novo no instante em que termina.
CURA_PEDIR_PCT_PADRAO = 30
CURA_PARAR_PCT_PADRAO = 90


def normalizar_pct(bruto: object, padrao: int) -> int:
    """Uma porcentagem de 1 a 100, ou o padrão. Nunca 0 e nunca acima de 100.

    Zero não é "desligado" aqui: seria "peça cura quando estiver morto". Quem
    desliga a cura é a tecla vazia, não a barra no fim da escala.
    """
    try:
        valor = int(bruto)
    except (TypeError, ValueError):
        return padrao
    return max(1, min(100, valor))


def normalizar_time_modo(bruto: object) -> str:
    """O modo escolhido, ou o padrão. Valor desconhecido NUNCA entra.

    Sem isto, um `config.json` editado à mão (ou um erro de digitação no
    JavaScript) colocaria uma string qualquer no campo, e quem lê o modo
    decidiria por comparação de igualdade -- ou seja, cairia silenciosamente no
    ramo "não é nenhum dos três" e o time não faria nada, sem erro nenhum.
    """
    modo = str(bruto or "").strip()
    return modo if modo in MODOS_DO_TIME else MODO_PADRAO_DO_TIME


@dataclass
class AppConfig:
    """A macro do módulo APP: teclas em laço contínuo, no estilo do UoPilot.

    Cada linha é uma tecla e um tempo de espera em milissegundos. A sequência roda
    de cima para baixo e recomeça da primeira linha ao terminar a última, até o
    usuário parar. TAB é aceito como tecla, como qualquer outra.

    ISTO NÃO TEM LIGAÇÃO COM O FARM DA CAVE. O módulo APP é um sistema separado
    (`blazesbot/modo_app/`): ele manda tecla e espera, e não lê memória, não
    reconhece tela e não navega mapa. Antes ele substituía a rotação de ataque do
    combate da cave, e os dois se influenciavam; hoje são independentes.
    """

    enabled: bool = False
    steps: list[AppStep] = field(
        default_factory=lambda: [AppStep() for _ in range(PASSOS_DO_APP)]
    )
    # A CADA QUANTAS VOLTAS o lixo da bolsa é apagado. 0 = nunca.
    #
    # Configurável, e não fixo no código, porque o tempo de uma volta depende
    # inteiramente da macro que o usuário montou: dez voltas podem ser
    # quarenta segundos ou dez minutos. O 0 dá o desligamento por conta, sem
    # mexer em código.
    #
    # Só o ecossistema APP usa isto -- o BC resolve bolsa cheia vendendo.
    apagar_lixo_a_cada: int = 10
    # ==================================================================
    # A LINHA 0 DA MACRO: o TAB, e o tempo depois dele
    # ==================================================================
    #
    # Pedido do usuário em 26/08/2026:
    #
    #     *"Como a macro 0, mas sem poder editar o botão e não pode colocar em
    #      outro lugar, sempre será a primeira, e o tempo sim será editável;
    #      aquele 1 segundo após o tab será isso."*
    #
    # ELA NÃO É UM `AppStep`, e isso é decisão de desenho. Como linha de verdade
    # ela obrigaria `passos_ativos`, `uma_volta` e a régua do inalcançável (que
    # conta LINHAS da macro) a conhecer uma exceção que não bate em ninguém. A
    # tela DESENHA como linha 0; o executor lê um número.
    #
    # A TECLA NÃO MORA AQUI: é `KeyBinds.next_target`, a mesma do BC, porque
    # tecla descreve o JOGO e não o ecossistema. A tela mostra essa tecla
    # desabilitada, para não mentir sobre o que o bot aperta.
    #
    # O 1000 substitui a constante `ESPERA_DEPOIS_DO_TAB` do executor, que passa
    # a ser só o padrão de quem roda sem configuração.
    espera_depois_do_tab_ms: int = 1000
    # TRAVA DE POSIÇÃO: ao iniciar o APP, salva a posição atual do personagem e,
    # se ele andar (pela própria macro ou por qualquer outro motivo), faz o
    # personagem voltar andando (sem montaria). Após N voltas sem movimento,
    # dá um pequeno "shuffle" anti-AFK.
    #
    # Funciona SOMENTE quando a memória lê (o supervisor injeta a leitura). Em
    # clientes onde a posição não é lida, o APP segue exatamente como antes --
    # o isolamento do executor não quebra.
    travar_posicao: bool = True
    shuffle_apos_n_voltas: int = 30
    # ==================================================================
    # O TIME: a mesma macro rodando em várias contas ao mesmo tempo
    # ==================================================================
    #
    # Pedido do usuário em 27/08/2026: *"eu posso escolher até 4 outras contas
    # cadastradas e todas vão rodar a macro daquela conta, de forma
    # sincronizada, para que sempre ataquem juntos"*.
    #
    # QUEM MONTA O TIME É O LÍDER, e estes dois campos só têm efeito na conta
    # que os preencheu. A conta que aparece no `time_logins` de outra é
    # SEGUIDORA, e o time dela própria é ignorado enquanto isso. É uma regra só,
    # e ela é o que impede o nó de A liderar B enquanto B lidera A.
    #
    # O QUE É EMPRESTADO É SÓ A MACRO -- as 20 linhas, os delays e a espera
    # depois do TAB. Trava de posição, cura e a tecla do TAB continuam de cada
    # conta: a posição-base é a coordenada DAQUELE personagem (copiar mandaria o
    # seguidor andar para o mapa errado) e a tecla descreve o teclado daquele
    # cliente, não a macro.
    #
    # GUARDA LOGIN, não nick: é o login que identifica conta na tela do editor.
    # Login que não existe mais não trava nada -- o time roda sem ele, e nunca
    # espera por quem não vai chegar.
    time_logins: list[str] = field(default_factory=list)
    time_modo: str = MODO_PADRAO_DO_TIME

    # ==================================================================
    # A FADA e as duas barras de cura
    # ==================================================================
    #
    # `fada` só tem efeito EM TIME: a conta marcada deixa de atacar e passa a
    # curar os aliados. Sozinha, a flag não faz nada -- e isso é de propósito,
    # para marcar a conta uma vez e ela se comportar conforme o contexto.
    #
    # AS DUAS BARRAS VALEM PARA TODA CONTA, com ou sem time: elas descrevem
    # "quando estou ferido o bastante" e "quando estou curado o bastante", e
    # essas perguntas existem desde antes da Fada -- a poção usa as mesmas.
    # EM TIME, as do LÍDER mandam, para o time inteiro se comportar igual.
    #
    # Ver `docs/decisoes/fada.md`.
    fada: bool = False
    cura_pedir_pct: int = CURA_PEDIR_PCT_PADRAO
    cura_parar_pct: int = CURA_PARAR_PCT_PADRAO
    # Posição base salva (X, Y) — INTERNA, não aparece na UI.
    # Gravada automaticamente quando o APP inicia com travar_posicao ligado.
    # Usada pelo executor para devolver o personagem ao ponto original.
    _base_pos_x: int = 0
    _base_pos_y: int = 0

    @property
    def passos_ativos(self) -> list[AppStep]:
        """As linhas que vão rodar: as que têm tecla, na ordem da tela."""
        return [p for p in self.steps if p.valido]

    @property
    def utilizavel(self) -> bool:
        """Ligado E com pelo menos uma tecla preenchida.

        Ligado sem tecla nenhuma não há o que enviar, então "ligado" não basta
        para o executor ter trabalho.
        """
        return bool(self.enabled and self.passos_ativos)


# Cliques na venda: a grade tem 24 slots, então os valores úteis são múltiplos
# de 6 (uma linha por vez). Passar de 24 cobre bolsas com mais itens.
SELL_CLICK_OPTIONS = tuple(range(6, 91, 6))

# Limite do jogo: a janela mostra 24 itens e só dá para marcar 24 por venda.
# Passando disso é obrigatório apertar Sell e recomeçar.
CLIQUES_POR_PASSADA = 24


@dataclass
class BCVendor:
    """Venda e recompra ao voltar da cave."""

    sell_start_slot: int = 3
    # GATILHO de retorno à cidade: contagem de runs do bot BC. A leitura de
    # itens na bolsa para saber a folga era imprecisa e o bot nunca entrava em
    # venda; o gatilho virou "depois de N runs da cave, busca o vendedor".
    runs_before_selling: int = 5
    # Total de cliques desejado na visita. O bot divide isso em passadas de 24,
    # porque 24 é o limite do jogo por venda: clica 24, aperta Sell, repete.
    sell_clicks: int = 24
    max_sell_passes: int = 4
    buy_return_charm: bool = False
    buy_quantity_clicks: int = 1
    # O antigo gatilho por espaço livre da bolsa (folga) foi REMOVIDO: a
    # leitura de itens da bolsa mostrou ser imprecisa e o bot nunca acionava a
    # venda por esse caminho. Ver `VendorService.precisa_ir_vender`.
    vendor_search_text: str = "Rich"

    @property
    def vendor_position(self) -> tuple[int, int]:
        from .bot.bc.mapa_bc import POSICAO_DO_VENDEDOR

        return POSICAO_DO_VENDEDOR

    @property
    def passadas_necessarias(self) -> int:
        """Quantas passadas de 24 cliques cobrem o total configurado."""
        alvo = max(1, self.sell_clicks)
        return min(self.max_sell_passes,
                   -(-alvo // CLIQUES_POR_PASSADA))   # divisão para cima


# Skill de velocidade da montaria, valores do jogo. Ficam aqui e não na
# configuração porque são mecânica, não escolha: errar o cooldown faz o bot
# apertar a tecla no vazio e achar que ganhou velocidade.
SPEED_DURACAO_SEGUNDOS = 30
SPEED_RECARGA_SEGUNDOS = 6 * 60

# Quantos mobs de guarda esperam na entrada do covil do boss. Contados no jogo.
GUARDAS_DO_COVIL = 4

# Como os quatro guardas se chamam no jogo. Lido no quadro do alvo, no print do
# covil. Fica no código e não na configuração pelo mesmo motivo dos waypoints: é
# propriedade do JOGO, não preferência de quem usa.
#
# NÃO USE ISTO PARA DECIDIR NADA NO COMBATE. Medido no covil
# (`logs/combate.log`), o nome do mob é ILEGÍVEL em parte das entidades: dos três
# Gun Witch mortos numa sessão, dois leram `'m93@\x1a'` e `'p?@\x1a'` -- que são os
# bytes de ponteiros de heap, não texto. O campo `+0xBC` guarda texto em algumas
# entidades e ponteiro em outras, e o mesmo endereço leu três nomes diferentes ao
# longo da sessão (slot reaproveitado).
#
# Havia uma conferência de nome na mira dos guardas por causa deste valor, e ela
# foi REMOVIDA: teria dado TAB para longe de Gun Witches de verdade. Quem seleciona
# é o TAB (que neste servidor só cicla mobs, porque o PvP é desligado) e quem
# reconhece a morte é o HP do alvo chegando a zero.
#
# O que sobrou: a rota segura usa este nome em `acquire_target`, e o log mostra o
# nome quando ele é legível. Nada além disso.
NOME_DOS_GUARDAS = "Gun Witch"


@dataclass
class BCConfig:
    """Tudo que é específico da Bewitcher Cave."""

    boss_name: str = "Blaze Skull Marshal"
    # Intervalo entre duas teclas da rotação de ataque: uma investida a cada
    # 500 ms, medido no jogo. Não é um limite de recarga -- skill em recarga
    # simplesmente não sai, e a rotação segue para a próxima.
    attack_delay: float = 0.5
    # Prazo da LUTA depois que ela começa. Não é mais editável na janela: é uma
    # rede de segurança contra a flag de combate presa em ligado, não um ajuste
    # de estratégia. Quem mexe nele está mexendo no detector de falha, e o valor
    # certo depende do bot, não do personagem.
    #
    # A espera para a luta COMEÇAR não tem prazo nenhum -- ver `combat.SEM_PRAZO`.
    max_fight_seconds: int = 300
    heal_before_second_phase: bool = True
    aoe_until_mana_pct: int = 30
    # Usar a skill de velocidade da montaria dentro da cave.
    #
    # Só dentro: ela dura 30 s e recarrega em 6 min, então gastá-la na cidade
    # significa não tê-la na travessia, que é onde o tempo custa vida.
    usar_skill_de_velocidade: bool = True
    # Matar os guardas é OBRIGATÓRIO, e por isso deixou de ser opção na janela.
    #
    # Não é preferência: eles atacam de qualquer forma, e a fase deles é o que
    # coloca o personagem em combate no covil. Desligar só faria a run chegar no
    # boss com quatro mobs somando dano por trás. O campo continua aqui para o
    # caso de alguma ferramenta precisar pular a fase em um teste.
    matar_guardas: bool = True
    # Nick da conta que fica parada só para resetar a cave.
    #
    # Vazio = não usa reset de time. Preenchido = o bot convida esse nick antes
    # de cada entrada. Não há liga/desliga separado: o campo em branco já diz
    # tudo, e um interruptor a mais seria só uma forma de errar.
    reset_nick: str = ""
    route: BCRoute = field(default_factory=BCRoute)
    vendor: BCVendor = field(default_factory=BCVendor)



# COMO CADA CAVE SE CHAMA no código. Existe para "qual cave está rodando" ser
# um valor comparável em vez de uma string solta em cada arquivo -- e é isso que
# permite `ctx.raise_if_stopped` conferir o interruptor CERTO.
CAVE_BC = "bc"
CAVE_HH = "hh"
CAVES = (CAVE_HH, CAVE_BC)      # na ordem do despacho: a HH tem precedência


# Os dois modos de reset da HH. A cave não renasce sozinha -- regra do jogo.
MODO_SOLO_DA_HH = "solo"
MODO_FADA_DA_HH = "fada"
MODOS_DO_RESET_DA_HH = (MODO_SOLO_DA_HH, MODO_FADA_DA_HH)


def normalizar_modo_do_reset(bruto: object) -> str:
    """O modo escolhido, ou "solo". Valor desconhecido NUNCA entra.

    Mesma razão de `normalizar_time_modo`: um arquivo editado à mão (ou uma
    interface com um campo livre) colocaria qualquer string aqui, e quem lê o
    modo faria a comparação falhar em silêncio -- a Fada simplesmente não
    entraria na cave, sem nada no log dizendo por quê.
    """
    modo = str(bruto or "").strip().lower()
    return modo if modo in MODOS_DO_RESET_DA_HH else MODO_SOLO_DA_HH


# ---------------------------------------------------------------------------
# HH -- Black Wind Camp Dungeon
# ---------------------------------------------------------------------------

@dataclass
class HHRoute:
    """Os NOMES da rota da HH. As coordenadas moram em `bot/hh/mapa_hh.py`.

    O CAMINHO NÃO ENTRA AQUI, e é a mesma regra da BC: um waypoint errado não
    deixa o bot "mais lento", faz o personagem bater na parede até o tempo
    estourar. Enquanto ele morou no `config.json`, uma rota antiga gravada por
    uma execução anterior continuou sendo usada depois de a certa ser medida, e
    era impossível perceber porque tudo parecia configurado.

    O que sobra aqui é o que realmente varia entre servidores e traduções: os
    TEXTOS de busca do painel de arredores.
    """

    # O MESMO NPC de transporte da Bewitcher Cave.
    transport_search_text: str = "Fay"
    # A NPC que fica perto da porta da HH, encontrada pelo painel de arredores.
    npc_search_text: str = "Mutual"
    # O vendedor, do lado de FORA da cave.
    vendor_search_text: str = "Roaming"


@dataclass
class HHVendor:
    """A venda da HH: o `Roaming Apothecary`, do lado de fora da cave.

    A JANELA É A MESMA DA BC -- mesma moldura, mesma grade, mesma paginação 1/3,
    mesmo par Sell/Cancel. Então a máquina de vender vale sem alteração e o que
    muda é só qual NPC e a partir de que slot.
    """

    # De que slot da bolsa começar a vender. Os primeiros são equipamento e
    # consumível; vender a partir deles seria vender o que o bot precisa.
    sell_start_slot: int = 3
    # Quantas runs antes de ir vender. A conta de verdade é a bolsa
    # (`BagConfig`); isto é o teto de segurança para quando a leitura falhar.
    runs_before_selling: int = 5
    sell_clicks: int = 24
    max_sell_passes: int = 4


@dataclass
class HHConfig:
    """Tudo que é específico da Black Wind Camp Dungeon."""

    # O modo do reset. A cave NÃO renasce sozinha: sem desfazer e refazer o
    # time, os bosses não voltam e a run seguinte não tem o que matar.
    #
    #   "solo"  -- igual à BC: convida a conta de reset, ela aceita, o
    #              personagem entra e o time é DESFEITO. A reset nunca entra.
    #   "fada"  -- as DUAS entram, a Fada acompanha e cura, e o desfaz-refaz
    #              acontece FORA, depois de sair.
    modo_do_reset: str = MODO_SOLO_DA_HH
    # Nick da conta que reseta (ou da Fada, no modo "fada").
    #
    # Vazio = sem reset, e aí a cave só rende na primeira run. Não há liga e
    # desliga separado: o campo em branco já diz tudo.
    reset_nick: str = ""
    # Intervalo entre duas teclas da rotação de ataque.
    attack_delay: float = 0.5
    # Rede de segurança contra a flag de combate presa em ligado.
    max_fight_seconds: int = 300
    aoe_until_mana_pct: int = 30
    usar_skill_de_velocidade: bool = True
    # Limpar os mobs do caminho a cada N waypoints quando NÃO está montado.
    #
    # Vem do bot em Lua, que limpa a cada 3 passos a pé e não limpa nada
    # montado -- montado o personagem não para, e é isso que torna a montaria a
    # forma normal de atravessar. `0` desliga.
    limpar_mobs_a_cada: int = 3
    route: HHRoute = field(default_factory=HHRoute)
    vendor: HHVendor = field(default_factory=HHVendor)


# ---------------------------------------------------------------------------
# Personagem
# ---------------------------------------------------------------------------

@dataclass
class AccountSettings:
    """Configuração do personagem.

    Note que NÃO existe seleção de classe. A ideia inicial de filtrar campos por
    classe atrapalhava mais que ajudava: o Wizard, por exemplo, se cura com a
    Super Skill, então esconder "cura" para quem não é Fairy tirava justamente a
    opção mais útil dele. Todos os campos ficam disponíveis e quem configura
    decide o que usa.
    """

    mount_speed_pct: int = DEFAULT_MOUNT_SPEED
    keys: KeyBinds = field(default_factory=KeyBinds)
    pet: PetConfig = field(default_factory=PetConfig)
    potions: PotionConfig = field(default_factory=PotionConfig)
    bags: BagConfig = field(default_factory=BagConfig)
    app: AppConfig = field(default_factory=AppConfig)
    bc: BCConfig = field(default_factory=BCConfig)
    hh: HHConfig = field(default_factory=HHConfig)
    # Marque na conta que fica parada só para as outras resetarem a cave.
    accept_team_invites: bool = False
    # Catar o loot do chão na mão, para a conta cujo pet NÃO tem a skill de
    # auto pick.
    #
    # POR CONTA e não global, e isso é o ponto: o usuário tem contas com o pet
    # certo e contas sem ele. Um interruptor global obrigaria a escolha errada
    # para metade delas. Ver `core/catador.py`.
    usar_catador: bool = False

    # -- derivados ---------------------------------------------------------

    @property
    def mount_multiplier(self) -> float:
        return mount_multiplier(self.mount_speed_pct)

    @property
    def time_factor(self) -> float:
        return travel_time_factor(self.mount_speed_pct)

    @property
    def use_aoe(self) -> bool:
        """AoE é usado se, e somente se, houver tecla definida para ele."""
        return self.keys.has_aoe

    # Atalhos para o código do bot não precisar navegar a árvore inteira.
    @property
    def route(self) -> BCRoute:
        return self.bc.route

    @property
    def vendor(self) -> BCVendor:
        return self.bc.vendor

    def validate(self) -> list[str]:
        problemas = list(self.keys.validate())
        if self.mount_speed_pct not in MOUNT_SPEEDS:
            problemas.append(
                f"Velocidade de montaria inválida: {self.mount_speed_pct}%."
            )
        if not (1 <= self.bags.bolsas <= MAX_BOLSAS):
            problemas.append(
                f"Quantidade de bolsas deve estar entre 1 e {MAX_BOLSAS}."
            )
        if not (1 <= self.bags.folga_minima <= self.bags.capacidade):
            problemas.append(
                "Folga mínima de espaços deve caber na capacidade das bolsas."
            )
        # Modo APP ligado sem tecla nenhuma não tem o que enviar: o executor
        # ficaria girando sem apertar nada.
        if self.app.enabled and not self.app.passos_ativos:
            problemas.append(
                "Modo APP está ligado mas nenhuma linha tem tecla. Preencha ao "
                "menos uma, ou desligue o modo."
            )
        if not (1 <= self.bc.vendor.sell_start_slot <= 24):
            problemas.append("Slot inicial de venda deve estar entre 1 e 24.")
        if self.bc.vendor.runs_before_selling < 1:
            problemas.append(
                "Runs antes de vender deve ser pelo menos 1."
            )
        if not (0 < self.potions.hp_pct < 100):
            problemas.append("Limiar de poção de HP deve estar entre 1 e 99.")
        # "safe" continua sendo aceito na LEITURA para não reprovar config antigo,
        # mas não muda nada: o caminho dele está desligado no código e a opção
        # saiu da janela. Ver o comentário em `BCRoute.mode`.
        if self.bc.route.mode not in ("standard", "safe"):
            problemas.append(f"Modo de rota inválido: '{self.bc.route.mode}'.")
        if not (PET_FEED_MINUTOS_MIN <= self.pet.feed_every_minutes
                <= PET_FEED_MINUTOS_MAX):
            problemas.append(
                "Intervalo de comida de pet deve estar entre "
                f"{PET_FEED_MINUTOS_MIN} e {PET_FEED_MINUTOS_MAX} minutos.")
        # A TECLA DA LISTA DE AMIGOS SAIU DAQUI, e a mudança é de ALCANCE, não
        # de rigor: ela continua obrigatória para quem usa reset de time, mas
        # agora reprova SÓ O BC DAQUELA CONTA, em `BotConfig.problema_do_reset`.
        # Aqui dentro ela derrubava a execução inteira -- uma conta mal
        # configurada e nenhuma das outras subia.
        return problemas


# ---------------------------------------------------------------------------
# Conta
# ---------------------------------------------------------------------------

@dataclass
class Account:
    """Uma conta do jogo, com a configuração do personagem dela.

    Login e relogin automático são padrão para toda conta ativa. O que se liga
    por conta é o farm da cave -- e pode ser ligado ou desligado com o bot
    rodando, porque o supervisor consulta este campo a cada ciclo.
    """

    login: str = ""
    password_enc: str = ""
    position: str = "Center"           # Left | Center | Right
    server: str = "Light in the Darkness"
    enabled: bool = True
    bc_farm: bool = False
    # Farmar a HH (Black Wind Camp Dungeon) nesta conta.
    #
    # SEPARADA do `bc_farm` de propósito: são duas caves, e ligar as duas
    # na mesma conta não é "farmar mais" -- é duas rotinas disputando o
    # teclado. O supervisor consulta as duas e a HH tem precedência, para a
    # escolha ser previsível em vez de depender de qual laço chegou antes.
    hh_farm: bool = False
    # NICK DO PERSONAGEM desta conta. É a chave de reconhecimento da janela.
    #
    # O bot batiza a janela do jogo com o nick e guarda o nick aqui, no
    # config.json. Na execução seguinte ele varre os clientes abertos, acha o
    # que tem este personagem e reassume o controle -- sem abrir cliente novo e
    # sem voltar para a fila de login, que em dia cheio passa de três horas.
    #
    # Pode ser preenchido à mão na edição da conta. O bot SOBRESCREVE com o que
    # ler da memória a cada login, então trocar de personagem se corrige sozinho.
    last_char_name: str = ""
    # PINO DA JANELA desta conta (hwnd, pid) — INTERNO, não aparece em nenhuma
    # interface. É a âncora para reconhecer a MESMA janela do jogo na próxima
    # execução, inclusive no MEIO do login, quando nem nick nem título
    # identificam a conta. O Windows recicla valores de hwnd, então o par é
    # sempre validado antes de usar (ver `_validar_hwnd_salvo` no supervisor) e
    # é apagado quando a janela morre ou passa a ser de outra conta. Por ser
    # serial, só existe no config.json — o usuário não o vê em tela nenhuma.
    last_hwnd: int = 0
    last_pid: int = 0
    # IDENTIDADE ESTÁVEL DESTA CONTA -- INTERNA, não aparece em interface nenhuma
    # (mesma categoria de `last_hwnd`/`last_pid`).
    #
    # A web endereçava toda escrita pelo ÍNDICE da conta na lista, e isso valia
    # enquanto a lista não podia ser reordenada: `_conta()` documentava a
    # premissa ("o índice é estável enquanto o editor está aberto"). Arrastar
    # linha para reordenar QUEBRA essa premissa por construção, e a falha não é
    # cosmética: com a ordem do disco diferente da ordem da tela, um
    # `definir_senha` grava a senha NA CONTA ERRADA -- login quebrado e senha
    # certa perdida, sem desfazer.
    #
    # O `uid` acerta a conta mesmo com a GUI e a web abertas ao mesmo tempo, que
    # é o cenário em que recarregar a tabela depois do arraste não protege.
    #
    # Vazio no dataclass e preenchido por `garantir_uid()`: conta de
    # `config.json` antigo recebe o dela na leitura, e o valor NUNCA muda depois.
    uid: str = ""
    # RÓTULO DE ORGANIZAÇÃO, escolhido pelo usuário. NÃO É TIME.
    #
    # Não representa nada para o bot: serve para ele agrupar as contas na tabela
    # como quiser. Time do APP continua sendo `AppConfig.time_logins` (por
    # LOGIN, no líder) e party do BC continua sendo `accept_team_invites` --
    # `docs/INVARIANTES.md` proíbe derivar qualquer um dos dois da tela.
    #
    # Os grupos existentes são os valores distintos deste campo, na ordem em que
    # aparecem na lista de contas: assim a ordem dos grupos também sai do array e
    # continua havendo UMA fonte de verdade sobre ordem.
    grupo: str = ""
    settings: AccountSettings = field(default_factory=AccountSettings)

    def garantir_uid(self) -> str:
        """Preenche o `uid` se ele não existe, e devolve o valor final.

        Idempotente de propósito: é chamada na leitura do arquivo, na criação da
        conta e antes de qualquer resposta que enderece contas. Trocar um `uid`
        já gravado apontaria as escritas em voo para outra conta.

        NORMALIZA PARA `str`, e isso não é zelo: o `config.json` é editado à mão
        (o usuário duplica conta copiando bloco), e um `uid` que chegasse como
        NÚMERO ficaria `int` aqui enquanto as buscas comparam com texto -- a
        conta existiria e nenhuma escrita a encontraria.
        """
        atual = self.uid
        if not isinstance(atual, str):
            atual = "" if atual is None else str(atual)
        self.uid = atual.strip() or uuid.uuid4().hex
        return self.uid

    @property
    def farms(self) -> bool:
        """Esta conta farma ALGUMA cave? Vale para as duas.

        =================================================================
        NÃO USE ISTO PARA DIZER "O BC ESTÁ LIGADO"
        =================================================================

        Era o que ela significava quando existia uma cave só, e alargar o
        significado sem revisar quem lê vazou estado da HH para o BC em
        02/09/2026: o resumo do supervisor publicava `farms` no campo `farm`, a
        ponte web repassava, e o espelho ao vivo MARCAVA a caixa do BC quando o
        usuário ligava a HH.

        A pergunta certa aqui é a de ELEGIBILIDADE -- "esta conta está ocupada
        farmando?" --, e é para isso que ela serve: validar a conta de reset,
        recusar uma conta de farm como seguidora do time do APP, cobrar a
        configuração de quem vai farmar.

        Quem quer saber de UMA cave lê `bc_farm` ou `hh_farm` direto. Travado
        por `tests/test_hh_nao_vaza_para_o_bc.py`.
        """
        return bool(self.bc_farm or self.hh_farm)

    @property
    def cave_ligada(self) -> str:
        """QUAL cave está ligada: `"hh"`, `"bc"` ou `""`.

        A ORDEM É A DO DESPACHO (`AccountSupervisor._operate`): marcar as duas
        roda a HH. Ter a mesma precedência escrita em dois lugares seria ter
        duas respostas possíveis para "o que vai rodar" -- então quem responde é
        esta propriedade, e o supervisor a usa.
        """
        if self.hh_farm:
            return CAVE_HH
        if self.bc_farm:
            return CAVE_BC
        return ""

    def remember_char_name(self, nome: str) -> bool:
        """Guarda o nick visto nesta conta. Devolve True se o valor MUDOU.

        O retorno é o gatilho de gravação: só vale escrever o config.json quando
        há novidade, e o login acontece muitas vezes por sessão.

        Nome vazio nunca apaga o que já está guardado -- a leitura da memória
        falha legitimamente enquanto o mundo carrega, e apagar o nick nesse
        instante destruiria justamente a pista que evita a fila.
        """
        nome = (nome or "").strip()
        if not nome or nome == self.last_char_name:
            return False
        self.last_char_name = nome
        return True

    def remember_window(self, hwnd: int, pid: int) -> bool:
        """Guarda o pino (hwnd, pid) da janela desta conta.

        Devolve True se o par MUDOU — é o gatilho de gravação, como
        `remember_char_name` (o login acontece muitas vezes por sessão, e
        gravar à toa reescreve o config.json). Valores não-positivos nunca
        apagam: um hwnd pode ser lido como 0 legitimamente, e apagar nesse
        instante destruiria a âncora que evita a fila.
        """
        hwnd = int(hwnd or 0)
        pid = int(pid or 0)
        if hwnd <= 0 or pid <= 0:
            return False
        if hwnd == self.last_hwnd and pid == self.last_pid:
            return False
        self.last_hwnd = hwnd
        self.last_pid = pid
        return True

    def forget_window(self) -> bool:
        """Apaga o pino (hwnd, pid). Devolve True se havia algo a apagar.

        Diferente de `remember_window`: este é o caminho EXPLÍCITO de remoção,
        usado quando a janela morreu ou passou a ser de outra conta. Aí sim se
        persiste o apagamento, para a âncora não ficar apontando para nada.
        """
        if not self.last_hwnd and not self.last_pid:
            return False
        self.last_hwnd = 0
        self.last_pid = 0
        return True

    def set_password(self, texto: str) -> None:
        self.password_enc = encrypt(texto)

    def get_password(self) -> str:
        return decrypt(self.password_enc)

    def validate(self) -> list[str]:
        problemas: list[str] = []
        if not self.password_enc:
            problemas.append(f"Conta '{self.login}': senha vazia.")
        if self.position not in ("Left", "Center", "Right"):
            problemas.append(f"Conta '{self.login}': posição inválida.")
        # Só cobra a configuração de farm de quem vai farmar.
        if self.farms:
            problemas += [f"Conta '{self.login}': {p}"
                          for p in self.settings.validate()]
        return problemas


# ---------------------------------------------------------------------------
# Máquina
# ---------------------------------------------------------------------------

@dataclass
class BotConfig:
    """Configuração da máquina. Nada aqui é específico de personagem."""

    version: int = CONFIG_VERSION
    client_bat: str = r"C:\Program Files (x86)\TalismanOnline\Client.bat"
    # `max_clients` FOI APOSENTADO em 26/08/2026, e o campo saiu de vez em vez
    # de virar interruptor: ele não guardava um caminho de código, guardava um
    # TETO, e teto órfão num `config.json` antigo continuaria cortando contas sem
    # nenhuma tela para desfazer. Quem manda é `enabled_accounts()`: roda quantas
    # contas o usuário marcar como ativas. A chave sai da lista de `from_dict`,
    # então arquivo velho com ela é simplesmente ignorado.
    launch_delay: float = 8.0
    dc_confirm_seconds: int = 20
    relogin_backoff_cap: int = 300
    minimize_clients: bool = False
    # Aproveitar um cliente qualquer parado na tela de login.
    #
    # Desligado por padrão de propósito. Reconhecer uma janela COMO SENDO desta
    # conta (pelo personagem na memória ou pelo título) é seguro e sempre vale.
    # Já pegar um cliente "livre" é surpreendente: com várias contas subindo ao
    # mesmo tempo, uma podia adotar o cliente que a outra acabou de abrir, e o
    # resultado era o bot não abrir a janela que devia ou abrir várias.
    reuse_login_screen_clients: bool = False
    accounts: list[Account] = field(default_factory=list)
    # Mantido só para reserva: a resolução real vem da janela medida.
    resolution: str = "1024x768"

    def __post_init__(self) -> None:
        # De onde esta configuração foi lida. NÃO é campo do dataclass de
        # propósito: não pertence ao JSON, e `asdict` só enxerga campos. Serve
        # para quem só tem o objeto em mãos (os supervisores) poder gravar de
        # volta no arquivo certo sem receber o caminho por parâmetro.
        self._source_path: Path | None = None

    def enabled_accounts(self) -> list[Account]:
        return [a for a in self.accounts if a.enabled and a.login]

    def farming_accounts(self) -> list[Account]:
        return [a for a in self.enabled_accounts() if a.farms]

    def reset_accounts(self) -> list[Account]:
        """Contas habilitadas marcadas como 'aceitar convites de time'.

        É a lista que as duas interfaces oferecem no seletor de reseter -- o
        campo deixou de ser texto livre justamente para que o nick escolhido
        seja sempre uma conta que este bot controla e, portanto, consegue
        observar. Ver `problema_do_reset`.
        """
        return [a for a in self.enabled_accounts()
                if a.settings.accept_team_invites]

    def reordenar_contas(self, uids: list[str]) -> bool:
        """Reordena `accounts` conforme a sequência de `uids`. `True` se mudou.

        A ORDEM DAS CONTAS É A ORDEM DO ARRAY -- não existe campo de ordem, e não
        pode existir: seriam duas fontes de verdade para a mesma coisa, com a
        pergunta sem resposta "se discordarem, quem manda?". Reordenar é
        reordenar a lista, e `save()` grava.

        TOLERANTE POR DESENHO, e cada tolerância conserta um estrago possível:

        - uid desconhecido é IGNORADO (a tela pode estar defasada de outra
          interface que removeu uma conta);
        - conta que a tela NÃO citou vai para o fim, na ordem relativa que já
          tinha -- nunca é descartada. Perder uma conta aqui é perder a senha
          cifrada dela;
        - `uids` repetido só vale na primeira aparição.

        O resultado tem SEMPRE o mesmo conjunto de contas de antes; só a ordem
        muda. É isso que `test_reordenar_nao_perde_conta` trava.
        """
        # PRIMEIRA APARIÇÃO GANHA, e a marca de "já colocada" é por IDENTIDADE
        # DE OBJETO (`id()`), não por `uid`.
        #
        # Conserta uma PERDA DE CONTA achada na revisão: com duas contas
        # carregando o mesmo uid (`config.json` editado à mão), um índice por uid
        # guardaria só a última, a primeira seria marcada como "usada" pelo uid
        # alheio e sumiria do resultado -- levando a senha cifrada dela. Objeto é
        # único mesmo quando o uid não é. Também alinha com `conta_por_uid`, que
        # devolve a PRIMEIRA: as duas concordam sobre quem um uid repetido
        # endereça.
        por_uid: dict[str, Account] = {}
        for conta in self.accounts:
            por_uid.setdefault(conta.garantir_uid(), conta)

        nova: list[Account] = []
        colocados: set[int] = set()
        for uid in uids:
            conta = por_uid.get(str(uid or "").strip())
            if conta is None or id(conta) in colocados:
                continue
            colocados.add(id(conta))
            nova.append(conta)
        # As não citadas mantêm a ordem relativa original.
        nova.extend(c for c in self.accounts if id(c) not in colocados)

        if len(nova) != len(self.accounts):
            # Rede de segurança: preferir NÃO reordenar a gravar uma lista
            # menor. Perder conta aqui é perder senha cifrada, sem desfazer.
            raise RuntimeError("reordenação perderia conta — ordem preservada")
        mudou = [id(c) for c in nova] != [id(c) for c in self.accounts]
        self.accounts = nova
        return mudou

    def garantir_uids_unicos(self) -> None:
        """Todo `Account` com `uid` próprio, sem repetição. Idempotente.

        POR QUE ISTO EXISTE, e por que é chamado também na LEITURA DA TABELA e
        não só ao abrir o arquivo: a interface endereça conta por `uid`, então
        duas contas com o mesmo uid são indistinguíveis PARA ELA -- arrastar a
        segunda moveria a primeira, e uma escrita cairia na conta errada. A
        desduplicação por identidade de objeto em `reordenar_contas` impede
        PERDER conta, mas não resolve endereçar a certa; quem resolve é isto.

        Uid repetido é cenário real: o `config.json` é editado à mão e o usuário
        duplica conta copiando o bloco. Quem repete perde o valor e ganha outro
        -- o primeiro a aparecer mantém o dele, para não invalidar referências.
        """
        vistos: set[str] = set()
        for conta in self.accounts:
            conta.garantir_uid()          # normaliza o tipo antes de comparar
            if conta.uid in vistos:
                conta.uid = ""
            vistos.add(conta.garantir_uid())

    def conta_por_uid(self, uid: str) -> Account | None:
        """A conta com este `uid`, ou `None`. A busca das escritas da interface."""
        alvo = str(uid or "")
        if not alvo:
            return None
        for conta in self.accounts:
            if conta.garantir_uid() == alvo:
                return conta
        return None

    def lider_do_time_do_app(self, login: str, ignorar: str = "") -> str:
        """Quem já puxa esta conta como seguidora do time do APP, ou "".

        `ignorar` é o login de um líder que NÃO conta na resposta -- e ele não é
        conveniência: a tela do editor pergunta isto sobre cada candidata para
        saber quais desabilitar, e sem ignorar a conta que está sendo editada a
        pergunta se responde sozinha. Os seguidores do próprio líder apareciam
        como "já no time de <ele mesmo>", desmarcados e travados: o usuário abria
        o time que ele montou e via um time vazio.

        UMA CONTA SÓ PODE SEGUIR UM LÍDER, e é esta pergunta que garante isso:
        a tela usa a resposta para desabilitar a conta na lista de outro líder,
        e o supervisor vai usá-la para saber que a própria lista dela deve ser
        ignorada enquanto ela for seguidora. Sem essa regra única, A pode
        liderar B enquanto B lidera A, e não existe resposta certa para "de quem
        é a macro".

        Varre TODAS as contas, inclusive as desativadas: uma conta desligada
        continua sendo a dona daquela vaga, e mostrar a vaga como livre faria o
        usuário montar um time que muda sozinho quando ele religar a outra.

        Ver `docs/decisoes/time-do-app.md`.
        """
        alvo = (login or "").strip()
        if not alvo:
            return ""
        dispensado = (ignorar or "").strip()
        for conta in self.accounts:
            if conta.login == alvo or (dispensado and conta.login == dispensado):
                continue
            if alvo in conta.settings.app.time_logins:
                return conta.login
        return ""

    def account_by_nick(self, nick: str) -> Account | None:
        """A conta cujo personagem é este nick, ou `None`.

        Varre TODAS as contas, inclusive as desativadas: a diferença entre
        "esta conta está desligada" e "este nick não existe" é o que separa um
        aviso preciso de um genérico. Quem filtra é quem pergunta.

        Nick único entre contas já é garantido por `validate()` -- duas contas
        com o mesmo nick disputariam a mesma janela, o que é um problema bem
        anterior a este.
        """
        alvo = (nick or "").strip().lower()
        if not alvo:
            return None
        for conta in self.accounts:
            if conta.last_char_name.strip().lower() == alvo:
                return conta
        return None

    def accounts_reset_by(self, reseter: Account) -> list[Account]:
        """Contas ATIVAS que dependem desta como reseter.

        É o que impede deletar ou desativar um reseter deixando outra conta
        órfã sem ninguém perceber. As interfaces perguntam isto ANTES de
        salvar: com a tela na mão, desfazer é um clique; descoberto três horas
        depois, no meio de uma run, o mesmo problema custa reconstruir todo o
        raciocínio.

        SÓ CONTAS ATIVAS. Uma conta desativada não roda, então ela não fica
        órfã de nada hoje -- e barrar a exclusão por causa dela seria criar
        trabalho para o usuário por um problema que não existe. Se ela for
        reativada depois, `problema_do_reset` a pega com a mensagem certa.
        """
        nick = reseter.last_char_name.strip().lower()
        if not nick:
            return []
        return [c for c in self.enabled_accounts()
                if c is not reseter
                and c.settings.bc.reset_nick.strip().lower() == nick]

    def problema_do_reset(self, conta: Account) -> str | None:
        """Por que o reset de time desta conta NÃO pode funcionar. `None` = ok.

        =================================================================
        POR QUE ISTO NÃO ESTÁ EM `validate()`
        =================================================================

        `validate()` é tudo-ou-nada: o `BotManager.start()` recebe a lista de
        problemas e não sobe supervisor NENHUM. Para o reset de time isso é
        desproporcional -- uma conta apontando para um reseter que não existe
        não é motivo para as outras quatro ficarem fora do ar.

        O desfecho aqui é o VETO POR CONTA: ela loga, fica online, com relogin
        ativo, e só o BC dela não roda. É o mesmo desenho que a venda sem tecla
        de retorno já usa (`vendor.py`): desliga o `bc_farm` daquela conta,
        salva, e o checkbox desmarcando nas duas interfaces É o aviso.

        =================================================================
        E POR QUE ELE É CONSULTADO EM DOIS MOMENTOS DIFERENTES
        =================================================================

        Na LARGADA, para não começar a farmar o que não vai dar certo. E COM O
        BOT RODANDO, no portão da entrada da cave -- porque é exatamente ali
        que a diferença entre "o reseter caiu" (espera, ele volta) e "o reseter
        não existe mais" (desliga o farm e avisa) precisa ser feita. Sem esta
        função a segunda pergunta não teria resposta e o bot esperaria para
        sempre por alguém que ele mesmo aposentou.
        """
        nick = conta.settings.bc.reset_nick.strip()
        if not nick:
            return None                     # campo vazio = não usa reset

        if not conta.settings.keys.friend_list:
            return ("o reset de time precisa da tecla da lista de amigos, e "
                    "ela não está configurada nesta conta")

        reseter = self.account_by_nick(nick)
        if reseter is None:
            return (f"a conta de reset '{nick}' não é nenhuma conta deste bot. "
                    "O reseter precisa estar cadastrado aqui para o bot saber "
                    "quando ele cai")
        if reseter is conta:
            return f"'{nick}' é esta própria conta; ela não pode resetar a si mesma"
        if not reseter.enabled:
            return f"a conta de reset '{nick}' está desativada"
        if not reseter.settings.accept_team_invites:
            return (f"a conta '{nick}' não está marcada para aceitar convites "
                    "de time, então ela não vai aceitar o convite desta conta")
        if reseter.farms:
            return (f"a conta de reset '{nick}' está com o BC farm ligado. "
                    "Reseter fica parado esperando o convite; farmando, ele "
                    "não está na porta da cave na hora")
        if reseter.settings.app.enabled:
            return (f"a conta de reset '{nick}' está em modo APP, e nesse modo "
                    "ela nunca chega a aceitar convite nenhum")
        return None

    def validate(self) -> list[str]:
        problemas: list[str] = []
        if not Path(self.client_bat).exists():
            problemas.append(f"Client.bat não encontrado em: {self.client_bat}")
        if not self.enabled_accounts():
            problemas.append("Nenhuma conta ativa.")
        for conta in self.enabled_accounts():
            problemas += conta.validate()

        # Nick repetido faria DUAS contas disputarem a MESMA janela: o
        # reconhecimento é feito pelo nick, então dois iguais apontam para o
        # mesmo cliente -- e uma das contas nunca sairia do lugar. É o erro fácil
        # de cometer digitando o campo à mão.
        vistos: dict[str, str] = {}
        for conta in self.enabled_accounts():
            nick = conta.last_char_name.strip().lower()
            if not nick:
                continue
            if nick in vistos:
                problemas.append(
                    f"O nick '{conta.last_char_name}' está em duas contas "
                    f"('{vistos[nick]}' e '{conta.login}'). O nick identifica a "
                    "janela do jogo, então precisa ser único."
                )
            else:
                vistos[nick] = conta.login
        return problemas

    # -- persistência ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: str | Path | None = None) -> Path:
        """Grava a configuração. Sem `path`, usa o arquivo de onde ela veio."""
        destino = Path(path) if path is not None else self.config_path
        destino.parent.mkdir(parents=True, exist_ok=True)
        dados = self.to_dict()
        # GRAVAÇÃO ATÔMICA: escreve ao lado e substitui de uma vez. A interface e
        # os supervisores gravam do mesmo objeto em threads diferentes; sem isso
        # uma escrita interrompida no meio deixaria o config.json pela metade, e
        # metade de config.json é senha cifrada perdida.
        with _LOCK_ARQUIVO:
            temporario = destino.with_name(destino.name + ".tmp")
            with temporario.open("w", encoding="utf-8") as fh:
                json.dump(dados, fh, indent=2, ensure_ascii=False)
            os.replace(temporario, destino)
        self._source_path = destino
        return destino

    @property
    def config_path(self) -> Path:
        """Arquivo desta configuração, mesmo que ela nunca tenha sido lida."""
        return self._source_path or DEFAULT_CONFIG_PATH

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> BotConfig:
        path = Path(path)
        if not path.exists():
            cfg = cls()
        else:
            with path.open(encoding="utf-8") as fh:
                cfg = cls.from_dict(json.load(fh))
        # Lembrar a origem é o que permite ao supervisor gravar o nick do
        # personagem sem conhecer o caminho do arquivo.
        cfg._source_path = path
        return cfg

    # -- reconstrução ------------------------------------------------------

    @staticmethod
    def _filtra(alvo, dados: dict) -> dict:
        return {k: v for k, v in dados.items() if k in alvo.__dataclass_fields__}

    @classmethod
    def _app_from_dict(cls, dados: dict) -> AppConfig:
        """Reconstrói a sequência do modo APP.

        A lista é sempre normalizada para `PASSOS_DO_APP` linhas: a interface
        mostra um número fixo de linhas, e um arquivo com mais ou menos que isso
        (gravado por outra versão) faria a tela e a configuração discordarem.

        O `enabled` POR LINHA de arquivos antigos é lido e respeitado uma última
        vez: a linha que estava desmarcada entra sem tecla. Sem isto, quem tinha
        linhas preenchidas mas desmarcadas veria todas elas passarem a rodar de
        uma vez só por causa da atualização -- uma mudança de comportamento que
        ninguém pediu.
        """
        app = AppConfig(
            enabled=bool(dados.get("enabled", False)),
            # LER TAMBÉM O QUE NÃO É `enabled`/`steps`. O campo estava sendo
            # GRAVADO certo no `config.json` e ignorado aqui, então voltava ao
            # default de 10 a cada vez que o bot abria -- o usuário configurava
            # e a configuração sumia. Todo campo novo do `AppConfig` precisa
            # entrar nesta linha; o dataclass sozinho não basta.
            apagar_lixo_a_cada=max(0, int(dados.get("apagar_lixo_a_cada", 10) or 0)),
            espera_depois_do_tab_ms=max(
                MINIMO_DE_ESPERA_DO_APP_MS,
                int(dados.get("espera_depois_do_tab_ms", 1000) or 0)),
            travar_posicao=bool(dados.get("travar_posicao", True)),
            shuffle_apos_n_voltas=max(
                1, int(dados.get("shuffle_apos_n_voltas", 30) or 30)),
            time_logins=normalizar_time_logins(dados.get("time_logins")),
            time_modo=normalizar_time_modo(dados.get("time_modo")),
            fada=bool(dados.get("fada", False)),
            cura_pedir_pct=normalizar_pct(
                dados.get("cura_pedir_pct"), CURA_PEDIR_PCT_PADRAO),
            cura_parar_pct=normalizar_pct(
                dados.get("cura_parar_pct"), CURA_PARAR_PCT_PADRAO),
            _base_pos_x=int(dados.get("_base_pos_x", 0) or 0),
            _base_pos_y=int(dados.get("_base_pos_y", 0) or 0),
        )
        passos: list[AppStep] = []
        for bruto in (dados.get("steps") or [])[:PASSOS_DO_APP]:
            if not isinstance(bruto, dict):
                continue
            tecla = str(bruto.get("key", "") or "").upper()
            if "enabled" in bruto and not bruto.get("enabled"):
                tecla = ""
            passos.append(AppStep(
                key=tecla,
                delay_ms=max(0, int(bruto.get("delay_ms", 800) or 0)),
            ))
        while len(passos) < PASSOS_DO_APP:
            passos.append(AppStep())
        app.steps = passos
        return app

    @classmethod
    def _settings_from_dict(cls, dados: dict) -> AccountSettings:
        st = AccountSettings()
        if "mount_speed_pct" in dados:
            st.mount_speed_pct = int(dados["mount_speed_pct"])
        if "accept_team_invites" in dados:
            st.accept_team_invites = bool(dados["accept_team_invites"])
        # SEM ESTA LINHA O CAMPO VOLTA AO PADRÃO A CADA ABERTURA DO BOT. É a
        # mesma armadilha que o `apagar_lixo_a_cada` já pagou: a leitura
        # reconstrói campo a campo, então gravar certo não basta -- o que não é
        # LIDO aqui é silenciosamente descartado, e o usuário vê a opção
        # desmarcar sozinha. Travado por `test_config_ida_e_volta.py`, que agora
        # varre TODO campo escalar do `AccountSettings` sem lista para manter.
        if "usar_catador" in dados:
            st.usar_catador = bool(dados["usar_catador"])
        if "keys" in dados:
            st.keys = KeyBinds(**cls._filtra(KeyBinds, dados["keys"]))
        if "pet" in dados:
            st.pet = PetConfig(**cls._filtra(PetConfig, dados["pet"]))
            # Ver `pet_feed_na_faixa`: arquivo antigo sobe corrigido.
            st.pet.feed_every_minutes = pet_feed_na_faixa(
                st.pet.feed_every_minutes)
        if "potions" in dados:
            st.potions = PotionConfig(**cls._filtra(PotionConfig, dados["potions"]))
        if "bags" in dados:
            st.bags = BagConfig(**cls._filtra(BagConfig, dados["bags"]))
        if "app" in dados:
            st.app = cls._app_from_dict(dados["app"])

        # --- Bewitcher Cave ---
        #
        # `_filtra` descarta chaves que não são campos do dataclass, e é isso que
        # faz o caminho antigo gravado no arquivo ser IGNORADO: `altar_path`,
        # `boss_approach`, `cave_entrance` e `boss_position` viraram propriedades
        # que leem de `bot/mapa_bc.py`. Um config gravado por uma versão antiga
        # continua carregando sem erro, e o caminho que vale é o do código.
        bruto_bc = dados.get("bc", {})
        bc = BCConfig(**cls._filtra(BCConfig, bruto_bc))
        if "route" in bruto_bc:
            bc.route = BCRoute(**cls._filtra(BCRoute, bruto_bc["route"]))
            # O texto de busca do NPC da entrada era "ku" -- um fragmento tão
            # curto que o painel de arredores devolve qualquer coisa que o
            # contenha, e o bot caminhava até o resultado errado. O nome do NPC é
            # Skull Herald; buscar "Skull" é específico e conferível.
            if bc.route.cave_search_text.strip().lower() in ("", "ku"):
                bc.route.cave_search_text = BCRoute.cave_search_text
        if "vendor" in bruto_bc:
            bc.vendor = BCVendor(**cls._filtra(BCVendor, bruto_bc["vendor"]))

        # --- HH (Black Wind Camp Dungeon) ---
        #
        # Mesma armadilha que o `usar_catador` já pagou: a leitura reconstrói
        # campo a campo, então gravar certo não basta -- o que não é LIDO aqui é
        # silenciosamente descartado e o usuário vê a opção voltar ao padrão.
        bruto_hh = dados.get("hh", {})
        hh = HHConfig(**cls._filtra(HHConfig, bruto_hh))
        hh.modo_do_reset = normalizar_modo_do_reset(hh.modo_do_reset)
        if "route" in bruto_hh:
            hh.route = HHRoute(**cls._filtra(HHRoute, bruto_hh["route"]))
        if "vendor" in bruto_hh:
            hh.vendor = HHVendor(**cls._filtra(HHVendor, bruto_hh["vendor"]))
        st.hh = hh

        # --- MIGRAÇÃO das versões 1 e 2 ---
        # Antes, combate/rota/venda/time viviam soltos no mesmo nível. Aqui o que
        # existia é trazido para os blocos novos, para ninguém perder ajustes.
        antigo_combate = dados.get("combat", {})
        if antigo_combate:
            for origem, destino in (
                ("boss_name", "boss_name"), ("attack_delay", "attack_delay"),
                ("max_fight_seconds", "max_fight_seconds"),
                ("heal_before_second_phase", "heal_before_second_phase"),
                ("aoe_until_mana_pct", "aoe_until_mana_pct"),
            ):
                if origem in antigo_combate:
                    setattr(bc, destino, antigo_combate[origem])
            # Os limiares de MANA saíram: o bot não usa mais poção de mana. Os
            # valores que existirem em config antigo são simplesmente ignorados,
            # e é isso mesmo -- migrar um ajuste para um campo que não existe
            # mais só criaria a impressão de que ele ainda faz alguma coisa.
            for origem, destino in (
                ("hp_potion_pct", "hp_pct"),
                ("battle_hp_pct", "battle_hp_pct"),
                ("emergency_pct", "emergency_pct"),
            ):
                if origem in antigo_combate:
                    setattr(st.potions, destino, antigo_combate[origem])

        antiga_rota = dados.get("route", {})
        if antiga_rota:
            # Só os ajustes sobrevivem: as coordenadas que existiam aqui são
            # ignoradas de propósito, porque o caminho passou a vir do código.
            r = cls._filtra(BCRoute, antiga_rota)
            if r:
                bc.route = BCRoute(**r)
            # `heal_to_pct` não existe mais: a cura tem um alvo só, que é
            # `hp_pct`. Config antigo com esse campo é ignorado.
            if "max_heal_seconds" in antiga_rota:
                st.potions.max_heal_seconds = antiga_rota["max_heal_seconds"]

        antiga_venda = dados.get("vendor", {})
        if antiga_venda:
            v = cls._filtra(BCVendor, antiga_venda)
            if "sell_clicks_per_pass" in antiga_venda:
                v["sell_clicks"] = antiga_venda["sell_clicks_per_pass"]
            bc.vendor = BCVendor(**v)

        antigo_time = dados.get("team_reset", {})
        if antigo_time.get("reset_nick"):
            bc.reset_nick = antigo_time["reset_nick"]

        st.bc = bc
        return st

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BotConfig:
        cfg = cls()
        for chave in ("version", "client_bat", "launch_delay",
                      "dc_confirm_seconds", "relogin_backoff_cap",
                      "minimize_clients", "resolution",
                      "reuse_login_screen_clients"):
            if chave in raw:
                setattr(cfg, chave, raw[chave])

        # Config v1 tinha teclas/combate/rota/venda GLOBAIS. Nesse caso cada
        # conta herda aquilo como ponto de partida.
        herdado: dict | None = None
        if any(c in raw for c in ("keys", "combat", "route", "vendor",
                                  "mount_level")):
            herdado = {
                "keys": raw.get("keys", {}),
                "combat": raw.get("combat", {}),
                "route": raw.get("route", {}),
                "vendor": raw.get("vendor", {}),
            }
            nivel = raw.get("mount_level")
            if isinstance(nivel, int):
                herdado["mount_speed_pct"] = 90 + (max(7, nivel) - 7) * 10

        cfg.accounts = []
        for item in raw.get("accounts", []):
            dados = cls._filtra(Account, item)
            dados.pop("settings", None)
            if "bc_farm" not in dados and "mode" in item:
                dados["bc_farm"] = (item["mode"] == "farm")

            bruto = item.get("settings")
            if bruto:
                settings = cls._settings_from_dict(bruto)
            elif herdado:
                settings = cls._settings_from_dict(herdado)
            else:
                settings = AccountSettings()
            cfg.accounts.append(Account(settings=settings, **dados))

        # UID PARA TODA CONTA, E SEM REPETIÇÃO -- ver `garantir_uids_unicos`.
        cfg.garantir_uids_unicos()

        # SÓ AQUI, com TODAS as contas construídas: esta migração é a única que
        # olha uma conta a partir de OUTRA.
        cls._migrar_reset_de_time(cfg)

        # O objeto em memória é sempre da versão atual: acabou de passar por
        # todas as migrações. Deixar o número antigo aqui faria o arquivo gravado
        # anunciar uma versão que não corresponde ao seu conteúdo, e a próxima
        # migração leria isso como "ainda não migrado".
        cfg.version = CONFIG_VERSION
        return cfg

    @staticmethod
    def _migrar_reset_de_time(cfg: BotConfig) -> None:
        """Liga a flag de reset na conta que o `reset_nick` já apontava.

        =================================================================
        POR QUE ISTO EXISTE
        =================================================================

        O `reset_nick` era um campo de TEXTO LIVRE e virou uma lista fechada,
        montada a partir de quem tem `accept_team_invites`. Sem esta migração,
        todo arquivo já gravado em que o nick foi digitado à mão -- e a flag
        ficou desmarcada, o que era perfeitamente possível -- viraria um reset
        órfão na primeira abertura, e o usuário teria que refazer à mão uma
        configuração que ele já tinha feito.

        =================================================================
        O QUE ELA PODE E O QUE ELA NÃO PODE FAZER
        =================================================================

        LIGAR A FLAG NÃO INVENTA INTENÇÃO. Quem escreveu aquele nick já
        declarou que aquela conta é o reseter; a flag é a mesma declaração dita
        de outro jeito. Não há palpite envolvido.

        MEXER NUMA CONTA QUE FARMA INVENTARIA. Se o nick aponta para uma conta
        com `bc_farm` ou modo APP ligado, ligar a flag seria eu decidindo que
        ela deve parar de farmar -- e essa decisão não é minha. Nesse caso a
        migração não toca em nada e o caso cai em `problema_do_reset`, que veta
        o BC daquela conta com a mensagem exata e deixa a escolha com quem
        configura.

        Também não inventa quando o nick não bate com conta nenhuma (reseter em
        outra máquina, ou nick digitado errado): não há o que ligar.
        """
        for conta in cfg.accounts:
            nick = conta.settings.bc.reset_nick.strip()
            if not nick:
                continue
            reseter = cfg.account_by_nick(nick)
            if reseter is None or reseter is conta:
                continue
            if reseter.settings.accept_team_invites:
                continue                       # já estava marcado
            if reseter.farms or reseter.settings.app.enabled:
                continue                       # conta suja: não é minha decisão
            reseter.settings.accept_team_invites = True


def find_config(explicit: str | None = None) -> Path:
    return Path(explicit) if explicit else DEFAULT_CONFIG_PATH
