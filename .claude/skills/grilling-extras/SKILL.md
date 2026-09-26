---
name: grilling-extras
description: Complemento OBRIGATÓRIO das sessões de grilling (mattpocock-skills:grilling, grill-me, grill-with-docs) neste projeto. Carregue junto, ANTES de montar a primeira rodada de perguntas.
---

# Grilling — complemento deste projeto

Skill **interna**. Só o que a `grilling` do plugin não diz e duas sessões reais
mediram. A skill do plugin continua valendo inteira (rodadas, fronteira, formato
❓/➡️, não agir antes do consenso); isto se soma a ela. Mora aqui, e não na do
plugin, porque a atualização do plugin apagaria a edição.

## 1. Separe DOMÍNIO de ENGENHARIA antes de perguntar

Classifique cada pergunta da fronteira antes de escrever a rodada:

- **DOMÍNIO** — só o usuário sabe: mecânica do jogo, regra de negócio,
  prioridade, preferência, o que ele viu na tela. → **PERGUNTE.**
- **ENGENHARIA** — você deveria decidir: onde mora o módulo, qual padrão, ordem
  dos commits, nível de log, formato de teste. → **ANUNCIE a decisão com o
  porquê e peça VETO**, não resposta.

Medido em duas sessões. Na primeira, 11 das 25 perguntas voltaram com "faça como
achar melhor" — todas de engenharia —, e as 6 respondidas com riqueza eram todas
de domínio. Na segunda, o padrão se repetiu: as de engenharia voltaram
delegadas, e as de domínio (o que o vendedor aceita, se uma área ainda roda, qual
interface fica) trouxeram fato que ninguém mais tinha e que mudou o plano.

Pergunta devolvida é rodada gasta. A mesma informação sai do anúncio para veto,
e o usuário continua podendo vetar.

**Conselho de IAs (`claude-council`):** consulte-o só nas de ENGENHARIA com
trade-off real. Ele não tem o domínio — nem memória, graphify ou logs deste
projeto —, então nas de domínio ele só produz palpite com cara de opinião.

## 2. Resposta em branco não é consenso silencioso

Pergunta que volta vazia: trate como "sem objeção à recomendação", mas DIGA
isso na síntese da rodada — "Qn ficou em branco: sigo a recomendação X". A
`grilling` exige que nada fique assumido em silêncio; o branco é o caso mais
fácil de assumir sem dizer.

## 3. Aprovação condicional ambígua: declare a leitura e siga

Saindo do grilling com "pode fazer, desde que X" e duas leituras possíveis: não
reabra a pergunta (é relitigar) e não escolha calado (é apostar). **Declare em
duas frases qual leitura vai implementar e o que ela custa**, e comece. Quem
sabe o domínio corrige no próprio fluxo — medido: a correção veio dois passos
depois, com a informação de domínio que faltava, e o retrabalho foi de duas
chamadas de ferramenta.

## Pré-voo — antes de enviar cada rodada

- [ ] Cada pergunta está marcada DOMÍNIO ou ENGENHARIA?
- [ ] As de engenharia saem como decisão anunciada para veto, com o porquê?
- [ ] O conselho aparece só nas de engenharia com trade-off?
- [ ] A síntese diz o que ficou em branco e como foi tratado?
