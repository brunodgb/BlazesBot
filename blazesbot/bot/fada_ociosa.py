"""A FADA OCIOSA -- o que ela faz quando NÃO tem ninguém para curar.

Saiu de `fada.py` em 07/09/2026 pela catraca de tamanho, e a costura é a mesma
que já tinha tirado `fada_reviver.py` de lá: o arquivo da Fada é sobre DECIDIR
QUEM CURAR, e nada aqui é sobre isso. Aqui está a outra metade do laço -- o que
fazer com o tempo em que a fila está vazia: sentar para regenerar, cuidar do pet
e da bolsa, e voltar para o ponto onde ela começou.

A COSTURA NÃO É CONTAGEM DE LINHAS: tudo aqui acontece SÓ com a fila vazia e
fora de batalha, tudo aqui é interrompido por um pedido de cura, e nada aqui
olha vida de aliado.

`fada` É A `FadaDoTime`, recebida como primeiro argumento -- o mesmo padrão de
`fada_reviver`. Não é `BotContext` e não é supervisor: continua sendo a Fada,
que por sua vez segue sem saber que supervisor existe.

=======================================================================
A TECLA DE SENTAR É UM INTERRUPTOR -- a regra que explica quase tudo aqui
=======================================================================

Ela ALTERNA. Apertá-la sem saber o estado é a diferença entre sentar e levantar,
e o bot não sabe o estado: um golpe levanta o personagem, um relogin devolve o
estado sem avisar ninguém. Por isso `descansar` e `levantar` PERGUNTAM à memória
antes de apertar, e por isso `sair_do_descanso` NÃO aperta nada -- ele só
corrige a contabilidade.

E PERGUNTAR É BARATO: `is_sitting` são duas leituras de memória, 1,71 µs
medidos em 07/09/2026 nesta máquina (0,86 µs por `ReadProcessMemory`) -- contra
22 ms de uma captura de janela, ou seja 13 mil vezes mais barato. A 10 Hz isso
dá 0,0017% de um núcleo. É o preço de não errar o interruptor.
"""

from __future__ import annotations

import time

# De quanto em quanto tempo a Fada cuida do pet e da bolsa, ESTANDO OCIOSA.
#
# Decisão do usuário em 01/09/2026: *"essas verificações podem ser feitas
# enquanto a fada está ociosa, mas não deixa direto, para não ficar pesando"*.
#
# Trinta segundos porque nenhuma das duas é urgente: pet sumido e bolsa cheia se
# resolvem em minutos, não em segundos. O que NÃO pode é a Fada gastar o laço
# nisso -- ela existe para estar pronta quando alguém pedir cura.
SEGUNDOS_ENTRE_CUIDADOS = 30.0

# De quanto em quanto tempo a Fada confere se saiu do ponto inicial.
#
# Pedido do usuário em 07/09/2026: *"a fada deve voltar ao ponto inicial para
# evitar zonas de risco (...) uma rotina de verificação de distância que opere
# com baixo custo computacional"*.
#
# O CUSTO É UMA LEITURA DE MEMÓRIA -- posição do personagem, quatro bytes, sem
# captura de tela e sem varredura de entidades. Mesmo assim ela não vai no giro
# do laço: a Fada gira a 10 Hz e ela não anda sozinha, então perguntar dez vezes
# por segundo seria gastar sem chance de resposta diferente. Três segundos é a
# cadência: mais rápido que qualquer risco que se resolva andando, e 30x mais
# barato que o giro.
SEGUNDOS_ENTRE_CONFERENCIAS_DO_PONTO = 3.0

# Por quanto tempo vale a batida dada ANTES de uma tarefa longa da ociosa.
#
# Medido pelo teto do próprio deletador: `TETO_DE_SEGUNDOS = 10.0` mais folga
# para abrir e fechar a bolsa. Não é espera nova -- é a validade que a Fada
# anuncia para o time enquanto está de cabeça na mochila.
SEGUNDOS_DE_CUIDADO_LONGO = 12.0


def descansar(fada, por_falta_de_mana: bool = False) -> bool:
    """Sem ninguém para curar (ou sem mana), senta e recupera.

    Sentar é a única coisa útil que ela pode fazer: não ataca, não coleta,
    e a mana é o insumo da próxima cura.

    PERGUNTA À MEMÓRIA ANTES DE APERTAR. A tecla é INTERRUPTOR: apertá-la
    com ela já sentada a faz LEVANTAR -- o oposto do que se queria. O
    controle interno (`_sentada`) não basta, porque ele descreve o que o bot
    fez, e não o que aconteceu: um golpe levanta o personagem sem passar por
    aqui, e um relogin devolve o estado sem avisar ninguém.

    Regra do usuário em 01/09/2026, e vale para TODO lugar que senta: *"se
    já estiver sentado é só não fazer nada"*.
    """
    no_chao = fada._esta_sentado()
    if no_chao is True:
        # Já está lá. Só acerta o controle interno e sai.
        fada._sentada = True
        return True
    if no_chao is None and fada._sentada:
        # Sem leitura, o controle interno é tudo o que há.
        return True
    if por_falta_de_mana:
        fada.log.info("FADA: mana abaixo de %.0f%% — sentando para recuperar.",
                      fada.mana_para_sentar)
    fada._apertar_sentar()
    fada._sentada = True
    return True


def sair_do_descanso(fada) -> None:
    """Registra que o descanso acabou. **NÃO aperta tecla nenhuma.**

    SENTAR NÃO É UMA TRAVA (regra do jogo, usuário, 01/09/2026): sentada, a
    Fada clica, seleciona e cura normalmente, e o estado sai sozinho na
    primeira ação que ela tomar. O que sentar faz é AUMENTAR a regeneração
    base de vida e de mana -- que é exatamente o que ela veio buscar.

    ISTO APERTAVA A TECLA E CHAMAVA-SE `levantar`. Apertar era pior que
    inútil: a tecla é INTERRUPTOR, então se ela já tivesse saído do chão
    sozinha (levou dano, a volta anterior clicou em alguém), o toque a
    SENTAVA -- bem na hora de curar, que é o único momento em que ela tem
    pressa. O toque também jogava fora a regeneração do caminho.

    O QUE FICOU É SÓ A CONTABILIDADE, e ela continua necessária: `_sentada`
    é a histerese da mana (`_tenho_mana_para_curar` pede
    `mana_para_voltar` enquanto sentada e `mana_para_sentar` de pé). Sem
    zerar a marca aqui, ela ficaria presa no patamar alto para sempre.
    """
    fada._sentada = False


def cuidados(fada) -> None:
    """Pet e bolsa, só com a fila vazia e fora de batalha.

    A CADÊNCIA EXISTE PARA NÃO PESAR: os dois abrem janela e clicam, e fazer
    isso a cada giro do laço gastaria a Fada em manutenção quando ela
    deveria estar pronta para curar.

    PARA NA HORA se alguém entrar na fila ou se ela entrar em batalha -- por
    isso a condição é conferida ANTES de cada um dos dois, e não só na
    entrada. Abrir o inventário com alguém esperando cura mata o alguém.

    SEM TECLA DE PET NÃO HÁ NADA A FAZER -- nem pet, nem bolsa. Decisão do
    usuário: uma Fada sem pet não cata item nenhum, então não tem lixo para
    apagar. É quem injeta que decide isso (passa `None` nos dois).
    """
    if time.monotonic() < fada._proximo_cuidado:
        return
    if not posso_cuidar(fada):
        return
    fada._proximo_cuidado = time.monotonic() + SEGUNDOS_ENTRE_CUIDADOS
    if fada._cuidar_do_pet is not None:
        bater_por(fada, SEGUNDOS_DE_CUIDADO_LONGO)
        fada._cuidar_do_pet()
    if fada._limpar_a_bolsa is not None and posso_cuidar(fada):
        # A BOLSA É A TAREFA MAIS LONGA DA FADA -- teto de 10 s no
        # deletador, o dobro do silêncio que a mata. Ela avisa ANTES por
        # quanto tempo vai sumir, senão quem chegar na fila no meio da
        # limpeza conclui que ela morreu e vai de poção.
        bater_por(fada, SEGUNDOS_DE_CUIDADO_LONGO)
        fada._limpar_a_bolsa()
        # E bate de novo ao voltar, para a validade longa não sobrar: a
        # partir daqui ela está pronta, e uma morte agora tem de aparecer
        # nos 5 s de sempre.
        fada.mural.bater_fada(fada.meu_login, em_batalha=fada._em_briga)


def bater_por(fada, segundos: float) -> None:
    """"Vou sumir por até `segundos`, e estou viva." Ver `TETO_DA_BATIDA_LONGA`."""
    fada.mural.bater_fada(fada.meu_login, em_batalha=fada._em_briga,
                          vale_por=segundos)


def voltar_ao_ponto_se_preciso(fada) -> bool:
    """`True` = estou indo para o ponto (então NÃO sente e não cuide de nada).

    SÓ COM A FILA VAZIA E FORA DE BATALHA -- é o mesmo lugar do laço em que
    ela cuida do pet e da bolsa, e pelo mesmo motivo: andar com alguém
    esperando cura é deixar o alguém morrer, e andar em batalha arrasta o mob
    pelo caminho (a regra do APP, medida).

    A CADÊNCIA É O QUE FAZ SER BARATO -- ver
    `SEGUNDOS_ENTRE_CONFERENCIAS_DO_PONTO` no topo deste módulo. Quem decide se já está
    no ponto e quem manda andar é a peça injetada; aqui só se pergunta na
    hora certa.

    DEPOIS DE ANDAR, A MARCA DE SENTADA CAI. Andar levanta o personagem no
    jogo, e manter a marca faria a Fada achar que está sentada quando não
    está -- o mesmo defeito que a tecla de sentar (interruptor) já causou.

    A CAMINHADA NÃO É ESPERADA. Nada aqui bloqueia: a Fada segue girando a
    10 Hz e, se alguém pedir cura no meio do caminho, ela cura de onde
    estiver (a cura em grupo é por retrato, não por distância de clique). A
    próxima conferência vê se chegou e, se não, manda andar de novo.
    """
    if fada._voltar_ao_ponto is None:
        return False
    agora = time.monotonic()
    if agora < fada._proxima_conferencia_do_ponto:
        # ENTRE DUAS CONFERÊNCIAS, A RESPOSTA É A ANTERIOR. É o que impede
        # a Fada de sentar nos ~30 giros que cabem dentro da cadência: sem
        # isto, ela mandaria andar e se sentaria 0,1 s depois.
        return fada._andando_para_o_ponto
    fada._proxima_conferencia_do_ponto = (
        agora + SEGUNDOS_ENTRE_CONFERENCIAS_DO_PONTO)
    try:
        fada._andando_para_o_ponto = bool(fada._voltar_ao_ponto())
    except Exception as exc:
        fada.log.debug("FADA: não deu para conferir o ponto (%s).", exc)
        fada._andando_para_o_ponto = False
        return False
    if fada._andando_para_o_ponto:
        sair_do_descanso(fada)
    return fada._andando_para_o_ponto


def posso_cuidar(fada) -> bool:
    """Nada na fila e fora de batalha."""
    if fada._em_batalha() is True:
        return False
    fila = [x for x in fada.mural.fila_de_cura(fada._membros_do_time())
            if x != fada.meu_login]
    return not fila


def levantar(fada) -> None:
    """Sai do chão para agir.

    A tecla de sentar é INTERRUPTOR e o bot não sabe em que estado está --
    por isso só este par de métodos mexe em `_sentada`. Apertar por engano
    com ela de pé a faria sentar bem na hora de curar.
    """
    no_chao = fada._esta_sentado()
    if no_chao is False:
        # Já está de pé -- apertar aqui a faria SENTAR bem na hora de curar.
        fada._sentada = False
        return
    if no_chao is None and not fada._sentada:
        return
    fada._apertar_sentar()
    fada._sentada = False
