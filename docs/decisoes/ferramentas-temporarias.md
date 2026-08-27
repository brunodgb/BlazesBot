# Ferramentas TEMPORÁRIAS de diagnóstico

> Recortado do `CLAUDE.md` em 14/08/2026, **verbatim**. O
> `CLAUDE.md` guarda a REGRA em uma ou duas linhas e aponta para cá; aqui
> fica a MEDIÇÃO que sustenta cada uma. Leia antes de mexer nesta área —
> quase toda decisão aqui já foi tentada do outro jeito e reprovou.

- **TEMPORÁRIO — botão "Testar Venda" (teste isolado da venda).** Vive em
  `blazesbot/bot/teste_venda.py`, um módulo FOLHA (nada do bot importa dele) e
  marcado para ser apagado quando a venda estiver validada. Faz **só dois
  passos**: `VendorService.travel_to_vendor()` e `sell_from_slot()` — e para.
  **NÃO** chama `voltar_para_a_cidade()` (o personagem já está em Stone City;
  usar o item gastaria pedra/recarga do token à toa) nem `buy_supplies()` (só
  repõe pedra gasta, e o teste não gasta). Descobre a janela do jogo reusando
  `AccountSupervisor._adotar_janela_existente()` **sem iniciar a thread** do
  supervisor, e devolve o PID com `_release()` no `finally` de TODA saída —
  sem isso o bot de verdade veria a janela como "de outra conta" e abriria um
  cliente novo (fila de três horas). Exige o bot **parado** (os dois disputariam
  teclado e mouse do mesmo cliente) e o personagem já dentro do jogo. Nas duas
  interfaces o **próprio botão vira o cancelar** enquanto a venda roda: o botão
  Parar da barra fica desabilitado com o bot parado, então não haveria outra
  saída. Blocos marcados `TEMPORÁRIO` em `web_app.py` (`_App.testar_venda`,
  `cancelar_teste_venda` + os dois métodos da `Api`), em
  `gui/main_window.py` (grupo "Teste isolado da venda" na aba Diagnóstico,
  `_testar_venda`, `_fim_do_teste_de_venda`, sinal `teste_venda_pronto`) e no
  `web/index.html` + `web/main.js` (`#btn-testar-venda`).
- **TEMPORÁRIO — botão "Amostrar Cliques" (amostragem de coordenadas de clique
  DIREITO).** Vive em `blazesbot/bot/amostragem_de_cliques.py`, módulo FOLHA
  (nada do bot importa dele), mesmo molde do `teste_venda`: adota a janela com
  `AccountSupervisor._adotar_janela_existente()` **sem iniciar a thread**,
  `supervisor._release()` no `finally` de TODA saída, exige o bot **parado** e o
  próprio botão vira o cancelar. Responde a UMA pergunta por medição: *quando o
  clique direito não abre o diálogo, a coordenada está fora do NPC?*
  - **Varre um grid** em volta do alvo que o bot usa hoje — `RAIO_DO_GRID = 12`,
    `PASSO_DO_GRID = 6` ⇒ 5 valores por eixo, 25 coordenadas —, com
    `AMOSTRAS_POR_COORDENADA = 3` (75 cliques). O `(0,0)` está sempre no grid:
    sem ele não haveria contra o que comparar o vencedor, e o relatório diz em
    que posição do ranking o alvo de hoje ficou.
  - **Quatro pontos, e o Altar Stone fica de FORA** (decisão do usuário: é o
    único cercado de mobs, e clique que erra faz o personagem andar). Entram o
    **vendedor** (`coords.vendor_npc`), a **Transport Fay** e a **entrada da
    cave** (as duas por `ui._ponto_padrao_do_npc()`, a entrada com
    `alturaDif=-48`, porque é o que `falar_com_npc` usa de verdade) e a **saída
    da cave** (`coords.cave_exit_npc`). O ponto é **reconhecido pela posição**
    (`_ponto_da_posicao`, raio 45) em vez de escolhido num seletor: os quatro
    estão a centenas de unidades uns dos outros, e um seletor a mais seria uma
    chance a mais de amostrar o ponto errado.
  - **Reancora ANTES DE CADA AMOSTRA, e isso é o coração da ferramenta.** Clique
    que erra o NPC cai no chão e MOVE o personagem — numa varredura a maioria
    das coordenadas erra de propósito, então o passeio é o regime normal, não
    acidente. Sem reancorar, as últimas coordenadas seriam medidas de um lugar
    diferente das primeiras e o ranking seria ruído com cara de dado. Andou ⇒
    `resetar_visao(forcar=True)` também (a câmera é parte da coordenada).
  - **O teto da medição é FIXO e largo** (`TETO_DA_AMOSTRA = 1.5`), ao contrário
    do teto adaptativo da produção. São objetivos opostos: lá se quer não gastar
    tempo com tentativa perdida, aqui se quer MEDIR a distribuição. E a
    ferramenta chama `ui.dialogo_esta_aberto()` num laço próprio, **nunca**
    `ui._esperar_o_dialogo` — é essa função que alimenta a memória de aberturas
    do bot, e envenená-la com cliques errados de propósito estragaria o teto
    adaptativo de produção.
  - **Ranking por TAXA primeiro, latência só no desempate.** Abrir em 400 ms
    sempre é melhor que abrir em 200 ms metade das vezes: tentativa perdida
    custa um ciclo inteiro da disputa, 200 ms não custam nada perto disso.
    Coordenada sem nenhuma abertura tem `mediana_ms = None`, não 0 — 0
    ordenaria como "instantâneo" e poria a pior coordenada no topo.
  - **Amostras intercaladas em RODADAS**, com a ordem de cada rodada embaralhada
    por semente fixa (`SEMENTE_DA_ORDEM`): nenhuma coordenada carrega sozinha a
    sorte de um momento (lag, mob passando), e duas amostragens continuam
    comparáveis.
  - **ESC só com o diálogo lido como aberto.** Com nada na tela o ESC abre o
    menu do sistema do jogo, e um menu aberto engole todo clique seguinte — a
    varredura viraria zeros sem ninguém perceber. Quadro preto (`None`) não faz
    apertar nada: espera e relê.
  - **Três travas de aborto:** `TENTATIVAS_DE_FECHAR` (diálogo que não fecha),
    `FALHAS_SEGUIDAS_PARA_ABORTAR = 20` (nenhuma coordenada abrindo ⇒ o ponto de
    partida está errado ou tem mob na frente) e
    `INVALIDAS_SEGUIDAS_PARA_ABORTAR` (a captura parou — a ferramenta mede pela
    TELA, e isso é conferido logo na largada, antes dos 75 cliques).
  - **Não encostou na âncora canônica ⇒ mede assim mesmo e AVISA.** O resultado
    sai com `ancora_exata: false`, a posição real vai no arquivo e o resumo
    carrega o alerta. Abortar entregaria nada em vez de um dado com ressalva —
    mas adotar a coordenada vencedora sem ler a ressalva seria adotar um número
    medido de outro lugar.
  - **Saída:** uma linha `AMOSTRA ponto=… dx=… abriu=… ms=… andou=…` por clique
    e uma `RANKING …` por coordenada no log (o JSON de dev **não copia campos de
    `extra`**, só a mensagem — por isso o dado vai no texto), mais o arquivo
    completo em `logs/amostragem/<ponto>-<carimbo>.json`. O veredito em texto é
    montado no Python (`resumir` / `resumir_curto`) e as duas interfaces só
    exibem: a GUI num `QMessageBox`, a web num toast de uma linha (o toast é
    pílula de uma linha que some sozinha; o relatório fica no log).
  - Blocos `TEMPORÁRIO` em `web_app.py` (`_App.amostrar_cliques`,
    `cancelar_amostragem` + os dois métodos da `Api`), em `gui/main_window.py`
    (grupo "Amostragem de coordenadas de clique direito" na aba Diagnóstico,
    `_amostrar_cliques`, `_fim_da_amostragem`, sinal `amostragem_pronta`), no
    `web/index.html` + `web/main.js` (`#btn-amostrar-cliques`) e o
    `tests/test_amostragem_de_cliques.py`.
- **TEMPORÁRIO — `blazesbot/bot/diagnostico_do_link.py`, as fotos em volta do
  clique no link.** Interruptor `ATIVADO` no topo (padrão do `USAR_TAB_NOS_GUARDAS`),
  ligado. Fotografa a tela ANTES do clique (referência com o diálogo aberto) e
  em `INSTANTES = (0.0, 0.10, 0.35, 0.75)` s depois, gravando PNG em
  `logs/diagnostico-do-link/`. Existe para decidir a questão acima por imagem em
  vez de dedução.
  - **Bounded por construção:** `MAXIMO_DE_EPISODIOS = 12` por processo, depois
    vira no-op silencioso — uma run de madrugada não enche o disco nem paga o
    custo a noite inteira.
  - **Não clica.** O `ctx.click(ponto_link)` continua exatamente onde estava; o
    módulo só fotografa dos dois lados. Apagar o teste é apagar o import e as
    duas linhas marcadas `TEMPORÁRIO` em `ui_service._abrir_dialogo_e_clicar`.
  - **`time.sleep`, e não `ctx.tick`:** o tick sorteia jitter, e jitter borra os
    instantes que se quer cravar. Preço aceito: o Parar demora até 0,75 s para
    responder durante um episódio. Tudo dentro de `try/except` — complemento
    nunca derruba a run.


---

# `9-VIGIAR-COMBATE` — a ferramenta que voltou diferente (26/08/2026)

> *"Cria para mim um .bat que acompanha em tempo real a batalha e USA A FUNÇÃO
> DE TARGET DO `target_hybrid`, pois eu quero ir vendo o que está acontecendo.
> Faça eu poder escolher o pid, liste eles que tenham o mesmo nome, só para eu
> escolher o número."*

## Por que a versão antiga tinha sido apagada

O `9-VIGIAR-COMBATE` já existiu e foi removido junto com a leitura de alvo por
ponteiro — ele tinha a **própria** leitura. A opção `--watch-combat` ficou no
`main.py` só imprimindo um recado explicando para onde ela tinha ido.

Uma ferramenta de diagnóstico que reimplementa a leitura que deveria estar
diagnosticando **não diagnostica o bot: diagnostica a cópia**. E a cópia pode
estar certa enquanto o bot está errado, que é o pior resultado possível — você
olha a tela, vê tudo normal, e o bot continua batendo em cadáver.

## O que a versão nova faz

Chama o mesmo caminho que o bot chama, e imprime. Peça por peça:

| o que aparece na tela | de onde vem |
|---|---|
| o alvo (id, nome, HP, nível) | `TargetHybrid.ler(..., com_tela=False)` |
| a linha `ALVO Gun Witch 52.2% [#####-----] (52/100, nv50) -34%` | `TargetHybrid.linha_do_log` — **a MESMA que o BC escreve no log da conta** |
| o `<<< MORREU` | `MorteDoAlvo.veredito` + `.contar` |
| quais `client.exe` existem | `watchdog.client_pids()` |
| como se chama cada um | `core/janelas.titulo_do_pid()` + `Memory.char_name()` |
| vida e batalha do personagem | `Memory.vida_pct` / `in_battle` |

Nada disso é novo. O único código que esta ferramenta tem de si mesma é **o
laço, a escolha do PID e a formatação da segunda linha**.

`com_tela=False` de propósito: a reserva pela barra desenhada é do BC e exige
captura. Aqui a pergunta é o que a MEMÓRIA responde — que é justamente a
pergunta que estava em dúvida.

## A escolha do cliente

Todos os processos se chamam `client.exe`, então o nome não separa nada. Quem
separa é o **nick lido na memória** (o que o usuário reconhece) e o **título da
janela** como reserva — o título existe mesmo quando a memória não abre, por
exemplo num cliente parado na tela de login.

Um cliente só ⇒ usa ele sem perguntar. Vários ⇒ lista numerada, e a lista é
**ordenada** para o número que a pessoa acabou de ler não mudar de dono entre
uma rodada e a seguinte.

## O que a promoção arrastou junto

A ferramenta precisava do título da janela por PID. Essa varredura estava
escrita **quatro vezes dentro do `main.py`**, cada uma com um recorte diferente
do mesmo resultado: uma queria o título, outra o handle, outra as duas coisas de
todas as janelas, a quarta o handle mais o título.

Pela diretiva de promoção, virou `core/janelas.py` com uma primitiva
(`janelas_do_pid`) e duas conveniências (`janela_do_pid`, `titulo_do_pid`), e as
quatro cópias saíram. Um teste confere que não sobrou nenhum `EnumWindows` no
`main.py` — senão a promoção teria ficado pela metade, que é o pior dos dois
mundos: a peça nova existe e as cópias antigas continuam apodrecendo.
