# Deletar itens (ecossistema APP) — decisões e medições

> Recortado do `CLAUDE.md` em 14/08/2026, **verbatim**. O
> `CLAUDE.md` guarda a REGRA em uma ou duas linhas e aponta para cá; aqui
> fica a MEDIÇÃO que sustenta cada uma. Leia antes de mexer nesta área —
> quase toda decisão aqui já foi tentada do outro jeito e reprovou.


`blazesbot/bot/app/deletador.py`. O BC resolve bolsa cheia vendendo; o APP roda
longe de vendedor, e deletar é a única saída lá.

- **O fluxo veio dos prints do usuário e NÃO usa tecla:** clique esquerdo no
  item → clique no **ÍCONE de deletar** (fileira de baixo do inventário) →
  aparece *"Are you sure to delete [item]?"* → clique em **Ok**. A primeira
  versão deste arquivo apertava uma tecla de apagar; não existe tecla.
- **Duas âncoras novas, medidas nos prints** (`data/templates/entrada/`):
  `btn_delete_item.png` (27×27, casa a **0.992** no inventário aberto) e
  `state_delete_confirm.png` (o TÍTULO "Delete Co...", 90×21: **1.000** com a
  caixa, **0.391** sem). O **Ok é derivado** do título por `(-76,+172)` a partir
  do CENTRO — medido pelo brilho das colunas: Ok em (439,364), título em
  (515,192). O template não pode ser o botão: Ok e Cancel são idênticos.
- **SÓ ABAIXO DA LINHA DE ABAS** "Item | Quest | Arrange | Ext."
  (`REGIOES_DA_BOLSA`, âncora `state_bag_tabs.png`, 240×21, casa **1.000**). O
  que está acima é o EQUIPAMENTO em uso: o jogo não deixaria apagar, mas tentar
  gasta clique, clique no ícone e a espera da caixa que nunca vem — dentro de um
  orçamento de 10 s, esse tempo é lixo que ficou na bolsa.
  - A região é um retângulo RELATIVO ao centro da âncora, `(-130,+12)` a
    `(+125,+186)`, medido no print: abas centradas em (665,466), grade de
    (542,483) a (780,648). A folga de ~5 px existe porque `matchTemplate` exige
    o modelo INTEIRO dentro do recorte — ícone encostado na borda não casaria.
  - **Ganho que não era o objetivo:** casar dentro da região em vez da janela
    inteira é **31,6 ms → 2,86 ms por modelo (11×)**. Os 81 modelos caíram de
    **2,6 s para 0,23 s**, e praticamente todo o teto de 10 s passou a ser
    gasto apagando.
  - **Sem achar a linha de abas, não apaga nada** — desfecho seguro.
  - **AS BOLSAS EXTRAS entram pela ETIQUETA, não pelo título.** Uma "Expand
    Bag" pode estar `Permanent`, `Limited Time`, `Expired` ou `Unactivated`, e
    só as duas primeiras são acessíveis. A `Expired` **continua mostrando os
    itens** (medido: no print do usuário ela aparece cheia e com a tarja
    vermelha), então sem olhar a etiqueta o bot gastaria clique e espera numa
    bag onde nada acontece.
  - **Procurar só as etiquetas BOAS, e não reconhecer a ruim**, faz o padrão ser
    PRESERVAR: `Unactivated` — ou qualquer etiqueta que o jogo invente amanhã —
    não casa com nada e a bag fica de fora sozinha. Reconhecer `Expired` para
    excluir teria a falha oposta: o que não estivesse na lista de exclusão seria
    varrido.
  - Templates `state_bag_permanent.png` (74×19) e `state_bag_limited.png`
    (94×20). **Cada um tem o seu retângulo**: a etiqueta fica no alto à DIREITA
    e é a borda direita dela que se alinha ao painel, então larguras diferentes
    (74 e 94) dão deslocamentos diferentes a partir do centro — os números não
    podem ser compartilhados.
  - **`find_all_templates` e não `find_template`** para achar as etiquetas: a
    MESMA etiqueta aparece em mais de uma bag ao mesmo tempo (medido:
    `Permanent` nas duas Expand Bags). Com o "melhor casamento" só uma seria
    varrida — foi um defeito real, corrigido e travado por teste.
  - **VALIDADO EM OUTRA RESOLUÇÃO:** o print `bag_unactivated.jpeg` é
    **1439×1073** (os outros são 1022×79x) e as mesmas âncoras acham as mesmas
    coisas. É a confirmação prática da descoberta que abre o `core/coords.py`:
    a UI do jogo não escala.
- **UMA FOTO para todos os alvos**, e isso só é seguro porque o usuário
  confirmou que **a bolsa NUNCA reorganiza os slots sozinha** (por isso existe
  o botão "Arrange", separado). Se ela compactasse, as coordenadas dos alvos
  2..N passariam a apontar para itens diferentes depois da primeira exclusão.
- **O ícone também é localizado UMA vez e reusado.** Medido: com a caixa de
  confirmação na tela ele cai para **0.423** — a barra de progresso passa por
  cima. Procurá-lo de novo a cada exclusão falharia por isso.
- **O ícone É o sinal de "inventário aberto".** `bag_open()` falhou em 5 de 5
  runs medidas; o ícone só existe com a bolsa na tela.
- **TODOS os modelos da pasta entram — não existe peneira por tamanho.** Havia
  um `LADO_MINIMO_DO_TEMPLATE = 24`, e ele foi REMOVIDO por decisão do usuário,
  com medição que derrubou o argumento original:
  - dos 125 rejeitados, **93 eram o ÚNICO modelo daquele item** — a peneira não
    tirava redundância, tirava COBERTURA;
  - vários rejeitados são ícone inteiro recortado justo e não-quadrado
    (`ApoCharm` 30×20, `BambShoot` 20×29, `BariteOre` 26×17). O corte pelo LADO
    MENOR derrubava esses junto com os pedaços de verdade.
  - **E o medo de "modelo pequeno casa com tudo" não se confirmou.** Medido
    contra a bolsa real: `dip` (17×17) casou 8 vezes, mas os 8 são **8 cópias
    do MESMO item**; `Sin48` casou 5 vezes, também 5 cópias da mesma armadura.
    Contar casamentos não diz nada sozinho — é preciso OLHAR o que casou.
- **A pasta é RELIDA a cada chamada** (`modelos_na_pasta`), para acrescentar um
  PNG passar a valer sem reiniciar o bot. Custa um `glob` (~1 ms); as imagens
  continuam em cache no `TemplateLibrary`. A versão anterior guardava a lista
  para sempre porque precisava abrir cada arquivo para medir o lado — sem a
  peneira, não há o que medir.
- **A pasta é a LISTA BRANCA, e é a única.** `data/templates/deletar/` (206
  PNGs hoje, sem subpasta). O que não tem modelo ali nunca é apagado: pôr um
  PNG é autorizar, tirar é revogar.
- **MEDIDO contra a bolsa real do usuário** (print de referência): os 206
  modelos varrem a região em **0,47 s** e casariam **21 itens** — `dip` (8),
  `Sin48` (5), `Fada48` (3), `Monk48` (2), `bag5`, `Tamer48`, `wizz48` (1 cada).
  O número é da bolsa daquele print, não uma constante; serve para mostrar que
  a conferência tem o que mostrar.
- **Teto de 10 s, conferido ENTRE exclusões — nunca no meio de uma.** A
  exclusão que COMEÇA aos 9 s termina (aos 12): cortar no meio deixaria a caixa
  de confirmação aberta e a macro mandaria tecla por cima dela. Medido: 81
  modelos × 31,7 ms = **2,6 s** só de varredura, mais ~0,6 s por exclusão.
- **A fila RETOMA de onde parou** (`ordem_da_fila`): o que não foi verificado
  vem primeiro na chamada seguinte. Sem isso os últimos modelos da lista nunca
  seriam olhados, porque o teto cai sempre antes de chegar neles.
- **O mesmo slot não é clicado duas vezes** (`DISTANCIA_QUE_E_O_MESMO_ITEM`):
  dois modelos parecidos casam no mesmo item, e o segundo clique apagaria o que
  entrou no lugar do primeiro.
- **Sem a caixa na tela, o Ok NÃO é clicado** — mesma lição do
  `_abrir_dialogo_e_clicar` do BC: o clique cairia dentro do inventário.
- **CAMPO NOVO NO `AppConfig` PRECISA ENTRAR NO `_app_from_dict`.** O dataclass
  sozinho NÃO basta: a gravação usa `asdict` e leva tudo, mas a leitura
  reconstrói o objeto campo a campo. O `apagar_lixo_a_cada` foi gravado certo e
  ignorado na leitura, e voltava ao default de 10 toda vez que o bot abria — o
  usuário configurava e a configuração sumia. Travado por
  `tests/test_config_ida_e_volta.py`, que faz a viagem completa (gravar → reler)
  e tem um teste que **reprova quando alguém acrescenta um campo ao `AppConfig`
  sem cobri-lo**. Gravar sozinho funcionava e ler sozinho funcionava; só a ida
  e volta mostrava a perda.
- **Gatilho:** `AppConfig.apagar_lixo_a_cada` (padrão **10**, `0` = nunca),
  editável na aba APP das duas interfaces. Configurável porque o tempo de uma
  volta depende da macro que o usuário montou. O executor recebe a limpeza como
  **função injetada** pelo supervisor — ele importa só `core.inputs` e continua
  sem saber o que é `BotContext`. Complemento: falha vira aviso, a macro nunca
  para.
- **A tecla do inventário é a da aba TECLAS** (`KeyBinds.inventory`), a mesma do
  `package_courage` no BC. Sem ela configurada, a limpeza fica desligada com
  aviso.
- **A TECLA DO INVENTÁRIO É UM INTERRUPTOR, e por isso o estado é LIDO antes**
  (`deletador.limpar_a_bolsa`): já aberto ⇒ não aperta nada e não fecha no fim;
  fechado ⇒ abre, apaga e devolve ao fechado. Apertar às cegas numa bolsa já
  aberta a FECHA — aí não há o que apagar e, pior, o "fechar" do fim a REABRE e
  a deixa aberta engolindo as teclas da macro pelas horas seguintes, sem nada
  no log dizendo por quê.
  - **Quem sabe se está aberta é o ÍCONE DE DELETAR** na tela
    (`inventario_esta_aberto`) — `bag_open()` falhou em 5 de 5 runs medidas.
  - **`None` (sem captura) NÃO é "está aberto"**: sem leitura, abre e devolve ao
    fechado, que é o comportamento que existia antes de haver conferência.
  - **O fechamento é CONFERIDO** e insiste até `TENTATIVAS_DE_FECHAR_A_BOLSA`.
    Conferir custa uma captura; não conferir custa a noite da macro.
  - **Abrir/apagar/fechar mora no DELETADOR**, não no supervisor: é lá que está
    o sinal de "a bolsa está aberta". O supervisor só monta o `BotContext`.
  - A **aferição** (`afericao.py`) segue a mesma regra, pelo mesmo motivo: com a
    bolsa já aberta, apertar a tecla a fecharia e não haveria o que fotografar.
- **AFERIÇÃO ANTES DE CONFIAR** (`bot/app/afericao.py`, botão "Conferir Modelos
  de Exclusão" no Diagnóstico das duas interfaces): fotografa a bolsa e DESENHA
  o que seria apagado, com retângulo e nome do modelo — **sem clicar em item
  nenhum**. Existe porque os 81 modelos vieram do ver.6139 de OUTRO bot e nunca
  foram medidos contra o nosso cliente, e deletar não tem desfazer. Ver *onde*
  casou importa mais que *quanto*: falso positivo aparece como retângulo em
  cima do item errado.

- **TEMPORÁRIO/FUTURO — `blazesbot/bot/deletador.py` existe e está DESLIGADO.**
  Apaga lixo da bolsa por imagem; escrito para uso futuro no módulo APP, onde não
  há vendedor. **Três travas:** `ATIVADO = False`, ninguém o importa (é folha), e
  a pasta `data/templates/lixo/` não existe. Deletar é irreversível, então ele tem
  mais travas que o `package_courage`: casamento em COR, lista branca por pasta,
  slots protegidos, confirmação por mudança do slot e teto de exclusões.
- **O deletador de itens continua DESLIGADO, mas já tem biblioteca.** Os
  templates vieram do T-R0XX (`Images/DELETE`, 209 .bmp) para
  `data/templates/deletar/`, convertidos para .png e separados em três pastas —
  ver o `LEIA-ME.md` de lá. `deletador.PASTA_DO_LIXO` aponta para
  `deletar/conferir` (81 ícones inteiros, 24-30 px); `deletar/fragmentos` (126
  recortes de 13-23 px) fica FORA do fluxo, barrado por
  `LADO_MINIMO_DO_TEMPLATE = 24`, porque pedaço de ícone casa com muito mais
  coisa e aqui falso positivo é perda irreversível; `deletar/conflito` isola
  `SmallRuby` e `BlueID`, que estão nas DUAS listas do T-R0XX (apagar E vender,
  arquivos idênticos).
  **Nenhum template foi validado contra o nosso cliente** — foram recortados do
  ver.6139. Medido sem o jogo: os 81 não se confundem entre si em cor a 0,92 e
  nenhum casa com os 16 itens da pasta `SELL` deles. Antes de ligar `ATIVADO`,
  medir contra uma captura da NOSSA bolsa, como foi feito com o
  `package_courage`.


## A bolsa que nunca abria — 268 falhas seguidas, 07/09/2026

No log de 06/09, em duas contas, por horas:

```
Volta 1885: hora de limpar a bolsa (a cada 5 voltas) [...]
Não achei o ícone de deletar na tela — o inventário não está aberto. Pulando.
   ... 268 vezes, com ZERO itens apagados.
```

### O mecanismo

`limpar_a_bolsa` lia a tela, via "fechada", apertava a tecla e esperava **0,58 s
CEGOS**. Quando a tela demorava mais que isso para pintar — e com várias contas
na mesma máquina ela demora —, `deletar_lixo` não achava o ícone, concluía "não
está aberta" e desistia.

E aí vinha o pior: o `finally` apertava a tecla **incondicionalmente**, para
"fechar o que abriu". A tecla é interruptor. Então cada tentativa era um par
abre/fecha em cima de uma bolsa que talvez tivesse acabado de abrir — os toques
se anulando, por horas.

O council resumiu: *"polling ajuda; o `finally` é o problema"*.

### As duas correções

1. **O abrir PERGUNTA** (`_esperar_a_bolsa_abrir`, passo 0,15 s, teto 2 s),
   saindo no instante em que o ícone aparece. O que era 0,58 s fixo virou ~0,15 s
   típico, e a bolsa que abre atrasada passou a ser limpa em vez de descartada.
2. **O fechar só fecha o que a tela diz estar aberto.** `eu_abri` diz o que se
   tentou; a tela diz o que É. Entre os dois, manda a tela. E se o ícone nunca
   apareceu, **não se aperta de novo**: o que se sabe é que a bolsa não está
   aberta, e o que não está aberto não precisa ser fechado.

`ESPERA_DA_BOLSA_ABRIR` (0,58 s) continua existindo para o **fechar**, que
aperta e depois confere — lá a espera cega é seguida de verificação, que é o
arranjo que o projeto aceita.

### De quebra: o dublê de log dos testes engolia tudo

`_Log.__getattr__` devolvia `lambda: None`, então nenhum teste conseguia cobrar
um aviso. Era exatamente o que faltava aqui: o log era a única coisa capaz de
mostrar o defeito, e nenhum teste podia exigi-lo. Agora ele guarda o que foi
dito.


### Revisão do Codex: intenção não fecha bolsa, observação fecha

A primeira versão deste conserto zerava `eu_abri` ao estourar o teto, "para não
apertar a tecla sem saber o estado". O Codex apontou o que isso jogava fora:
**se a bolsa abrir DEPOIS do teto, ela fica aberta** — e bolsa aberta atrapalha
as voltas seguintes.

`eu_abri` continua `True` porque é verdade: a tecla saiu. Quem decide se aperta
de novo é o `finally`, e ele decide **olhando** — fecha só o que a tela diz estar
aberto. Com isso os dois casos ficam cobertos pelo mesmo mecanismo:

| o que aconteceu | o que o `finally` vê | o que ele faz |
|---|---|---|
| abriu no prazo | aberta | fecha |
| abriu depois do teto | aberta | **fecha** |
| não abriu | fechada | não aperta |

## A quinta linha da bolsa principal, que nunca era varrida — 10/09/2026

### O relato

> *"nessa parte do inventário tem 5 linhas, mas na última e quinta linha, quando
> fica algo nessa parte do inventário em específico o item não é deletado pela
> função de deletar itens de HH. Eu testei com vários itens ali, e não
> reconhece... nos expand bag funciona corretamente"* — usuário, com prints.

### A medição

No print de referência `data/templates/entrada/inventario.jpg`, a âncora
`state_bag_tabs.png` casa em **1.000** com centro em (665,466). Os separadores
da grade caem em:

| dy | +13 | +48 | +83 | +118 | +153 | **+190** |
|---|---|---|---|---|---|---|

Cinco linhas de 35 px, terminando em **+190**. O retângulo da bolsa principal
ia até **+186** — quatro pixels a menos.

E `matchTemplate` **exige o modelo INTEIRO dentro do recorte**: não existe
casamento parcial. Item na 5ª linha simplesmente não era encontrado.

### Por que as Expand Bag funcionavam

A régua delas sempre teve folga: grade até +186, retângulo até +193. É a mesma
folga de ~5 px que o resto da lista usa e que a bolsa principal tinha perdido.

### Por que o defeito parecia "coisa do item"

Reproduzido no print, colando um ícone em cada linha:

| modelo | linhas 1–4 | linha 5 |
|---|---|---|
| 22×22 | acha | acha |
| 27×27 | acha | acha |
| 33×33 | acha | **não acha** |
| 35×35 e 40×40 | acha | **não acha** |

Recorte pequeno e alto na célula cabia nos 186 px; recorte de célula cheia, ou
qualquer um colado mais para baixo (o número da quantidade fica no rodapé do
slot), não cabia. Daí "às vezes não reconhece" em vez de "nunca".

### A correção

`dy1` da bolsa principal: **186 → 195** (os +190 da grade mais os ~5 px de folga
da convenção). Nada mais mudou: a borda de cima continua em +12, logo abaixo da
linha de abas, porque a regra de não tocar no equipamento não mudou.

### A janela do inventário NÃO é fixa na tela

Lembrete do usuário no mesmo dia: *"é bom só tomar cuidado que o usuário pode
mudar onde está o inventário aberto, pois ela não é fixa na tela"*. É por isso
que a região nasce da ÂNCORA a cada chamada (`regioes_visiveis` procura
`state_bag_tabs.png` no quadro e deriva o retângulo dela), e não de coordenada
de tela. Todo número desta seção é RELATIVO ao centro da linha de abas.

A correção mexeu só no deslocamento, então essa propriedade não mudou -- e
agora ela está travada também para a 5ª linha, que é onde a régua era curta.

### Travado por

`tests/test_deletador.py`:

* `test_a_geometria_medida_ainda_e_a_do_print` -- os números medidos envelhecem
  junto com o print de referência, em vez de mentir calados;
* `test_a_regiao_da_principal_alcanca_o_FIM_da_grade` -- a borda de baixo passa
  do fim da grade, nunca fecha nela;
* `test_item_em_QUALQUER_das_cinco_linhas_e_encontrado` -- um ícone em cada uma
  das cinco linhas, em quatro tamanhos de modelo (com o valor antigo, três
  casos reprovam);
* `test_a_ultima_linha_continua_valendo_com_o_INVENTARIO_ARRASTADO` -- o quadro
  inteiro é deslocado em duas direções e a 5ª linha continua sendo encontrada.

## O limiar em cor, REMEDIDO (11/09/2026)

### O pedido que estava no código desde sempre

O comentário de `LIMIAR_EM_COR` dizia, palavra por palavra: *"PRECISA SER
REMEDIDO com os templates de lixo"*. O 0,92 vinha do `package_courage`, onde o
vão medido era item verdadeiro **0,971–0,999** contra distrator **0,583–0,878** —
com distratores chegando a 0,878, 0,92 era o mínimo seguro **para aquele
conjunto**.

### O sintoma que forçou a remedição

> *"eu tinha removido a Trap-Meshwork.png, mas agora adicionei de volta, porém
> não está deletando os itens que são iguais"* — e, depois de um dia inteiro de
> farm: *"ainda não está deletando os Trap Meshwork"*.

Dos 15 modelos da HH, treze apagavam normalmente (o `Purple-Cowry` 52 vezes) e o
`Trap-Meshwork` **nunca**.

### A medição

3456 pontuações de não-casamento colhidas do log de produção pelo relatório
`_quem_nao_casou`, cobrindo as duas pastas (208 modelos globais + 15 da HH). A
distribuição é **bimodal**, com um vão vazio no meio:

| faixa | ocorrências | quem |
|---|---|---|
| 0,90–0,91 | 48 | **só o `Trap-Meshwork`**, em todas as passadas |
| **0,71–0,89** | **0** | **o vão** |
| 0,50–0,70 | 3408 | todo o resto |

Os maiores distratores, por modelo:

| modelo | melhor não-casamento |
|---|---|
| `Biddha-Bone` | 0,70 |
| `RottedSeed`, `charm` | 0,68 |
| `greenid` | 0,67 |
| `Silver_Ore` | 0,65 |

**O distrator mais forte de todo o conjunto de lixo marca 0,70** — muito abaixo
dos 0,878 do `package_courage` que justificavam o 0,92. E o `Trap-Meshwork`
marcava **0,90 de forma absolutamente estável** (idêntico em 48 relatórios ao
longo de horas), o que diz que a diferença entre o PNG e o que o cliente desenha
é **fixa e pequena** — não é ruído de renderização, que variaria.

### A decisão: 0.85

Fica **dentro do vão vazio**: 0,15 acima do maior distrator medido e 0,05 abaixo
do casamento verdadeiro que estava falhando. **Nenhuma das 3456 amostras cai
nessa margem** — baixar de 0,92 para 0,85 não faz nenhum item novo passar, além
dos `Trap-Meshwork` que deveriam passar desde o começo.

### O que NÃO muda

**Apagar continua irreversível**, e a proteção continua sendo a mesma:
`conferir()` — o botão "Conferir Modelos de Exclusão" — desenha o que **seria**
apagado, sem apagar. Rodar antes de ligar a limpeza continua sendo a única
proteção que não depende de palpite.

### A alternativa que NÃO foi escolhida, e por quê

Refazer o recorte do `Trap-Meshwork` (incluindo o contorno do ícone e o fundo
escuro do slot, como estão o `Purple-Cowry` e o `Dragon-Roc`) levaria aquele
modelo de 0,90 para ~0,98 e não mexeria em nada global.

Mas isso conserta **um** modelo. A medição mostra que o problema é do **limiar**:
ele foi calibrado para outro conjunto de imagens, e o próximo recorte novo que o
usuário fizer bate na mesma parede. Consertar o número que estava errado é o que
resolve a classe.

**As duas coisas convivem:** um recorte melhor continua sendo melhor, e o
`Warm-Jade` — que marca 0,54, muito abaixo do vão — é candidato a isso. Naquele,
o recorte pegou só o miolo liso da esfera, sem contorno e sem fundo: nitidez
1 067 contra a média de 14 937 dos que funcionam. Gradiente suave não dá o que
correlacionar. Mas 0,54 também é compatível com "o item não estava na tela", e
isso ainda não foi separado.


## Sete horas sem apagar nada: o processo era mais velho que os arquivos — 17/09/2026

### O sintoma

*"O deletador de itens no APP parou de funcionar."* E, na sequência: *"tem vezes
que o inventário está sendo fechado, mesmo quando o usuário deixou aberto."*

### O que o log dizia

```
21:05:34   as subpastas de categoria são criadas (data/templates/botao/, estado/, ...)
21:06:14   [blazestpas] Sem o template btn_delete_item.png; não sei onde clicar para deletar.
...        12.804 vezes, sem parar, por sete horas
03:52:32   [blazestpas] A bolsa não apareceu em 2.0s depois da tecla 'I'.
```

Quarenta segundos entre mover os arquivos e o primeiro erro.

### A causa

O commit `45f2d4d` (16/09, 21:17) organizou os templates em subpastas por
função, e `TemplateLibrary.caminho_de` passou a procurar na raiz **e** nas
categorias. O código ficou certo. O que não ficou foi o processo:

| quando | o quê |
|---|---|
| 16/09 15:24 | o bot subiu — `templates.py` carregado em memória, versão que só olha a RAIZ |
| 16/09 21:05 | os PNG saíram da raiz para `botao/`, `estado/`, `janela/`, … |
| 16/09 21:06 | o bot perdeu TODO template de categoria |

Python lê o módulo uma vez, no import. Editar o arquivo depois não alcança um
processo que já está rodando — e a migração de dados alcançou. **Nenhum
reinício, nenhuma exceção, nenhum sinal** além da linha que o deletador, sozinho
entre os chamadores, tem o cuidado de registrar.

### Os dois sintomas eram o mesmo defeito

O ícone de deletar é o SINAL de que a bolsa está aberta (`inventario_esta_aberto`
— a leitura de UI por memória falhou em 5 de 5 runs). E ele respondia assim:

```python
return _achar_icone(ctx, quadro) is not None      # None do template == "fechada"
```

Sem o PNG, `_achar_icone` devolve `None`, e isso virava **"a bolsa está
fechada"**, com toda a confiança. O resto se segue sozinho: o bot aperta 'I' no
inventário que o usuário tinha deixado ABERTO e o fecha; espera dois segundos
pelo ícone que não existe; desiste; e não devolve nada, porque o fechamento do
fim também decide olhando. A queixa do inventário não era um segundo defeito —
era o mesmo, visto de outro ângulo.

### O que mudou

1. **A pasta é resolvida contra a raiz do projeto, não contra o CWD.** Todo
   chamador constrói a biblioteca com `Path("data") / "templates"`, e um atalho
   lançado de outro diretório faria TODOS os templates sumirem de uma vez.
2. **Template que falta AVISA — uma vez por nome, na biblioteca.** Era o
   deletador, sozinho, quem registrava o `None`; agora quem registra é quem
   carrega, e vale para vendedor, login, entrada da cave e o resto.
3. **Sem o modelo, `inventario_esta_aberto` devolve `None`** — não "fechada".
4. **Cego, a limpeza não encosta na tecla.** A regra antiga era "sem leitura,
   faz o que se fazia antes de haver conferência"; ela custou o inventário
   aberto do usuário. Sem tela não há o que apagar de qualquer forma.

### O que isto NÃO conserta

O processo que já está rodando. Um bot no ar desde antes de uma alteração roda o
código de antes dela — vale para esta e para qualquer outra. A cada mudança de
código **ou de arquivo de dados**, o que passa a valer só vale no próximo
arranque.
