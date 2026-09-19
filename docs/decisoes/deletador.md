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

## A aferição saiu do deletador — 18/09/2026

`conferir()` mudou de casa: de `bot/deletador.py` para **`bot/afericao_do_lixo.py`**,
linha por linha, sem uma alteração de comportamento. O motivo é a catraca de
tamanho — o `deletador.py` bateu em **799 linhas de um teto de 800**, e a regra
do projeto é que a próxima linha paga a extração.

O corte é o natural, e não um pedaço arrancado para caber: **o deletador apaga;
a aferição só desenha.** Ela não clica em item, não manda tecla e não muda
estado nenhum.

Ela ficou em `bot/` e não em `bot/app/` porque a pergunta que responde — *o que
seria apagado se eu ligasse isso agora?* — vale para qualquer ecossistema que
apague lixo, e `bot/hh/` não pode importar de `bot/app/`.

**Dependência cruzada, escrita no cabeçalho do módulo novo:** ela usa as peças
internas do deletador (`_carregar`, `regioes_visiveis`, `_casamentos_nas_regioes`,
`_achar_icone`) de propósito — a conferência tem de enxergar EXATAMENTE o que a
exclusão enxerga. Duas leituras diferentes fariam a aferição mentir, e não
confiar nos modelos sem olhar é o motivo de ela existir.

## Cada conta escolhe o que NÃO apaga — 18/09/2026

### O pedido

*"Quero que dentro da aba APP na edição tenha uma opção que abra uma nova
janela para o usuário escolher de forma simples quais itens ele pode deletar."*
E, sobre o estado: *"o bot vai ignorar aquele png em específico para aquela
conta em questão, pois daí ele quer que mantenha aquele item, sem deletar."*

### A escolha é POR CONTA, e a pasta não muda

A pasta é uma só para o bot inteiro, então a escolha por conta não cabe nela —
ela vive na configuração da conta. A pasta continua sendo a lista de quem
**pode** ser apagado; a conta guarda as **exceções**.

### Exceção, e não a lista inteira

`AppConfig.desativados` / `HHConfig.desativados` guardam os nomes que a conta
**não** apaga. A alternativa — guardar os ATIVOS — foi recusada por duas
medições:

* **O invariante "PNG autoriza" morreria.** Um modelo novo na pasta nasceria
  inerte até alguém ligá-lo em cada conta, uma por uma. Hoje ele passa a valer
  sozinho, e é assim que a pasta funciona desde que o deletador existe.
* **O `config.json` engordaria 208 nomes por conta.** Com a exceção, quem nunca
  abriu a janela guarda `[]`.

### A leitura é AGORA, e isso é o recurso

`deletador.modelos_ativos(ctx, pasta)` lê `ctx.settings` **no momento da
limpeza**. A interface e a thread da conta compartilham o mesmo objeto de
configuração (`salvar_personagem` muta `AccountSettings` vivo; `config.save()` é
só o backup em disco), então salvar na janela vale na **limpeza seguinte**, sem
religar o bot.

O erro que isso evita tem nome no próprio código: `travar_posicao` e
`shuffle_apos_n_voltas` são lidos uma vez na montagem do executor e só valem ao
religar. O contrário — `voltas_por_limpeza`, `fonte_dos_passos`,
`espera_depois_do_tab_ms` — é passado como função, com o comentário explicando
por quê. Este campo segue o segundo grupo.

### Quem apaga e quem confere carregam pela MESMA porta

O filtro entra em `_carregar`, que serve tanto `deletar_lixo` quanto a aferição
(`bot/afericao_do_lixo.conferir`). Se a conferência carregasse por outro
caminho, ela desenharia um retângulo vermelho sobre um item que aquela conta
não apaga — e o usuário preservaria o item errado por causa do desenho.

### O preço de renomear um PNG

Tanto a lista da conta quanto o dicionário de rótulos são chaveados pelo **nome
do arquivo**. Renomear um PNG faz a conta esquecer que aquele item era
preservado, e ele volta a ser apagado — em silêncio. Chavear por conteúdo
resolveria e é complexidade que não se paga numa pasta que só o desenvolvedor
mexe. Fica escrito aqui e no `LEIA-ME.md` da pasta: **renomeou, reveja os
preservados.**

### Travado por

`tests/test_lixo_desativado.py` — a pasta escolhe o campo, a leitura é agora
(e não na montagem), nome órfão não atrapalha, lista suja não derruba a macro,
e `_carregar` respeita a lista. Mais `test_config_ida_e_volta.py` (o campo
sobrevive ao disco) e `test_app_config_campo_por_campo.py` (a ponte leva nos
dois sentidos).

## A janela de seleção: 208 miniaturas — 18/09/2026

### Só na web, e por decisão escrita

A PyQt6 está descontinuada (decisão do usuário) e isto não é um campo — é uma
janela com 208 miniaturas, busca, filtro e ação em massa. A GUI antiga não tem
**um único `QPixmap`** nem um único diálogo aberto de dentro do editor. O campo
entrou em `CAMPOS_SO_DA_WEB`, com o porquê em `docs/decisoes/interface.md`.

### Duas janelas irmãs, não uma com abas

APP abre da aba APP, HH abre da aba HH. Mesma estrutura, muda a pasta e o
campo. *"Acho que é melhor 2 janelas para o usuário não se confundir."*

### O desenho decide, então o desenho é o cartão

`AlmOre`, `bag3` e `Amuleto39` não dizem nada. O ícone vai ampliado com
`image-rendering: pixelated` — suavizar 20 px vira borrão, e borrão não se
reconhece. O rótulo em cima, o nome do arquivo embaixo em cinza (é por ele que
o dicionário de nomes é editado).

O cartão INTEIRO é o alvo do clique: caixinha de 12 px em grade de 208 itens é
erro de pontaria garantido. E o estado se lê de longe — cinza, borda tracejada,
nome riscado e o selo MANTÉM —, porque cor sozinha não informa quem não
distingue verde de vermelho.

### O escopo da ação em massa vai escrito no botão

"Manter os visíveis (14)". Um botão que diz "todos" e mexe em 208 com um filtro
ligado é armadilha: a pessoa vê catorze na tela.

### Nada fecha a janela além de Salvar e Cancelar

Sem Esc, sem X e sem clique no fundo — os três fecham sem querer, e depois de
marcar trinta itens isso custa os trinta. Cancelar com alteração pendente
pergunta antes. Pedido do usuário, com o motivo dele: *"se ele apertar sem
querer e fechar, depois de ter editado várias imagens, o usuário vai ficar bem
frustrado"*.

### A miniatura viaja embutida, e isso é medido

A página roda em `file://` e o WebView2 recusa `<img src>` para arquivo local.
As 208 do APP dão **349 KB e 15,6 ms** para ler e codificar tudo — então a
grade vai num payload só, sem cache, sem carga sob demanda e sem paginação.

**WebP foi recusado**, e não pelo tamanho: a miniatura é a PROVA do que o bot
vai apagar. Reencodar faria o usuário decidir olhando um arquivo e o bot decidir
comparando outro — e num ícone de 20 px qualquer diferença de encodagem é a
diferença entre reconhecer e não reconhecer.

### Exportar/importar: o arquivo diz de qual lista ele é

Sem isso, importar um arquivo do APP na janela da HH passaria despercebido: os
nomes não casariam com nada e a pessoa ficaria com a seleção vazia achando que
importou. Importar SUBSTITUI e diz o que muda antes; e não grava nada — devolve
a lista, quem aplica é a janela, e por isso o Cancelar ainda desfaz.

### Conferido no navegador

Não só em teste: 208 cartões desenhados, contador "208 itens · 3 mantidos",
filtro Inativos deixando 3, busca "bag" deixando 5 com o botão de massa
acompanhando o número, e o Cancelar com alteração pendente abrindo a pergunta.
A receita do harness: Chrome com CDP pelo `test-web.ps1`, o dev server do Vite
(no `file://` o erro de módulo vem opaco), e o stub da ponte injetado por
`<script>` depois do load, seguido de um `pywebviewready` disparado à mão.

## Como cada modelo se chama, e a ordem da grade — 19/09/2026

### A convenção dos nomes

Os modelos de equipamento seguem um esquema que o usuário leu na tela, item por
item, e que agora está executável em `tools/sincronizar_nomes_do_lixo.py`:

| no arquivo | vira | regra |
|---|---|---|
| `SpinelOre` | Spinel Ore | separador **e maiúscula no meio** viram espaço |
| `Sin13` | Armguard Sin lvl13 | o **dígito final** diz a peça; a classe está no nome |
| `Wizz68` | Robe Wizz lvl68 | 2 Cuff · 3 Armguard · 4 Kneedpad · 5 Boots · 6 Belt · 8 Robe |
| `Cuff12` | Cuff lvl12 | a peça já está escrita e a classe **não aparece** |
| `Amuleto39` | Amuleto lvl39 | fora do esquema: só normalização e nível |

**O corte do camelCase reverteu uma decisão de 18/09.** Ela se recusava a
separar "para não estragar `BAG7` e `bag3`", e o medo era infundado: o corte
acontece só entre MINÚSCULA e MAIÚSCULA, fronteira que não existe nesses dois.

**Classe não se inventa.** `Cuff12`, `Belt16`, `Knee4` e `Ring27` ficam sem
classe porque o arquivo não diz qual é. Rótulo errado num item que o usuário
decide apagar OLHANDO é pior que rótulo genérico.

**Dez rótulos deixaram de ser chute em 19/09/2026** — vieram do site oficial,
que enumera os materiais de Magicstone com o nome exato: `Bjewel` é *Bandit
Jewel*, `CrackBB` é *Cracked Buddha Bone*, e `DarkBed` era *Dark Bead* (o
arquivo é que tem erro de digitação). O que foi conferido, o que continua sem
nome e onde procurar o resto: **`docs/referencia-do-site-oficial.md`**.

**O dígito da frente é o TIER, não a classe** — medido no próprio dado: a
maioria dos arquivos já traz a classe (`Sin`, `Wizz`, `Monk`, `Tamer`,
`Fairy`), e o dígito varia de 1 a 6 para a MESMA classe (`Sin3`, `Sin13`,
`Sin23`, ... `Sin63`).

### A ordem da grade é a do RÓTULO, com nível lido como número

Ela vinha do nome do ARQUIVO, e por isso `Belt6.png` caía depois de
`belt56.png`: o usuário via "lvl16, lvl26, lvl36, lvl46, lvl56, lvl6" e
precisava caçar o menor no fim da fila.

Ordenar pelo rótulo com chave natural (`web_lixo.ordem_da_tela`) resolve as duas
coisas de uma vez: itens iguais ficam colados — o prefixo "Armguard Fairy lvl" é
idêntico entre eles — e a família inteira aparece em sequência de nível.

### Renomeou um PNG? Rode a sincronia

    python -m blazesbot.tools.sincronizar_nomes_do_lixo

Ela acrescenta chave nova com o rótulo padrão, remove a órfã e **não toca em
rótulo já escrito à mão**. Não há teste exigindo sincronia: ele reprovaria na
máquina de quem tem outros PNG, e `data/` não é versionado — a sincronia é uma
AÇÃO, não uma trava.

### JPG na pasta é um arquivo que o bot nunca enxerga

`modelos_na_pasta` varre `*.png`. Um JPG ali dentro **não dá erro, não entra na
janela e não apaga item nenhum** — some calado, do mesmo feitio da falha que
custou sete horas em 16/09/2026.

Por isso a sincronia converte antes de listar: o JPEG já perdeu o que tinha de
perder quando foi salvo, e o PNG guarda exatamente os pixels que o
`matchTemplate` vai comparar. **Ela nunca sobrescreve** — PNG de mesmo nome já
existente faz a conversão ser recusada e contada, porque apagar template é
irreversível e `data/` não é versionado.

### O nome da classe vai em inglês

`Fada` e `Fairy` eram a mesma classe em dois idiomas, e a família saía partida
na grade. Unificadas em **Fairy** — o nome da classe em inglês, como as outras
quatro —, e os arquivos foram renomeados junto (`Fada23.png` → `Fairy23.png`).

`Sin`, `Wizz`, `Monk` e `Tamer` ficam: já estão em inglês, são a abreviação que
a comunidade usa, e foi assim que o usuário nomeou os arquivos. Expandir para
"Assassin"/"Wizard" é trocar duas linhas em `CLASSES` e rodar a sincronia.

**A grafia antiga continua sendo entendida** (`"fada": "Fairy"` no mapa): uma
pasta vinda de outra máquina, ou um PNG antigo que reapareça, não pode virar
item sem rótulo por causa disso.

## A inversão: a conta escolhe o que apaga — 19/09/2026

### O pedido, e o número que o sustenta

*"Hoje todos os itens entram direto para ser deletado, mas vamos inverter [...]
em vez de o bot procurar por mais de 200 ícones, o usuário seleciona 10/20 que
de fato vão ser deletados naquela rota, pois cada mob dropa itens diferentes."*

Medido antes de mexer, com os modelos reais contra uma região do tamanho da que
a bolsa ocupa:

| modelos comparados | tempo por limpeza |
|---|---|
| 213 (a pasta inteira) | **1,68 s** |
| 40 | 301 ms |
| 20 | **147 ms** |
| 10 | 72 ms |

Onze vezes menos com vinte escolhidos — e o teto de 10 s por limpeza deixa de
ser um risco.

### O que mudou de semântica

`AppConfig.desativados` (as exceções) deu lugar a `AppConfig.apagaveis` (a
escolha). **Vazio = não apaga nada**, e esse é o padrão.

**Campo NOVO, e não o mesmo com sentido trocado.** Um `config.json` lido por
uma versão anterior apagaria exatamente os itens que o usuário quis preservar;
e um nome que diz o contrário do que o campo faz é a armadilha exata para um
sistema que apaga sem desfazer. As contas existentes começam vazias — o campo
velho deixa de ser lido e some do arquivo no primeiro salvamento.

### O atalho: não se abre a bolsa para não fazer nada

Com a escolha vazia, `limpar_a_bolsa` devolve na primeira linha: **sem tecla e
sem captura**. Não é economia de milissegundos — a tecla do inventário é
interruptor, e apertá-la numa bolsa que o usuário deixou aberta a FECHA. Como
seleção vazia passou a ser o estado normal de conta recém-configurada, esse
caminho tinha de ser barato e silencioso.

E a mensagem de "nenhum template" deixou de mentir: pasta vazia (defeito de
instalação) e conta sem escolha (o normal) são causas diferentes, e confundi-las
esconde a que importa.

### O portão do Iniciar

Seleção vazia virou o estado NORMAL de conta recém-criada, e o risco disso é
silencioso: a conta farma a noite inteira, a bolsa enche, e o usuário só
descobre quando o inventário transborda — a falha que o deletador existe para
evitar.

Por isso a conferência acontece no **Iniciar**, com confirmação e com os dois
caminhos escritos nos botões: **"Iniciar assim"** e **"Desligar essas e
iniciar"**. Um diálogo que decide se uma conta vai farmar a noite inteira não
pode depender de o usuário lembrar qual era o "Confirmar".

**Quem entra na lista:** conta ativa, função APP ou HH, limpeza ligada, seleção
vazia **e** tecla de pet configurada. As três exclusões têm motivo:

* **limpeza desligada** é decisão do usuário — cobrá-la em todo Iniciar vira OK
  automático, e aí, no dia em que o aviso estiver certo, ele é clicado sem ser
  lido;
* **sem tecla de pet** o personagem não cata item do chão, a bolsa não enche e
  não há o que apagar (regra do jogo que a Fada já usa, em `fada_montagem.py`);
* **BC** não apaga item hoje.

**Desligar é atômico no time.** *"Se o líder for inativado, todos do time são
inativados, e se algum do time for inativado o contrário também deve
acontecer."* O motivo é mecânico: o seguidor só roda a macro enquanto o líder
está com o APP ligado. O diálogo mostra quem cai junto ANTES de a decisão ser
tomada.

As contas desligadas continuam **Ativas** — logam e relogam normalmente. É o que
permite ajustar a seleção com o resto do bot no ar.

**Dois defeitos que o teste pegou no caminho:** `uid` vazio casava com toda
conta sem uid (e, com a regra do time, desligaria a função do bot inteiro de uma
vez); e a mensagem da confirmação colapsava as quebras de linha, transformando a
lista de contas num blocão — `white-space: pre-line`.

## A LISTA DE OUTRO BOT — 19/09/2026

O usuário trouxe a lista de itens de outro bot (313 nomes, sem contagem nem
duplicata) e pediu duas coisas: usá-la para higienizar os rótulos que sobraram
e descobrir o que falta na pasta.

### O que ela resolveu: 31 abreviações

O site oficial tinha resolvido dez nomes, todos da receita do Magicstone. As
abreviações que sobravam não estão em lugar nenhum da internet — eram nome de
arquivo do próprio usuário — e a lista do outro bot bateu com quase todas:

    AlmOre     -> Aluminum Ore         GrosM      -> Grosvenor Mormodica
    AnFur      -> Animal Fur           HoneW      -> Honewort
    BambShoot  -> Bamboo Shoot         HoneyS     -> Honeysuckle
    brtpil     -> Breath Pill          LascToken  -> Lascivious Token
    CIronShot  -> Cursed Iron Shot     MagOre     -> Magnesium Ore
    Cowb       -> Cowbane              MysSkel    -> Mystic Skeleton
    Crista_Bot -> Crystal Bottle       Myth_Wood  -> Myth Sea Wood
    DfrmtJos   -> Deformity Joss       Nimbuz     -> Nimbus Quartz
    dip        -> Dipterocarp          PechOil    -> Peach Oil
    Durmarst   -> Durmast              PhMet      -> Ph Meat
    FrMush     -> Fresh Mushroom       StonOr     -> Stone Orchid
    FTMC       -> Far Temple Map Chip  TigrMet    -> Tiger Meat
    GlosBead   -> Glossy Bead          Gold_T     -> Gold Thread

Mais as correções de grafia e de forma: `FireSneakMeat` era *Snake*, não
"Sneak"; `Black_Evil` é *Black Evil Crystal*; `Secret_silver` é *Secret Silver
Necklace*; os cinco sinos coloridos são uma família (*Blue/Golden/Purple/Red/
Silver Bell*), e `PetFood1` é *Pet Food* — o "1" era a quantidade.

**ONDE AS DUAS FONTES DISCORDAM, O SITE VENCE.** `RottedSeed` fica "Rotted
Seed", que é como a página do Magicstone escreve, e não "Rotten Seed" da lista:
um é a fonte do jogo, o outro é outro bot.

### O que continua sem nome, e não vai sair daí

`SF`, `charm`, `Bife`, `DarkSM`, `Purple_Beast`, `Lion_Meat`, `VultureMeat`,
`Blue_Wolf_Meat`. A lista tem candidatos plausíveis para três deles — *Sacking
Frock* para `SF`, *Return Charm* para `charm`, *Red Bull Steak* para `Bife` --
mas nenhum é certo, e rótulo errado é pior que rótulo cru: quem decide olhando
a miniatura confia no nome que está do lado. Ficam como estão até alguém ver o
item no jogo. Curiosamente `DarkSM` também é "Dark Sm" na lista do outro bot --
os dois herdaram a mesma abreviação de algum lugar.

### O que FALTA na pasta

A lista tem 313 itens; a pasta tem 234 modelos. Descontando o que já existe com
outro nome, sobram **cinco famílias inteiras** que o deletador nunca vai
reconhecer:

| família | o que falta | quantos |
|---|---|---|
| **Armas** | Blade, Bow, Dagger, Pearl, Shovel, Simitar, Staff, Sword, Wheel, Xbow — tiers 20/30/40/50 | ~31 |
| **Talismã assistente numerado** | `<Classe> Assistant` 05/10/20/30, nas cinco classes | 20 |
| **Equipamento 7x/8x** | Amulet 79, Armguard 73 e 81, Armor 78, Belt 76, Boots 75, Cuff 72 e 80, Kneepad 74, Ring 77 | 10 |
| **Peça de classe** | 05 e 25 em Wizard, Monk, Assassin e Tamer; 25 e 28 na Fairy | 10 |
| **Joia grande** | Bright Emerald (e Chip), Bright Ruby (e Chip), Large Emerald, Large Ruby | 6 |

E os soltos: Blueness Stone, Titanium Stone, Teleport Stone, Pith of Energy
Stone, Cold Jade, Cuttle Bone, Lygodium, Polypody, Lizard Meat, Demon Medal,
Devil Token, Return Charm, Soul Bell, Jackstraw, Treasure Box, Grinderstone of
Phoenix, Package of Courage Badge, Sacking Frock, Golden Identify Gem, Occult
Berry, Ganoderma, Red Bull Steak, Fighting Healing Potion, Fighting Mana
Potion, Level 7 Gem Bag.

**Nada disso foi criado aqui**, e não por preguiça: modelo é RECORTE DE TELA
daquele ícone, feito da bolsa do jogo na resolução em que o bot roda. Nome numa
lista não vira PNG. A tabela serve para o usuário decidir o que vale recortar
-- e, depois da inversão de 19/09, um modelo a mais na pasta não custa
desempenho nenhum enquanto ninguém o marcar.

### E ele decidiu, no mesmo dia: três famílias ficam FORA

- **Armas** (Blade, Bow, Dagger, Pearl, Shovel, Simitar, Staff, Sword, Wheel,
  Xbow — tiers 20 a 50): *"não vou adicionar para deletar"*.
- **Talismã assistente numerado**: entram um a um, conforme a necessidade.
- **JOIA GRANDE — e esta é regra, não preferência do dia.** Bright Emerald (e
  Chip), Bright Ruby (e Chip), Large Emerald e Large Ruby **não podem sequer
  aparecer como opção**: *"são itens caros, se remover sem querer pode ser
  prejuízo"*. Sem PNG na pasta não há como marcar por engano — a pasta é a
  lista branca, e o que não está nela nunca é apagado. Small e Medium já
  estavam lá e ficam.

O critério vale além das joias, e é ele que separa a seção 4 da lista de
trabalho (`data/templates/deletar/FALTAM.md`, não versionada porque `data/`
não é): **item com uso ou valor não é lixo óbvio** — Golden Identify Gem ativa
equipamento dourado, Jackstraw revive sem perder exp, as Fighting Potions são
poção de combate, e Package of Courage Badge é moeda de missão. Esses vão para
uma seção "confira antes", não para a lista de recortar.
