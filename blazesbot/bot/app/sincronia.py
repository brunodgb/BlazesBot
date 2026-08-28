"""A largada sincronizada do time do APP.

=========================================================================
ONDE ISTO MORA, E POR QUÊ
=========================================================================

Ecossistema **APP**. Este arquivo pode importar `bot/mural.py`; o
`app/executor.py` **não pode** -- ele não importa nada de `blazesbot.bot`
(travado por `tests/test_ecossistemas.py`) e recebe tudo por injeção. Por isso
a sincronia é um OBJETO construído pelo supervisor e entregue ao executor como
fábrica, exatamente como a cura já é (`executor.__init__`, o `cura(self)` na
última linha). O executor chama um método e não sabe que existe mural.

=========================================================================
O QUE ELA FAZ, EM UMA FRASE
=========================================================================

Antes de cada volta da macro, o líder pega um alvo, ANUNCIA "volta N, alvo X",
e os seguidores entram nessa volta -- no modo `mesmo_alvo`, depois de darem TAB
até o próprio alvo bater com o do líder.

=========================================================================
AS DUAS REGRAS QUE MANDAM AQUI
=========================================================================

1. **NINGUÉM FICA PARADO ESPERANDO.** Toda espera tem teto, e estourar o teto
   NUNCA cancela a volta: a conta segue batendo sozinha e entra na próxima
   largada que alcançar. Pedido explícito do usuário -- personagem parado num
   farm morre, e três contas paradas por causa de uma que está curando é o
   oposto do que o time existe para fazer.

2. **NENHUM NÚMERO AQUI FOI MEDIDO.** Todos são PROVISÓRIOS, por decisão do
   usuário em 27/08/2026: *"é importante deixar rodando mesmo sem as medições,
   para justamente a gente testar em um cenário real, e após termos os logs a
   gente ajusta os tempos e a sincronia perfeita."* Em troca, esta classe
   REGISTRA no log tudo que a medição precisaria -- quanto se esperou, quantos
   TABs custou o alinhamento e quantas vezes o teto estourou. Ver
   `docs/decisoes/time-do-app.md`.
"""
from __future__ import annotations

import itertools
import time
from collections.abc import Callable
from typing import Any

from ...config import MINIMO_DE_ESPERA_DO_APP_MS
from .. import mural

# ÉPOCA: um número por objeto de sincronia criado neste processo.
#
# O contador de voltas recomeça do 1 a cada reinício do executor (relogin, o
# usuário religando o modo), e o estado publicado sobrevive a esse reinício por
# `ESTADO_VALIDO_SEGUNDOS`. Sem a época, uma confirmação da execução ANTERIOR
# do mesmo líder valia para a volta 1 da execução nova -- o líder largava
# sozinho achando que o seguidor já tinha entrado.
_EPOCAS = itertools.count(1)

# ---------------------------------------------------------------------------
# TEMPOS PROVISÓRIOS -- nenhum deles foi medido (ver o cabeçalho)
# ---------------------------------------------------------------------------

# Quanto o líder espera os seguidores confirmarem a largada.
#
# PROVISÓRIO. Chute informado: uma volta típica da macro do usuário passa de 10
# s, e esperar mais que ~3 s por conta atrasada custaria mais do que a
# sincronia rende. O log diz quanto foi de fato usado.
#
# É O MESMO NÚMERO da validade da largada no mural, e por isso é IMPORTADO em
# vez de repetido: enquanto eram dois, havia um buraco entre eles em que o
# seguidor "entrava" numa largada que o líder já tinha abandonado -- os dois se
# contavam como juntos estando segundos fora de fase.
TETO_DA_LARGADA_SEGUNDOS = mural.LARGADA_VALIDA_SEGUNDOS

# Quanto o seguidor insiste no TAB até o alvo dele bater com o do líder.
#
# PROVISÓRIO no valor, mas NÃO na forma: ele é DERIVADO do teto da largada e
# tem de caber dentro dele. Eram dois números soltos, 4 s de alinhamento contra
# 3 s de espera do líder, e a conta não fechava: o líder desistia de esperar
# ANTES de o seguidor terminar de alinhar, então "todos começam juntos no mesmo
# alvo" -- que é a razão de o modo existir -- nunca acontecia quando o
# alinhamento demorava. A margem de 1 s cobre a publicação da confirmação.
#
# Estourar não cancela nada: a conta bate no próprio mob nessa volta, confirma
# assim mesmo e larga JUNTO, só que em outro mob.
TETO_DO_ALINHAMENTO_SEGUNDOS = max(0.5, TETO_DA_LARGADA_SEGUNDOS - 1.0)

# Cadência do TAB durante o alinhamento.
#
# PROVISÓRIO, e é o número MAIS ARRISCADO do arquivo: existe um atraso entre o
# TAB e a memória mostrar o `TARGET_ID` novo, e TAB mais rápido que esse atraso
# faz a conta comparar contra o alvo ANTERIOR -- concluindo "não alinhou"
# quando alinhou, calada. Por isso o provisório é 4x mais lento que o piso de
# 100 ms da macro, e não o piso: errar para o lado lento custa segundos, errar
# para o rápido custa a funcionalidade inteira parecendo quebrada pelo motivo
# errado.
ESPERA_ENTRE_TABS_DO_ALINHAMENTO = 0.4

# De quanto em quanto tempo o seguidor confere se a largada saiu.
PASSO_DA_ESPERA_DA_LARGADA = 0.05

# Sem trocar de estado de batalha por este tempo, dá TAB.
#
# NÚMERO DECLARADO PELO USUÁRIO (27/08/2026), não medido: *"se não sair de
# batalha em 4 segundos, devem dar tab e virar no provável mob que está batendo
# em algum dos personagens"*. Não é preciso identificar o mob: o TAB deste jogo
# pega o mais perto, e o mais perto de quem está apanhando é justamente ele.
SEGUNDOS_SEM_MUDANCA_PARA_TAB = 4.0

# Quanto o seguidor espera a marca de UMA linha antes de mandar assim mesmo.
#
# PROVISÓRIO. Curto de propósito: passar disso significa que o líder parou (está
# curando, voltando à base, caindo), e nesse caso mandar a linha sozinho é
# melhor que ficar parado -- a regra do time. Quem alcança de novo alcança na
# linha seguinte, porque a comparação da marca é `>=`.
TETO_DA_LINHA_SEGUNDOS = 2.0

# De quanto em quanto tempo a espera da linha acorda para conferir o botão
# Parar. Não é a latência do aviso: o aviso chega por `Condition.notify_all` em
# microssegundos. Isto é só o intervalo em que a espera é interrompível.
PASSO_DA_ESPERA_DA_LINHA = 0.05


class SincroniaDoTime:
    """A parte do time que roda DENTRO do executor de macro.

    Recebe o executor porque precisa de três coisas dele -- dormir respeitando o
    botão Parar (`_dormir`), ler o id do alvo (`_ler_id_do_alvo`) e conseguir um
    alvo (`_garantir_alvo`). É o mesmo acordo da cura, que também recebe o
    executor inteiro pela fábrica.
    """

    def __init__(
        self,
        executor: Any,
        *,
        login: str,
        lider: str,
        modo: str,
        membros: Callable[[], list[str]],
        max_hp: Callable[[], int | None],
        log: Any,
    ) -> None:
        self._ex = executor
        # LOGIN EM CAIXA BAIXA, sempre. O mural guarda tudo por
        # `strip().lower()`, e comparar aqui em caixa original fazia a conta
        # `Foo` não se reconhecer como o líder `foo`: ela esperaria para sempre
        # a largada que ela mesma deveria anunciar.
        self.login = (login or "").strip().lower()
        # O líder DECLARADO na configuração. Quem manda de fato pode ser outro
        # quando ele cai -- ver `_lider_efetivo`.
        self.lider_declarado = (lider or "").strip().lower()
        self.modo = modo
        # FUNÇÃO e não lista: quem está no time muda enquanto o bot roda (uma
        # conta liga o farm da cave, outra cai). Ler na hora é o que faz o time
        # encolher sem precisar religar nada.
        self._membros_brutos = membros
        self._max_hp = max_hp
        self.log = log

        self.epoca = next(_EPOCAS)
        self.volta = 0
        # O NÚMERO DA VOLTA DO TIME, que NÃO é `self.volta`.
        #
        # `self.volta` conta as voltas DESTA conta; o time conta as do líder, e
        # as duas divergem no instante em que alguém perde uma largada. O líder
        # compara `volta_pronta` com o número DELE, então é este que precisa ser
        # publicado -- publicar o contador local fazia os dois baterem só por
        # coincidência, e a barreira "todos prontos" nunca fechava.
        self.volta_do_time = 0
        # DE QUEM é a largada que esta conta está cumprindo. Sem isto a
        # confirmação era só um número, e um número de outro líder (ou de uma
        # execução anterior, que recomeça do 1) contava como "este seguidor já
        # entrou" -- o líder largava sozinho achando que estava acompanhado.
        self.largada_de = ""
        self.largada_epoca = 0
        # A ÚLTIMA LARGADA em que esta conta entrou, como identidade completa
        # `(lider, epoca, volta)` -- e não como número solto. Guardar só o
        # número fazia a largada 1 de um líder NOVO ser recusada por já se ter
        # entrado na largada 1 do anterior.
        self.ultima_largada: tuple[str, int, int] = ("", 0, -1)
        # Contadores para a medição que ainda não foi feita.
        self.largadas_juntas = 0
        self.largadas_perdidas = 0
        self.tabs_de_alinhamento = 0
        self.alinhamentos_falhos = 0
        self.linhas_juntas = 0
        self.linhas_sem_marca = 0
        # Relógio do "4 s sem mudar de estado de batalha".
        self._estado_de_batalha: bool | None = None
        self._mudou_em = time.monotonic()

    def _membros(self) -> list[str]:
        """Os membros do time, na mesma caixa que o mural usa."""
        return [str(x).strip().lower() for x in self._membros_brutos() if x]

    # -- quem manda --------------------------------------------------------

    def sou_o_lider(self) -> bool:
        return self._lider_efetivo() == self.login

    def _lider_efetivo(self) -> str:
        """Quem abre a largada AGORA.

        Normalmente é o líder declarado. Quando ele cai (relogin, watchdog, o
        usuário fechou a janela), o time não pode parar -- personagem parado num
        farm morre. Então assume quem tem mais VIDA MÁXIMA entre os que ainda
        estão publicando estado, e o líder real retoma na próxima largada em que
        voltar a publicar.

        A ESCOLHA É DETERMINÍSTICA, e isso não é preciosismo: cada conta decide
        isso sozinha, na sua própria thread. Um sorteio faria duas contas
        chegarem a respostas diferentes e o time passaria a ter DOIS líderes
        anunciando largadas concorrentes -- que é pior que não ter nenhum. Por
        isso o desempate é por `max_hp` e, se ele empatar ou não puder ser lido,
        pela ordem do login: todo mundo calcula o mesmo.
        """
        # EU SOU O LÍDER DECLARADO E ESTOU RODANDO -- não há o que eleger.
        #
        # Sem esta linha havia um golpe na primeira volta: o líder só publica
        # estado no FIM da largada, então qualquer seguidor que já tivesse
        # publicado ganhava a eleição, e o líder declarado passava a esperar a
        # largada de quem ele lidera. Ninguém anunciava nada.
        if self.login == self.lider_declarado:
            return self.login
        if mural.estado_da_conta(self.lider_declarado) is not None:
            return self.lider_declarado

        vivos = []
        for login in self._membros():
            estado = mural.estado_da_conta(login)
            if estado is None:
                continue
            vivos.append((-(estado.get("max_hp") or 0), login))
        if not vivos:
            # Ninguém publicou nada ainda -- inclusive esta conta, que publica no
            # fim deste mesmo método de largada. Manter o líder declarado é o
            # que evita um "golpe" na primeira volta, antes de o time existir.
            return self.lider_declarado
        vivos.sort()
        return vivos[0][1]

    # -- o que o executor chama -------------------------------------------

    def esperar_a_largada(self) -> bool:
        """Chamada antes de cada volta. `False` = é para parar (botão Parar).

        NUNCA devolve `False` por causa de sincronia -- só por parada de
        verdade. "Não consegui sincronizar" é sempre "vai assim mesmo".
        """
        self.volta += 1
        if self.modo == "copiar":
            return True
        # SEM TIME NÃO HÁ LARGADA. A pergunta é feita a cada volta, e não uma
        # vez na construção, porque o time nasce e morre com o bot rodando: o
        # usuário marca uma conta, liga o farm da cave de outra, o líder
        # desliga o APP. Sozinha, esta conta roda exatamente como sempre rodou.
        if len(self._membros()) <= 1:
            return True

        # PRESENÇA ANTES DA ESPERA. O estado também era publicado só no FIM, e
        # isso deixava uma janela: o líder que volta de um relogin ficava
        # "calado" durante a largada inteira, e o líder temporário continuava
        # anunciando em paralelo. Publicar aqui faz o substituto devolver o
        # posto na primeira volta em que o titular reaparece.
        self._publicar()

        if self.sou_o_lider():
            ok = self._abrir_a_largada()
        else:
            ok = self._entrar_na_largada()
        self._publicar()
        return ok

    # -- o líder -----------------------------------------------------------

    def _abrir_a_largada(self) -> bool:
        alvo = 0
        if self.modo == "mesmo_alvo":
            # O ALVO PRECISA EXISTIR ANTES DE ANUNCIAR. Sem isto o líder
            # publicaria o alvo da volta ANTERIOR -- que acabou de morrer, e é
            # justamente por isso que a volta terminou. Os seguidores gastariam
            # o alinhamento inteiro procurando um cadáver.
            try:
                self._ex._garantir_alvo()
                alvo = self._ex._ler_id_do_alvo() or 0
            except Exception as exc:
                # COMPLEMENTO: sem alvo o time só perde o "mesmo mob" desta
                # volta. Derrubar a macro por isso seria trocar um problema
                # pequeno por um grande.
                self.log.warning("Time: não consegui alvo para anunciar (%s)", exc)

        self.volta_do_time = self.volta
        self.largada_de = self.login
        self.largada_epoca = self.epoca
        mural.anunciar_largada(self.login, self.epoca, self.volta_do_time, alvo)
        if not self._esperar_os_seguidores(alvo):
            return False
        return True

    def _esperar_os_seguidores(self, alvo: int) -> bool:
        """Segura a largada até os seguidores confirmarem, com TETO."""
        esperados = [x for x in self._membros() if x != self.login]
        if not esperados:
            return True
        limite = time.monotonic() + TETO_DA_LARGADA_SEGUNDOS
        while time.monotonic() < limite:
            prontos = sum(
                1 for x in esperados
                if self._confirmou(x)
            )
            if prontos >= len(esperados):
                # FECHA A LARGADA ao sair da espera, nos DOIS caminhos. A partir
                # daqui a macro começa, e quem entrasse agora estaria começando
                # a volta com o líder já batendo -- contando-se como junto sem
                # estar. Quem perdeu esta entra na próxima.
                mural.esquecer_largada(self.login)
                self.largadas_juntas += 1
                self.log.debug(
                    "Time: volta %d com %d/%d juntos (alvo %s)",
                    self.volta_do_time, prontos, len(esperados), alvo or "-")
                return True
            if not self._ex._dormir(PASSO_DA_ESPERA_DA_LARGADA):
                return False
        # TETO ESTOURADO. Não é erro e não cancela nada: quem não chegou segue
        # batendo sozinho e entra na próxima. O aviso existe para a medição --
        # é este número que diz se o teto está apertado demais.
        mural.esquecer_largada(self.login)
        atrasados = [x for x in esperados
                     if not self._confirmou(x)]
        self.largadas_perdidas += 1
        self.log.info(
            "Time: volta %d largou sem %s (teto de %.1fs) -- eles entram na próxima",
            self.volta_do_time, ", ".join(atrasados) or "?", TETO_DA_LARGADA_SEGUNDOS)
        return True

    def _confirmou(self, login: str) -> bool:
        """Este membro confirmou a largada QUE EU abri, e não outra qualquer."""
        estado = mural.estado_da_conta(login) or {}
        return (estado.get("volta_pronta") == self.volta_do_time
                and estado.get("largada_de") == self.login
                and estado.get("largada_epoca") == self.epoca)

    # -- o seguidor --------------------------------------------------------

    def _entrar_na_largada(self) -> bool:
        lider = self._lider_efetivo()
        limite = time.monotonic() + TETO_DA_LARGADA_SEGUNDOS
        largada = None
        while time.monotonic() < limite:
            pendente = mural.largada_pendente(lider)
            if (pendente is not None
                    and (lider, pendente[0], pendente[1]) != self.ultima_largada):
                largada = pendente
                break
            if not self._ex._dormir(PASSO_DA_ESPERA_DA_LARGADA):
                return False

        if largada is None:
            # O líder não anunciou a tempo (caiu, está curando, voltando à base).
            # A conta NÃO fica parada: roda a volta dela e tenta de novo.
            self.largadas_perdidas += 1
            self.log.debug("Time: sem largada de %s em %.1fs -- indo sozinho",
                           lider, TETO_DA_LARGADA_SEGUNDOS)
            return True

        epoca, volta, alvo = largada
        self.ultima_largada = (lider, epoca, volta)
        self.volta_do_time = volta
        self.largada_de = lider
        self.largada_epoca = epoca
        self.largadas_juntas += 1
        if self.modo == "mesmo_alvo" and alvo:
            self._alinhar_no_alvo(alvo)
        return True

    def _alinhar_no_alvo(self, alvo: int) -> bool:
        """TAB até o próprio alvo ser o do líder. Estourou o teto, bate no seu.

        NÃO EXISTE TECLA DE ASSIST neste jogo, então esta é a única via: dar
        TAB e comparar o `TARGET_ID`. O mob do líder pode nem estar no ciclo de
        TAB desta conta (longe, outro andar, já morto) -- daí o teto.
        """
        limite = time.monotonic() + TETO_DO_ALINHAMENTO_SEGUNDOS
        while time.monotonic() < limite:
            try:
                atual = self._ex._ler_id_do_alvo() or 0
            except Exception:
                # Sem memória não há como perguntar. Esta conta cai para o
                # comportamento do modo "largada": bate no que tiver.
                self.log.debug("Time: sem leitura de alvo -- volta sem alinhar")
                return False
            if atual == alvo:
                return True
            self.tabs_de_alinhamento += 1
            if not self._ex._tab_simples():
                return False
            if not self._ex._dormir(ESPERA_ENTRE_TABS_DO_ALINHAMENTO):
                return False
        self.alinhamentos_falhos += 1
        self.log.info(
            "Time: não alinhei no alvo %s em %.1fs -- bato no meu nesta volta",
            alvo, TETO_DO_ALINHAMENTO_SEGUNDOS)
        return False

    def deve_dar_tab_na_abertura(self) -> bool:
        """O TAB de cortesia do começo da volta ainda faz sentido?

        NÃO no modo `mesmo_alvo`: a largada acabou de alinhar todas as contas
        no mob do líder, e o TAB do prelúdio troca esse alvo na linha seguinte
        -- desfazendo exatamente o que a largada custou a fazer. Foi encontrado
        lendo o código contra a descrição do usuário, antes de rodar.

        Nos outros modos ele continua: lá ninguém combinou alvo, e pegar mob
        novo no começo da volta é o que faz a macro ter no que bater.
        """
        return not (self._sincronizando() and self.modo == "mesmo_alvo")

    # -- linha a linha -----------------------------------------------------

    def _sincronizando(self) -> bool:
        """Há time E o modo pede sincronia."""
        return self.modo != "copiar" and len(self._membros()) > 1

    def antes_da_linha(self, i: int) -> bool:
        """Chamada antes de CADA tecla da macro. `False` = é para parar.

        No líder: marca a linha, e segue sem esperar ninguém. Segurar o líder a
        cada linha faria o time inteiro andar na velocidade do pior momento de
        qualquer conta -- e a regra é que ninguém fica parado.

        No seguidor: espera a marca. Se ela já foi dada (ele está atrasado), não
        espera nada -- é assim que a defasagem se desfaz em vez de se manter.
        """
        if not self._sincronizando():
            return True
        if self.sou_o_lider():
            mural.abrir_passo(self.login, self.epoca, self.volta_do_time, i)
            return True

        alvo = (self.largada_epoca, self.volta_do_time, i)
        limite = time.monotonic() + TETO_DA_LINHA_SEGUNDOS
        while time.monotonic() < limite:
            if mural.esperar_passo(self.largada_de, alvo,
                                   PASSO_DA_ESPERA_DA_LINHA):
                self.linhas_juntas += 1
                return True
            if not self._ex._continuar():
                return False
        # O líder não marcou a tempo: está curando, voltando à base ou caiu.
        # Mandar sozinho é melhor que ficar parado, e a linha seguinte já
        # realinha (a comparação da marca é `>=`).
        self.linhas_sem_marca += 1
        return True

    def espera_da_linha(self, delay_ms: int) -> int:
        """Quanto esperar DEPOIS de mandar a tecla.

        No líder é o delay da macro -- é ele quem dita o ritmo do time.

        No SEGUIDOR é só o piso, e essa é a correção que faz a sincronia parar
        de escorregar. Antes ele dormia o próprio delay ALÉM de esperar a
        marca: um atraso de 13 s medido em 28/08/2026 era carregado volta após
        volta, porque o seguidor nunca corria mais rápido que o líder e por isso
        nunca alcançava. Agora, atrasado, ele manda as linhas no piso até
        emparelhar; emparelhado, quem segura é a marca da linha seguinte.
        """
        if not self._sincronizando() or self.sou_o_lider():
            return delay_ms
        return MINIMO_DE_ESPERA_DO_APP_MS

    # -- o relógio dos 4 segundos -----------------------------------------

    def conferir_a_parada(self) -> bool:
        """Devolve True quando faz tempo demais que nada muda -- é hora de TAB.

        O gatilho é UM cronômetro para as duas situações que o usuário
        descreveu, porque o desfecho é o mesmo (dar TAB) e a causa é a mesma
        (esta conta não está no combate do time): a conta ociosa, que não
        entrou em batalha, e a conta com um add em cima, que não SAIU dela.
        """
        try:
            agora_em_batalha = self._ex._ler_em_batalha()
        except Exception:
            return False
        if agora_em_batalha is None:
            # SEM MEMÓRIA, ESTA REGRA NÃO EXISTE -- e isso não deixa a conta
            # parada: a macro continua sendo enviada volta após volta, e o
            # `_garantir_alvo` do executor continua dando TAB quando não há
            # alvo. Os 4 s são um EXTRA para quem lê memória, não a única coisa
            # que faz a conta bater.
            return False
        if agora_em_batalha != self._estado_de_batalha:
            self._estado_de_batalha = agora_em_batalha
            self._mudou_em = time.monotonic()
            return False
        if (time.monotonic() - self._mudou_em) < SEGUNDOS_SEM_MUDANCA_PARA_TAB:
            return False
        # REARMA AO DISPARAR. Sem isto, passados os 4 s a resposta seria `True`
        # em TODA volta seguinte até o estado de batalha mudar -- e o executor
        # daria TAB antes de cada macro, indefinidamente, justamente quando o
        # personagem está num combate longo e não deveria trocar de alvo.
        self._mudou_em = time.monotonic()
        return True

    # -- publicação --------------------------------------------------------

    def _publicar(self) -> None:
        """O que esta conta conta ao time. UMA VEZ POR VOLTA, e nunca mais.

        A vida circula porque ela decide quem assume se o líder cair. Hoje é só
        isso -- o time não recua nem espera por vida baixa, que seria a barreira
        sem teto por outro nome. O dado já anda para quando isso for pedido.
        """
        def _seguro(fn):
            try:
                return fn()
            except Exception:
                return None

        mural.publicar_estado(
            self.login,
            volta_pronta=self.volta_do_time,
            largada_de=self.largada_de,
            largada_epoca=self.largada_epoca,
            max_hp=_seguro(self._max_hp),
            alvo=_seguro(lambda: self._ex._ler_id_do_alvo()) or 0,
            em_batalha=_seguro(lambda: self._ex._ler_em_batalha()),
        )

    def resumo(self) -> str:
        """Uma linha para o log quando o modo APP termina -- é a medição bruta."""
        return (f"time[{self.modo}] {self.largadas_juntas} largadas juntas, "
                f"{self.largadas_perdidas} perdidas, "
                f"{self.linhas_juntas} linhas na marca, "
                f"{self.linhas_sem_marca} sem marca, "
                f"{self.tabs_de_alinhamento} TABs de alinhamento, "
                f"{self.alinhamentos_falhos} sem alinhar")
