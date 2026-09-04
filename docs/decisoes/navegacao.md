# Navegação — o porquê medido

## A FAY PRECISAVA DO PONTO EXATO (25/08/2026)

Relato com print. O bot parava em `Stone City [180,-516]` — uns 2 passos antes do
ponto — e clicava no **White Eagle** que estava no caminho.

> *"Ele está parando nessa posição da imagem e clicando no White Eagle, não sei
> por quê. Daí ele desce da montaria, não faz nada, fica um pouco parado, volta
> para a montaria, abre o Surroundings, filtra pela Fay, clica e anda 2 passos
> até ela. Não deveria existir isso, deveria ir para a coordenada 178,-517, que é
> a configurada como coordenada onde pode clicar na Fay e abrir ela."*

### O encadeamento, lido no código

```
auto-path para ~2 passos antes da Fay
  -> falar_com_npc clica no ponto GENÉRICO de NPC -> acerta o White Eagle
  -> diálogo não abre, viajar_para_ghost_din_woods devolve False
  -> a rotina conclui "não estou em Stone City" e USA O ITEM DE RETORNO
       -> desmonta, usa (já está em Stone City: nada acontece), remonta
  -> tenta de novo: Surroundings -> Fay -> os 2 passos que faltavam -> funciona
```

Os dois passos "a mais" que o usuário via na segunda tentativa são a prova: o
auto-path para PERTO, não no ponto.

### O vendedor já tinha aprendido isso

`travel_to_vendor` anda até `POSICAO_DO_VENDEDOR` com `PRECISAO_NO_PONTO_DO
_VENDEDOR = 0.7` e **se recusa a clicar de fora**:

> *"NÃO vou clicar no NPC de fora do ponto: o clique cairia no chão e o
> personagem andaria, piorando a tentativa seguinte."*

A Fay tinha a coordenada — `POSICAO_DA_FAY = (178, -518)`, em `mapa_bc` desde
sempre — e **a produção não a usava**: só a ferramenta de amostragem e os testes.
Faltava o passo de encostar nela.

### O que ficou

1. `_encostar_na_fay()` anda os últimos passos até `POSICAO_DA_FAY` e **recusa o
   clique** se não conseguir.
2. A precisão é **1.5**, não 0.7. A constante diz `-518` e o usuário falou em
   `-517`; uma unidade que ninguém remediu. 1,5 aceita as duas células e as
   vizinhas. Apertar antes de remedir transformaria um erro de uma unidade em run
   travada. O `14-INSTRUMENTAR-CLIQUE` tem o alvo `fay` para fechar isso.
3. **O item de retorno passou a depender da POSIÇÃO**, não da falha do clique.
   Estando em Stone City, falhar na Fay manda tentar de novo — não gastar item
   para viajar até onde já se está.

### E isto responde a escala, de graça

A barra de título do print mostra `Stone City [180,-516]` e o ponto configurado é
`(178,-518)`. **A coordenada da interface do jogo e a do bot estão no mesmo
espaço** — o que enfraquece a hipótese de escala que eu tinha levantado para o
loop do Surroundings. A causa daquele loop continua em aberto, e é por isso que
`CONFIRMAR_CHEGADA_POR_COORDENADA` segue desligado com a distância indo para o
log: a medição decide, não a hipótese.

---

## NUNCA A PÉ DENTRO DA CAVE (25/08/2026)

Regra do usuário, palavra por palavra:

> *"Nunca deve seguir a pé dentro da cave, é algo que precisa estar documentado
> inclusive, pois ir até o last boss depende de ter a montaria e estar usando
> ela."*

**O código fazia o contrário, e com justificativa escrita.** O portão
`garantir_montaria_para_andar` documentava:

> *"Devolve False -- e aí quem chama anda a pé mesmo assim... A alternativa a
> andar a pé não é andar montado, é ficar PARADO -- e parado com o trem de mobs
> da cave em cima o personagem morre."*

E os três trechos de dentro da cave — `atravessar a cave`, `travessia até o
altar`, `ir até os guardas` — **ignoravam o retorno**.

O raciocínio antigo parecia certo e estava incompleto: ele comparava "a pé"
com "parado" e concluía que a pé era menos pior. Faltava a terceira opção, que é
a que existe de verdade: **insistir na montaria até ela subir**. E faltava o
fato que o usuário trouxe — **a pé ele não chega no boss**. Ou seja, andar a pé
não é "chegar mais devagar", é gastar a travessia inteira para falhar no fim.

### O mecanismo, e por que ele quase nunca dá uma volta

> *"Até então nunca falhou a montaria durante os testes... o máximo que vai ter
> que fazer é ler o ponteiro da montaria e ver se ativo; se não, clica de novo,
> já deve resolver. Subir na montaria pode levar 1 a 3 segundos, porque depende
> da montaria."*

O portão lê o ponteiro, espera, e clica de novo se não subiu. Não desiste. A
partir de `CICLOS_ANTES_DE_GRITAR = 5` (~30 s) passa a sair `ERROR` por ciclo —
o laço continua, o que muda é que o problema deixa de ser silencioso.

O único caso em que ele desiste é **tecla não configurada**: aí não há o que
acionar, e insistir seria clicar no nada para sempre.

### O defeito que apareceu junto

`INTERVALO_REMONTAR` era **1,50 s** — *menos* que o tempo de montar. A tecla é
interruptor, então o segundo toque caía DENTRO da subida da montaria mais lenta
e desmontava quem estava montando. O sintoma é indistinguível de "a montaria não
funciona": o bot aperta, aperta de novo, e continua a pé.

Agora são **3,0 s**, que é o teto da medição do usuário.

---

## FORA DA CAVE SÓ DESMONTA POR PET INATIVO (25/08/2026)

> *"Fora da cave BC ele só vai sair da mount caso o pet não esteja ativo; de
> resto, alimentar o PET, usar qualquer coisa que dependa tirar a montaria vai
> ser feito naquele momento que entra na cave, que começa se curando e vai
> fazendo o resto das coisas."*

O sintoma: em Stone City, indo ao vendedor e à Fay, o bot descia da montaria no
meio do caminho para curar, buffar ou alimentar. Cada desmonte custa a descida,
a ação e a remontagem, com o intervalo da tecla no meio.

**A exceção do pet é a certa:** entrar sem pet significa invocar lá dentro, e lá
dentro parar para invocar é parar com o trem de mobs em cima.

**"Não sei onde estou" não bloqueia.** `posicao_esta_fora_da_cave` só afirma
`True` quando a coordenada PROVA que está fora; sem leitura ela responde `False`
e a ação passa. É a direção segura: não curar dentro da cave mata o personagem,
e um desmonte a mais fora dela custa alguns segundos.

---

## OS CRONÔMETROS COMEÇAM NA MONTARIA (25/08/2026)

> *"Os timers de Tempo do 'estatísticas BC' hoje começam a contar a partir do
> momento que entrou; vamos mudar, vamos contar a partir do momento que terminar
> esse processo inicial — se cura, usa as skill, dá comida ao pet e afins; aí no
> momento que ativar a montaria novamente para andar, você começa a contagem."*

Ficam de fora da conta: a disputa da entrada (que já estava fora) e agora
também curar, buffar, invocar e alimentar. O tempo medido passa a ser o da RUN,
não o do preparo.

**Começa mesmo que o preparo falhe.** Amarrar a contagem ao sucesso faria a run
com problema sumir das estatísticas — e é justamente ela que interessa olhar.

**Consequência a esperar:** os tempos ficam alguns segundos menores que os
históricos. A comparação com runs anteriores fica torta por uma sessão.

---

## A GRADE DA COMIDA DO PET É FIXA (25/08/2026)

> *"É importante que a comida do pet só seja depois do tempo estipulado. Caso
> esteja fora da cave e passar o tempo, você alimenta na próxima vez que entrar,
> mas já vai contando para o próximo uso, para não dar tempos errados... por
> exemplo, se configurar a cada 50 minutos tem que alimentar 28,8 vezes por
> dia."*

E o motivo: *"para o pet no jogo o tempo vai passando e vai gastando a fome dele;
se chega a 0 ele automaticamente some."*

    intervalo 50 min, venceu 10:00, o bot só conseguiu alimentar 10:12

        ancorado na REFEIÇÃO   -> próxima 11:02   (escorregou 12 min)
        ancorado no VENCIMENTO -> próxima 10:50   (a grade não se move)

Doze minutos por atraso viram refeições a menos ao longo do dia — e o pet some
por fome. A grade é fixa: o atraso encurta AQUELA refeição, não desloca as
seguintes.

**Sem fila:** atraso maior que um intervalo inteiro re-ancora no presente. A
barra de comida tem teto (100, e cada ração dá 5), então refeições em dívida
seriam ração jogada fora.

**Persistida** em `PetConfig.proxima_comida_em`, pelo mesmo motivo que
`last_hwnd`/`last_pid`: sem isso a grade nasce de novo a cada restart.

---

## O AUTO-PATH DO SURROUNDINGS É CONFIRMADO POR COORDENADA (25/08/2026)

> *"Ao ir até a Fay em Stone City inclusive está clicando fora e indo para o
> lugar levemente errado, sendo que se deixa o auto path do Surroundings ele já
> para no lugar correto."*

**A primeira hipótese estava errada e foi derrubada pelo usuário:** eu apontei o
clique DIREITO no NPC como causa. Ele corrigiu — *"só anda com o botão esquerdo,
mas caso clique com o botão direito no minimapa ele anda, então tem essa
diferença"*.

**A causa real é o clique ESQUERDO no painel.** O ponto vem de
`_pontos("surroundings")`: acha o template do painel (limiar **0,80**, e
`find_template` devolve o **centro** do match) e soma um deslocamento fixo de
**(-97, +99)**. A 99 px de distância, um match alguns pixels deslocado põe o
clique fora da linha do resultado — e clique esquerdo fora do painel é ANDAR.

**E a verificação antiga não pegava isso:** ela esperava a POSIÇÃO MUDAR. Clique
errado no chão também muda a posição. Ela não sabia distinguir auto-path de
clique perdido.

### O conserto que eu tentei REPROVOU em produção, no mesmo dia

Eu troquei a confirmação para a coordenada do painel e mandei reabrir o painel
quando o personagem parava longe. Reprovou em horas:

> *"As aberturas do Surroundings começaram a ser constantes, principalmente na
> hora de ir para a Fay, aí fica entrando em loop e andando para lugar errado;
> nesse sentido as verificações estavam melhor antes."*

**A causa é uma escala que eu não conferi.** `Memory._coord` lê a posição e
DIVIDE POR 20 (`raw / 20.0`); o `[x,y]` do painel vem do TEXTO da interface.
Ninguém nunca provou que os dois números vivem no mesmo espaço — e se não vivem,
a distância nunca fecha, toda chegada é julgada "longe", e cada reabertura é mais
um clique com chance de cair fora do painel e mandar o personagem andar.

O código anterior nunca tropeçou nisso porque usava a coordenada **só como
atalho** ("cheguei perto, paro de esperar"), nunca como veredito. Quem encerrava
a espera era "parou de andar" — critério que não depende de escala nenhuma.

**A lição, e ela é a regra do projeto:** eu construí uma decisão em cima de uma
suposição não medida, e a suposição estava errada. O mesmo erro que o
`alvo-o-que-esta-medido.md` registra quatro vezes.

### O que ficou

`CONFIRMAR_CHEGADA_POR_COORDENADA = False`. A espera volta a sair por "parou de
andar", e a coordenada vira **medição**: a cada chegada sai no log a posição em
que o personagem parou e o que o painel prometeu. Se ao longo de algumas runs a
distância aparecer consistentemente pequena, os dois espaços são o mesmo e o
interruptor pode ligar — com número atrás, dessa vez.

**O minimapa foi considerado como atalho e recusado.** O usuário: *"entre
velocidade e precisão eu prefiro precisão, mesmo que custe alguns milésimos a
mais"*. O `CLAUDE.md` já tem regra medida de que repetir clique no minimapa
perde precisão, e a precisão de salto curto nunca foi medida.


# Navegação, rota e tempos — decisões e medições

> Recortado do `CLAUDE.md` em 14/08/2026, **verbatim**. O
> `CLAUDE.md` guarda a REGRA em uma ou duas linhas e aponta para cá; aqui
> fica a MEDIÇÃO que sustenta cada uma. Leia antes de mexer nesta área —
> quase toda decisão aqui já foi tentada do outro jeito e reprovou.

- **Antes de clicar no Altar Stone, o bot encosta EXATO em (218,45) — e se não
  encostar, NÃO CLICA.** A rota termina aceitando `TRICKY_TOLERANCE` (8 unidades)
  no Secret Altar — pirâmide apertada, exigir folga por waypoint travaria. Mas as
  coordenadas do clique no `altar_npc` foram medidas COM o personagem exatamente
  em (218,45). Em `routine._do_entrar_no_covil`, DEPOIS de o pré-requisito de
  posição (8u) confirmar, `_encostar_exato_no_patamar()` dá o último passo com
  `mapa_bc.PRECISAO_NO_PATAMAR_DO_ALTAR` (0.9, < 1 ⇒ no espaço inteiro só a
  célula exata passa), com `goto` ao vivo no minimapa (escala 1.7 px/unid.).
  - **A constante mora em `mapa_bc`** porque os DOIS lados a leem: quem anda até
    o ponto (`routine`) e quem confere antes de clicar
    (`ui_service.entrar_no_covil_do_boss`). Dois números escolhidos à parte foi o
    que travou a run no incidente da tolerância 3.
  - **"Parou" não é "chegou".** `_encostar_exato_no_patamar` só devolve True
    quando a LEITURA DE POSIÇÃO bate. O `wait_until_still` serve só para
    esperar: ele devolve True em duas condições, e uma delas é apenas "a posição
    parou de mudar" — parar em qualquer lugar contava como ter chegado. Medido
    no log de dev, era assim que o ajuste terminava em (217,45)/(216,45), do
    outro lado do alvo ("dentro" do Altar Stone), sem avisar: nos 3 casos em que
    o clique saiu de fora do ponto o aviso de falha não apareceu.
  - **Evidência que sustenta o portão** (`logs/dev/blazes-dev.jsonl`): das
    tentativas que abriram o diálogo, TODAS tinham o personagem exatamente em
    (218,45); das 11 fora do ponto, ZERO abriram. Estar exato **não basta** (26
    falhas no ponto certo, taxa de ~13%) — a causa restante é oclusão por mob na
    frente da pedra —, mas fora do ponto não se tenta: clicar de fora só gasta a
    tentativa do ciclo.
  - **Orçamento do ajuste:** `TENTATIVAS_DE_ENCOSTAR_NO_ALTAR = 6` ×
    `SEGUNDOS_POR_TENTATIVA_NO_ALTAR = 3.0` (era 4 × 8 s = até 32 s). O passo
    real é de 1 a 2 unidades, medido em 1 a 2 s.
  - **View Reset só quando o personagem andou:** `entrar_no_covil_do_boss` recebe
    `forcar_visao` (padrão True) e a rotina passa `forcar_visao=andou`, comparando
    a posição com a do clique anterior. Parado, a câmera não se mexe, e o reset
    custava um clique mais a espera em cada volta do ciclo — tempo em que o mob
    que engoliu o clique continua na frente da pedra.
- **Otimização de tempos FORA da cave — "onde havia espera cega, agora se
  PERGUNTA".** Medido no `logs/dev/blazes-dev.jsonl` (4034 registros): a fase
  `ENTRAR` gasta **478 s de mediana**, contra ~300 s da run inteira depois dela;
  dentro dela, **167 de 272 cliques direitos (61%) não abriam o diálogo** e cada
  um consumia um ciclo. A cadência NÃO era o problema —
  `ESPERA_ENTRE_TENTATIVAS` já era 0,05 s e o ciclo já rodava a ~1 s.
  - **O log de dev ganhou MILISSEGUNDOS** (`log_json.py`, `record.msecs`). Sem
    eles o `ts` era `20:02:52` e nada abaixo de 1 s podia ser medido — as
    esperas em questão são de 0,05 a 0,9 s e todas apareciam como "1,00s". É
    pré-requisito de medição, não capricho.
  - **O teto da espera do diálogo APRENDE** (`ui_service.limite_da_espera_do_dialogo`).
    Era `LIMITE_DA_ESPERA_DO_DIALOGO = 0.35` fixo; um teto fixo erra dos dois
    lados (curto joga fora tentativa boa, longo paga o teto inteiro em toda
    tentativa que nunca ia abrir) e o valor certo depende da máquina e de
    quantos clientes estão abertos. Agora começa **permissivo** (0,90 s) e
    aperta conforme as aberturas reais são cronometradas, ficando 1,6× acima da
    pior vista, entre 0,35 e 1,20 s. `_esperar_o_dialogo` cronometra cada
    abertura e loga a demora e o teto seguinte.
  - **Surroundings: as duas esperas cegas viraram pergunta.** Fechar o painel
    confere `_pontos("surroundings") is None` (medido: 0,00-0,16 s contra 0,20 s
    sempre); clicar no resultado espera a POSIÇÃO MUDAR — o clique põe o
    pathfinding para trabalhar, e isso é leitura de memória. De quebra, o
    clique que cai no vazio agora aparece no log.
  - **A hipótese do teto do diálogo foi CONFIRMADA na run seguinte**, com os
    milissegundos ligados: as aberturas reais medidas foram **354, 458, 356 e
    283 ms** — três das quatro estavam ACIMA do teto fixo de 350 ms e eram
    jogadas fora por impaciência. O log agora conta a história:
    `Diálogo abriu em 354 ms (teto era 1300 ms; próximo teto 566 ms)`.
  - **A lição "o leitor de arredores não funciona neste cliente" atravessa as
    runs.** `surroundings_first()` não responde nesta build — medido. O bot já
    aprendia isso e parava de esperar, mas o contador vivia na instância do
    `UIService`, que nasce de novo a cada run: **a mesma lição era paga outra
    vez toda run**, 1,5 s por busca até reaprender (3,0 s por run). Agora mora
    em `_BUSCAS_SEM_LEITURA`, por hwnd, no módulo. Uma leitura boa a qualquer
    momento zera a contagem.
  - **`ESPERA_CEGA_DO_RESULTADO` caiu de 0,9 para 0,45 s**, e só porque agora
    existe REDE: `ir_para_resultado` confere se o personagem saiu do lugar. Sem
    ela, encurtar seria trocar tempo por risco — clicar numa lista que ainda
    mostra o resultado ANTERIOR manda o personagem para outro lugar em silêncio.
  - **Teleporte do vendedor: 6,0 s cegos → sai no salto de posição.** A
    confirmação já era `distancia(antes, depois) >= SALTO_QUE_CONFIRMA`; agora o
    laço sai no instante em que o salto acontece. Medido: **4,5 s por venda**
    quando o teleporte leva 1,5 s. O teto de 6 s continua e só é pago quando o
    teleporte realmente não acontece, que é quando se quer certeza.
- **O zoom do minimapa é padronizado a cada run** (`UIService.padronizar_zoom_do_minimapa`).
  São **cinco níveis** (padrão no meio, 2 de aproximar, 2 de afastar) e os botões
  **param no batente** — `minimap_zoom_out` em (995,126) e `minimap_zoom_in` em
  (995,100), do canto superior direito. Por isso não é preciso LER o zoom atual:
  encosta no batente (5 cliques out, sendo o 5º folga para um clique engolido) e
  volta 2. Custa 0,35 s por run.
  - **Padrão, e NÃO zoom-out máximo**, e o motivo é duro: `zones.MINIMAP_SCALE =
    1.7` px/unidade foi medido com o jogo no zoom em que ele abre, porque esses
    botões nunca tinham sido usados pelo bot. Toda a navegação sai daí
    (`ALCANCE_DO_MINIMAPA` = 30/1,7 ≈ 17,6 unidades por clique). Em outro zoom a
    escala é outra e **todo clique de movimento passa do alvo — sem erro e sem
    aparecer no log**.
  - Zoom-out máximo poderia ser melhor (mais unidades por clique = menos cliques
    por trajeto), mas exige remedir a escala, e errar ali quebra o movimento em
    todo lugar de uma vez.
- **O teleporte da Fay tem teto de 3 s e sai no instante em que confirma**
  (`ui_service.TETO_DO_TELEPORTE_DA_FAY`, `_esperar_o_teleporte`). Era
  `ctx.tick(4.0)` CEGO, com o comentário "tempo do teleporte". Medido no log de
  dev de 13/08/2026:
  ```
  02:52:31.422  Clicando no link em (305, 591)
  02:52:37.547  Teleportado; local agora: Ghost Din Woods   <- 6,1 s depois
  02:52:37.589  Abrindo o painel de arredores               <- 40 ms depois
  ```
  O painel de arredores abre IMEDIATAMENTE — a demora inteira era espera, não
  trabalho. Mesma regra do teleporte do vendedor e do painel: **onde havia
  espera cega, agora se PERGUNTA.**
  - **A confirmação é pela COORDENADA** (`mapa_bc.x_contradiz_a_cave`): Ghost
    Din Woods é o único ponto da rotina com X acima de 500, e o campo de nome
    tem falha medida de ficar preso na área anterior.
  - **Estourar o teto NÃO muda o valor de retorno**, e isso é o cuidado que
    esta mudança exigia: quando `viajar_para_ghost_din_woods` devolve False, a
    rotina conclui "não estou em Stone City" e **usa o item de retorno** — uma
    pedra ou a recarga do token. Um teleporte de 3,5 s viraria item gasto à
    toa. Então o teto vira AVISO no log e a rotina segue; quem descobre que não
    saiu do lugar é a leitura de posição do passo seguinte, que já existe e não
    custa nada. Se o aviso aparecer com frequência, é o teto que está curto — e
    a linha traz o número para decidir, em vez de um palpite.
  - **`fechar_dialogo()` passou para DEPOIS da espera:** a troca de mapa fecha o
    diálogo sozinha, então no caminho feliz `_pontos` não acha nada e o passo
    custa só uma captura — o `tick(0.6)` de dentro nem roda. Antes era pago
    sempre, e antes ainda dos 4 s cegos.
- **A SAÍDA da cave tem UM número de precisão, e a terceira repetição do mesmo
  erro está registrada.** `mapa_bc.PRECISAO_NO_PONTO_DA_SAIDA = 0.9`, lido por
  quem ANDA (`routine._encostar_exato_na_saida`) e por quem CLICA
  (`ui_service.sair_da_cave`, passando a tolerância em vez do default de 12).
  - **Era intermitente por 0,06 unidades.** O portão antigo do `_do_sair` andava
    só quando `distancia > 8`, e `na_posicao_de_clicar` clicava com até **12**.
    O waypoint do boss (80,-406) fica a **8,06** unidades da saída (81,-398):
    parado exatamente nele o bot andava e saía; tendo derivado 1-2 unidades na
    luta — (84,-405), 7,62 — **não andava** e **clicava assim mesmo**, de um
    lugar de onde o clique não pega. Funcionava ou não conforme onde a luta do
    boss terminasse, sem nenhuma mudança de código.
  - **Medido** (`logs/dev/blazes-dev.jsonl`, 13/08/2026): personagem em
    (84,-405), clique direito em (616,326) repetido, diálogo nunca abrindo,
    `Não saí da cave (falha 2168)` e subindo — 1615 registros na fase SAIR.
  - **Falhar sem clicar é melhor que falhar clicando:** ali o clique perdido não
    custa só a tentativa, cai no chão e o personagem sai andando pelo covil do
    boss, piorando a tentativa seguinte. Sem leitura de posição, porém, segue e
    deixa o clique decidir — recusar travaria a saída num laço sem saída.
  - Travado por teste (`test_mapa_bc.py`): o 8,06, a posição real da luta caindo
    do lado errado do portão antigo, e os TRÊS pontos de clique posicional
    (altar, vendedor, saída) exigindo `0 < precisão < 1`.
- **Destravamento por VIZINHOS NA ROTA — 1 à frente + 1 atrás.** Os três
  gatilhos (rollback, parado, sem progresso) chamam a mesma manobra,
  `Navigator.destravar_pelos_vizinhos`, que reentra na rota por um waypoint
  oficial e devolve o índice ALCANÇADO (chegou no 52, a rota segue do 53).
  - **Três candidatos, todos IMEDIATOS** (`mapa_bc.vizinhos_na_rota` devolve
    `(anterior, mais_proximo, seguinte)`): o waypoint mais próximo e os dois
    colados nele **na ordem da lista** — `base-1` e `base+1`. **Nunca "o mais
    próximo entre os de índice maior"**, que foi o que custou uma run: parado em
    (205,31), a versão antiga escolhia (219,44) a 19 unidades, **pulando três
    waypoints**, quando (205,23) estava a 8. O jogo respondia no chat
    `Failed to auto-path [Secret Altar(205,31)->Secret Altar(218,43)]`. A rota
    não é um conjunto de pontos, é um **caminho**: cada trecho foi desenhado
    porque é andável a partir do anterior, e na pirâmide pular é atravessar
    parede.
  - **A referência é a posição ATUAL**, nunca o índice em que a rota achava que
    o personagem estava. Depois de um rollback os dois divergem (log: "Voltei do
    waypoint 51 para perto do 49") e é o índice que está errado.
  - **Ordem: mais próximo → seguinte → anterior.** O mais próximo primeiro
    porque, estando FORA do caminho, andar pelo caminho é impossível antes de
    voltar a ele. **No rollback, o anterior vem antes do seguinte** (o chão por
    onde o personagem acabou de passar é o comprovadamente andável); o mais
    próximo continua em primeiro.
  - **O candidato mais próximo exige chegar de verdade**
    (`TOLERANCIA_DE_VOLTA_AO_CAMINHO = 3`, contra os 8 da área). Com a tolerância
    da área ele seria um "cheguei" instantâneo: o personagem a 8,0 unidades de
    (205,23) já era dado por alcançado sem andar, e o alvo seguinte virava
    (244,23), a 40 unidades atravessando a pirâmide.
  - **A rota vai INTEIRA, com `comecar_em`** (`seguir_rota(rota, comecar_em=N)`).
    Antes a retomada passava uma FATIA (`CAMINHO_ATE_O_ALTAR[retomar:]`), e a
    fatia levava embora tudo o que estava atrás — inclusive o waypoint anterior,
    que é candidato. No log de (205,31) o anterior estava a 10 unidades e não
    existia na lista que a manobra recebeu.
  - **Estando NA ROTA, só frente.** Se o personagem está dentro da tolerância de
    um waypoint ele não está perdido — está no caminho, e o que falta é andar.
    Voltar dali era o que produzia a série de cinco, seis waypoints de ré.
  - **2 passadas × 4 s** (`PASSADAS_DO_DESTRAVAMENTO`,
    `SEGUNDOS_POR_TENTATIVA_DE_DESTRAVAR`): frente, trás, frente, trás = 16 s no
    pior caso, contra 3 × 20 s = 60 s de antes. Os 4 s têm medição: dos 18
    candidatos alcançados no log, 16 chegaram em ≤4 s; os 5 que falharam
    gastaram o orçamento inteiro (16-20 s). Usa `follow_path` direto, não `goto`
    — o `goto` tem piso de 5 s (`max_seconds=max(5.0, ...)`) e mexer nele
    mudaria todos os outros deslocamentos do bot. Não passa `rota=`, senão os
    gatilhos de travamento disparariam DENTRO da manobra, recursivamente.
  - **Trava do retrocesso** (o `precisa_avancar` foi REMOVIDO): voltar é
    permitido — proibi-lo descartava 6 das 20 chegadas bem-sucedidas do log —,
    mas não em série. Duas regras: não retroceder duas vezes para o MESMO
    waypoint (`_retrocessos_feitos`), e depois de um retrocesso bem-sucedido só
    tentar a FRENTE (`_retrocesso_bloqueado`) até a rota AVANÇAR além dele
    (`indice > _indice_do_retrocesso`). É isso que impede o deadlock que o
    `precisa_avancar` evitava — "cheguei no 1/10, a rota continua do 2/10", para
    sempre — sem proibir o retrocesso legítimo.
  - **A memória do retrocesso é POR RUN**, zerada só em `routine`
    (`nav.esquecer_retrocessos()`, no início da run). Ela ficava sendo zerada no
    começo do `follow_path`, e isso **anulava a trava inteira**: a própria
    manobra chama `follow_path` para cada candidato — cada tentativa apagava o
    que a manobra tinha acabado de gravar —, e cada volta SITUAR → ATE_O_ALTAR
    abria outro (seis num minuto no log). A trava existia e nunca valeu uma vez;
    o sintoma era o personagem andando cinco, seis waypoints de ré.
  - **Falhou tudo ⇒ devolve o controle ao SITUAR**, igual nos três gatilhos.
    Antes "sem progresso" abortava e "parado" continuava no laço; a diferença era
    acidente, não decisão. Se dois waypoints oficiais colados no personagem não
    foram alcançados em 4 tentativas, o problema não é escolha de destino.
  - **Sem limite de distância**: com 4 s por candidato, tentar de longe custa
    pouco. Há caso real de parada a 50 u de qualquer waypoint (`(380,166)`, na
    Centipede Zone) e caso real de chegada bem-sucedida a 45 u.
  O passo lateral (`_destravar`) foi **REMOVIDO DE VEZ** (pedido do usuário):
  ele andava o personagem 1-2u e impedia o detector de "sem progresso" de
  disparar o relançamento — o log ficava 40 s em `destravando 1` sem concluir.
  Chegou num waypoint oficial da rota, o trajeto natural continua do seguinte.
  Fora da cave (sem rota) não há relançamento — o laço fica reclicando o alvo e
  desiste em `travas > 6`.

  O detector de **rollback/lag** usa `houve_rollback` com
  `FOLGA_ROLLBACK = 1`: voltar até 1 índice é ruído normal de leitura; voltar
  **2+ índices** é rollback e relança (o usuário confirmou: o lag costuma
  devolver 2-3 waypoints, nunca mais de 5). O rollback relança com
  `tras_primeiro=True` (o chão por onde o personagem acabou de passar é o
  comprovadamente andável) e reconfirma a posição ~0,5 s antes de relançar
  (leitura pode pegar o personagem no meio do "pulo" do lag). Se a manobra não
  alcançar nada, o índice volta para o waypoint do rollback.

  O **círculo de offsets** (`_tentar_circulo`) e a **retomada de rota**
  (`onde_retomar`) ficaram **DESLIGADOS do fluxo** por decisão do usuário ("só
  use o cálculo dos waypoints vizinhos"); o código continua definido
  (navigation.py + mapa_bc.py) para reuso futuro, mas nada os chama mais. O
  círculo era a antiga "última carta" (offsets ao redor da própria posição e do
  waypoint, teto `CIRCULO_TETO_SEGUNDOS`); detalhes históricos na seção 5 do
  `NAVEGACAO.md`. A rota continua do waypoint ALCANÇADO; se nada deu, retoma do
 waypoint do rollback.


---

## 18/08/2026 — o laço do destravamento: o mesmo waypoint dezenas de vezes

Relato com foto do chat do jogo (`data/templates/entrada/erro-repeticao.png`):

    Failed to auto-path [Secret Altar(203,30)->Secret Altar(216,43)]
    Failed to auto-path [Secret Altar(203,30)->Secret Altar(216,43)]
    ... (o usuário confirmou que a foto mostra só uma parte)

O jogo dizendo, dezenas de vezes, que aquele trajeto não existe de onde o
personagem está — e o bot pedindo de novo.

### Causa 1: o orçamento medido tinha sido cortado 5,3x

| | este documento registrava | código encontrado |
|---|---|---|
| tempo por candidato | **4 s** | 1,5 s |
| passadas | **2** | 1 |

Os 4 s têm medição explícita registrada acima: *"dos 18 candidatos alcançados no
log, 16 chegaram em ≤4 s"*. O valor caiu no halvamento geral de tempos — cuja
própria regra excluía thresholds medidos — e **nem consta no
`alteracao_tempo.md`**. Pior: os comentários dentro do `navigation.py`
continuavam descrevendo 4 s e "3 candidatos x 2 passadas x 4 s = 24 s" ao lado
dos valores 1,5 e 1.

Confirmado no log de produção de 03:21: cada tentativa durou **~1,7 s** e todas
falharam; a manobra inteira gastou 5 s. Candidato que chegaria em 2-4 s era
abandonado antes de chegar.

**Restaurados para 4,0 s e 2 passadas.**

### Causa 2: não havia memória de candidato que falhou

A manobra escolhe os candidatos a partir da POSIÇÃO ATUAL. Se ela não muda, a
escolha não muda — cada nova chamada recomeçava com os mesmos três vizinhos e
pedia ao jogo o mesmo trajeto que ele já tinha recusado.

`Navigator._candidatos_que_falharam` guarda o que já foi tentado e não alcançado
**neste episódio**. Zerado quando o personagem CHEGA em algum waypoint
(`esquecer_falhas_do_episodio`) — a informação era sobre uma posição em que ele
não está mais, e mantê-la envenenaria o episódio seguinte.

Esgotada a lista inteira, a memória morre e a manobra recomeça em vez de
devolver `None` para sempre: trocar um laço por paralisia não seria conserto.

### A expansão, e a tensão que ela assume

Pedido do usuário: *"já que aquele não está funcionando é importante testar os
outros para ver se destrava e volta para o caminho dos waypoints"*.

`ALCANCE_DA_EXPANSAO = 4`: falhados os imediatos, a manobra se afasta de um em um
**NA ORDEM DA ROTA** — base+2, base-2, base+3, base-3.

**Nunca por proximidade em linha reta.** Essa é a regra que custou uma run
("a rota é um CAMINHO, e pular waypoint é atravessar parede"), e ela continua
valendo: todo candidato é waypoint da rota, e a ordem de tentativa é do mais
perto ao mais longe DENTRO DELA.

**A tensão fica registrada:** afastar-se pula waypoint intermediário, que é
exatamente o que a regra antiga proíbe. A diferença é a ordem dos fatos — no
incidente antigo o waypoint distante era escolhido DE PRIMEIRA, por estar mais
perto em linha reta; aqui ele só é tentado depois de o imediato ter falhado de
verdade, o que é informação que o bot não tinha antes.

Travado por `tests/test_destravamento_sem_laco.py`, com dente: sem a memória,
duas chamadas seguidas têm que pedir o MESMO trajeto.

---

## A câmera: o `set_camera` nunca escreveu na câmera (25/08/2026)

**O sintoma que o usuário relatou:** o View Reset acerta esquerda/direita, mas
cima/baixo não se ajusta nunca. E: *"eu testei setar manualmente pelo Cheat
Engine, mas não aceita, ele volta para o valor anterior e não muda nada na
tela"* — isso sobre `client.exe+D6339C`, o termômetro.

**A pergunta que nunca tinha sido feita.** `set_camera` escreve zoom/rotação/
ângulo em `resolve(ADDR_CAMERA, ...)` depois de todo View Reset, desde sempre.
`ADDR_CAMERA = 0x0116FFF4` é herança do T-R0XX/GhostBot da versão **6139**, a
câmera **não está** na lista do `core/rebase.py`, e ela **nunca tinha aparecido
no diagnóstico**. Ou seja: podia estar escrevendo em lugar nenhum desde sempre,
e ninguém teria como saber.

**Medição de 25/08 (`2-DIAGNOSTICO`, conta BlazesOfGamer):**

```
[câmera FORA] ângulo = 1220.339355 | esperado 956.720459 | diferença 263.618896
[câmera] ADDR_CAMERA     (0x0116fff4) -> NULO: ponteiro nulo ou fora da faixa
[câmera] ADDR_CAMERA+0x60(0x01170054) -> 0x15a0f3c8: aceitou a escrita
           rotacao = 0.0     angulo = 41.59999084472656     zoom = 300.0
```

Três coisas saem daí:

1. **O endereço de hoje está morto.** `ADDR_CAMERA` resolve NULO na 6400. Todo
   `set_camera` desde o transplante do GhostBot escreveu em lugar nenhum.
2. **O `+0x60` é medido, não chute.** O `TARGET_ID` do GhostBot é `0x0115CB20`;
   o que responde na 6400 é `0x0115CB80`. Mesmo banco de estáticos, mesmo
   deslocamento. A câmera é desse banco.
3. **`ADDR_CAMERA+0x60` tem a FORMA da câmera.** `rotacao` exatamente `0.0` (é
   o View Reset), `angulo` ~41,6 e `zoom` 300 — contra os `(380, 0, 40)` que o
   GhostBot escrevia. Mesma ordem de grandeza, mesmos três campos.

### O defeito da primeira prova: era o relógio, não o endereço

A primeira versão do diagnóstico escrevia na struct e relia o termômetro **na
instrução seguinte**. O termômetro é recalculado pelo jogo A CADA QUADRO — a
30 FPS, o quadro leva 33 ms. Ela leu o quadro ANTERIOR e imprimiu:

```
aceitou a escrita mas o termômetro NÃO mudou -- não é a câmera
```

Essa conclusão errada quase mandou o projeto automatizar as telas de Gráficos do
jogo, que é o caminho caro (abre janela na cara do usuário: *"não é bacana isso
acontecer para o usuário ver"*).

A prova de hoje **pergunta** ao termômetro a cada `PASSO_DA_PROVA_DA_CAMERA` e
sai no instante em que ele mexe (`TETO_DA_PROVA_DA_CAMERA` é aviso, não gasto),
prova os **três** campos separadamente, e separa:

| o que se vê | o que significa |
|---|---|
| o termômetro mexeu | **é a câmera** — é o caminho |
| o jogo DESFEZ o valor | campo **derivado**, como o próprio termômetro |
| o valor FICOU, termômetro parado | campo de **entrada**, mas o termômetro mede outro eixo — desempata olhando a TELA |

### O veredito (25/08, com a prova consertada)

```
[câmera] ADDR_CAMERA      (0x0116fff4) -> NULO
[câmera] ADDR_CAMERA+0x60 (0x01170054) -> 0x15a0f3c8: ESCREVE E MOVE A CÂMERA
    rotacao 0x15a0f424 = 0.0   -> 5.0    o valor FICOU, termômetro parado
    angulo  0x15a0f428 = 41.6  -> 46.6   MOVE  (termômetro 756.34 -> 738.13)
    zoom    0x15a0f42c = 300.0 -> 305.0  MOVE  (termômetro 738.13 -> 760.08)
```

**Dá para corrigir a câmera por escrita de memória**, sem tocar no mouse e sem
abrir as telas de Gráficos. O caminho (a), automatizar o Lock the View, fica
arquivado: era o caro e o feio (*"não é bacana isso acontecer para o usuário
ver"*).

A `rotacao` não mexer o termômetro **casa com o sintoma relatado**: o View Reset
já resolve esquerda/direita; o que falta é cima/baixo, que é o `angulo`.

Uma ressalva de leitura: o termômetro do zoom (`+21,9`) está contaminado pelo
`finally` que restaurou o ângulo no teste anterior — a linha de base dele já
vinha caindo. O sinal de que MOVE é sólido; a magnitude, não.

### O que ainda NÃO se sabe

**Qual é a pose certa em números.** `ANGULO_DA_CAMERA = 956.720459` é leitura do
TERMÔMETRO, não da struct. Ninguém sabe quanto valem `rotacao/angulo/zoom` com a
câmera na pose em que os cliques 3D foram medidos — os `(380, 0, 40)` são da
6139 e nunca foram conferidos na 6400.

Quem responde é o **`17-LER-CAMERA`** (`blazesbot/tools/ler_camera.py`): vigia a
struct ao vivo, imprime uma linha a cada mudança e **não escreve nada** (travado
por teste de AST). Roda-se ele, faz-se o Lock the View na mão, e a última linha
é a pose de referência.

Enquanto essa medição não existir, `set_camera` fica como está: corrigir o
endereço sem saber o valor certo trocaria uma escrita inofensiva em lugar nenhum
por uma escrita eficaz com o número errado.

**Se o termômetro é constante do JOGO ou do LUGAR.** Dois `2-DIAGNOSTICO` do
mesmo personagem, com a câmera intocada entre eles, leram `1220.339355` e
`756.339355`: **464,000000 cravados** de diferença, e a fração `.339355`
idêntica nos dois. Fração preservada com o inteiro andando em bloco não parece
ruído de interpolação.

Se quem manda for a POSIÇÃO, `ANGULO_DA_CAMERA = 956.720459` deixa de ser
constante do projeto e vira "o valor medido naquele ponto" — e todo o
`camera_no_angulo_certo` passa a comparar contra a régua errada fora dali. Contra
essa hipótese pesa a medição do usuário: andando, o termômetro oscila 0,0005 e
volta. A favor, os 464 exatos.

**O experimento:** rodar o `17-LER-CAMERA`, **não tocar na câmera**, e andar. A
ferramenta imprime termômetro, delta e posição na mesma linha justamente para
isso.

### A pose, medida (25/08/2026)

O usuário rodou o `17-LER-CAMERA`, pôs a câmera na pose em que os cliques
funcionam, e a linha foi:

```
[06:20:48] termômetro = 761.813538  (+18.385254)   posição = (78, -406)
           ADDR_CAMERA        <ponteiro nulo>
           ADDR_CAMERA+0x60   rotacao=0.000000  angulo=40.000000  zoom=300.000000
```

`POSE_DA_CAMERA = (300.0, 0.0, 40.0)`, na ordem `(zoom, rotacao, angulo)`.

**O ângulo 40 sempre esteve certo.** O `(380, 0, 40)` herdado errava só o
ZOOM -- 380 contra 300. E como toda escrita caía no `ADDR_CAMERA` morto, nem a
metade certa nem a errada chegavam ao jogo: não havia como descobrir qual era
qual.

**O termômetro lia 761,81 nesse instante, e não 956,72.** É a confirmação de
que ele não servia de régua: a câmera estava na pose CERTA e ele estava a 195
pontos do valor que o projeto tratava como alvo.

### Onde se mexe: um lugar só, e é o `.py`

`POSE_DA_CAMERA`, em `blazesbot/core/memory.py`. Trocar a tupla é tudo -- não há
chave em `config.json`, não há campo em `BotConfig`, não há nada para
sincronizar.

**A pose já passou pela config, e voltou.** Chegou a existir como
`BotConfig.camera` lido do `data/config.json`, e isso produziu na hora o
problema clássico de valor em dois lugares: o arquivo salvo do usuário trazia
`[380.0, 0.0, 40.0]` e **ganhava** do padrão do código -- corrigir o `.py` não
chegava em quem já tinha config gravado. Um lugar só é mais fácil de mexer *e*
não tem como divergir. A pose é propriedade do JOGO, como os waypoints da cave:
conta nenhuma tem câmera diferente da outra.

Duas coisas seguram isso:

1. **`test_a_pose_mora_SO_no_py`** reprova se `camera` reaparecer em
   `BotConfig` ou no `data/config.json`.
2. **A pose em uso vai para o LOG**, uma vez por sessão. Sem isso, testar uma
   pose nova é palpite -- o mesmo buraco que deixou o zoom 380 sobreviver anos.

`camera_na_pose_certa(alvo)` recebe o alvo em vez de reler a constante: é o que
deixa o diagnóstico conferir uma pose candidata sem editar o módulo.

---

## O painel de arredores: escala respondida, e a cadência (25/08/2026)

### A escala do `[x,y]` do painel — RESPONDIDA

Ficou aberto por dias que `Memory.position()` divide a leitura por **20** e o
`[x,y]` do painel vem do texto da UI, e que *"ninguém provou que os dois estão
na mesma escala"*. O log do seletor de endereço respondeu de graça:

```
surroundings: CANDIDATO @0x012ce33c (o candidato +0x60 respondeu e o atual não)
  -- 0x012ce2dc=None, 0x012ce33c={'nome': 'Rich Man', 'coords': (153, -493), ...}
```

E `mapa_bc.POSICAO_DO_VENDEDOR = (158, -494)`.

**Mesma escala.** A diferença de 5 unidades em x é o NPC contra o ponto onde o
personagem para para clicar nele — que é exatamente o que se espera de um
waypoint de aproximação.

De brinde, o mesmo log confirma que **o painel É legível por memória** na 6400,
pelo candidato `+0x60` (o `core/rebase.py` já escolhe sozinho). É mais um item
do inventário de `memoria-primeiro.md` pronto para migrar.

### Mas o interruptor continua desligado, e não é teimosia

`CONFIRMAR_CHEGADA_POR_COORDENADA = False`. A escala era **metade** do problema.
A outra metade é de desenho: ligado, ele transforma um ATALHO de saída ("cheguei
perto, paro de esperar") em VEREDITO ("não cheguei, reabre o painel"). Foi assim
que virou loop de aberturas na ida à Fay, com o bot andando para o lugar errado
-- *"as verificações estavam melhor antes"*.

Respondida a escala, o que falta para ligar não é medição: é redesenhar a
confirmação para que uma distância grande signifique "espero mais um pouco" e
não "abro tudo de novo".

### A cadência entre usos

Relato: *"tem vezes que fica abrindo, filtrando, clicando para dar o auto path,
aí fechando e repetindo o processo tudo bem rápido... pode ser mal visto pelo
usuário final"*.

A causa é `buscar_npc`, que retenta até 3 vezes e refaz o ciclo inteiro a cada
volta. Três quedas seguidas abrem e fecham o painel três vezes em poucos
segundos, e isso não parece alguém jogando.

`INTERVALO_ENTRE_USOS_DO_PAINEL = 2.0`, e o detalhe que importa: **a espera é o
RESTO do intervalo, não o intervalo.** Entre um uso e o seguinte costumam passar
minutos -- Fay, entrada da cave e vendedor são três usos por run -- e nesses
casos o resto é negativo e ninguém espera nada. Só a REPETIÇÃO rápida paga, que
é justamente o que fica feio de ver.

Cumprida com `ctx.tick`, não `time.sleep`: o Parar continua imediato dentro da
espera.

**Número COSMÉTICO, e é honesto dizer:** não há medição atrás dele, porque a
pergunta que ele responde não é técnica ("com que rapidez o painel pode
reabrir?") e sim de aparência ("a partir de quanto isso parece um robô?"). Está
lá para o usuário ajustar.

### CORREÇÃO de 26/08/2026: o carimbo estava no lugar errado

O relato voltou -- *"a aba surroundings tem aberto muitas vezes em sequência"* --
e a causa era esta cadência **quase nunca morder**: o carimbo saía só na
ABERTURA, então o intervalo media *abrir → abrir*. Um ciclo inteiro (abre,
filtra, clica, espera parar, fecha) passa dos 2 s, e aí a reabertura seguinte não
pagava nada.

Agora o carimbo sai em **três** pontos e vale o mais recente: abrir, clicar no
auto-path e fechar (`_marcar_uso_do_painel`).

E a cadência **não era o problema principal**. Havia mais três defeitos somados,
incluindo um laço infinito digitando dentro do campo de busca. O relato inteiro,
a medição do guarda de janela e os quatro consertos estão em
**`docs/decisoes/janela-na-frente.md`** -- leia aquele arquivo antes de mexer
aqui.


## O PORTÃO DA MONTARIA INSISTIA MUDO — 24 MINUTOS PARADOS (01/09/2026)

### O log, inteiro

Conta `creubo`, run `db7ebdace7`, 31/08/2026. Waypoint dos Gun Witch,
`(110,-406)`, `Secret Cemetery`. Linhas repetidas suprimidas:

```
23:27:42  ATE_OS_GUARDAS levou 7,0s -> GUARDAS | posição (110, -406)
23:27:43  Desmontando antes da luta de guardas
23:27:46  ALVO MORREU: Gun Witch hp=0/100   -> TAB 1 de 3
23:27:49  ALVO MORREU: Gun Witch hp=0/100   -> TAB 2 de 3
23:27:53  ALVO MORREU: Gun Witch hp=0/100   -> TAB 3 de 3
23:27:58  ALVO MORREU: Gun Witch hp=0/100   -> TAB 4 de 3
23:27:58  Cemetery Guard na mira (TAB 4: tela, match em (535, 38)).
          Largo a mira no ESC, paro de bater e AGUARDO a saída de combate.
23:28:02  A flag de combate baixou em guardas (18s). Confirmando por 2,5s.
23:28:07  Fora de combate confirmado: 2,6s contínuos com a flag baixa
23:28:07  FASE 1 concluída em 23s (92 golpes); indo direto para o boss
23:28:07  GUARDAS levou 24,4s -> ATE_O_BOSS | posição (103, -406)
23:28:07  Não estou montado; montando antes de percorrer 1 waypoint(s)
23:28:14  Não conseguiu montar em 6s          <- 453 linhas iguais a esta
23:28:39  NÃO CONSIGO MONTAR ... há 32s (5 tentativas). Continuo insistindo.
          ...                                 <- 62 vezes a MESMA frase
23:52:32  Montaria confirmada depois de 1465s insistindo
23:52:32  Percorrendo 1 waypoints (tolerância 6, teto 60s)
23:52:34  sem progresso indo para (80, -406) (distância 578)
23:52:48  Travado no waypoint 1/1, a 575 unidades. Posição (426, 53)
23:52:48  ATE_O_BOSS levou 1481,4s -> SITUAR
```

**24 minutos e 25 segundos.** E ele não se recuperou: a posição final é
`(426, 53)`, que é **Bewitcher Cave**, não o covil. A instância expirou e cuspiu
o personagem para fora — foi isso que soltou a montaria. A recuperação em
produção era SORTE, não lógica.

### O que o log prova, e que muda o desenho

**1. A fase dos guardas ENCERROU LIMPA.** "Fora de combate confirmado, 2,6 s
contínuos com a flag baixa". Então um conserto colocado no estado `GUARDAS` não
pegaria este caso: para aquele estado, deu tudo certo. A saída de combate foi um
**pisco** — o Cemetery Guard que o ESC largou às 23:27:58 voltou a engajar
depois da confirmação.

**2. O portão não lia nada.** 1465 s, 62 ciclos, e nenhuma leitura de
`in_battle`, de `dead` ou de vida. "Continuo insistindo" 62 vezes não é
diagnóstico, é a mesma frase 62 vezes. Volume de log inversamente proporcional
à informação.

**3. Havia um segundo travamento latente, pior.** O portão nunca devolve o
controle, e `_guard()` — quem detecta o personagem morto — só roda no topo do
laço principal da rotina. Personagem morto dentro do portão = tecla de montaria
apertada num cadáver **para sempre**, sem manutenção, sem poção, sem log. Nunca
foi observado porque o de cima acontece primeiro.

### Por que insistir não podia resolver

**Em batalha o jogo RECUSA a montaria.** É a mesma parede que
`ensure_dismounted` já documenta do outro lado. O portão insiste sem teto por
decisão firme e correta (`NUNCA A PÉ DENTRO DA CAVE`, 25/08/2026 — a pé não se
chega no boss), mas essa decisão pressupõe que insistir eventualmente funcione.
Contra uma condição que só um GOLPE remove, insistir é esperar para sempre.

E o `garantir_montaria_para_andar` diz, com todas as letras, que **não consulta
flag de batalha**: *"a flag fica ligada com qualquer mob por perto, demora a
baixar depois do último golpe e já foi vista presa. Consultá-la só fazia o bot
deixar de acionar a tecla em situações em que ela funcionaria."* **Isso continua
valendo e não foi revertido.** A flag NÃO decide se a tecla sai — ela continua
saindo em todo ciclo. A flag só decide **se vale a pena tirar a causa do
caminho**, e só a partir do 2º ciclo, quando o resultado já provou que o
acionamento não está pegando.

### Alternativas reprovadas

| alternativa | por que não |
|---|---|
| Consertar no estado `GUARDAS` (o que o usuário pediu primeiro) | O log prova que aquele estado encerrou limpo. Não pegaria este caso, nem a volta do altar, nem a saída pelo Skull Herald. |
| Dar teto ao portão e seguir a pé | Viola `NUNCA A PÉ DENTRO DA CAVE`. A pé não se chega no boss: seria perder a run mais tarde, depois de gastar a travessia. |
| Dar teto ao portão e abandonar o waypoint | Foi oferecido ao usuário em 01/09/2026 e **recusado**: *"deve insistir"*. O portão continua sem teto. |
| Bater em área para limpar rápido | Área acerta quem está em volta e puxa mob que não estava em combate. Troca um travamento por outro, agora em bola de neve. |
| TAB imediato depois de cada morte | Mesmo defeito: sem nome esperado, o TAB mira o mob seguinte e o golpe o puxa. Daí a pausa de 3 s do usuário. |
| Matar o Cemetery Guard sempre | A trava existe para EVITAR puxá-lo, e ela funciona. O usuário foi explícito: *"mantém o ESC, mas caso passe os segundos máximos de espera ... vai matando de 1 em 1"*. A trava só é suspensa **dentro** do destravamento. |

### O conserto

Duas peças, ligadas pela rotina porque `combat.py` já importa `navigation.py`:

* **`navigation._diagnosticar_o_portao`** — a cada ciclo lê a causa. Morto ⇒
  levanta `PersonagemMortoNoPortao` (a rotina converte em `RECUPERAR`). Em
  batalha, a partir de `CICLOS_ANTES_DE_DESTRAVAR = 2` ⇒ chama o destravamento.
  `in_battle() is None` (não sei) **não** destrava.
* **`combat.limpar_o_combate`** — mata mob a mob, um por vez, sem AoE, com
  pausa de 3 s olhando a flag depois de cada morte, teto de 60 s.

O número `CICLOS_ANTES_DE_DESTRAVAR = 2` não é arredondamento: um ciclo é
`TETO_DO_PORTAO = 6,0 s`, que já é o **dobro** da montagem mais lenta medida
(1 a 3 s, usuário, 25/08/2026). Dois ciclos dão margem para um caso raro e põem
o diagnóstico em **~13 s** contra os 1465 s do log.

Medido na simulação (`tests/test_destravamento_do_combate.py`, relógio falso):
1 mob ⇒ 5,6 s e **zero TAB**; 2 mobs ⇒ 11,5 s e **1 TAB**; ninguém cai ⇒ 63,1 s
e `False`, com o portão voltando a insistir.

---

## O ROLLBACK PASSA A SER MEDIDO PELO TRECHO, E NÃO PELO PONTO (03/09/2026)

**Vale para as duas caves — o conserto é em `core/rota.py`.**

`houve_rollback` perguntava *"qual waypoint está mais perto do personagem"*
quando a pergunta é *"ele foi jogado para trás"*. Numa rota que só avança as
duas coisas coincidem. Numa rota que **volta pelo mesmo corredor**, não: o mais
próximo pode ser um índice bem anterior enquanto o personagem anda, certinho, no
rumo do próximo.

O sintoma é um **loop infinito**: "voltei" → relança a navegação → o
destravamento escolhe o vizinho de trás → recruza → "voltei". A HH bateu nele
duas vezes no mesmo dia, em geometrias diferentes:

| trecho | geometria | por que o mais próximo mentia |
|---|---|---|
| 1 | (209,182) e (207,186) a **4,5** unidades — menos que a tolerância de chegada (7) | o bot cruza os dois de uma vez, o índice vai para 12, e o mais próximo continua sendo o 10 |
| 4 | (510,126) é uma **espora**: desce 19 para depois subir 33 até (509,93) | andando de 13 para 14 o personagem passa de novo pela altura do (507,107) |

Os dois pontos são **legítimos** — o bot em Lua usa os mesmos, e o `via` de cada
um é diferente: o ponto existe para virar a direção do clique no minimapa, não
para andar 4 unidades. O errado era a régua.

**A correção:** quem decide é o **trecho atual** (`distancia_ao_trecho`, do
waypoint anterior ao alvo). Estar em cima dessa reta é a definição de "estou
indo para onde mandaram", por mais perto que passe um waypoint antigo. Nos dois
casos medidos a distância ao trecho era **2,3** e **0,7** unidade, contra as 12
de `NA_ROTA` — a mesma régua que o resto do módulo já usa para separar
"escorreguei" de "saí da rota". **Número novo, nenhum.**

O rollback de verdade continua sendo pego, e o teste prova: teleporte para trás
fica **longe do trecho atual E perto de um índice bem anterior**. Precisa das
duas coisas, e o andar normal só tem a segunda.

**Uma alternativa foi proposta e REPROVADA no caminho:** "olhar o waypoint mais
avançado dentro da tolerância". Ela conserta o trecho 1 e **não** conserta o
trecho 4 — em (509,115) nenhum waypoint está dentro da tolerância 7 (o 12 a 8,2;
o 13 a 11,0; o 14 a 22). Só o segundo log mostrou isso. **Subir a folga de 1
para 2** também consertaria os dois, e foi reprovada por outro motivo: pararia
de detectar o lag de 2 waypoints, que o próprio comentário da função registra
como acontecendo.

Detalhe medido, com os trechos do log: `docs/decisoes/hh.md` §12.2.

---

## UM GANCHO POR WAYPOINT ALCANÇADO — `ao_chegar` (03/09/2026)

`seguir_rota` e `follow_path` aceitam `ao_chegar`, chamado uma vez por waypoint
alcançado, com a coordenada dele. Existe para o punhado de pontos onde a rota
precisa **parar e fazer algo** — na HH, o (232,188), onde os mobs bloqueiam a
passagem.

Três decisões dentro dele:

1. **É OPCIONAL, e o padrão é `None`.** Sem gancho o comportamento é exatamente
   o de antes — é assim que a BC não muda.
2. **VALE PARA OS ATRAVESSADOS.** O laço pode cruzar dois ou três waypoints numa
   leitura só (a montaria é rápida), e um ponto que exige parada não pode ser
   pulado por causa da velocidade. Por isso o gancho roda para
   `caminho[indice:novo]`, e não só para o último.
3. **OS CRONÔMETROS RECOMEÇAM DEPOIS DELE.** O gancho pode ficar um minuto
   matando mob, e sem isso esse minuto contaria como "parado sem progresso" — o
   próprio laço concluiria que o personagem travou e dispararia o destravamento.
   `marco`, `ultimo_progresso`, `parado_desde` e `ultima_posicao` são
   reiniciados.

---

## O DESTRAVAMENTO QUE ANDAVA ZERO — 4 MIN 10 S NUM PONTO SÓ (04/09/2026)

O usuário mandou o print do jogo com o chat repetindo

    Failed to auto-path [Happiness Hall Visitor Room(282,139)->...(282,139)]

e o personagem cercado de *Elite Blackshirt Bandit*. O log deu o resto: **~180
voltas em 4 minutos e 10 segundos**, sempre o mesmo ciclo:

    sem progresso indo para (271,137) (waypoint 22/22, distância 11)
    Navegação travada em (282,139). Vizinhos: 21 em (282,139) a 0 -> 22 a 11
    Destravando pelo waypoint 21/22 em (282,139) (tolerância 2)
    waypoint 1/1 alcançado em 0.0s | posição (282,139)      <- andou ZERO
    Cheguei no waypoint 21; a rota continua do 22
    sem progresso indo para (271,137) ...                    <- e recomeça

### Por que o laço nunca fechava

`follow_path` de um ponto **já alcançado** devolve `True` sempre, em zero
segundo, com qualquer tolerância. A manobra declarava sucesso, o chamador zerava
o contador de travas, e a situação voltava idêntica.

Três proteções existiam e **nenhuma** cobria este caso:

| proteção | por que não pegou |
|---|---|
| tolerância apertada no mais próximo (`TOLERANCIA_DE_VOLTA_AO_CAMINHO`) | resolve "quase lá"; distância **zero** passa em qualquer tolerância |
| memória de candidatos que falharam | guarda quem **falhou**, e este tem sucesso |
| contador de travas com teto | é zerado pelo sucesso falso, então nunca cresce |

A terceira é especialmente instrutiva: o módulo **já tinha** um comentário
avisando que zerar `melhor_distancia` fazia "o contador de travas NUNCA crescer,
e com isso o teto nunca disparava". O mesmo formato, num campo diferente.

### O conserto

**Candidato dentro da tolerância de chegada é descartado**, e se sobrarem zero a
manobra devolve `None` em vez de fingir. A régua do filtro é a **mesma** da
tentativa (`_tolerancia_do_candidato`, extraída para função): duas cópias dessa
conta divergiriam em silêncio, e o sintoma seria um candidato descartado com uma
régua e tentado com outra.

---

## A NAVEGAÇÃO PASSA A SABER DE COMBATE, E A FICAR PRESA TEM PRAZO (04/09/2026)

Duas faltas no mesmo ponto do laço, e a causa de fundo do episódio acima.

### O jogo prende o personagem em combate

Insistir no clique de minimapa contra um combate não anda um passo — é o
`Failed to auto-path` do chat. O remédio **já existia**: `destravar_o_combate`,
o gancho que mata mob a mob até a flag baixar.

Mas só o **portão da montaria** o chamava. E o portão só entra quando se vai
montar; ali o personagem já estava montado e andando, então ele nunca era
consultado. É o mesmo gancho, no lugar que faltava.

Regra do usuário: *"é importante não deixar ficar sem progresso, arranjar uma
forma de continuar a cave, mas sem pular a morte dos boss, pois aqui em HH,
junto com os boss, tem vários mobs que precisam ser mortos"*. **Matar é
continuar** — e por isso matar vem ANTES do teto e ANTES da manobra de vizinhos.

`in_battle() is True`, e não `not ...`: leitura ilegível não autoriza sair
batendo, que seria puxar mob por causa de uma leitura que falhou.

### Ficar preso tem prazo — `TETO_PRESO_NO_MESMO_PONTO = 30 s`

Número do usuário: *"o ideal é não ficar muito tempo parado, 30 segundos sem
fazer nada já é bastante tempo parado"*.

Ele conta só o tempo **inútil**: matar mob zera o relógio, porque matar é
progresso mesmo com o personagem parado no lugar; e o avanço da rota zera
também, para o teto valer **por ponto** e não pelo trajeto inteiro.

**O que o prazo compra não é só tempo.** Enquanto a navegação insistia,
`_do_ate_o_boss` não devolvia o controle — e sem isso o `_guard()` da rotina não
roda, então o Parar e o watchdog ficam sem resposta. Os 4 min 10 s do episódio
só terminaram porque o usuário desligou a HH na mão. Estourado o teto,
`follow_path` devolve `False` e **quem decide é a rotina**, que sabe refazer o
trecho, matar ou falhar — e que respira.

