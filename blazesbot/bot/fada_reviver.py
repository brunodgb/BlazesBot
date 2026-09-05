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

Os 40 s não são arredondamento: o morto se auto-revive aos 60
(`morte.PRAZO_PARA_A_FADA`) e a skill leva 5 s preparando. Com 40 a Fada tem
folga de sobra para começar, terminar e ainda avisar que começou.
"""

from __future__ import annotations

import time

# Quanto se espera o feitiço pegar depois de apertar a tecla.
#
# Os 5 s de preparo medidos no tooltip mais folga para o servidor responder e
# para a vítima ver a janela e clicar no "Ok" dela. Estourou sem a vítima
# levantar: o feitiço não saiu (ela saiu de alcance, faltou mana, a tecla não
# pegou), e insistir custaria a fila inteira.
TETO_DO_FEITICO = 12.0

# Passo entre duas perguntas enquanto o feitiço prepara.
PASSO_DA_ESPERA = 0.2

# Tentativas de reviver a MESMA vítima antes de deixá-la para o prazo dela.
#
# Mesmo freio da cura, e pelo mesmo motivo medido em 01/09/2026: sem limite, o
# laço volta em 100 ms e clica de novo, para sempre -- foram 357 cliques no
# mesmo retrato, e o personagem saiu ANDANDO de tanto clique.
TENTATIVAS_POR_MORTO = 3


def reviver(fada, login_vitima: str) -> bool:
    """A Fada tenta reviver esta vítima. `False` = é para parar o laço dela.

    `fada` é a `FadaDoTime`: esta função é um método dela que mora fora do
    arquivo, e usa as mesmas peças (o painel, o clique no retrato, a
    confirmação por id, o descanso).
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
        # sozinho e ela se revive: aqui só não há como ajudar.
        fada.log.warning("FADA: %s morreu e eu não sei o nick dele — não sei "
                         "em quem clicar.", login_vitima)
        return fada._descansar()

    slot = fada._slot_do_nick(nick)
    if slot is None:
        # Morto fora do painel: passageiro na maioria das vezes. Esperar é mais
        # barato que insistir, e o prazo dele continua correndo de qualquer
        # forma.
        return fada._dormir(PASSO_DA_ESPERA)

    fada._sair_do_descanso()
    if not fada._clicar_no_retrato(slot):
        return False

    if fada._clique_saiu_errado(login_vitima, nick):
        # ID QUE NÃO BATE NÃO REVIVE -- a mesma regra da cura. O clique pode não
        # ter pego, e o alvo continua o de antes: o feitiço iria para o aliado
        # ANTERIOR, gastando a mana inteira em quem está vivo.
        tentativas = fada._tentativas_de_reviver.get(login_vitima, 0) + 1
        fada._tentativas_de_reviver[login_vitima] = tentativas
        if tentativas >= TENTATIVAS_POR_MORTO:
            fada._tentativas_de_reviver.pop(login_vitima, None)
            fada.log.warning(
                "FADA: %s não selecionou em %d tentativas — deixo o prazo dele "
                "correr, ele se revive sozinho.", nick, tentativas)
            fada.mural.esquecer_morte(login_vitima)
            return True
        return fada._dormir(PASSO_DA_ESPERA)

    fada._tentativas_de_reviver.pop(login_vitima, None)

    if not fada._tenho_mana_para_curar():
        # MANA CONTADA ANTES DO TOQUE: o reviver custa muito mais que uma cura
        # (1168 na medição), e apertar sem ter só queima a recarga.
        fada.log.info("FADA: %s está morto, mas minha mana não dá para o "
                      "reviver agora.", nick)
        return fada._descansar(por_falta_de_mana=True)

    # AVISA QUE COMEÇOU, E ISSO É PARTE DO CONTRATO. A vítima tem prazo próprio
    # para se auto-reviver; sem este aviso ela pode clicar no "Ok" do jogo no
    # meio dos 5 s de preparo -- e aí a mana da Fada vai fora e a janela de
    # convite aparece para um personagem que já está vivo.
    fada.mural.comecei_a_conjurar(login_vitima)
    fada.log.info("FADA: revivendo %s.", nick)
    fada._apertar_reviver()
    fada.revives += 1

    fim = time.monotonic() + TETO_DO_FEITICO
    while time.monotonic() < fim:
        if not fada.mural.esta_morto(login_vitima):
            # A PRÓPRIA VÍTIMA TIRA O AVISO ao ficar de pé -- é ela quem lê o
            # próprio `hp`. A Fada nunca decide isso pela struct do time: aquele
            # campo já se provou ser o MÁXIMO, não a vida atual.
            fada.log.info("FADA: %s está de pé.", nick)
            return True
        if not fada._dormir(PASSO_DA_ESPERA):
            return False

    fada.revives_sem_efeito += 1
    fada.log.warning("FADA: %s não levantou em %.0fs — o feitiço não pegou. "
                     "Sigo com a fila; o prazo dele resolve.", nick,
                     TETO_DO_FEITICO)
    return True
