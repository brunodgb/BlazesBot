"""Catador de loot: o substituto manual do auto-pick do pet.

=============================================================================
POR QUE ISTO EXISTE
=============================================================================

No Talisman o pet com a skill **auto pick** recolhe os itens sozinho. Nem todo
pet tem essa skill -- na prática, algumas contas do usuário têm e outras não --,
e a conta sem ela deixa o chão cheio de item a cada boss morto. Como o bot é
para ser automático, a conta sem o pet certo precisa catar na mão.

Por isso o gatilho é **por conta** (`AccountSettings.usar_catador`), e não global:
a mesma configuração serve as duas situações sem ninguém escolher pelas outras.

=============================================================================
DE ONDE VEIO, E O QUE FOI JUNTADO
=============================================================================

Duas implementações de outros bots, e nenhuma das duas serve inteira:

* **T-R0XX v1.8.3, `bc_manual_auto_pick`** -- clica em cruz ao redor do centro da
  tela e depois clica no botão "Pick Up". Por mensagem de janela, sem mouse
  físico, que é o que este projeto exige. **É CEGO:** não confere se achou nada,
  não confere se a janela abriu, e gasta os oito cliques mais 3 s toda vez, ache
  ou não ache.
* **AutoFarmBot, `auto_pick`** -- varre uma grade e, **depois de cada clique**,
  PROCURA O BOTÃO NA TELA; achou, clica e para. A lógica é certa; a execução é
  `pyautogui`, que **move o mouse físico** -- proibido aqui, com várias contas em
  paralelo.

O que ficou: o anel e a mensagem de janela do primeiro, a **localização do botão
por imagem** e a conferência a cada clique do segundo.

=============================================================================
O BOTÃO É ACHADO POR IMAGEM, NÃO POR COORDENADA -- E ISSO NÃO É DETALHE
=============================================================================

A primeira versão daqui clicava numa coordenada fixa (`coords.pickup`) e usava
`loot_window_open()` como critério de parada. O usuário corrigiu: o botão é o
**"Pick up all"**, e *"até ele sumir deve ficar clicando nele... quando sumir o
botão aí de fato pode abrir o inventário"*.

A correção melhora três coisas de uma vez:

1. **Segurança.** O clique ESQUERDO é o único que move o personagem neste jogo
   (o direito interage). Clicar numa coordenada fixa significa clicar onde o
   botão DEVERIA estar; clicar onde ele foi VISTO significa que, se não há
   botão, não há clique. Passa de "provavelmente seguro" para "seguro por
   construção".
2. **Critério de parada observável.** "O botão sumiu" é a definição de "pegou
   tudo", e é o próprio jogo dizendo. Não depende de `ADDR_LOOT_WINDOW`, que é
   mais um endereço herdado do GhostBot na versão 6139 do cliente e que **nunca
   foi confirmado aqui**.
3. **Independência de resolução e de janela.** A coordenada fixa envelhece; o
   template é procurado onde quer que ele esteja.

O ponteiro de memória continua sendo LIDO, mas só para o log -- é o jeito barato
de descobrir, ao longo das primeiras noites, se `ADDR_LOOT_WINDOW` responde neste
cliente. Ele não decide nada.

=============================================================================
QUANDO PARAR
=============================================================================

Clica no botão e volta a PROCURÁ-LO. Ainda está lá, clica de novo. Sumiu, acabou.
`TETO_DE_CLIQUES` existe só para que uma janela que não fecha não prenda a run --
é rede de segurança, não estratégia; quem decide de verdade é o botão sumir.

O botão é RELOCALIZADO a cada volta, e não clicado sempre no mesmo ponto: custa
uma captura, e cobre a janela ter se movido ou uma segunda ter aberto em outro
lugar.

MÓDULO DE USO GERAL: recebe PEÇAS (funções de clicar, de procurar, de esperar)
e não `BotContext`. É o mesmo desenho do `watchdog.avaliar_saude`, e é o que
permite o APP chamá-lo amanhã sem importar nada do `bc/`.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

__all__ = ["RAIOS_DO_ANEL", "Resultado", "catar"]

Ponto = tuple[int, int]

# Raios do anel de cliques direitos, em pixels, a partir do ponto do loot.
#
# Vindos do T-R0XX (`range(20, 60, 20)`), e mantidos porque são o único número
# aqui com alguma prova de campo -- é o bot dele rodando. Cada raio produz quatro
# cliques (direita, esquerda, baixo, cima), então são oito no total, e o laço sai
# no primeiro que fizer o botão aparecer.
RAIOS_DO_ANEL = (20, 40)

# Espera entre dois cliques direitos. Também do T-R0XX. Não é tempo de abrir a
# janela -- é o intervalo mínimo para o cliente não engolir o segundo clique.
ESPERA_ENTRE_CLIQUES = 0.1

# Espera entre o clique no botão e a próxima conferência. NÚMERO DO USUÁRIO.
#
# Ele pediu *"uns 2 segundos"* e ajustou para 4 em seguida -- e faz sentido ficar
# em aberto: quanto o jogo leva para recolher depende de quantos itens caíram, e
# isso varia por run.
#
# ERRAR PARA MENOS É O LADO CARO, e é o que este número existe para evitar. Era
# 0,4 s, escolhido por mim: conferir antes de o jogo ter recolhido faz o botão
# ainda estar lá, o catador clica de novo, e os cliques do teto vão sendo gastos
# contra um recolhimento que JÁ ESTAVA EM ANDAMENTO -- até estourar com o loot no
# chão. Esperar a mais custa segundos numa run que já acabou; esperar a menos
# custa o loot.
#
# Mexer aqui mexe no pior caso, que é `ESPERA_APOS_PEGAR * TETO_DE_CLIQUES`.
ESPERA_APOS_PEGAR = 4.0

# Teto de cliques no botão. REDE DE SEGURANÇA, não estratégia -- mesmo papel do
# `max_heal_seconds`. Quem decide de verdade é o botão SUMIR.
#
# ELE SÓ É ALCANÇADO QUANDO ALGO JÁ DEU ERRADO: uma janela que não fecha, com o
# boss morto e a instância gasta. No caminho normal o laço sai no primeiro ou
# segundo clique.
#
# OS DOIS SE MULTIPLICAM: com a espera em 4 s, o pior caso é 40 s. Se a espera
# subir mais, este número desce junto -- senão a rede passa a custar mais que o
# problema que ela evita.
TETO_DE_CLIQUES = 10


@dataclass(frozen=True, slots=True)
class Resultado:
    """O que aconteceu, em forma que o log entende sem interpretar nada."""

    pegou: bool
    cliques_ate_achar: int
    cliques_no_botao: int
    motivo: str

    def __str__(self) -> str:
        if self.pegou:
            return (f"loot recolhido: botão achado em {self.cliques_ate_achar} "
                    f"clique(s) e clicado {self.cliques_no_botao}x até sumir")
        return f"nada recolhido: {self.motivo}"


def _pontos_do_anel(centro: Ponto) -> list[Ponto]:
    """Os pontos do anel, do mais perto para o mais longe.

    Ordem importa: o cadáver costuma cair perto do centro, então começar pelo
    raio menor faz o caso comum sair no primeiro ou segundo clique.
    """
    x, y = centro
    pontos: list[Ponto] = []
    for raio in RAIOS_DO_ANEL:
        pontos += [(x + raio, y), (x - raio, y), (x, y + raio), (x, y - raio)]
    return pontos


def catar(
    *,
    ponto_do_loot: Ponto,
    localizar_botao: Callable[[], Ponto | None],
    clicar_direito: Callable[[Ponto], None],
    clicar_esquerdo: Callable[[Ponto], None],
    esperar: Callable[[float], None],
    log,
) -> Resultado:
    """Recolhe o loot do chão. Não levanta -- devolve o que aconteceu.

    `localizar_botao()` procura o "Pick up all" na tela e devolve onde ele está,
    ou `None`. É ele, e só ele, que autoriza um clique esquerdo.
    """
    # O botão pode já estar na tela -- o auto-pick de um companheiro, um clique
    # anterior, ou o próprio jogo. Procurar antes economiza o anel inteiro.
    if localizar_botao() is not None:
        log.info("Catador: o botão de recolher já estava na tela")
        return _pegar(localizar_botao, clicar_esquerdo, esperar, log, cliques=0)

    for numero, ponto in enumerate(_pontos_do_anel(ponto_do_loot), start=1):
        clicar_direito(ponto)
        esperar(ESPERA_ENTRE_CLIQUES)
        if localizar_botao() is not None:
            log.info("Catador: botão de recolher no clique %s (%s)",
                     numero, ponto)
            return _pegar(localizar_botao, clicar_esquerdo, esperar, log,
                          cliques=numero)

    return Resultado(False, len(_pontos_do_anel(ponto_do_loot)), 0,
                     "nenhum dos cliques fez o botão de recolher aparecer")


def _pegar(
    localizar_botao: Callable[[], Ponto | None],
    clicar_esquerdo: Callable[[Ponto], None],
    esperar: Callable[[float], None],
    log,
    cliques: int,
) -> Resultado:
    """Clica no botão até ele SUMIR. Relocaliza a cada volta.

    O clique esquerdo só sai em cima de um botão que ACABOU de ser visto -- é o
    que impede o único clique que move o personagem de cair na cena 3D.
    """
    for clicado in range(TETO_DE_CLIQUES):
        onde = localizar_botao()
        if onde is None:
            return Resultado(True, cliques, clicado, "")
        clicar_esquerdo(onde)
        esperar(ESPERA_APOS_PEGAR)

    if localizar_botao() is None:
        return Resultado(True, cliques, TETO_DE_CLIQUES, "")

    log.info("Catador: o botão de recolher não sumiu em %s cliques",
             TETO_DE_CLIQUES)
    return Resultado(False, cliques, TETO_DE_CLIQUES,
                     f"o botão de recolher não sumiu em {TETO_DE_CLIQUES} "
                     "cliques")
