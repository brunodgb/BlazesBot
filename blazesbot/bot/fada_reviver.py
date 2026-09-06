"""A FADA REVIVENDO — o outro serviço dela, ao lado da cura.

Mora fora de `fada.py` porque aquele arquivo já estava a poucas linhas do teto
de 800, e porque a costura é real: curar é apertar uma tecla até uma barra
subir; reviver é apertar UMA vez e esperar um feitiço de 5 s pegar. As duas
compartilham a seleção pelo retrato do painel — e é justamente ela que é
chamada daqui, em vez de copiada.

=======================================================================
A PRIORIDADE, E POR QUE O MORTO ESPERA
=======================================================================

*"O ideal é colocar o morto à frente só se estiver demorando muito; se passou
(...) e ainda não foi revivido, você deve colocar o morto à frente na fila e
reviver, mas tirando isso a cura vem primeiro."* — usuário, 04/09/2026.

Parece contraintuitivo e não é: um morto não está apanhando nem gastando poção,
e ele tem um prazo próprio de um minuto até se reviver sozinho. Um ferido a 30%
sentado esperando, ao contrário, pode virar o próximo morto. Então a cura vem
primeiro **até** o morto passar de `SEGUNDOS_DE_MORTO_PARA_FURAR_A_FILA` (40 s),
e aí ele fura a fila.

=======================================================================
POR QUE O ID NÃO CONFIRMA UM MORTO — medido em 06/09/2026
=======================================================================

A primeira versão exigia, para reviver, a MESMA confirmação da cura: clicar no
retrato, ler `TARGET_ID` e conferir contra o id que a vítima publicou. Em campo,
na única morte da noite:

```
00:09:43  blazestpas     MORRI. A macro para aqui — avisando o time.
00:09:45  mfaustoapp069  FADA: BlazesAPP1 não selecionou em 3 tentativas —
                         deixo o prazo dele correr, ele se revive sozinho.
00:10:43  blazestpas     A Fada não me reviveu no prazo — revivo sozinho.
```

**Dois segundos de tentativa, 58 segundos de prazo desperdiçados.**

O usuário respondeu o que o jogo faz: o retrato do morto **continua no painel e
continua clicável**, mas o clique **não põe o morto no `TARGET_ID`** — ou seleciona
o corpo, ou não seleciona nada. Ou seja: a confirmação por id, que para a CURA é
a proteção contra curar o aliado errado, para o morto é uma pergunta que não tem
resposta certa. Ela recusava corretamente e reprovava a única coisa que ia
funcionar.

Vale então a regra que o usuário já tinha dado sobre a cura: *"se sabe qual o
slot, não precisa de outra confirmação depois — você já tem a informação correta
na hora que verifica o slot"*. O SLOT vem da memória (`companheiros`), na ordem
do painel do jogo. É ele que manda aqui.

O id continua sendo LIDO, e continua indo para o log: ele é o diagnóstico de
quando o clique pega e de quando não pega. Só deixou de ser veto.
"""

from __future__ import annotations

import time

# Por quanto tempo a Fada insiste num mesmo morto antes de passar adiante.
#
# Decisão do usuário em 06/09/2026: *"deve tentar por pelo menos 10 segundos, aí
# se não for pode desistir e continuar a fila ou ficar parada"*. Com o preparo de
# 5 s da skill, isso dá duas tentativas cheias.
#
# NÃO é o fim da linha para o morto: ele CONTINUA na fila, e a Fada volta a
# tentar na volta seguinte enquanto o prazo dele correr. Largar de vez no
# primeiro ciclo foi o que desperdiçou 50 s de prazo na medição de campo.
JANELA_DE_TENTATIVAS = 10.0

# Quanto se espera o feitiço pegar depois de apertar a tecla.
#
# Os 5 s de preparo medidos no tooltip mais folga para o servidor responder e
# para a vítima ver a janela e clicar no "Ok" dela.
TETO_DO_FEITICO = 8.0

# Passo entre duas perguntas enquanto o feitiço prepara.
PASSO_DA_ESPERA = 0.2

# Teto de TOQUES na janela, independente do relógio.
#
# Com 5 s de preparo, dois ou três toques é tudo o que cabe em 10 s -- então o
# teto não tira nada. Ele existe como cinto de segurança contra o defeito já
# medido em 01/09/2026: com a espera devolvendo na hora (pausa, injeção de
# teste, relógio parado), o laço clicou 357 vezes no mesmo retrato e o
# personagem saiu ANDANDO de tanto clique.
MAXIMO_DE_TOQUES = 3


def reviver(fada, login_vitima: str) -> bool:
    """A Fada tenta reviver esta vítima. `False` = é para parar o laço dela.

    `fada` é a `FadaDoTime`: esta função é um método dela que mora fora do
    arquivo, e usa as mesmas peças (o painel, o clique no retrato, o descanso).
    """
    if not fada.tem_tecla_de_reviver():
        if not fada._avisou_sem_tecla_de_reviver:
            fada._avisou_sem_tecla_de_reviver = True
            fada.log.warning(
                "FADA: %s está morto e eu não tenho tecla de reviver "
                "configurada (Editar conta > Teclas > Magias de Suporte). Ele "
                "vai se reviver sozinho quando o prazo dele vencer.",
                login_vitima)
        return fada._descansar()

    nick = fada._nick_de(login_vitima) or fada.mural.nick_do_morto(login_vitima)
    if not nick:
        # SEM NICK NÃO HÁ RETRATO. Não é desistir da vítima: o prazo dela corre
        # sozinho e ela se revive; aqui só não há como ajudar.
        fada.log.warning("FADA: %s morreu e eu não sei o nick dele — não sei "
                         "em quem clicar.", login_vitima)
        return fada._descansar()

    slot = fada._slot_do_nick(nick)
    if slot is None:
        # Morto fora do painel: passageiro na maioria das vezes. Esperar é mais
        # barato que insistir, e o prazo dele continua correndo de qualquer
        # forma.
        fada.log.info("FADA: %s está morto e não aparece no meu painel — "
                      "espero ele aparecer.", nick)
        return fada._dormir(PASSO_DA_ESPERA)

    if not fada._tenho_mana_para_curar():
        # MANA CONTADA ANTES DO TOQUE: o reviver custa muito mais que uma cura
        # (1168 na medição), e apertar sem ter só queima a recarga.
        fada.log.info("FADA: %s está morto, mas minha mana não dá para o "
                      "reviver agora.", nick)
        return fada._descansar(por_falta_de_mana=True)

    return _insistir(fada, login_vitima, nick, slot)


def _insistir(fada, login_vitima: str, nick: str, slot: int) -> bool:
    """Clica, conjura e espera — por `JANELA_DE_TENTATIVAS` segundos."""
    fim = time.monotonic() + JANELA_DE_TENTATIVAS
    tentativa = 0
    while (time.monotonic() < fim and tentativa < MAXIMO_DE_TOQUES
           and fada._continuar()):
        tentativa += 1
        fada._sair_do_descanso()
        if not fada._clicar_no_retrato(slot):
            return False

        _anotar_o_clique(fada, login_vitima, nick, slot, tentativa)

        # AVISA QUE COMEÇOU, E ISSO É PARTE DO CONTRATO. A vítima tem prazo
        # próprio para se auto-reviver; sem este aviso ela pode clicar no "Ok"
        # do jogo no meio dos 5 s de preparo -- e aí a mana da Fada vai fora e a
        # janela de convite aparece para um personagem que já está vivo.
        fada.mural.comecei_a_conjurar(login_vitima)
        fada.log.info("FADA: revivendo %s (slot %d, tentativa %d).",
                      nick, slot + 1, tentativa)
        fada._apertar_reviver()
        fada.revives += 1

        if _esperar_levantar(fada, login_vitima, nick, fim):
            return True

    fada.revives_sem_efeito += 1
    fada.log.warning(
        "FADA: %s não levantou em %.0fs (%d tentativa(s)). Passo adiante, mas "
        "ele CONTINUA na fila — volto a tentar enquanto o prazo dele correr.",
        nick, JANELA_DE_TENTATIVAS, tentativa)
    return True


def _esperar_levantar(fada, login_vitima: str, nick: str, fim_da_janela) -> bool:
    """`True` = a vítima ficou de pé.

    QUEM AVISA É A PRÓPRIA VÍTIMA, saindo da fila dos mortos: é ela quem lê o
    próprio `hp`. A Fada nunca decide isso pela struct do time -- aquele campo já
    se provou ser o MÁXIMO, não a vida atual.
    """
    limite = min(time.monotonic() + TETO_DO_FEITICO, fim_da_janela)
    while time.monotonic() < limite and fada._continuar():
        if not fada.mural.esta_morto(login_vitima):
            fada.log.info("FADA: %s está de pé.", nick)
            return True
        if not fada._dormir(PASSO_DA_ESPERA):
            return False
    return False


def _anotar_o_clique(fada, login_vitima: str, nick: str, slot: int,
                     tentativa: int) -> None:
    """O id lido depois do clique — DIAGNÓSTICO, nunca veto.

    Ver o cabeçalho: o clique no retrato de um morto não põe o id dele no
    `TARGET_ID`, então exigir que batesse era reprovar a única coisa que ia
    funcionar. Mas a leitura continua valendo ouro no log: é ela que diz se o
    clique pegou, se caiu em outro alvo, ou se a tela está engolindo o clique.
    """
    try:
        lido = fada._id_do_alvo()
    except Exception:
        lido = None
    esperado = fada.mural.id_publicado(login_vitima)
    fada.log.debug(
        "FADA/REVIVER: clique %d em %s (slot %d) — id esperado=%s lido=%s "
        "(%s). O id NÃO decide aqui; quem manda é o slot.",
        tentativa, nick, slot + 1, esperado, lido,
        "bateu" if (esperado and lido == esperado) else "não bateu")
