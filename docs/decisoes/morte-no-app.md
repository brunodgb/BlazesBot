# O ciclo da morte no APP — 04/09/2026

> *"Implemente então no APP também o reconhecimento de morte, é importante ter
> isso."* — usuário.

## O buraco que existia

`Personagem morto detectado` e `Revivendo` só existiam no **BC**
(`bot/bc/routine.py`). O APP não tinha nada: morrer significava a macro seguir
apertando tecla contra um cadáver até alguém olhar a tela.

A prova está no log de 03→04/09/2026 — 7 h de farm em duas contas de APP
(`blazestpas`, `gamerblazes`), **zero eventos de morte**. Não porque não
morreram: porque ninguém perguntava. As mesmas 7 h têm 38 `Personagem morto
detectado` das contas de BC.

## A pergunta

`hp == 0`, lido da memória, **a cada linha da macro** — o mesmo lugar e o mesmo
naipe da conferência do alvo zerado, e pelo mesmo motivo: é leitura de quatro
bytes, não de tela.

**Sem leitura não há morte.** Cego não declara morte; declarar pararia a macro
de uma conta viva, que é o oposto do que este ciclo existe para consertar.

## A ordem, e o porquê de cada prazo

| passo | prazo | por quê |
|---|---|---|
| avisa o time (`mural.morri`) | — | é o que põe a conta na fila dos mortos da Fada |
| espera a Fada | **60 s** (`PRAZO_PARA_A_FADA`) | *"não dá para esperar (...) o ideal é esperar no máximo 1 minuto"*; o jogo revive sozinho em ~5 min, então 1 min deixa margem larga |
| feitiço em curso | **+15 s** (`EXTENSAO_PELO_FEITICO`) | a skill tem 5 s de preparo — sem esticar, dá para a Fada começar aos 58 s e a vítima se auto-reviver aos 60, **no meio do feitiço** |
| revive sozinho | na hora | o "Ok" do jogo levanta perto de onde caiu, custando mais Exp — e é essa Exp que compra o resto da noite farmando |
| senta e regenera | teto de 60 s | revivido pela Fada ele ganha vida junto; sozinho, não. Atravessar o spot fraco é o que a coleira dos 12 existe para evitar |
| volta ao ponto | `Navigator.goto` | mapa-múndi para longe, minimapa para perto, com destravamento — a única caminhada testada em horas de campo |

**Sem Fada no time — ou sendo eu a própria Fada — revive na hora.** *"Caso não
tenha fada, revive na hora, não faz sentido esperar."*

## Os dois "Ok", e por que este é o único ponto decidido por imagem

O print do usuário mostra a janela do convite **por cima** da janela de morte:

- **"Ok" do convite**, em `(440, 337)` cliente: aceita ser revivido **pela
  Fada**, e o personagem nasce na coordenada dela.
- **"Ok" da morte**, em `(515, 469)` cliente (`coords.revive_ok`, o mesmo que o
  BC usa desde sempre): revive no lugar, com mais perda de Exp.

**133 px separam os dois.** Clicar no errado tira o personagem do spot. É o
único lugar deste desenho em que a imagem ganha da memória, e ganha por muito:
`convite_reviver.png` (recorte da fileira dos dois botões), limiar **0,9** —
mais exigente que o 0,85 das telas de login, porque o custo do falso positivo
aqui é justamente o clique na outra janela.

E o clique sai **onde o template casou**, não numa coordenada fixa:
`find_template` devolve o centro do casamento e `DO_CENTRO_ATE_O_OK = (-70, -1)`
leva dali ao botão. Assim o clique acompanha a janela em vez de depender da
aritmética de quem recortou o print.

### Como o recorte foi medido

O print salvo (`reviveu.png`) é **796×1023** — inclui a moldura da janela. A
área de cliente começa **28 px abaixo**, e isso não foi chutado: o "Ok" da morte
aparece em `y=499` no print, e o bot já tinha `revive_ok` medido em `y=469`
cliente. Mesma coluna, 30 px de diferença — a moldura.

## O freio

**Três mortes seguidas sem conseguir voltar ao ponto param a conta**
(`MORTES_SEGUIDAS_PARA_PARAR`). É "seguidas", não "no total": voltar ao ponto
zera o contador, porque um farm de horas morre várias vezes e isso é normal.
Sem o contador, um spot que virou armadilha vira um moedor de tentativas a noite
toda.

## Onde mora, e por quê

`blazesbot/bot/morte.py` — no `bot/`, **não** no `bot/app/`. Os dois lados
precisam dele: a conta que roda macro e a própria Fada, que também morre e
também é do `bot/`. Nada ali sabe que ecossistema existe; tudo chega injetado,
como na `FadaDoTime`.

A montagem das peças (`montar_para_o_app`) ficou no mesmo arquivo, e não no
supervisor, pela catraca de tamanho — e ficou bem: o ciclo e as peças dele são
o mesmo assunto.

## O que este documento NÃO cobre

O lado da **Fada** — clicar no retrato do morto, conferir a mana, apertar a
tecla e furar a fila dos feridos depois de 40 s — está em
`docs/decisoes/fada.md`.


## A volta ao ponto vai A PÉ — medido em campo, 06/09/2026

A primeira versão chamou `Navigator.goto` como a BC chama. Resultado na conta
líder (`blazestpas`), depois de reviver às 00:10:43:

```
00:11:44  Não estou montado; montando antes de atravessar o mapa até (1771, 1668)
00:11:51  Não conseguiu montar em 6s
...       (mais 314 vezes)
00:45:18  NÃO CONSIGO MONTAR ... há 2015s (315 tentativas). Continuo insistindo.
```

**33 minutos parada, sem andar um passo** — e o usuário só percebeu porque o
líder do time não fazia nada.

O portão da montaria insiste **de propósito**: é regra da BC, *"nunca deve
seguir a pé dentro da cave"*. Ele só desiste quando **não há tecla**
configurada — e aqui a tecla existe (é o padrão da conta); o que não existe é a
montaria no personagem. Então ele nunca confirma e nunca desiste.

`Navigator(ctx, exigir_montaria=False)` resolve na origem, e é a decisão que o
usuário já tinha dado: *"só volta montado se tiver a tecla configurada, pois
normalmente os personagens que rodam APP não vão ter montaria"*. O padrão
continua `True` — a cave não mudou.

Junto veio o teto (`TETO_DO_RETORNO`, 180 s): sem ele, a volta tentaria a noite
inteira em vez de contar a falha e deixar a volta seguinte tentar de novo.


## A pergunta estava no lugar errado — 07/09/2026, com 96 minutos de prova

`hp == 0` era conferido **só dentro do laço das linhas**. E morto não consegue
adquirir alvo: a volta aborta na aquisição e **nunca chega às linhas**.

O que isso produziu em campo, na conta `blazestpas`:

```
20:25:20  APP: 1 TAB(s) seguidos e o alvo não mudou.
   ...    96 minutos: TAB a cada 2 s, pedido de cura à Fada, poção,
          "APP: terminei de regenerar sentado com a vida em 0%",
          268 tentativas de abrir a bolsa. E nenhum "MORRI".
```

O ciclo da morte existia, funcionava (na mesma noite ele foi revivido pela Fada
às 20:23) — e não era chamado, porque a única porta de entrada dele ficava atrás
de uma etapa que um morto não consegue passar.

**Agora a pergunta é a PRIMEIRA coisa da volta**, antes de pet, comida, trava de
posição, bolsa e aquisição. A conferência por linha continua, para a morte que
acontece no meio da macro.

### E uma leitura não basta

Apontado pelo council: `hp == 0` aparece transitoriamente em **troca de mapa,
tela de carregamento, respawn e leitura de ponteiro inconsistente**. Declarar
morte na primeira amostra pararia a macro de uma conta viva — o oposto do que
este ciclo existe para consertar.

`estou_morto()` passou a exigir **duas leituras seguidas de zero**. A segunda
custa microssegundos, e duas falhas no mesmo instante num personagem vivo já
seriam um problema de outra natureza. `None` (ilegível) continua valendo NÃO,
em qualquer das duas.

### O que isso implica, e o council foi direto

*"96 minutos enviando input para um personagem morto é assinatura fortíssima
para anti-cheat."* Não é só produtividade perdida: um bot que aperta TAB 2 880
vezes contra um cadáver é um padrão que nenhum jogador humano produz. Detectar
rápido é proteção de conta, não só de farm.
