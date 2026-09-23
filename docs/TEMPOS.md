# TEMPOS — tudo que o bot ESPERA

> **GERADO. Não edite à mão.**
> `./.venv/Scripts/python.exe -m blazesbot.core.indice_de_tempos`
> Travado por `tests/test_indice_de_tempos.py`: mexeu num tempo e não regerou,
> a suíte reprova.

## REGRA PERMANENTE

**Todo tempo novo — constante OU literal no meio de uma função — entra aqui.**
Não por disciplina: a extração acha sozinha, e o teste reprova se o arquivo
estiver velho. Basta regerar.

O que NÃO se faz sozinho é o **ponto de restauração**. Ver a seção
"Se você mudou um tempo e deu errado", no fim.

## Como ler a coluna NATUREZA

| natureza | o que é | mexer nele significa |
|---|---|---|
| **TETO** | prazo máximo; quem responde antes não paga | encurtar arrisca **o caso lento**, não o comum |
| **PASSO** | cadência de uma pergunta em laço | encurtar gasta **CPU**, não relógio |
| **FIXO** | espera **CEGA**: paga sempre, inteira | é **aqui** que há tempo a ganhar |

A regra do projeto é *"onde havia espera cega, agora se PERGUNTA"*. Cada **FIXO**
desta lista é ou uma exceção justificada, ou dívida que ninguém converteu ainda.

## A coluna ORIGINAL

`=` significa que o valor está como o de referência. **`⚠` significa que alguém
mudou** — e a coluna mostra de quanto era. É o ponto de restauração.


**367 tempos catalogados** — 252 FIXOS (espera cega), 115 entre TETO e PASSO.


**3 estão diferentes do original:** `FATIA_DE_ESPERA`, `INTERVALO_ENTRE_INVOCACOES`, `PASSOS_DO_APP`


## FORA DA CAVE — venda em Stone City

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| *literal em* `buy_supplies` | 0.4 s | = | FIXO | [vendor.py:359](blazesbot/bot/bc/vendor.py#L359) | `buy_supplies` | Compra a Pedra de Retorno gasta, no mesmo NPC da venda. |
| *literal em* `buy_supplies` | 0.25 s | = | FIXO | [vendor.py:361](blazesbot/bot/bc/vendor.py#L361) | `buy_supplies` | Compra a Pedra de Retorno gasta, no mesmo NPC da venda. |
| *literal em* `buy_supplies` | 0.3 s | = | FIXO | [vendor.py:365](blazesbot/bot/bc/vendor.py#L365) | `buy_supplies` | Compra a Pedra de Retorno gasta, no mesmo NPC da venda. |
| *literal em* `buy_supplies` | 0.35 s | = | FIXO | [vendor.py:370](blazesbot/bot/bc/vendor.py#L370) | `buy_supplies` | Compra a Pedra de Retorno gasta, no mesmo NPC da venda. |
| *literal em* `run_maintenance` | 0.2 s | = | FIXO | [vendor.py:458](blazesbot/bot/bc/vendor.py#L458) | `run_maintenance` | Ida completa à cidade: teleportar, viajar, vender, comprar. |
| *literal em* `run_maintenance` | 0.5 s | = | FIXO | [vendor.py:471](blazesbot/bot/bc/vendor.py#L471) | `run_maintenance` | Ida completa à cidade: teleportar, viajar, vender, comprar. |


## FORA DA CAVE — painel, diálogos, Fay

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `TETO_DO_TELEPORTE_DA_FAY` | 2 s | = | TETO | [ui_service.py:54](blazesbot/bot/bc/ui_service.py#L54) | `viajar_para_ghost_din_woods, _esperar_o_teleporte` | TELEPORTE DA FAY (Stone City -> Ghost Din Woods) |
| `PASSO_DA_ESPERA_DO_TELEPORTE` | 0.08 s | = | PASSO | [ui_service.py:55](blazesbot/bot/bc/ui_service.py#L55) | `viajar_para_ghost_din_woods, _esperar_o_teleporte` |  |
| `TETO_POR_TENTATIVA_NA_ENTRADA` | 2.5 s | *novo* | TETO | [ui_service.py:92](blazesbot/bot/bc/ui_service.py#L92) | `garantir_coordenada_da_entrada` | TETO de cada tentativa -- não é o tempo gasto, é o limite. Quem encerra é a |
| `SEGUNDOS_ENTRE_REAPLICACOES` | 120 s (2 min) | *novo* | FIXO | [ui_service.py:129](blazesbot/bot/bc/ui_service.py#L129) | `_reaplicar_o_petbug_se_preciso` | Espaço mínimo entre duas reaplicações vindas DAQUI. |
| *literal em* `entrar_no_covil_do_boss` | 1.5 s | = | FIXO | [ui_service.py:610](blazesbot/bot/bc/ui_service.py#L610) | `entrar_no_covil_do_boss` | Altar Stone -> "Secret Cemetery", que é a sala do boss. |
| *literal em* `sair_da_cave` | 1.5 s | = | FIXO | [ui_service.py:647](blazesbot/bot/bc/ui_service.py#L647) | `sair_da_cave` | Skull Herald do covil -> "Leave Bewitcher Cave". |


## FORA DA CAVE — montaria e trajeto

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `INTERVALO_RECLIQUE` | 1.1 s | = | FIXO | [navegacao.py:98](blazesbot/bot/navegacao.py#L98) | `follow_path` | Intervalo MÁXIMO entre cliques enquanto anda. Não é a cadência normal -- o |
| `SEM_PROGRESSO_SEGUNDOS` | 1.2 s | = | FIXO | [navegacao.py:112](blazesbot/bot/navegacao.py#L112) | `follow_path` | Sem aproximar-se do alvo por este tempo, considera travado. |
| `TETO_PRESO_NO_MESMO_PONTO` | 30 s | *novo* | TETO | [navegacao.py:128](blazesbot/bot/navegacao.py#L128) | `follow_path` | TETO PARA FICAR PRESO NO MESMO WAYPOINT, sem conseguir manobra nenhuma. |
| `SEGUNDOS_PARADO_DE_VERDADE` | 1.5 s | = | FIXO | [navegacao.py:158](blazesbot/bot/navegacao.py#L158) | `follow_path` | PERSONAGEM COMPLETAMENTE PARADO DENTRO DA CAVE |
| `SEGUNDOS_POR_TENTATIVA_DE_DESTRAVAR` | 4 s | = | FIXO | [navegacao.py:187](blazesbot/bot/navegacao.py#L187) | `destravar_pelos_vizinhos, _tentar_circulo` | Prazo para alcançar CADA candidato da manobra de destravamento. |
| `CIRCULO_TETO_SEGUNDOS` | 6.5 s | = | TETO | [navegacao.py:269](blazesbot/bot/navegacao.py#L269) | `_tentar_circulo` | Teto de tempo TOTAL do círculo antes de desistir e devolver o controle. É a |
| `SEGUNDOS_POR_CLIQUE_CIRCULO` | 1 s | = | FIXO | [navegacao.py:271](blazesbot/bot/navegacao.py#L271) | `_clicar_offset_e_verificar` | Janela por ponto do círculo para saber se o clique fez o personagem andar. |
| `INTERVALO_MANUTENCAO` | 0.6 s | = | FIXO | [navegacao.py:273](blazesbot/bot/navegacao.py#L273) | `follow_path` | Cadência da manutenção durante o deslocamento (poção). |
| `INTERVALO_REMONTAR` | 3 s | = | FIXO | [navegacao.py:284](blazesbot/bot/navegacao.py#L284) | `_pode_tocar_na_montaria, _manter_montaria` | A MONTARIA É PRÉ-REQUISITO DE ANDAR, NÃO UMA OTIMIZAÇÃO -- tudo que este bot |
| `TETO_DO_PORTAO` | 6 s | = | TETO | [navegacao.py:311](blazesbot/bot/navegacao.py#L311) | `__init__, garantir_montaria_para_andar` | A ORDEM DO PORTÃO: CONFERIR -> ATIVAR -> CONFIRMAR -> ANDAR |
| `SEGUNDOS_ANTES_DE_CUTUCAR` | 10 s | *novo* | FIXO | [navegacao.py:371](blazesbot/bot/navegacao.py#L371) | `destravar_ao_entrar, _passo_para_destravar_a_montaria` | Quanto esperar, desde a PRIMEIRA tentativa, antes de andar um passo. Numero do |
| `PASSO_PARA_DESTRAVAR_A_MONTARIA` | 6 s | *novo* | PASSO | [navegacao.py:379](blazesbot/bot/navegacao.py#L379) | `_passo_para_destravar_a_montaria` | O tamanho do passo, em unidades de posicao. Numero do usuario ("6px"). |
| `PASSO_AO_ENTRAR_NA_CAVE` | 3 s | *novo* | PASSO | [navegacao.py:381](blazesbot/bot/navegacao.py#L381) | `destravar_ao_entrar` | METADE dele ao ENTRAR na cave (16/09/2026, *"qualquer andada ja resolve"*). |
| `INTERVALO_PARADA_POCAO` | 10 s | = | FIXO | [navegacao.py:441](blazesbot/bot/navegacao.py#L441) | `_manutencao_em_movimento` | Recarga da PARADA para tomar poção durante o trajeto. |
| *literal em* `wait_until_still` | 0.25 s | = | FIXO | [navegacao.py:621](blazesbot/bot/navegacao.py#L621) | `wait_until_still` | Espera o personagem parar de andar. |
| *literal em* `_abrir_mapa` | 0.5 s | = | FIXO | [navegacao.py:645](blazesbot/bot/navegacao.py#L645) | `_abrir_mapa` |  |
| *literal em* `_fechar_mapa` | 0.3 s | = | FIXO | [navegacao.py:651](blazesbot/bot/navegacao.py#L651) | `_fechar_mapa` |  |
| *literal em* `_mover_pelo_mapa` | 0.2 s | = | FIXO | [navegacao.py:689](blazesbot/bot/navegacao.py#L689) | `_mover_pelo_mapa` | Anda até `alvo` usando o mapa-múndi. |
| *literal em* `_mover_pelo_mapa` | 1 s | = | FIXO | [navegacao.py:695](blazesbot/bot/navegacao.py#L695) | `_mover_pelo_mapa` | Anda até `alvo` usando o mapa-múndi. |
| *literal em* `_clicar_offset_e_verificar` | 0.1 s | = | FIXO | [navegacao.py:1054](blazesbot/bot/navegacao.py#L1054) | `_clicar_offset_e_verificar` | Clique curto num offset e medição: o personagem andou? |
| *literal em* `_parada_para_pocao` | 0.25 s | = | FIXO | [navegacao.py:1152](blazesbot/bot/navegacao.py#L1152) | `_parada_para_pocao` | Desmonta, toma poção e remonta. É a ÚNICA forma que funciona. |
| *literal em* `_parada_para_pocao` | 0.2 s | = | FIXO | [navegacao.py:1163](blazesbot/bot/navegacao.py#L1163) | `_parada_para_pocao` | Desmonta, toma poção e remonta. É a ÚNICA forma que funciona. |
| *literal em* `follow_path` | 0.25 s | = | FIXO | [navegacao.py:1451](blazesbot/bot/navegacao.py#L1451) | `follow_path` | Percorre waypoints em ordem, SEM parar entre eles. |
| *literal em* `travel_via_surroundings` | 0.5 s | = | FIXO | [navegacao.py:1817](blazesbot/bot/navegacao.py#L1817) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.2 s | = | FIXO | [navegacao.py:1819](blazesbot/bot/navegacao.py#L1819) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.15 s | = | FIXO | [navegacao.py:1821](blazesbot/bot/navegacao.py#L1821) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.4 s | = | FIXO | [navegacao.py:1823](blazesbot/bot/navegacao.py#L1823) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.25 s | = | FIXO | [navegacao.py:1836](blazesbot/bot/navegacao.py#L1836) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.5 s | = | FIXO | [navegacao.py:1842](blazesbot/bot/navegacao.py#L1842) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.25 s | = | FIXO | [navegacao.py:1844](blazesbot/bot/navegacao.py#L1844) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `ensure_mounted` | 1 s | = | FIXO | [navegacao.py:2318](blazesbot/bot/navegacao.py#L2318) | `ensure_mounted` |  |
| *literal em* `ensure_mounted` | 1 s | = | FIXO | [navegacao.py:2329](blazesbot/bot/navegacao.py#L2329) | `ensure_mounted` |  |
| *literal em* `ensure_dismounted` | 0.75 s | = | FIXO | [navegacao.py:2377](blazesbot/bot/navegacao.py#L2377) | `ensure_dismounted` |  |


## FORA DA CAVE — pontos exatos

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `SEGUNDOS_DESENCALHANDO_O_ALTAR` | 3 s | = | FIXO | [mapa_bc.py:183](blazesbot/bot/bc/mapa_bc.py#L183) |  | Quanto esperar no ponto de vai-e-volta antes de retornar. |
| `SEGUNDOS_POR_TENTATIVA_NA_SAIDA` | 1.8 s | = | FIXO | [mapa_bc.py:229](blazesbot/bot/bc/mapa_bc.py#L229) |  |  |


## A RUN — passos da rotina

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `PASSO_DO_RECONHECIMENTO` | 0.04 s | = | PASSO | [routine.py:121](blazesbot/bot/bc/routine.py#L121) | `_reconhecer_entrada` | PASSO: de quanto em quanto tempo perguntar, dentro da janela. A pergunta é uma |
| `ESPERA_ENTRE_TENTATIVAS` | 0.025 s | = | FIXO | [routine.py:131](blazesbot/bot/bc/routine.py#L131) | `_do_entrar` | E O INTERVALO ENTRE TENTATIVAS quase desaparece: a janela de reconhecimento já |
| `SEGUNDOS_POR_TENTATIVA_NO_ALTAR` | 1.5 s | = | FIXO | [routine.py:167](blazesbot/bot/bc/routine.py#L167) | `_encostar_exato_no_patamar` |  |
| `SEGUNDOS_ESPERANDO_A_BOLSA` | 0.2 s | = | FIXO | [routine.py:284](blazesbot/bot/bc/routine.py#L284) | `_usar_package_courage` | Quanto esperar a bolsa CONFIRMAR que abriu, lendo a memória. |
| `PASSO_DA_ESPERA_DA_BOLSA` | 0.05 s | = | PASSO | [routine.py:309](blazesbot/bot/bc/routine.py#L309) | `_usar_package_courage` | De quanto em quanto tempo perguntar se a bolsa já abriu. Era 0,15 s, o que |
| `ASSENTAMENTO_DA_BOLSA` | 0.14 s | = | FIXO | [routine.py:315](blazesbot/bot/bc/routine.py#L315) | `_usar_package_courage` | Depois que a MEMÓRIA confirma a bolsa aberta, o quanto esperar o DESENHO dela. |
| *literal em* `_do_situar` | 1 s | = | FIXO | [routine.py:524](blazesbot/bot/bc/routine.py#L524) | `_do_situar` | Olha onde o personagem está e entra no estado que faz sentido. |
| *literal em* `_do_preparar` | 0.2 s | = | FIXO | [routine.py:617](blazesbot/bot/bc/routine.py#L617) | `_do_preparar` |  |
| *literal em* `_do_recuperar` | 3 s | = | FIXO | [routine.py:2209](blazesbot/bot/bc/routine.py#L2209) | `_do_recuperar` | Recuperação após morte ou falhas em sequência. |


## DENTRO DA CAVE — combate

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| *literal em* `_curar_antes_da_segunda_fase` | 0.3 s | = | FIXO | [combat.py:370](blazesbot/bot/bc/combat.py#L370) | `_curar_antes_da_segunda_fase` | Cura antes de encostar na fase seguinte, se a conta pedir. |


## DENTRO DA CAVE — outros

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `PASSO_DO_GRID` | 6 s | = | PASSO | [amostragem_de_cliques.py:121](blazesbot/bot/bc/amostragem_de_cliques.py#L121) | `gerar_grid` |  |
| `TETO_DA_AMOSTRA` | 1.5 s | = | TETO | [amostragem_de_cliques.py:140](blazesbot/bot/bc/amostragem_de_cliques.py#L140) | `rodar, amostrar` | Teto da medição. Largo de propósito -- ver o cabeçalho. As aberturas reais |
| `PASSO_DA_MEDICAO` | 0.03 s | = | PASSO | [amostragem_de_cliques.py:145](blazesbot/bot/bc/amostragem_de_cliques.py#L145) | `amostrar` | Passo do laço que pergunta se o diálogo abriu. Cada volta custa uma captura |
| `ASSENTAMENTO_APOS_O_CLIQUE` | 0.125 s | = | FIXO | [amostragem_de_cliques.py:150](blazesbot/bot/bc/amostragem_de_cliques.py#L150) | `amostrar` | Assentamento depois da amostra, antes de reler a posição. É o tempo de o |
| `ESPERA_APOS_O_ESC` | 0.075 s | = | FIXO | [amostragem_de_cliques.py:153](blazesbot/bot/bc/amostragem_de_cliques.py#L153) | `fechar_dialogo` | Espera depois de cada ESC, antes de reconferir se o diálogo fechou. |
| `SEGUNDOS_POR_TENTATIVA_DE_ANCORAR` | 3 s | = | FIXO | [amostragem_de_cliques.py:168](blazesbot/bot/bc/amostragem_de_cliques.py#L168) | `ancorar` |  |
| `INTERVALO_DO_BATIMENTO` | 15 s | = | FIXO | [localizacao.py:67](blazesbot/bot/bc/localizacao.py#L67) | `_registrar` | Cadência do batimento no diário. Uma linha a cada meio minuto dá uma trilha |
| `SEGUNDOS_PARA_DESCONFIAR` | 3 s | = | FIXO | [localizacao.py:72](blazesbot/bot/bc/localizacao.py#L72) | `_registrar_falha` | Tempo com o nome ilegível a partir do qual o bot passa a tratar a fonte de |
| *literal em* `rodar` | 0.2 s | = | FIXO | [teste_venda.py:125](blazesbot/bot/bc/teste_venda.py#L125) | `rodar` | Executa a venda na janela JÁ ABERTA desta conta. Bloqueia até terminar. |


## ECOSSISTEMA APP

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `TETO_DA_ESPERA_DO_ALVO` | 2 s | *novo* | TETO | [afericao_do_aliado.py:81](blazesbot/bot/app/afericao_do_aliado.py#L81) | `_medir_a_troca` | Quanto esperar, no máximo, a memória refletir o alvo novo depois do clique. |
| `PASSO_DA_MEDICAO` | 0.02 s | *novo* | PASSO | [afericao_do_aliado.py:85](blazesbot/bot/app/afericao_do_aliado.py#L85) | `_medir_a_troca` | De quanto em quanto tempo perguntar. 20 ms é fino o bastante para o número |
| `SEGUNDOS_ENTRE_POCOES` | 15 s | = | FIXO | [cura.py:143](blazesbot/bot/app/cura.py#L143) | `_curar_com_pocao` | Quanto esperar entre uma poção e a próxima. |
| `SEGUNDOS_SENTADO` | 30 s | = | TETO | [cura.py:175](blazesbot/bot/app/cura.py#L175) | `_curar_sentado` | Teto sentado, para quem não tem tecla de poção configurada. |
| `SEGUNDOS_ESPERANDO_SAIR_DE_BATALHA` | 2 s | = | FIXO | [cura.py:182](blazesbot/bot/app/cura.py#L182) | `_esperar_sair_de_batalha` | Quanto esperar a flag de batalha baixar depois que a macro termina. |
| `SEGUNDOS_PARA_SENTAR_COM_A_POCAO` | 1 s | *novo* | FIXO | [cura.py:193](blazesbot/bot/app/cura.py#L193) | `_a_pocao_saiu` | Quanto esperar o personagem SENTAR depois de apertar a tecla de poção. |
| `PASSO_DA_PERGUNTA` | 0.1 s | = | PASSO | [cura.py:198](blazesbot/bot/app/cura.py#L198) | `_passo` | Cadência de toda pergunta deste módulo. Leitura de memória é ~1 µs; o custo é |
| `FATIA_DE_ESPERA` | 0.08 s | **0.05 s** ⚠ | PASSO | [executor.py:104](blazesbot/bot/app/executor.py#L104) | `_esperar, _dormir (+1)` | Fatia máxima de espera antes de conferir se é para continuar. 0,05 s dá parada |
| `CADENCIA_DO_AVISO_DE_COMIDA` | 300 s (5 min) | *novo* | PASSO | [executor.py:163](blazesbot/bot/app/executor.py#L163) | `_avisar_se_a_comida_esta_presa` | Entre dois avisos de "a comida venceu e a batalha não deixa alimentar". |
| `INTERVALO_ENTRE_INVOCACOES` | 6 s | **10 s** ⚠ | FIXO | [executor.py:172](blazesbot/bot/app/executor.py#L172) | `garantir_pet` | Intervalo mínimo entre dois toques na tecla do pet. |
| `ESPERA_DEPOIS_DE_INVOCAR` | 1 s | = | FIXO | [executor.py:177](blazesbot/bot/app/executor.py#L177) | `garantir_pet` | Espera depois de apertar a tecla do pet, antes de seguir para as teclas da |
| `ESPERA_DEPOIS_DA_LIMPEZA` | 0.3 s | = | FIXO | [executor.py:199](blazesbot/bot/app/executor.py#L199) | `_recolher_ao_ponto` | Quanto esperar o jogo processar o F1 antes de TABar. |
| `SEGUNDOS_DE_DESISTENCIA_DO_PERIMETRO` | 60 s (1 min) | = | FIXO | [executor.py:213](blazesbot/bot/app/executor.py#L213) | `_recolher_ao_ponto` | Quanto tempo o perímetro fica só MEDINDO depois de desistir. |
| `SEGUNDOS_PARA_CONFIRMAR_A_SAIDA` | 2.5 s | *novo* | FIXO | [executor.py:236](blazesbot/bot/app/executor.py#L236) | `_confirmar_a_saida_de_batalha` | Quanto se espera a flag de combate BAIXAR depois de o alvo cair. |
| `PASSO_DA_SAIDA_DE_BATALHA` | 0.1 s | *novo* | PASSO | [executor.py:240](blazesbot/bot/app/executor.py#L240) | `_confirmar_a_saida_de_batalha` | Passo da conferência ativa acima. É leitura de memória; 0,1 s dá 20 amostras |
| `SEGUNDOS_PARA_O_ALVO_APARECER` | 0.35 s | *novo* | FIXO | [executor.py:273](blazesbot/bot/app/executor.py#L273) | `_esperar_o_alvo_trocar` | O TAB DEIXOU DE SER LINHA DA MACRO |
| `PASSO_DA_CONFERENCIA_DO_ALVO` | 0.16 s | *novo* | PASSO | [executor.py:311](blazesbot/bot/app/executor.py#L311) | `_esperar, _dormir (+1)` | De quanto em quanto tempo perguntar "o alvo morreu?" DENTRO da espera de uma |
| `SEGUNDOS_PARA_A_RODA_REINICIAR` | 1.6 s | *novo* | FIXO | [executor.py:370](blazesbot/bot/app/executor.py#L370) | `_garantir_alvo` | Quanto esperar depois de uma aquisição FRACASSADA, antes da volta seguinte. |
| `ESPERA_SEM_ALVO` | 0.4 s | *novo* | FIXO | [executor.py:550](blazesbot/bot/app/executor.py#L550) | `uma_volta, _uma_volta_simples (+1)` | Quanto esperar antes de tentar de novo quando NÃO HÁ alvo vivo. |
| `ESPERA_ANTES_DO_TAB` | 0.4 s | *novo* | FIXO | [executor.py:577](blazesbot/bot/app/executor.py#L577) | `_tab_simples, _garantir_alvo` | PAGO UMA VEZ POR AQUISIÇÃO, NÃO UMA VEZ POR TECLA |
| `ESPERA_DEPOIS_DO_TAB` | 0.01 s | *novo* | FIXO | [executor.py:597](blazesbot/bot/app/executor.py#L597) | `_respiro_depois_do_tab` | Respiro entre o TAB e a PRIMEIRA linha da macro. |
| `SEGUNDOS_PARA_A_TRAVA_DEVOLVER` | 2 s | = | FIXO | [executor.py:599](blazesbot/bot/app/executor.py#L599) | `_voltar_para_base` |  |
| `MINIMO_DE_ESPERA_DO_APP_MS` | 100 s (2 min) | *novo* | FIXO | [executor.py:606](blazesbot/bot/app/executor.py#L606) | `_respiro_depois_do_tab` | Piso de qualquer tempo do APP, em milissegundos. O MESMO número vive em |
| `SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE` | 2.5 s | *novo* | FIXO | [executor.py:662](blazesbot/bot/app/executor.py#L662) | `_observar_depois_da_morte` | DEPOIS DE MATAR, O BOT OBSERVA -- E O QUE ELE OBSERVA É A BATALHA |
| `INTERVALO_MINIMO_DA_TELA` | 0.5 s | *novo* | FIXO | [executor.py:730](blazesbot/bot/app/executor.py#L730) | `_olhar_a_tela` | Intervalo minimo entre duas capturas. |
| `ESPERA_ENTRE_TABS` | 0.6 s | *novo* | FIXO | [executor.py:769](blazesbot/bot/app/executor.py#L769) | `_garantir_alvo` | Espaçamento entre um salto da roda do TAB e o seguinte. |
| `PASSO_DA_ESPERA_DA_BASE` | 0.1 s | = | PASSO | [executor.py:784](blazesbot/bot/app/executor.py#L784) | `_esperar_chegar_na_base` | Cadência da pergunta "já cheguei?". Leitura de posição é de microssegundos; o |
| `SEGUNDOS_DO_PASSO_DO_SHUFFLE` | 3 s | *novo* | PASSO | [executor.py:820](blazesbot/bot/app/executor.py#L820) | `_fazer_shuffle_anti_afk` | Cada perna do shuffle anti-AFK (ida e volta). Era `time.sleep(1.0)` cego duas |
| *literal em* `rodar` | 0.25 s | = | FIXO | [executor.py:3489](blazesbot/bot/app/executor.py#L3489) | `rodar` | Laço contínuo: volta após volta, até `continuar()` devolver False. |
| `ESPERA_ENTRE_TABS_DO_ALINHAMENTO` | 0.5 s | *novo* | FIXO | [sincronia.py:97](blazesbot/bot/app/sincronia.py#L97) |  | Cadência do TAB durante o alinhamento. |
| `PASSO_DA_ESPERA_DA_LARGADA` | 0.04 s | *novo* | PASSO | [sincronia.py:100](blazesbot/bot/app/sincronia.py#L100) | `_esperar_os_seguidores, _entrar_na_largada` | De quanto em quanto tempo o seguidor confere se a largada saiu. |
| `SEGUNDOS_SEM_MUDANCA_PARA_TAB` | 3 s | *novo* | FIXO | [sincronia.py:108](blazesbot/bot/app/sincronia.py#L108) | `conferir_a_parada` | Sem trocar de estado de batalha por este tempo, dá TAB. |
| `TETO_DA_LINHA_SEGUNDOS` | 2 s | *novo* | TETO | [sincronia.py:116](blazesbot/bot/app/sincronia.py#L116) | `linha_a_enviar` | Quanto o seguidor espera a marca de UMA linha antes de mandar assim mesmo. |
| `PASSO_DA_ESPERA_DA_LINHA` | 0.05 s | *novo* | PASSO | [sincronia.py:121](blazesbot/bot/app/sincronia.py#L121) | `linha_a_enviar` | De quanto em quanto tempo a espera da linha acorda para conferir o botão |


## LOGIN E RELOGIN

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `PRE_SERVER_TIMEOUT` | 600 s (10 min) | = | TETO | [login.py:88](blazesbot/bot/login.py#L88) | `_sair_da_lista_de_servidores, run` | NÃO EXISTE LIMITE DE TEMPO NA FILA. |
| `ESPERA_CEGA_SEGUNDOS` | 90 s (2 min) | = | FIXO | [login.py:104](blazesbot/bot/login.py#L104) | `_advance_phase` | Depois de esgotar as tentativas às cegas, o bot NÃO desiste -- ele espaça. |
| `ESPERA_SERVIDOR_FORA` | 10 s | = | FIXO | [login.py:120](blazesbot/bot/login.py#L120) | `_handle_acquiring_ip` | Espera depois de fechar "Acquiring server IP address." (servidores fora do ar). |
| `ESPERA_SERVIDOR_FORA_MAX` | 60 s (1 min) | = | TETO | [login.py:121](blazesbot/bot/login.py#L121) | `_handle_acquiring_ip` |  |
| `SEGUNDOS_CONECTANDO` | 6 s | = | FIXO | [login.py:147](blazesbot/bot/login.py#L147) | `_handle_connecting` | "Connecting to the server, please wait a moment." -- espera LEGÍTIMA, com |
| `FATIA_DA_ESPERA_DO_LOGIN` | 0.05 s | = | PASSO | [login.py:152](blazesbot/bot/login.py#L152) | `_esperar` | Fatia da espera do login. A espera é cumprida em pedaços para que Parar e |
| *literal em* `_abort_if_stopped` | 0.075 s | = | FIXO | [login.py:320](blazesbot/bot/login.py#L320) | `_abort_if_stopped` | Verifica parada E pausa. |
| *literal em* `_do_credentials` | 0.35 s | = | FIXO | [login.py:406](blazesbot/bot/login.py#L406) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.15 s | = | FIXO | [login.py:408](blazesbot/bot/login.py#L408) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.3 s | = | FIXO | [login.py:419](blazesbot/bot/login.py#L419) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.25 s | = | FIXO | [login.py:422](blazesbot/bot/login.py#L422) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.15 s | = | FIXO | [login.py:428](blazesbot/bot/login.py#L428) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.3 s | = | FIXO | [login.py:436](blazesbot/bot/login.py#L436) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 1.25 s | = | FIXO | [login.py:439](blazesbot/bot/login.py#L439) | `_do_credentials` |  |
| *literal em* `_do_server` | 0.4 s | = | FIXO | [login.py:488](blazesbot/bot/login.py#L488) | `_do_server` | Seleciona o servidor da conta e confirma. |
| *literal em* `_do_server` | 1.75 s | = | FIXO | [login.py:549](blazesbot/bot/login.py#L549) | `_do_server` | Seleciona o servidor da conta e confirma. |
| *literal em* `_try_enter_world` | 0.6 s | = | FIXO | [login.py:600](blazesbot/bot/login.py#L600) | `_try_enter_world` | Seleciona o personagem e entra. Chamado a cada 20 s. |
| *literal em* `_try_enter_world` | 1.5 s | = | FIXO | [login.py:609](blazesbot/bot/login.py#L609) | `_try_enter_world` | Seleciona o personagem e entra. Chamado a cada 20 s. |
| *literal em* `_handle_login_error` | 0.6 s | = | FIXO | [login.py:623](blazesbot/bot/login.py#L623) | `_handle_login_error` |  |
| *literal em* `_handle_login_error` | 0.6 s | = | FIXO | [login.py:628](blazesbot/bot/login.py#L628) | `_handle_login_error` |  |
| *literal em* `_handle_conn_interrupted` | 1 s | = | FIXO | [login.py:653](blazesbot/bot/login.py#L653) | `_handle_conn_interrupted` | Fecha o aviso de conexão interrompida. |
| *literal em* `_handle_login_busy` | 0.75 s | = | FIXO | [login.py:676](blazesbot/bot/login.py#L676) | `_handle_login_busy` | Fecha o aviso "Login server is busy now, please try again." |
| *literal em* `_handle_connecting` | 0.5 s | = | FIXO | [login.py:707](blazesbot/bot/login.py#L707) | `_handle_connecting` | "Connecting to the server, please wait a moment." — espera COM PRAZO. |
| *literal em* `_handle_connecting` | 0.5 s | = | FIXO | [login.py:710](blazesbot/bot/login.py#L710) | `_handle_connecting` | "Connecting to the server, please wait a moment." — espera COM PRAZO. |
| *literal em* `_handle_acquiring_ip` | 0.6 s | = | FIXO | [login.py:765](blazesbot/bot/login.py#L765) | `_handle_acquiring_ip` | Fecha o aviso "Acquiring server IP address." e volta a tentar. |
| *literal em* `_modal_travando_antes_do_servidor` | 0.3 s | = | FIXO | [login.py:822](blazesbot/bot/login.py#L822) | `_modal_travando_antes_do_servidor` | Aviso na tela ANTES de conectar, reconhecido só pela memória. |
| *literal em* `_modal_travando_antes_do_servidor` | 0.5 s | = | FIXO | [login.py:824](blazesbot/bot/login.py#L824) | `_modal_travando_antes_do_servidor` | Aviso na tela ANTES de conectar, reconhecido só pela memória. |
| *literal em* `_handle_conn_failed` | 0.75 s | = | FIXO | [login.py:837](blazesbot/bot/login.py#L837) | `_handle_conn_failed` | Fecha o aviso "Connection failed, please try again later." |
| *literal em* `_handle_queue` | 5 s | = | FIXO | [login.py:852](blazesbot/bot/login.py#L852) | `_handle_queue` | Na fila, apenas esperar. |
| *literal em* `_finish` | 0.25 s | = | FIXO | [login.py:903](blazesbot/bot/login.py#L903) | `_finish` | Confirma a entrada no mundo e batiza a janela. |
| *literal em* `_advance_phase` | 2.5 s | = | FIXO | [login.py:1011](blazesbot/bot/login.py#L1011) | `_advance_phase` | Executa a fase atual quando nada excepcional foi detectado. |
| *literal em* `_advance_phase` | 1 s | = | FIXO | [login.py:1022](blazesbot/bot/login.py#L1022) | `_advance_phase` | Executa a fase atual quando nada excepcional foi detectado. |


## O SISTEMA — supervisor e watchdog

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `ESPERA_DA_AUTO_SELECAO` | 0.125 s | *novo* | FIXO | [combate.py:78](blazesbot/bot/combate.py#L78) | `auto_selecionar, reancorar_o_alvo` | Espera depois da auto-seleção, para a seleção chegar da rede. Era literal |
| `SEGUNDOS_SENTADO_APOS_GUARDAS` | 4 s | = | FIXO | [combate.py:100](blazesbot/bot/combate.py#L100) | `sentar_para_recuperar` | Quatro segundos sentado recuperam vida e mana de graça, e é o único momento da |
| `SEGUNDOS_DA_POCAO_DE_VIDA` | 15 s | = | FIXO | [combate.py:116](blazesbot/bot/combate.py#L116) | `curar_ao_entrar, _beber_ate_encher (+1)` | A POÇÃO DE VIDA LEVA 15 SEGUNDOS, E ANDAR CANCELA |
| `SEGUNDOS_DEPOIS_DA_SUPER_SKILL` | 12 s | = | FIXO | [combate.py:120](blazesbot/bot/combate.py#L120) | `curar_ao_entrar, curar_antes_do_boss` | Respiro depois da Super Skill de cura. Ela é instantânea; isto é só o tempo de |
| `ESPERA_DEPOIS_DO_TAB` | 0.6 s | = | FIXO | [combate.py:140](blazesbot/bot/combate.py#L140) | `lutar_contra_um_boss` | Espera depois de UM TAB, para a seleção chegar da rede antes de conferir. |
| `FATIA_DA_ESPERA_DA_POCAO` | 0.5 s | = | PASSO | [combate.py:172](blazesbot/bot/combate.py#L172) | `_esperar_o_efeito_da_pocao` | Fatia da espera da poção. O TOTAL é medido por relógio (ver acima), então esta |
| `SEGUNDOS_DE_CONJURACAO_DA_CURA` | 1.6 s | = | FIXO | [combate.py:262](blazesbot/bot/combate.py#L262) | `_a_cura_subiu` | Conjuração da skill de cura. Informado pelo usuário em 19/08/2026. |
| `INTERVALO_DE_CONFERENCIA` | 0.1 s | = | FIXO | [combate.py:268](blazesbot/bot/combate.py#L268) | `_a_cura_subiu` | De quanto em quanto tempo perguntar se a vida subiu. É leitura de memória -- |
| `SEGUNDOS_SEM_ALVO_PARA_MORTE` | 3 s | = | FIXO | [combate.py:320](blazesbot/bot/combate.py#L320) |  | 2. TEMPO -- segundos contínuos sem nada vivo selecionado. Dá lastro à contagem: |
| `PASSO_DA_VIGIA_DE_COMBATE` | 0.05 s | = | PASSO | [combate.py:400](blazesbot/bot/combate.py#L400) | `esperar_entrar_em_combate, _esperar_a_mira_cair (+3)` | Passo da vigia da flag. É o que "não bloqueante" significa na prática: o laço |
| `TETO_PARA_A_MIRA_CAIR` | 0.6 s | *novo* | TETO | [combate.py:429](blazesbot/bot/combate.py#L429) | `_esperar_a_mira_cair` | Quanto esperar o `target_id` zerar depois de cada ESC. |
| `ESPERA_PARA_ENTRAR_EM_COMBATE` | 5 s | = | FIXO | [combate.py:436](blazesbot/bot/combate.py#L436) | `esperar_entrar_em_combate` | Quanto esperar a flag LIGAR depois de chegar no waypoint. |
| `ESPERA_ENTRAR_EM_COMBATE_GUARDAS` | 5 s | = | FIXO | [combate.py:445](blazesbot/bot/combate.py#L445) |  | Prazo curto para os GUARDAS (os 4 mobs no waypoint antes do boss). |
| `AVISO_DA_ESPERA_SEM_PRAZO` | 10 s | = | TETO | [combate.py:462](blazesbot/bot/combate.py#L462) | `esperar_entrar_em_combate` | Cadência do aviso enquanto espera sem prazo. Uma espera sem limite PRECISA |
| `CARENCIA_SEM_LER_O_NOME` | 3 s | = | FIXO | [combate.py:726](blazesbot/bot/combate.py#L726) | `atacar_ate_sair_de_combate` | Quantos TAB gastar tentando SAIR de um alvo errado, por luta. |
| `TETO_DO_DESTRAVAMENTO` | 60 s (1 min) | *novo* | TETO | [combate.py:786](blazesbot/bot/combate.py#L786) | `limpar_o_combate` | Teto de UMA rodada de destravamento. Palavra do usuario: *"no maximo atrasar 1 |
| `ESPERA_APOS_A_MORTE_ANTES_DO_TAB` | 3 s | *novo* | FIXO | [combate.py:800](blazesbot/bot/combate.py#L800) | `limpar_o_combate` | Quanto esperar PARADO, sem bater, depois de cada morte, antes de gastar o TAB |
| `CADENCIA_DA_LEITURA_DO_ALVO` | 0.15 s | = | PASSO | [combate.py:930](blazesbot/bot/combate.py#L930) | `atacar_ate_sair_de_combate, _bater_ate_o_alvo_cair` | De quanto em quanto tempo olhar a barra do alvo durante a luta. |
| `CARENCIA_APOS_O_TAB` | 2.4 s | = | FIXO | [combate.py:939](blazesbot/bot/combate.py#L939) | `atacar_ate_sair_de_combate, _bater_ate_o_alvo_cair` | Depois de apertar TAB, quanto tempo ignorar a leitura. |
| `SEGUNDOS_ANTES_DO_TAB_NO_BOSS` | 4 s | = | FIXO | [combate.py:940](blazesbot/bot/combate.py#L940) | `lutar_contra_um_boss` |  |
| *literal em* `maintain` | 0.15 s | = | FIXO | [combate.py:1325](blazesbot/bot/combate.py#L1325) | `maintain` | Poções e cura, escolhendo o item certo para a situação. |
| *literal em* `maintain` | 0.2 s | = | FIXO | [combate.py:1347](blazesbot/bot/combate.py#L1347) | `maintain` | Poções e cura, escolhendo o item certo para a situação. |
| *literal em* `maintain` | 0.15 s | = | FIXO | [combate.py:1352](blazesbot/bot/combate.py#L1352) | `maintain` | Poções e cura, escolhendo o item certo para a situação. |
| *literal em* `_manter_vida_caminho_antigo` | 0.2 s | = | FIXO | [combate.py:1382](blazesbot/bot/combate.py#L1382) | `_manter_vida_caminho_antigo` | O comportamento anterior a 19/08/2026, inteiro. |
| *literal em* `_manter_vida_caminho_antigo` | 0.15 s | = | FIXO | [combate.py:1389](blazesbot/bot/combate.py#L1389) | `_manter_vida_caminho_antigo` | O comportamento anterior a 19/08/2026, inteiro. |
| *literal em* `_manter_vida_caminho_antigo` | 0.15 s | = | FIXO | [combate.py:1394](blazesbot/bot/combate.py#L1394) | `_manter_vida_caminho_antigo` | O comportamento anterior a 19/08/2026, inteiro. |
| *literal em* `esperar_entrar_em_combate` | 0.2 s | = | FIXO | [combate.py:1777](blazesbot/bot/combate.py#L1777) | `esperar_entrar_em_combate` | Espera a flag de combate LIGAR. NÃO aperta TAB, não mira nada. |
| *literal em* `_travar_no_alvo_proibido` | 0.28 s | *novo* | FIXO | [combate.py:1976](blazesbot/bot/combate.py#L1976) | `_travar_no_alvo_proibido` | A ÚNICA trava do waypoint dos guardas -- UMA porta, duas fontes. |
| *literal em* `sentar_para_recuperar` | 0.25 s | = | FIXO | [combate.py:3339](blazesbot/bot/combate.py#L3339) | `sentar_para_recuperar` | Senta alguns segundos para recuperar vida e mana, e levanta. |
| *literal em* `heal_to_full` | 0.125 s | = | FIXO | [combate.py:3692](blazesbot/bot/combate.py#L3692) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.125 s | = | FIXO | [combate.py:3695](blazesbot/bot/combate.py#L3695) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.125 s | = | FIXO | [combate.py:3698](blazesbot/bot/combate.py#L3698) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.3 s | = | FIXO | [combate.py:3701](blazesbot/bot/combate.py#L3701) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.25 s | = | FIXO | [combate.py:3730](blazesbot/bot/combate.py#L3730) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.6 s | = | FIXO | [combate.py:3743](blazesbot/bot/combate.py#L3743) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.15 s | = | FIXO | [combate.py:3752](blazesbot/bot/combate.py#L3752) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.15 s | = | FIXO | [combate.py:3756](blazesbot/bot/combate.py#L3756) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.4 s | = | FIXO | [combate.py:3760](blazesbot/bot/combate.py#L3760) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.5 s | = | FIXO | [combate.py:3762](blazesbot/bot/combate.py#L3762) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `ensure_pet` | 1.5 s | = | FIXO | [combate.py:3790](blazesbot/bot/combate.py#L3790) | `ensure_pet` | Garante que o pet está invocado. |
| *literal em* `ensure_pet` | 1.5 s | = | FIXO | [combate.py:3803](blazesbot/bot/combate.py#L3803) | `ensure_pet` | Garante que o pet está invocado. |
| *literal em* `apply_buffs` | 0.6 s | = | FIXO | [combate.py:3830](blazesbot/bot/combate.py#L3830) | `apply_buffs` | Aplica os buffs configurados, em si mesmo. |
| `SEGUNDOS_PARA_CUTUCAR` | 15 s | *novo* | FIXO | [congelamento.py:76](blazesbot/bot/congelamento.py#L76) | `olhar` | Quanto tempo na MESMA coordenada, tentando andar, antes de mexer na montaria. |
| `SEGUNDOS_PARA_A_SEGUNDA` | 22.5 s | *novo* | TETO | [congelamento.py:82](blazesbot/bot/congelamento.py#L82) | `olhar` | A segunda cutucada, no MEIO do que resta até aquele teto. |
| `FATIA_DA_ESPERA` | 0.25 s | = | PASSO | [context.py:212](blazesbot/bot/context.py#L212) | `tick` | Fatia máxima de sono dentro de um `tick`. |
| *literal em* `wait_if_paused` | 0.075 s | = | FIXO | [context.py:573](blazesbot/bot/context.py#L573) | `wait_if_paused` | Bloqueia enquanto a pausa estiver ativa. |
| `TETO_DE_SEGUNDOS` | 10 s | *novo* | TETO | [deletador.py:165](blazesbot/bot/deletador.py#L165) | `deletar_lixo, limpar_a_bolsa` | Teto do passo inteiro (verificar + apagar), pedido do usuário. |
| `TETO_DA_CAIXA` | 1.2 s | *novo* | TETO | [deletador.py:168](blazesbot/bot/deletador.py#L168) | `_esperar_a_caixa` | Espera pela caixa de confirmação aparecer, depois do clique no ícone. |
| `PASSO_DA_ESPERA` | 0.08 s | *novo* | PASSO | [deletador.py:169](blazesbot/bot/deletador.py#L169) | `_esperar_a_caixa` |  |
| `ESPERA_DA_BOLSA_ABRIR` | 0.58 s | *novo* | FIXO | [deletador.py:179](blazesbot/bot/deletador.py#L179) | `_fechar_a_bolsa` | A janela do inventário terminar de pintar depois da tecla. |
| `TETO_DA_BOLSA_ABRIR` | 2 s | = | TETO | [deletador.py:191](blazesbot/bot/deletador.py#L191) | `_esperar_a_bolsa_abrir, limpar_a_bolsa` | Teto da espera pela bolsa APARECER depois da tecla -- 07/09/2026. |
| `PASSO_DA_BOLSA_ABRIR` | 0.15 s | = | PASSO | [deletador.py:195](blazesbot/bot/deletador.py#L195) | `_esperar_a_bolsa_abrir` | Passo entre duas perguntas pelo ícone. Cada uma custa uma captura de janela, |
| *literal em* `_apagar_um` | 0.05 s | *novo* | FIXO | [deletador.py:485](blazesbot/bot/deletador.py#L485) | `_apagar_um` | Uma exclusão completa: item -> ícone -> Ok. |
| `PASSO_DA_ESPERA_DO_RESETER` | 1 s | *novo* | PASSO | [espera_do_reseter.py:80](blazesbot/bot/espera_do_reseter.py#L80) | `esperar_o_reseter` | Cadência da espera pela conta de reset. |
| `INTERVALO_DO_AVISO_DO_RESETER` | 300 s (5 min) | *novo* | FIXO | [espera_do_reseter.py:87](blazesbot/bot/espera_do_reseter.py#L87) | `esperar_o_reseter` | De quanto em quanto tempo repetir o aviso enquanto a trava dura. |
| `PASSO_DA_FADA` | 0.1 s | *novo* | PASSO | [fada.py:80](blazesbot/bot/fada.py#L80) | `rodar` | Cadência do laço da Fada quando não há nada a fazer. |
| `TETO_PARA_O_ALVO_VIRAR` | 0.4 s | *novo* | TETO | [fada.py:87](blazesbot/bot/fada.py#L87) | `_clique_saiu_errado` | Depois do clique no retrato, quanto esperar a memória mostrar o alvo novo. |
| `PASSO_DA_CONFERENCIA_DO_ALVO` | 0.02 s | *novo* | PASSO | [fada.py:88](blazesbot/bot/fada.py#L88) | `_clique_saiu_errado` |  |
| `TETO_DA_CURA_SEGUNDOS` | 20 s | *novo* | TETO | [fada.py:95](blazesbot/bot/fada.py#L95) | `_me_defender, _curar (+1)` | Quanto tempo insistir numa cura antes de desistir daquela vítima. |
| `ESPERA_ENTRE_CURAS` | 0.34 s | *novo* | FIXO | [fada.py:102](blazesbot/bot/fada.py#L102) | `_me_defender, _curar (+1)` | Entre uma tecla de cura e a seguinte. |
| `ESPERA_DEPOIS_DE_ERRAR` | 0.333 s | *novo* | FIXO | [fada.py:120](blazesbot/bot/fada.py#L120) | `_atender` | Depois de uma tentativa que não pegou, espera antes da seguinte. |
| `SEGUNDOS_ENTRE_TENTATIVAS` | 1 s | *novo* | FIXO | [fada_montagem.py:35](blazesbot/bot/fada_montagem.py#L35) | `rodar_a_fada` | Respiro quando a Fada não consegue nem começar (memória fechada, por exemplo). |
| `SEGUNDOS_ENTRE_CUIDADOS` | 30 s | = | FIXO | [fada_ociosa.py:45](blazesbot/bot/fada_ociosa.py#L45) | `cuidados` | De quanto em quanto tempo a Fada cuida do pet e da bolsa, ESTANDO OCIOSA. |
| `SEGUNDOS_ENTRE_CONFERENCIAS_DO_PONTO` | 3 s | = | FIXO | [fada_ociosa.py:59](blazesbot/bot/fada_ociosa.py#L59) | `voltar_ao_ponto_se_preciso` | De quanto em quanto tempo a Fada confere se saiu do ponto inicial. |
| `SEGUNDOS_DE_CUIDADO_LONGO` | 12 s | = | FIXO | [fada_ociosa.py:66](blazesbot/bot/fada_ociosa.py#L66) | `cuidados` | Por quanto tempo vale a batida dada ANTES de uma tarefa longa da ociosa. |
| `TETO_DO_FEITICO` | 8 s | *novo* | TETO | [fada_reviver.py:77](blazesbot/bot/fada_reviver.py#L77) | `_esperar_levantar` | Quanto se espera o feitiço pegar depois de apertar a tecla. |
| `PASSO_DA_ESPERA` | 0.2 s | *novo* | PASSO | [fada_reviver.py:80](blazesbot/bot/fada_reviver.py#L80) | `reviver, _esperar_levantar` | Passo entre duas perguntas enquanto o feitiço prepara. |
| `SEGUNDOS_POR_TENTATIVA_DE_ENCOSTAR` | 1.8 s | *novo* | FIXO | [entrada.py:90](blazesbot/bot/hh/entrada.py#L90) | `_ir_ao_ponto_de_abrir_os_arredores, garantir_coordenada_da_entrada (+1)` | Quanto tempo dar a cada tentativa de encostar no ponto exato. |
| `TETO_DA_ENTRADA` | 0.12 s | *novo* | TETO | [entrada.py:167](blazesbot/bot/hh/entrada.py#L167) | `esperar_entrar` | 0,25 -> 0,12 EM 11/09/2026, E O NÚMERO SAIU DO LOG |
| `PASSO_DA_ESPERA_DA_ENTRADA` | 0.04 s | *novo* | PASSO | [entrada.py:168](blazesbot/bot/hh/entrada.py#L168) | `esperar_sair, esperar_entrar` |  |
| `TETO_DA_SAIDA` | 3 s | *novo* | TETO | [entrada.py:177](blazesbot/bot/hh/entrada.py#L177) | `esperar_sair` | A CONFIRMAÇÃO DA SAÍDA é mais generosa que a da entrada, e de propósito. |
| `TETO_DO_TELEPORTE` | 2 s | *novo* | TETO | [entrada.py:180](blazesbot/bot/hh/entrada.py#L180) | `viajar_para_a_hh, _ir_ao_ponto_de_abrir_os_arredores` | Teto da espera pelo teleporte do Fay. |
| `PASSO_DA_ESPERA_DO_TELEPORTE` | 0.08 s | *novo* | PASSO | [entrada.py:181](blazesbot/bot/hh/entrada.py#L181) | `viajar_para_a_hh, _ir_ao_ponto_de_abrir_os_arredores` |  |
| `PASSO_DO_ACOMPANHAMENTO` | 0.3 s | *novo* | PASSO | [fada.py:73](blazesbot/bot/hh/fada.py#L73) | `acompanhar` | Quanto esperar entre duas leituras enquanto acompanha o líder. |
| `INTERVALO_DE_REAFIRMAR_O_FOLLOW` | 4 s | *novo* | FIXO | [fada.py:80](blazesbot/bot/hh/fada.py#L80) | `acompanhar` | De quanto em quanto tempo reafirmar a tecla de seguir. |
| `PASSO_ESPERANDO_O_LIDER` | 0.5 s | *novo* | PASSO | [fada.py:87](blazesbot/bot/hh/fada.py#L87) | `esperar_o_lider_entrar` |  |
| *literal em* `seguir_o_lider` | 0.15 s | *novo* | FIXO | [fada.py:160](blazesbot/bot/hh/fada.py#L160) | `seguir_o_lider` | Clica no retrato do líder e aperta a tecla de seguir. |
| *literal em* `entrar` | 0.25 s | *novo* | FIXO | [fada.py:250](blazesbot/bot/hh/fada.py#L250) | `entrar` | Entra na cave. Mesma porta, mesma máquina, mesmo NPC do líder. |
| `PASSO_DENTRO_DA_CAVE` | 0.05 s | *novo* | PASSO | [routine.py:121](blazesbot/bot/hh/routine.py#L121) | `run` | Quanto esperar entre estados DENTRO da cave. |
| `PASSO_FORA_DA_CAVE` | 0.4 s | *novo* | PASSO | [routine.py:122](blazesbot/bot/hh/routine.py#L122) | `run` |  |
| `SEGUNDOS_PARA_ENGAJAR` | 5 s | *novo* | FIXO | [routine.py:141](blazesbot/bot/hh/routine.py#L141) | `_do_boss` | Quanto esperar, num ponto de batalha, para a flag de combate LIGAR. |
| *literal em* `_do_situar` | 1 s | *novo* | FIXO | [routine.py:433](blazesbot/bot/hh/routine.py#L433) | `_do_situar` | Descobre em que ponto do ciclo a conta está, e entra por ali. |
| *literal em* `_do_recuperar` | 2 s | *novo* | FIXO | [routine.py:1612](blazesbot/bot/hh/routine.py#L1612) | `_do_recuperar` | Algo saiu do roteiro. Volta a se situar, sem inventar. |
| `SEGUNDOS_POR_TENTATIVA` | 1.8 s | *novo* | FIXO | [vendedor.py:71](blazesbot/bot/hh/vendedor.py#L71) | `encostar_no_ponto_da_venda` |  |
| `RECARGA` | 5 s | = | FIXO | [hotbar.py:63](blazesbot/bot/hotbar.py#L63) | `garantir_pagina_1` | Recarga do caminho com `ctx`. Os momentos-chave acontecem em rajada -- o portão |
| `PASSO_DA_SONDA` | 0.012 s | = | PASSO | [instrumentar_clique.py:110](blazesbot/bot/instrumentar_clique.py#L110) | `_sondar_ate_mudar` | De quanto em quanto tempo a sonda fotografa o minimapa esperando o efeito. |
| `TETO_DA_SONDA` | 1.2 s | = | TETO | [instrumentar_clique.py:113](blazesbot/bot/instrumentar_clique.py#L113) | `_sondar_ate_mudar, _um_modo` | Teto da espera pelo efeito. Passou disso, o clique é dado como PERDIDO. |
| *literal em* `rodar` | 0.05 s | = | FIXO | [instrumentar_clique.py:390](blazesbot/bot/instrumentar_clique.py#L390) | `rodar` |  |
| *literal em* `main` | 8 s | = | FIXO | [instrumentar_clique.py:488](blazesbot/bot/instrumentar_clique.py#L488) | `main` |  |
| `ESPERA_PELO_SERVIDOR_FORA_DO_AR` | 30 s | *novo* | FIXO | [login_states.py:189](blazesbot/bot/login_states.py#L189) |  | Entre uma ida à lista e a seguinte com o servidor fora do ar. 30 s e não os |
| `PRAZO_PARA_A_FADA` | 60 s (1 min) | *novo* | TETO | [morte.py:54](blazesbot/bot/morte.py#L54) | `_esperar_a_fada` | Quanto o morto espera pela Fada antes de se reviver sozinho. |
| `PASSO_DA_ESPERA` | 0.3 s | *novo* | PASSO | [morte.py:64](blazesbot/bot/morte.py#L64) | `_esperar_a_fada, _esperar_ficar_de_pe (+1)` | Passo entre duas perguntas durante a espera. Tudo o que ele pergunta é |
| `CADENCIA_DO_CONVITE` | 0.5 s | *novo* | PASSO | [morte.py:72](blazesbot/bot/morte.py#L72) | `_esperar_a_fada` | Cadência da conferência do convite da Fada na TELA. |
| `TETO_PARA_O_REVIVE_PEGAR` | 10 s | *novo* | TETO | [morte.py:75](blazesbot/bot/morte.py#L75) | `_esperar_ficar_de_pe` | Quanto se espera o `hp` subir depois de um clique que deveria reviver. |
| `TETO_DA_REGENERACAO` | 60 s (1 min) | *novo* | TETO | [morte.py:82](blazesbot/bot/morte.py#L82) | `_regenerar_antes_de_andar` | Teto da regeneração sentada antes de andar de volta. |
| `TETO_DO_RETORNO` | 180 s (3 min) | *novo* | TETO | [morte.py:90](blazesbot/bot/morte.py#L90) | `montar_para_o_app, voltar_ao_ponto` | Teto da caminhada de volta ao ponto inicial. |
| `CONVITE_VALIDO_SEGUNDOS` | 60 s (1 min) | = | FIXO | [mural.py:89](blazesbot/bot/mural.py#L89) | `convite_pendente` | Validade do anúncio. Cobre a fila de resposta do outro cliente com folga; mais |
| `ACEITE_VALIDO_SEGUNDOS` | 15 s | = | FIXO | [mural.py:211](blazesbot/bot/mural.py#L211) | `aceite_pendente` | Validade do aceite. Curta de propósito: ele confirma UM convite recém-enviado, |
| `LARGADA_VALIDA_SEGUNDOS` | 5 s | *novo* | FIXO | [mural.py:295](blazesbot/bot/mural.py#L295) | `largada_pendente` | Quanto tempo uma largada anunciada continua valendo. |
| `ESTADO_VALIDO_SEGUNDOS` | 30 s | *novo* | FIXO | [mural.py:303](blazesbot/bot/mural.py#L303) | `estado_da_conta` | Quanto tempo o estado publicado por uma conta continua valendo. |
| `TETO_DA_BATIDA_LONGA` | 15 s | *novo* | TETO | [mural.py:524](blazesbot/bot/mural.py#L524) | `bater_fada` | Quanto uma batida pode valer, no MÁXIMO, quando a Fada avisa que vai sumir. |
| `SEGUNDOS_DE_MORTO_PARA_FURAR_A_FILA` | 40 s | *novo* | FIXO | [mural_da_morte.py:42](blazesbot/bot/mural_da_morte.py#L42) | `morto_ha_muito_tempo` | A partir de quantos segundos de morto a vítima FURA a fila dos feridos. |
| `PASSO_VERTICAL` | 4 s | = | PASSO | [recorte_do_time.py:90](blazesbot/bot/recorte_do_time.py#L90) | `_candidatos` |  |
| `CADENCIA_DO_VIGIA` | 6 s | *novo* | PASSO | [sentinela.py:129](blazesbot/bot/sentinela.py#L129) | `__init__` | O ORÇAMENTO DE 20 SEGUNDOS, repartido |
| `TETO_DA_FATIA_DE_ESPERA` | 0.25 s | = | TETO | [supervisor.py:91](blazesbot/bot/supervisor.py#L91) | `wait` | Teto de uma fatia dentro de `_AnyEvent.wait`. É REDE, não o caminho normal -- |
| `TETO_DA_ESPERA_PELA_FADA` | 60 s (1 min) | *novo* | TETO | [supervisor.py:100](blazesbot/bot/supervisor.py#L100) | `_rodar_modo_app, chamar_a_fada` | Quanto uma vítima espera pela Fada antes de voltar para a poção. |
| *literal em* `_sleep_interruptible` | 0.125 s | = | FIXO | [supervisor.py:364](blazesbot/bot/supervisor.py#L364) | `_sleep_interruptible` | Espera até `seconds`, acordando se o usuário mandar parar. |
| *literal em* `_launch_client` | 1 s | = | FIXO | [supervisor.py:452](blazesbot/bot/supervisor.py#L452) | `_launch_client` | Lança o Client.bat e devolve o PID da nova instância. |
| *literal em* `_find_window` | 1 s | = | FIXO | [supervisor.py:469](blazesbot/bot/supervisor.py#L469) | `_find_window` | Localiza a janela de nível superior pertencente ao PID. |
| *literal em* `_run_session` | 1.5 s | = | FIXO | [supervisor.py:1073](blazesbot/bot/supervisor.py#L1073) | `_run_session` | Uma sessão: obter uma janela, logar se preciso, e operar. |
| *literal em* `_operate` | 2.5 s | *novo* | FIXO | [supervisor.py:1368](blazesbot/bot/supervisor.py#L1368) | `_operate` | Opera a conta logada, respeitando o farm ligado/desligado ao vivo. |
| *literal em* `_operate` | 2.5 s | *novo* | FIXO | [supervisor.py:1389](blazesbot/bot/supervisor.py#L1389) | `_operate` | Opera a conta logada, respeitando o farm ligado/desligado ao vivo. |
| *literal em* `_operate` | 0.5 s | = | FIXO | [supervisor.py:1488](blazesbot/bot/supervisor.py#L1488) | `_operate` | Opera a conta logada, respeitando o farm ligado/desligado ao vivo. |
| *literal em* `_publicar_o_proprio_id` | 0.3 s | *novo* | FIXO | [supervisor.py:1733](blazesbot/bot/supervisor.py#L1733) | `_publicar_o_proprio_id` | o alvo leva ~0,1 s para virar |
| *literal em* `chamar_a_fada` | 0.2 s | *novo* | FIXO | [supervisor.py:2232](blazesbot/bot/supervisor.py#L2232) | `chamar_a_fada` | Pede cura à Fada do time e espera. `False` = não há Fada, beba poção. |
| `ESPERA_DO_MENU` | 0.35 s | = | FIXO | [team.py:165](blazesbot/bot/team.py#L165) | `_enviar_convite` | Tempo para o menu de contexto aparecer depois do clique direito. |
| `ESPERA_PELA_RESPOSTA` | 4 s | = | FIXO | [team.py:170](blazesbot/bot/team.py#L170) | `montar_time` | Quanto esperar a outra conta aceitar. Ela recebe o anúncio interno e clica no |
| `PASSO_DA_ESPERA_DO_TIME` | 0.1 s | = | PASSO | [team.py:178](blazesbot/bot/team.py#L178) | `montar_time` | De quanto em quanto tempo conferir se o time já formou. |
| *literal em* `_abrir_lista` | 0.6 s | = | FIXO | [team.py:336](blazesbot/bot/team.py#L336) | `_abrir_lista` | Abre a lista de amigos e vai para a aba Block. |
| *literal em* `_abrir_lista` | 0.45 s | = | FIXO | [team.py:341](blazesbot/bot/team.py#L341) | `_abrir_lista` | Abre a lista de amigos e vai para a aba Block. |
| *literal em* `_fechar_janelas` | 0.35 s | = | FIXO | [team.py:369](blazesbot/bot/team.py#L369) | `_fechar_janelas` | Fecha a caixa de nick e a lista de amigos, CONFIRMANDO que fecharam. |
| *literal em* `_fechar_janelas` | 0.4 s | = | FIXO | [team.py:377](blazesbot/bot/team.py#L377) | `_fechar_janelas` | Fecha a caixa de nick e a lista de amigos, CONFIRMANDO que fecharam. |
| *literal em* `_fechar_janelas` | 0.3 s | = | FIXO | [team.py:385](blazesbot/bot/team.py#L385) | `_fechar_janelas` | Fecha a caixa de nick e a lista de amigos, CONFIRMANDO que fecharam. |
| *literal em* `_limpar_lista` | 0.15 s | = | FIXO | [team.py:415](blazesbot/bot/team.py#L415) | `_limpar_lista` | Remove todas as entradas da Block list. |
| *literal em* `_limpar_lista` | 0.25 s | = | FIXO | [team.py:417](blazesbot/bot/team.py#L417) | `_limpar_lista` | Remove todas as entradas da Block list. |
| *literal em* `_limpar_lista` | 0.2 s | = | FIXO | [team.py:421](blazesbot/bot/team.py#L421) | `_limpar_lista` | Remove todas as entradas da Block list. |
| *literal em* `_adicionar_nick` | 0.5 s | = | FIXO | [team.py:432](blazesbot/bot/team.py#L432) | `_adicionar_nick` | Adiciona um nick à Block list pelo botão Block. |
| *literal em* `_adicionar_nick` | 0.2 s | = | FIXO | [team.py:440](blazesbot/bot/team.py#L440) | `_adicionar_nick` | Adiciona um nick à Block list pelo botão Block. |
| *literal em* `_adicionar_nick` | 0.1 s | = | FIXO | [team.py:442](blazesbot/bot/team.py#L442) | `_adicionar_nick` | Adiciona um nick à Block list pelo botão Block. |
| *literal em* `_adicionar_nick` | 0.2 s | = | FIXO | [team.py:444](blazesbot/bot/team.py#L444) | `_adicionar_nick` | Adiciona um nick à Block list pelo botão Block. |
| *literal em* `_adicionar_nick` | 0.6 s | = | FIXO | [team.py:446](blazesbot/bot/team.py#L446) | `_adicionar_nick` | Adiciona um nick à Block list pelo botão Block. |
| *literal em* `_enviar_convite` | 0.5 s | = | FIXO | [team.py:619](blazesbot/bot/team.py#L619) | `_enviar_convite` | Envia o convite pelo MENU DE CONTEXTO da entrada na Block list. |
| *literal em* `sair_do_time` | 0.4 s | = | FIXO | [team.py:782](blazesbot/bot/team.py#L782) | `sair_do_time` | Sai do time por DOIS CLIQUES medidos no cliente. |
| *literal em* `sair_do_time` | 0.5 s | = | FIXO | [team.py:797](blazesbot/bot/team.py#L797) | `sair_do_time` | Sai do time por DOIS CLIQUES medidos no cliente. |
| *literal em* `_aceitar` | 0.5 s | = | FIXO | [team.py:1123](blazesbot/bot/team.py#L1123) | `_aceitar` |  |
| *literal em* `_recusar` | 0.5 s | = | FIXO | [team.py:1130](blazesbot/bot/team.py#L1130) | `_recusar` |  |
| `ESPERA_DEPOIS_DO_CLIQUE` | 0.35 s | = | FIXO | [teste_do_cursor.py:100](blazesbot/bot/teste_do_cursor.py#L100) | `_uma_fase` |  |
| *literal em* `main` | 8 s | = | FIXO | [teste_do_cursor.py:476](blazesbot/bot/teste_do_cursor.py#L476) | `main` |  |
| `CADENCIA_DAS_CONFERENCIAS` | 60 s (1 min) | *novo* | PASSO | [time_do_app.py:116](blazesbot/bot/time_do_app.py#L116) | `montar_se_for_a_hora` | De quanto em quanto tempo o líder confere se o time está completo. |
| `TETO_DO_MENU` | 0.8 s | *novo* | TETO | [time_do_app.py:638](blazesbot/bot/time_do_app.py#L638) | `pick_mode_free` | TETO da espera pelo menu e pelo submenu aparecerem. TETO, não gasto: quem |
| `PASSO_DO_MENU` | 0.06 s | *novo* | PASSO | [time_do_app.py:639](blazesbot/bot/time_do_app.py#L639) | `pick_mode_free` |  |
| `PASSO_DA_ESPERA_DO_DIALOGO` | 0.08 s | = | PASSO | [ui_do_jogo.py:150](blazesbot/bot/ui_do_jogo.py#L150) | `_esperar_o_dialogo` | Diálogo do NPC aparecer. Era 0,30 s fixos, gastos inteiros mesmo quando o |
| `LIMITE_INICIAL_DA_ESPERA_DO_DIALOGO` | 0.65 s | = | TETO | [ui_do_jogo.py:189](blazesbot/bot/ui_do_jogo.py#L189) | `limite_da_espera_do_dialogo` | TETO DA ESPERA DO DIÁLOGO -- ajustado pelo que foi MEDIDO, não chutado |
| `LIMITE_MINIMO_DA_ESPERA_DO_DIALOGO` | 0.18 s | = | TETO | [ui_do_jogo.py:193](blazesbot/bot/ui_do_jogo.py#L193) | `limite_da_espera_do_dialogo` | Piso: o valor que valia antes. Abaixo disto não se aperta nem com evidência -- |
| `LIMITE_MAXIMO_DA_ESPERA_DO_DIALOGO` | 0.6 s | = | TETO | [ui_do_jogo.py:197](blazesbot/bot/ui_do_jogo.py#L197) | `limite_da_espera_do_dialogo` | Teto do teto. Passado disto, o diálogo não vai abrir mesmo, e insistir só |
| `TETO_DO_DESESPERO` | 1.2 s | *novo* | TETO | [ui_do_jogo.py:247](blazesbot/bot/ui_do_jogo.py#L247) | `_afrouxar_o_teto` | O teto do desespero. Passado daqui não é mais latência: é NPC errado, cliente |
| `LIMITE_DA_ESPERA_DO_DIALOGO_LENTA` | 0.65 s | = | TETO | [ui_do_jogo.py:271](blazesbot/bot/ui_do_jogo.py#L271) | `limite_da_espera_do_dialogo_lenta` | Diálogo aparecer na REDESCOBERTA, depois de cada clique direito. Era `tick(1.3)` |
| `ESPERA_DEPOIS_DO_LINK` | 0.2 s | = | FIXO | [ui_do_jogo.py:293](blazesbot/bot/ui_do_jogo.py#L293) | `_abrir_dialogo_e_clicar` | Servidor processar o pedido de entrada. Zero na disputa: quem confirma a entrada |
| `INTERVALO_DO_GUARDA_DE_JANELA` | 3 s | *novo* | FIXO | [ui_do_jogo.py:329](blazesbot/bot/ui_do_jogo.py#L329) | `_desobstruir_se_faz_tempo` | CLIQUE ENGOLIDO = JANELA NA FRENTE. E O GUARDA VALE PARA A SAIDA TAMBEM |
| `PASSO_DA_ESPERA_DO_PAINEL` | 0.08 s | = | PASSO | [ui_do_jogo.py:367](blazesbot/bot/ui_do_jogo.py#L367) | `_esperar_o_painel` | Passo e teto da espera pelo painel aparecer. Cada volta custa uma captura de |
| `LIMITE_DA_ESPERA_DO_PAINEL` | 0.8 s | = | TETO | [ui_do_jogo.py:373](blazesbot/bot/ui_do_jogo.py#L373) | `abrir_surroundings, _esperar_o_painel` | O teto é EXATAMENTE a espera fixa que havia antes (1,2 s), e isso é de propósito: |
| `ESPERA_DA_TROCA_DE_ABA` | 0.05 s | = | FIXO | [ui_do_jogo.py:377](blazesbot/bot/ui_do_jogo.py#L377) | `abrir_surroundings` | Assentar depois de clicar na aba NPC. Não é "esperar a aba renderizar": é só dar |
| `PASSO_DA_ESPERA_DO_RESULTADO` | 0.08 s | = | PASSO | [ui_do_jogo.py:395](blazesbot/bot/ui_do_jogo.py#L395) | `_esperar_resultado_da_busca` | De quanto em quanto tempo perguntar à memória se o resultado apareceu, e por |
| `LIMITE_DA_ESPERA_DO_RESULTADO` | 0.8 s | = | TETO | [ui_do_jogo.py:396](blazesbot/bot/ui_do_jogo.py#L396) | `_esperar_resultado_da_busca` |  |
| `ESPERA_CEGA_DO_RESULTADO` | 0.3 s | = | FIXO | [ui_do_jogo.py:422](blazesbot/bot/ui_do_jogo.py#L422) | `_esperar_resultado_da_busca` | Quando a leitura de arredores por memória não funciona neste cliente, a lista |
| `PASSO_DA_ESPERA_DO_ANDAR` | 0.04 s | = | PASSO | [ui_do_jogo.py:465](blazesbot/bot/ui_do_jogo.py#L465) | `_saiu_do_lugar` | Depois de clicar no resultado o personagem já saiu andando -- o pathfinding do |
| `LIMITE_DA_ESPERA_DO_ANDAR` | 0.4 s | = | TETO | [ui_do_jogo.py:466](blazesbot/bot/ui_do_jogo.py#L466) | `ir_para_resultado, _saiu_do_lugar` |  |
| `ESPERA_DEPOIS_DE_CLICAR_NO_RESULTADO` | 0.15 s | = | FIXO | [ui_do_jogo.py:467](blazesbot/bot/ui_do_jogo.py#L467) | `_saiu_do_lugar` |  |
| `INTERVALO_ENTRE_USOS_DO_PAINEL` | 2 s | = | FIXO | [ui_do_jogo.py:549](blazesbot/bot/ui_do_jogo.py#L549) | `_respeitar_a_cadencia_do_painel` | CADÊNCIA MÍNIMA ENTRE UM USO DO PAINEL DE ARREDORES E O SEGUINTE |
| `PASSO_DA_ESPERA_DA_CHEGADA` | 0.25 s | = | PASSO | [ui_do_jogo.py:573](blazesbot/bot/ui_do_jogo.py#L573) | `_esperar_chegar` | Passo da leitura de posição enquanto se espera a chegada. Ler memória custa |
| `PASSO_DA_ESPERA_DO_FECHAMENTO` | 0.04 s | = | PASSO | [ui_do_jogo.py:591](blazesbot/bot/ui_do_jogo.py#L591) | `fechar_surroundings` |  |
| `LIMITE_DA_ESPERA_DO_FECHAMENTO` | 0.4 s | = | TETO | [ui_do_jogo.py:592](blazesbot/bot/ui_do_jogo.py#L592) | `fechar_surroundings` |  |
| `ESPERA_DEPOIS_DE_FECHAR` | 0.2 s | = | FIXO | [ui_do_jogo.py:593](blazesbot/bot/ui_do_jogo.py#L593) |  |  |
| `ESPERA_ANTES_DE_CONFERIR` | 0.15 s | = | FIXO | [ui_do_jogo.py:595](blazesbot/bot/ui_do_jogo.py#L595) |  |  |
| `PASSOS_DE_ROLAGEM` | 12 s | *novo* | PASSO | [ui_do_jogo.py:621](blazesbot/bot/ui_do_jogo.py#L621) | `rolar_o_dialogo` | Quantas rolagens no máximo antes de aceitar que o link não está na lista. |
| `ESPERA_DA_ROLAGEM` | 0.08 s | *novo* | FIXO | [ui_do_jogo.py:626](blazesbot/bot/ui_do_jogo.py#L626) | `rolar_o_dialogo` | A lista redesenhar depois do clique na seta. Uma volta de laço do cliente, não |
| *literal em* `resetar_visao` | 0.175 s | = | FIXO | [ui_do_jogo.py:753](blazesbot/bot/ui_do_jogo.py#L753) | `resetar_visao` | Aperta o View Reset para recentrar a câmera. |
| *literal em* `buscar_npc` | 0.5 s | = | FIXO | [ui_do_jogo.py:1213](blazesbot/bot/ui_do_jogo.py#L1213) | `buscar_npc` | Busca um NPC e devolve o primeiro resultado, conferido. |
| *literal em* `fechar_dialogo` | 0.3 s | = | FIXO | [ui_do_jogo.py:1750](blazesbot/bot/ui_do_jogo.py#L1750) | `fechar_dialogo` |  |
| *literal em* `clicar_link` | 0.75 s | = | FIXO | [ui_do_jogo.py:1769](blazesbot/bot/ui_do_jogo.py#L1769) | `clicar_link` | Clica num link do diálogo, localizado pelo texto. Devolve o ponto. |
| *literal em* `clicar_link` | 0.4 s | = | FIXO | [ui_do_jogo.py:1771](blazesbot/bot/ui_do_jogo.py#L1771) | `clicar_link` | Clica num link do diálogo, localizado pelo texto. Devolve o ponto. |
| `SEGUNDOS_ANDANDO_ANTES` | 0.5 s | = | FIXO | [velocidade.py:45](blazesbot/bot/velocidade.py#L45) | `usar_se_puder` | Quanto o personagem precisa ter andado antes de valer a pena acionar. |
| `ESPERA_DO_TELEPORTE` | 5 s | = | TETO | [vendedor.py:99](blazesbot/bot/vendedor.py#L99) |  | TETO da espera do teleporte -- não é mais o tempo gasto, é o limite. |
| `PASSO_DA_ESPERA_DO_TELEPORTE` | 0.12 s | *novo* | PASSO | [vendedor.py:103](blazesbot/bot/vendedor.py#L103) |  | Entre leituras. A posição vem da memória e custa microssegundos; o passo é |
| `ESPERA_ENTRE_TENTATIVAS_DE_RETORNO` | 8 s | = | FIXO | [vendedor.py:135](blazesbot/bot/vendedor.py#L135) |  |  |
| `SEGUNDOS_POR_TENTATIVA_NO_VENDEDOR` | 4 s | = | FIXO | [vendedor.py:144](blazesbot/bot/vendedor.py#L144) |  |  |
| `ESPERA_ENTRE_CLIQUES_DA_VENDA` | 0.065 s | = | FIXO | [vendedor.py:213](blazesbot/bot/vendedor.py#L213) | `_clicar_no_slot` | Espera entre um clique e o seguinte na grade. Era 200 ms. |
| `ESPERA_PARA_CONFIRMAR_VAZIO` | 0.5 s | = | FIXO | [vendedor.py:284](blazesbot/bot/vendedor.py#L284) | `_confirmar_slot_vazio, sell_from_slot` | As leituras de confirmação são ESPAÇADAS, não coladas: veja |
| `ESPERA_ANTES_DO_SELL` | 0.4 s | = | FIXO | [vendedor.py:316](blazesbot/bot/vendedor.py#L316) | `sell_from_slot` | O RESPIRO EM VOLTA DO BOTÃO "SELL" |
| `ESPERA_DEPOIS_DO_SELL` | 0.6 s | = | FIXO | [vendedor.py:317](blazesbot/bot/vendedor.py#L317) | `_vender_a_lista, _bolsa_depois_do_sell` |  |
| `PASSO_DA_CONFERENCIA_DA_VENDA` | 0.05 s | *novo* | PASSO | [vendedor.py:324](blazesbot/bot/vendedor.py#L324) | `_bolsa_depois_do_sell` |  |
| *literal em* `_tentar_abrir_a_venda` | 0.3 s | = | FIXO | [vendedor.py:512](blazesbot/bot/vendedor.py#L512) | `_tentar_abrir_a_venda` |  |
| *literal em* `_dismiss_confirm` | 0.125 s | = | FIXO | [vendedor.py:566](blazesbot/bot/vendedor.py#L566) | `_dismiss_confirm` | Fecha a caixa "It's precious item, please confirm!", se aberta. |
| `ESPERA_PELA_MORTE` | 2 s | *novo* | FIXO | [watchdog.py:293](blazesbot/bot/watchdog.py#L293) | `kill_client` | Quanto tempo esperar o Windows realmente derrubar o processo depois do |
| `PASSO_DA_CONFIRMACAO_DA_MORTE` | 0.05 s | *novo* | PASSO | [watchdog.py:297](blazesbot/bot/watchdog.py#L297) | `_morreu` | Passo entre as conferências de "já morreu?". Fatia curta porque a resposta |


## CORE — capacidades compartilhadas

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `ESPERA_ENTRE_CLIQUES` | 0.1 s | = | FIXO | [catador.py:96](blazesbot/core/catador.py#L96) | `catar` | Espera entre dois cliques direitos. Também do T-R0XX. Não é tempo de abrir a |
| `ESPERA_APOS_PEGAR` | 4 s | = | FIXO | [catador.py:112](blazesbot/core/catador.py#L112) | `_pegar` | Espera entre o clique no botão e a próxima conferência. NÚMERO DO USUÁRIO. |
| `TETO_DE_CLIQUES` | 10 s | = | TETO | [catador.py:124](blazesbot/core/catador.py#L124) | `_pegar` | Teto de cliques no botão. REDE DE SEGURANÇA, não estratégia -- mesmo papel do |
| `PASSO_ENTRE_RETRATOS_DO_TIME` | 80 s (1 min) | *novo* | PASSO | [coords.py:112](blazesbot/core/coords.py#L112) |  |  |
| `INTERVALO_DE_DESPEJO` | 30 s | *novo* | FIXO | [cronometro.py:98](blazesbot/core/cronometro.py#L98) | `_laco_do_despejo` | De quanto em quanto tempo a thread despeja o que foi acumulado. |
| `TETO_DO_BLOQUEIO_MS` | 80 s (1 min) | = | TETO | [inputs.py:90](blazesbot/core/inputs.py#L90) | `passar_o_mouse, _click_sendmessage_rapido (+1)` | TETO do bloqueio do mouse físico, em milissegundos -- e TETO, não gasto: o |
| `INTERVALO_ENTRE_CLIQUES_DIREITOS` | 0.044 s | = | FIXO | [inputs.py:229](blazesbot/core/inputs.py#L229) | `right_click` | Espaço entre um clique e o seguinte. Curto de propósito: a aposta é que a |
| `SEGUNDOS_ENTRE_CONFERENCIAS_DO_PROCESSO` | 2 s | = | FIXO | [inputs.py:317](blazesbot/core/inputs.py#L317) | `_motivo_para_nao_enviar` | De quanto em quanto tempo o NOME do processo é reconferido. |
| *literal em* `_click_postmessage_com_delay` | 0.015 s | = | FIXO | [inputs.py:882](blazesbot/core/inputs.py#L882) | `_click_postmessage_com_delay` | 5ms (insuficiente) |
| *literal em* `_click_sendmessage_rapido` | 0.002 s | = | FIXO | [inputs.py:968](blazesbot/core/inputs.py#L968) | `_click_sendmessage_rapido` | TESTE 2 (2026-08-14): SendMessage com sleep reduzido de 15ms → 1ms. |
| *literal em* `_click_sendmessage_rapido` | 0.002 s | = | FIXO | [inputs.py:978](blazesbot/core/inputs.py#L978) | `_click_sendmessage_rapido` | TESTE 2 (2026-08-14): SendMessage com sleep reduzido de 15ms → 1ms. |
| *literal em* `_click_rapido_reafirmado` | 0.002 s | = | FIXO | [inputs.py:1034](blazesbot/core/inputs.py#L1034) | `_click_rapido_reafirmado` | O rápido, mais a coordenada REAFIRMADA entre o down e o up. |
| *literal em* `_click_postmessage_puro` | 0.002 s | = | FIXO | [inputs.py:1143](blazesbot/core/inputs.py#L1143) | `_click_postmessage_puro` | AS QUATRO mensagens por `PostMessageW`. Nenhuma síncrona. |
| `TIMEOUT_DA_SONDA_MS` | 1500 s (25 min) | *novo* | TETO | [janelas.py:116](blazesbot/core/janelas.py#L116) | `janela_responde` | A SONDA DE TRAVAMENTO -- "Não Está Respondendo", medido em vez de suposto |
| `INTERVALO_ENTRE_LIMPEZAS` | 3600 s (60 min) | *novo* | FIXO | [log_limitado.py:89](blazesbot/core/log_limitado.py#L89) | `_limpar_de_tempos_em_tempos` | De quanto em quanto tempo varrer a pasta do arquivo morto. |
| `SEGUNDOS_DE_SILENCIO_ANTES_DE_COMPRIMIR` | 60 s (1 min) | *novo* | FIXO | [log_limitado.py:97](blazesbot/core/log_limitado.py#L97) | `_esta_quieto` | Quanto tempo um arquivo precisa estar QUIETO para poder ser comprimido. |
| `TETO_DA_PROVA_DA_CAMERA` | 1 s | = | TETO | [memory.py:384](blazesbot/core/memory.py#L384) | `_esperar_o_termometro` | Teto da espera pelo termômetro depois de uma escrita na câmera. |
| `PASSO_DA_PROVA_DA_CAMERA` | 0.05 s | = | PASSO | [memory.py:385](blazesbot/core/memory.py#L385) | `_esperar_o_termometro` |  |
| `PASSO_ENTRE_MEMBROS` | 136 s (2 min) | *novo* | PASSO | [memory.py:415](blazesbot/core/memory.py#L415) | `time_do_jogo, vida_do_time` |  |
| *literal em* `_ensure_hook_installed` | 0.05 s | = | FIXO | [mouse_shield.py:223](blazesbot/core/mouse_shield.py#L223) | `_ensure_hook_installed` | Sobe o hook uma vez. NADA aqui bloqueia o callback. |
| `SEGUNDOS_PARA_A_COMIDA_SER_USADA` | 4 s | *novo* | FIXO | [pet.py:159](blazesbot/core/pet.py#L159) | `falta_da_comida` | 1,5 -> 4,0 EM 16/09/2026: O DEFEITO NUNCA FOI CONSERTADO, SÓ ENCURTADO |
| `SEGUNDOS_NO_MAPA_ANTES_DE_ALIMENTAR` | 30 s | *novo* | FIXO | [pet.py:200](blazesbot/core/pet.py#L200) | `deve_alimentar` | QUANTO TEMPO NO MAPA ANTES DE ALIMENTAR -- o defeito de 15 e 16/09/2026 |
| `LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS` | 15 s | *novo* | TETO | [pet.py:296](blazesbot/core/pet.py#L296) | `a_fome_e_urgente` | QUANTO ATRASO A REFEIÇÃO AGUENTA ANTES DE FURAR O VETO DA CAVE |
| `CADENCIA_DAS_TENTATIVAS_DE_COMIDA` | 30 s | *novo* | PASSO | [pet.py:309](blazesbot/core/pet.py#L309) | `tentativa_liberada` | Entre duas TENTATIVAS de alimentar depois de o prazo estourar. |
| `INTERVALO_MINIMO` | 30 s | = | FIXO | [petbug.py:227](blazesbot/core/petbug.py#L227) | `aplicar_patch` | Tempos |
| `SEGUNDOS_PARA_A_JANELA_ABRIR` | 10 s | = | FIXO | [petbug.py:230](blazesbot/core/petbug.py#L230) | `_abrir_o_programa` | Espera pela janela aparecer depois de lançar o programa. |
| `SEGUNDOS_PARA_O_PROGRAMA_MORRER` | 3 s | = | FIXO | [petbug.py:233](blazesbot/core/petbug.py#L233) | `aplicar_patch` | Espera o processo antigo MORRER antes de abrir o novo. Curto: é um formulário |
| `SEGUNDOS_PARA_O_LOG_CONFIRMAR` | 5 s | = | FIXO | [petbug.py:235](blazesbot/core/petbug.py#L235) | `aplicar_patch, _esperar_a_confirmacao` | Espera pela confirmação no log depois do clique. |
| `FATIA_DA_ESPERA` | 0.25 s | = | PASSO | [petbug.py:236](blazesbot/core/petbug.py#L236) | `aplicar_patch, _abrir_o_programa (+1)` |  |
| `SEGUNDOS_POR_TENTATIVA_NA_FAY` | 1.8 s | = | FIXO | [stone_city.py:55](blazesbot/core/stone_city.py#L55) |  |  |
| `TETO_PARA_O_ALVO_TROCAR` | 0.35 s | *novo* | TETO | [target_hybrid.py:692](blazesbot/core/target_hybrid.py#L692) | `esperar_o_alvo_trocar` | Teto da espera. Passado isto, a tecla nao pegou -- insistir e trabalho do |
| `PASSO_DA_CONFIRMACAO_DO_TAB` | 0.01 s | *novo* | PASSO | [target_hybrid.py:697](blazesbot/core/target_hybrid.py#L697) | `esperar_o_alvo_trocar` | De quanto em quanto tempo perguntar. A leitura do id e UM `read_int` (~1 us): |
| `SEGUNDOS_ATE_O_ESC` | 30 s | = | FIXO | [teclado_mudo.py:84](blazesbot/core/teclado_mudo.py#L84) | `o_que_fazer` | Quanto tempo as duas teclas precisam estar mudas antes de o ESC sair. |
| `SEGUNDOS_ATE_O_RELOGIN` | 300 s (5 min) | = | FIXO | [teclado_mudo.py:95](blazesbot/core/teclado_mudo.py#L95) | `o_que_fazer` | Quanto tempo mudo até declarar queda e mandar relogar. |
| `SEGUNDOS_ENTRE_RELOGINS` | 900 s (15 min) | = | FIXO | [teclado_mudo.py:103](blazesbot/core/teclado_mudo.py#L103) | `o_que_fazer` | Espaço mínimo entre dois relogins automáticos por teclado mudo. |
| `SEGUNDOS_ENTRE_AVISOS` | 60 s (1 min) | = | FIXO | [teclado_mudo.py:225](blazesbot/core/teclado_mudo.py#L225) | `avisar` | De quanto em quanto tempo o TAB MUDO volta a falar -- 06/09/2026. |
| `PASSO_DA_AMOSTRAGEM_DO_QUADRO` | 8 s | *novo* | PASSO | [captura.py:27](blazesbot/core/vision/captura.py#L27) | `frame_is_blank` | De quantos em quantos pixels o `frame_is_blank` amostra o quadro. |
| `SEGUNDOS_PARA_CHEGAR` | 5 s | = | TETO | [volta_ao_ponto.py:44](blazesbot/core/volta_ao_ponto.py#L44) |  | Teto da caminhada de volta ao ponto. |


## OUTROS

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `PET_FEED_MINUTOS_MIN` | 40 s | *novo* | FIXO | [config.py:275](blazesbot/config.py#L275) | `pet_feed_na_faixa, validate` | FAIXA FECHADA DO INTERVALO DE COMIDA (26/08/2026, decisão do usuário). |
| `PET_FEED_MINUTOS_MAX` | 60 s (1 min) | *novo* | TETO | [config.py:276](blazesbot/config.py#L276) | `pet_feed_na_faixa, validate` |  |
| `PASSOS_DO_APP` | 20 s | **16 s** ⚠ | PASSO | [config.py:488](blazesbot/config.py#L488) | `_app_from_dict` | Linhas oferecidas na aba APP. Dezesseis cobre com folga a macro mais longa que |
| `MINIMO_DELAY_MS` | 100 s (2 min) | *novo* | FIXO | [config.py:507](blazesbot/config.py#L507) | `segundos_para_ms, ms_para_segundos` | Espera mínima de QUALQUER campo de tempo do APP, em milissegundos. |
| `SPEED_DURACAO_SEGUNDOS` | 30 s | = | FIXO | [config.py:877](blazesbot/config.py#L877) |  | Skill de velocidade da montaria, valores do jogo. Ficam aqui e não na |
| `INTERVALO_DE_DESCARGA_MS` | 200 s (3 min) | = | FIXO | [main_window.py:96](blazesbot/gui/main_window.py#L96) | `__init__` | Cadência com que a interface esvazia a fila de log. 5 vezes por segundo é |
| *literal em* `_limpar_a_saida_anterior` | 3 s | *novo* | FIXO | [empacotar.py:115](blazesbot/tools/empacotar.py#L115) | `_limpar_a_saida_anterior` | A pasta da entrega anterior sai ANTES de o PyInstaller começar. |
| `PASSO` | 0.25 s | = | PASSO | [ler_camera.py:50](blazesbot/tools/ler_camera.py#L50) | `run_ler_camera` | Cadência da leitura. Barata: são 8 leituras de 4 bytes por volta. |
| `SEGUNDOS_PADRAO` | 300 s (5 min) | = | TETO | [ler_camera.py:53](blazesbot/tools/ler_camera.py#L53) | `run_ler_camera` | Teto padrão, para a ferramenta fechar sozinha se você esquecer dela aberta. |
| `PASSO` | 0.1 s | *novo* | PASSO | [vigiar_combate.py:48](blazesbot/tools/vigiar_combate.py#L48) | `run_vigiar_combate` | Cadência da leitura. É memória pura -- algumas leituras de 4 bytes por volta, |
| `SEGUNDOS_PADRAO` | 900 s (15 min) | *novo* | TETO | [vigiar_combate.py:51](blazesbot/tools/vigiar_combate.py#L51) | `run_vigiar_combate` | Teto padrão, para a ferramenta fechar sozinha se você esquecer dela aberta. |
| `SEGUNDOS_ENTRE_ECOS` | 5 s | *novo* | FIXO | [vigiar_combate.py:58](blazesbot/tools/vigiar_combate.py#L58) | `run_vigiar_combate` | De quanto em quanto tempo repetir uma linha que NÃO mudou. |


---

## Se você mudou um tempo e deu errado

1. Ache a linha aqui pelo nome (ou pelo arquivo).
2. A coluna **ORIGINAL** com `⚠` traz o valor de referência.
3. Volte para ele no arquivo apontado pela coluna ONDE.

O ponto de restauração vive em `docs/tempos-originais.json`.

**Ele NÃO é atualizado sozinho, e isso é de propósito**: se toda geração
refotografasse os valores, o "original" seria sempre o de agora e o arquivo não
serviria para nada. Refotografar é ato deliberado:

```python
from blazesbot.core.indice_de_tempos import extrair, gravar_originais
gravar_originais(extrair())
```

Faça isso **só** quando um valor novo já estiver provado em produção e você
quiser que ele passe a ser a referência.

## O que este catálogo NÃO cobre

* **Tempo que vem da configuração** (`attack_delay`, `max_fight_seconds`,
  `launch_delay`, `time_factor`, os `delay_ms` da macro do APP): muda por conta,
  na interface, e não tem "valor original" único. Está em `blazesbot/config.py`.
* **Tempo que o JOGO impõe** (animação de montar, teleporte, efeito de poção):
  não é nosso, e o bot só pode medir.
* **Esperas calculadas** (`tick(resto)`, `tick(segundos * fator)`): o valor não
  é literal, então não há número para catalogar. Elas aparecem indiretamente,
  pelas constantes que as alimentam.

