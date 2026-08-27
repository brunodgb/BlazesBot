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
