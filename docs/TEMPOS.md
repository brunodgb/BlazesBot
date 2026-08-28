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


**278 tempos catalogados** — 212 FIXOS (espera cega), 66 entre TETO e PASSO.


**1 estão diferentes do original:** `PASSOS_DO_APP`


## FORA DA CAVE — venda em Stone City

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `ESPERA_DO_TELEPORTE` | 5 s | = | TETO | [vendor.py:115](blazesbot/bot/bc/vendor.py#L115) |  | TETO da espera do teleporte -- não é mais o tempo gasto, é o limite. |
| `PASSO_DA_ESPERA_DO_TELEPORTE` | 0.12 s | = | PASSO | [vendor.py:119](blazesbot/bot/bc/vendor.py#L119) |  | Entre leituras. A posição vem da memória e custa microssegundos; o passo é |
| `ESPERA_ENTRE_TENTATIVAS_DE_RETORNO` | 8 s | = | FIXO | [vendor.py:151](blazesbot/bot/bc/vendor.py#L151) | `voltar_para_a_cidade` |  |
| `SEGUNDOS_POR_TENTATIVA_NO_VENDEDOR` | 4 s | = | FIXO | [vendor.py:160](blazesbot/bot/bc/vendor.py#L160) | `travel_to_vendor` |  |
| `ESPERA_ENTRE_CLIQUES_DA_VENDA` | 0.065 s | = | FIXO | [vendor.py:229](blazesbot/bot/bc/vendor.py#L229) | `_clicar_no_slot` | Espera entre um clique e o seguinte na grade. Era 200 ms. |
| `ESPERA_PARA_CONFIRMAR_VAZIO` | 0.5 s | = | FIXO | [vendor.py:300](blazesbot/bot/bc/vendor.py#L300) | `_confirmar_slot_vazio, sell_from_slot` | As leituras de confirmação são ESPAÇADAS, não coladas: veja |
| `ESPERA_ANTES_DO_SELL` | 0.4 s | = | FIXO | [vendor.py:332](blazesbot/bot/bc/vendor.py#L332) | `sell_from_slot` | O RESPIRO EM VOLTA DO BOTÃO "SELL" |
| `ESPERA_DEPOIS_DO_SELL` | 0.6 s | = | FIXO | [vendor.py:333](blazesbot/bot/bc/vendor.py#L333) | `sell_from_slot` |  |
| *literal em* `_tentar_abrir_a_venda` | 0.3 s | = | FIXO | [vendor.py:629](blazesbot/bot/bc/vendor.py#L629) | `_tentar_abrir_a_venda` |  |
| *literal em* `_dismiss_confirm` | 0.125 s | = | FIXO | [vendor.py:732](blazesbot/bot/bc/vendor.py#L732) | `_dismiss_confirm` | Fecha a caixa "It's precious item, please confirm!", se aberta. |
| *literal em* `buy_supplies` | 0.4 s | = | FIXO | [vendor.py:1162](blazesbot/bot/bc/vendor.py#L1162) | `buy_supplies` | Compra a Pedra de Retorno gasta, no mesmo NPC da venda. |
| *literal em* `buy_supplies` | 0.25 s | = | FIXO | [vendor.py:1164](blazesbot/bot/bc/vendor.py#L1164) | `buy_supplies` | Compra a Pedra de Retorno gasta, no mesmo NPC da venda. |
| *literal em* `buy_supplies` | 0.3 s | = | FIXO | [vendor.py:1168](blazesbot/bot/bc/vendor.py#L1168) | `buy_supplies` | Compra a Pedra de Retorno gasta, no mesmo NPC da venda. |
| *literal em* `buy_supplies` | 0.35 s | = | FIXO | [vendor.py:1173](blazesbot/bot/bc/vendor.py#L1173) | `buy_supplies` | Compra a Pedra de Retorno gasta, no mesmo NPC da venda. |
| *literal em* `run_maintenance` | 0.2 s | = | FIXO | [vendor.py:1261](blazesbot/bot/bc/vendor.py#L1261) | `run_maintenance` | Ida completa à cidade: teleportar, viajar, vender, comprar. |
| *literal em* `run_maintenance` | 0.5 s | = | FIXO | [vendor.py:1274](blazesbot/bot/bc/vendor.py#L1274) | `run_maintenance` | Ida completa à cidade: teleportar, viajar, vender, comprar. |


## FORA DA CAVE — painel, diálogos, Fay

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `PASSO_DA_ESPERA_DO_DIALOGO` | 0.08 s | = | PASSO | [ui_service.py:129](blazesbot/bot/bc/ui_service.py#L129) | `_esperar_o_dialogo` | Diálogo do NPC aparecer. Era 0,30 s fixos, gastos inteiros mesmo quando o |
| `LIMITE_INICIAL_DA_ESPERA_DO_DIALOGO` | 0.65 s | = | TETO | [ui_service.py:168](blazesbot/bot/bc/ui_service.py#L168) | `limite_da_espera_do_dialogo` | TETO DA ESPERA DO DIÁLOGO -- ajustado pelo que foi MEDIDO, não chutado |
| `LIMITE_MINIMO_DA_ESPERA_DO_DIALOGO` | 0.18 s | = | TETO | [ui_service.py:172](blazesbot/bot/bc/ui_service.py#L172) | `limite_da_espera_do_dialogo` | Piso: o valor que valia antes. Abaixo disto não se aperta nem com evidência -- |
| `LIMITE_MAXIMO_DA_ESPERA_DO_DIALOGO` | 0.6 s | = | TETO | [ui_service.py:176](blazesbot/bot/bc/ui_service.py#L176) | `limite_da_espera_do_dialogo` | Teto do teto. Passado disto, o diálogo não vai abrir mesmo, e insistir só |
| `LIMITE_DA_ESPERA_DO_DIALOGO_LENTA` | 0.65 s | = | TETO | [ui_service.py:202](blazesbot/bot/bc/ui_service.py#L202) | `limite_da_espera_do_dialogo_lenta` | Diálogo aparecer na REDESCOBERTA, depois de cada clique direito. Era `tick(1.3)` |
| `ESPERA_DEPOIS_DO_LINK` | 0.2 s | = | FIXO | [ui_service.py:224](blazesbot/bot/bc/ui_service.py#L224) | `_abrir_dialogo_e_clicar` | Servidor processar o pedido de entrada. Zero na disputa: quem confirma a entrada |
| `PASSO_DA_ESPERA_DO_PAINEL` | 0.08 s | = | PASSO | [ui_service.py:262](blazesbot/bot/bc/ui_service.py#L262) | `_esperar_o_painel` | Passo e teto da espera pelo painel aparecer. Cada volta custa uma captura de |
| `LIMITE_DA_ESPERA_DO_PAINEL` | 0.8 s | = | TETO | [ui_service.py:268](blazesbot/bot/bc/ui_service.py#L268) | `abrir_surroundings, _esperar_o_painel` | O teto é EXATAMENTE a espera fixa que havia antes (1,2 s), e isso é de propósito: |
| `ESPERA_DA_TROCA_DE_ABA` | 0.05 s | = | FIXO | [ui_service.py:272](blazesbot/bot/bc/ui_service.py#L272) | `abrir_surroundings` | Assentar depois de clicar na aba NPC. Não é "esperar a aba renderizar": é só dar |
| `PASSO_DA_ESPERA_DO_RESULTADO` | 0.08 s | = | PASSO | [ui_service.py:290](blazesbot/bot/bc/ui_service.py#L290) | `_esperar_resultado_da_busca` | De quanto em quanto tempo perguntar à memória se o resultado apareceu, e por |
| `LIMITE_DA_ESPERA_DO_RESULTADO` | 0.8 s | = | TETO | [ui_service.py:291](blazesbot/bot/bc/ui_service.py#L291) | `_esperar_resultado_da_busca` |  |
| `ESPERA_CEGA_DO_RESULTADO` | 0.3 s | = | FIXO | [ui_service.py:317](blazesbot/bot/bc/ui_service.py#L317) | `_esperar_resultado_da_busca` | Quando a leitura de arredores por memória não funciona neste cliente, a lista |
| `PASSO_DA_ESPERA_DO_ANDAR` | 0.04 s | = | PASSO | [ui_service.py:360](blazesbot/bot/bc/ui_service.py#L360) | `_saiu_do_lugar` | Depois de clicar no resultado o personagem já saiu andando -- o pathfinding do |
| `LIMITE_DA_ESPERA_DO_ANDAR` | 0.4 s | = | TETO | [ui_service.py:361](blazesbot/bot/bc/ui_service.py#L361) | `ir_para_resultado, _saiu_do_lugar` |  |
| `ESPERA_DEPOIS_DE_CLICAR_NO_RESULTADO` | 0.15 s | = | FIXO | [ui_service.py:362](blazesbot/bot/bc/ui_service.py#L362) | `_saiu_do_lugar` |  |
| `INTERVALO_ENTRE_USOS_DO_PAINEL` | 2 s | = | FIXO | [ui_service.py:444](blazesbot/bot/bc/ui_service.py#L444) | `_respeitar_a_cadencia_do_painel` | CADÊNCIA MÍNIMA ENTRE UM USO DO PAINEL DE ARREDORES E O SEGUINTE |
| `PASSO_DA_ESPERA_DA_CHEGADA` | 0.25 s | = | PASSO | [ui_service.py:468](blazesbot/bot/bc/ui_service.py#L468) | `_esperar_chegar` | Passo da leitura de posição enquanto se espera a chegada. Ler memória custa |
| `PASSO_DA_ESPERA_DO_FECHAMENTO` | 0.04 s | = | PASSO | [ui_service.py:486](blazesbot/bot/bc/ui_service.py#L486) | `fechar_surroundings` |  |
| `LIMITE_DA_ESPERA_DO_FECHAMENTO` | 0.4 s | = | TETO | [ui_service.py:487](blazesbot/bot/bc/ui_service.py#L487) | `fechar_surroundings` |  |
| `ESPERA_DEPOIS_DE_FECHAR` | 0.2 s | = | FIXO | [ui_service.py:488](blazesbot/bot/bc/ui_service.py#L488) |  |  |
| `ESPERA_ANTES_DE_CONFERIR` | 0.15 s | = | FIXO | [ui_service.py:490](blazesbot/bot/bc/ui_service.py#L490) | `_entrar_descobrindo` |  |
| `TETO_DO_TELEPORTE_DA_FAY` | 2 s | = | TETO | [ui_service.py:510](blazesbot/bot/bc/ui_service.py#L510) | `_esperar_o_teleporte` | TELEPORTE DA FAY (Stone City -> Ghost Din Woods) |
| `PASSO_DA_ESPERA_DO_TELEPORTE` | 0.08 s | = | PASSO | [ui_service.py:511](blazesbot/bot/bc/ui_service.py#L511) | `_esperar_o_teleporte` |  |
| *literal em* `resetar_visao` | 0.175 s | = | FIXO | [ui_service.py:652](blazesbot/bot/bc/ui_service.py#L652) | `resetar_visao` | Aperta o View Reset para recentrar a câmera. |
| *literal em* `buscar_npc` | 0.5 s | = | FIXO | [ui_service.py:1098](blazesbot/bot/bc/ui_service.py#L1098) | `buscar_npc` | Busca um NPC e devolve o primeiro resultado, conferido. |
| *literal em* `fechar_dialogo` | 0.3 s | = | FIXO | [ui_service.py:1523](blazesbot/bot/bc/ui_service.py#L1523) | `fechar_dialogo` |  |
| *literal em* `clicar_link` | 0.75 s | = | FIXO | [ui_service.py:1542](blazesbot/bot/bc/ui_service.py#L1542) | `clicar_link` | Clica num link do diálogo, localizado pelo texto. Devolve o ponto. |
| *literal em* `clicar_link` | 0.4 s | = | FIXO | [ui_service.py:1544](blazesbot/bot/bc/ui_service.py#L1544) | `clicar_link` | Clica num link do diálogo, localizado pelo texto. Devolve o ponto. |
| *literal em* `entrar_no_covil_do_boss` | 1.5 s | = | FIXO | [ui_service.py:2065](blazesbot/bot/bc/ui_service.py#L2065) | `entrar_no_covil_do_boss` | Altar Stone -> "Secret Cemetery", que é a sala do boss. |
| *literal em* `sair_da_cave` | 1.5 s | = | FIXO | [ui_service.py:2102](blazesbot/bot/bc/ui_service.py#L2102) | `sair_da_cave` | Skull Herald do covil -> "Leave Bewitcher Cave". |


## FORA DA CAVE — montaria e trajeto

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `INTERVALO_RECLIQUE` | 1.1 s | = | FIXO | [navigation.py:94](blazesbot/bot/bc/navigation.py#L94) | `follow_path` | Intervalo MÁXIMO entre cliques enquanto anda. Não é a cadência normal -- o |
| `SEM_PROGRESSO_SEGUNDOS` | 1.2 s | = | FIXO | [navigation.py:108](blazesbot/bot/bc/navigation.py#L108) | `follow_path` | Sem aproximar-se do alvo por este tempo, considera travado. |
| `SEGUNDOS_PARADO_DE_VERDADE` | 1.5 s | = | FIXO | [navigation.py:138](blazesbot/bot/bc/navigation.py#L138) | `follow_path` | PERSONAGEM COMPLETAMENTE PARADO DENTRO DA CAVE |
| `SEGUNDOS_POR_TENTATIVA_DE_DESTRAVAR` | 4 s | = | FIXO | [navigation.py:166](blazesbot/bot/bc/navigation.py#L166) | `destravar_pelos_vizinhos, _tentar_circulo` | Prazo para alcançar CADA candidato da manobra de destravamento. |
| `CIRCULO_TETO_SEGUNDOS` | 6.5 s | = | TETO | [navigation.py:248](blazesbot/bot/bc/navigation.py#L248) | `_tentar_circulo` | Teto de tempo TOTAL do círculo antes de desistir e devolver o controle. É a |
| `SEGUNDOS_POR_CLIQUE_CIRCULO` | 1 s | = | FIXO | [navigation.py:250](blazesbot/bot/bc/navigation.py#L250) | `_clicar_offset_e_verificar` | Janela por ponto do círculo para saber se o clique fez o personagem andar. |
| `INTERVALO_MANUTENCAO` | 0.6 s | = | FIXO | [navigation.py:252](blazesbot/bot/bc/navigation.py#L252) | `follow_path` | Cadência da manutenção durante o deslocamento (poção). |
| `INTERVALO_REMONTAR` | 3 s | = | FIXO | [navigation.py:288](blazesbot/bot/bc/navigation.py#L288) | `_pode_tocar_na_montaria, _manter_montaria` | A MONTARIA É PRÉ-REQUISITO DE ANDAR, NÃO UMA OTIMIZAÇÃO |
| `TETO_DO_PORTAO` | 6 s | = | TETO | [navigation.py:315](blazesbot/bot/bc/navigation.py#L315) | `garantir_montaria_para_andar` | A ORDEM DO PORTÃO: CONFERIR -> ATIVAR -> CONFIRMAR -> ANDAR |
| `INTERVALO_PARADA_POCAO` | 10 s | = | FIXO | [navigation.py:356](blazesbot/bot/bc/navigation.py#L356) | `_manutencao_em_movimento` | Recarga da PARADA para tomar poção durante o trajeto. |
| *literal em* `wait_until_still` | 0.25 s | = | FIXO | [navigation.py:427](blazesbot/bot/bc/navigation.py#L427) | `wait_until_still` | Espera o personagem parar de andar. |
| *literal em* `_abrir_mapa` | 0.5 s | = | FIXO | [navigation.py:451](blazesbot/bot/bc/navigation.py#L451) | `_abrir_mapa` |  |
| *literal em* `_fechar_mapa` | 0.3 s | = | FIXO | [navigation.py:457](blazesbot/bot/bc/navigation.py#L457) | `_fechar_mapa` |  |
| *literal em* `_mover_pelo_mapa` | 0.2 s | = | FIXO | [navigation.py:495](blazesbot/bot/bc/navigation.py#L495) | `_mover_pelo_mapa` | Anda até `alvo` usando o mapa-múndi. |
| *literal em* `_mover_pelo_mapa` | 1 s | = | FIXO | [navigation.py:501](blazesbot/bot/bc/navigation.py#L501) | `_mover_pelo_mapa` | Anda até `alvo` usando o mapa-múndi. |
| *literal em* `_clicar_offset_e_verificar` | 0.1 s | = | FIXO | [navigation.py:801](blazesbot/bot/bc/navigation.py#L801) | `_clicar_offset_e_verificar` | Clique curto num offset e medição: o personagem andou? |
| *literal em* `_parada_para_pocao` | 0.25 s | = | FIXO | [navigation.py:899](blazesbot/bot/bc/navigation.py#L899) | `_parada_para_pocao` | Desmonta, toma poção e remonta. É a ÚNICA forma que funciona. |
| *literal em* `_parada_para_pocao` | 0.2 s | = | FIXO | [navigation.py:910](blazesbot/bot/bc/navigation.py#L910) | `_parada_para_pocao` | Desmonta, toma poção e remonta. É a ÚNICA forma que funciona. |
| *literal em* `follow_path` | 0.25 s | = | FIXO | [navigation.py:1168](blazesbot/bot/bc/navigation.py#L1168) | `follow_path` | Percorre waypoints em ordem, SEM parar entre eles. |
| *literal em* `travel_via_surroundings` | 0.5 s | = | FIXO | [navigation.py:1466](blazesbot/bot/bc/navigation.py#L1466) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.2 s | = | FIXO | [navigation.py:1468](blazesbot/bot/bc/navigation.py#L1468) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.15 s | = | FIXO | [navigation.py:1470](blazesbot/bot/bc/navigation.py#L1470) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.4 s | = | FIXO | [navigation.py:1472](blazesbot/bot/bc/navigation.py#L1472) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.25 s | = | FIXO | [navigation.py:1485](blazesbot/bot/bc/navigation.py#L1485) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.5 s | = | FIXO | [navigation.py:1491](blazesbot/bot/bc/navigation.py#L1491) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.25 s | = | FIXO | [navigation.py:1493](blazesbot/bot/bc/navigation.py#L1493) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `ensure_mounted` | 1 s | = | FIXO | [navigation.py:1800](blazesbot/bot/bc/navigation.py#L1800) | `ensure_mounted` |  |
| *literal em* `ensure_mounted` | 1 s | = | FIXO | [navigation.py:1811](blazesbot/bot/bc/navigation.py#L1811) | `ensure_mounted` |  |
| *literal em* `ensure_dismounted` | 0.75 s | = | FIXO | [navigation.py:1859](blazesbot/bot/bc/navigation.py#L1859) | `ensure_dismounted` |  |


## FORA DA CAVE — pontos exatos

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `SEGUNDOS_DESENCALHANDO_O_ALTAR` | 3 s | = | FIXO | [mapa_bc.py:144](blazesbot/bot/bc/mapa_bc.py#L144) |  | Quanto esperar no ponto de vai-e-volta antes de retornar. |
| `SEGUNDOS_POR_TENTATIVA_NA_SAIDA` | 1.8 s | = | FIXO | [mapa_bc.py:190](blazesbot/bot/bc/mapa_bc.py#L190) |  |  |
| `SEGUNDOS_POR_TENTATIVA_NA_FAY` | 1.8 s | = | FIXO | [mapa_bc.py:237](blazesbot/bot/bc/mapa_bc.py#L237) |  |  |


## A RUN — passos da rotina

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `PASSO_DO_RECONHECIMENTO` | 0.04 s | = | PASSO | [routine.py:119](blazesbot/bot/bc/routine.py#L119) | `_reconhecer_entrada` | PASSO: de quanto em quanto tempo perguntar, dentro da janela. A pergunta é uma |
| `ESPERA_ENTRE_TENTATIVAS` | 0.025 s | = | FIXO | [routine.py:129](blazesbot/bot/bc/routine.py#L129) | `_do_entrar` | E O INTERVALO ENTRE TENTATIVAS quase desaparece: a janela de reconhecimento já |
| `PASSO_DA_ESPERA_DO_RESETER` | 1 s | *novo* | PASSO | [routine.py:143](blazesbot/bot/bc/routine.py#L143) | `_esperar_o_reseter` | Cadência da espera pela conta de reset (ver `_esperar_o_reseter`). |
| `INTERVALO_DO_AVISO_DO_RESETER` | 300 s (5 min) | *novo* | FIXO | [routine.py:150](blazesbot/bot/bc/routine.py#L150) | `_esperar_o_reseter` | De quanto em quanto tempo repetir o aviso enquanto a trava dura. |
| `SEGUNDOS_POR_TENTATIVA_NO_ALTAR` | 1.5 s | = | FIXO | [routine.py:180](blazesbot/bot/bc/routine.py#L180) | `_encostar_exato_no_patamar` |  |
| `SEGUNDOS_ESPERANDO_A_BOLSA` | 0.2 s | = | FIXO | [routine.py:299](blazesbot/bot/bc/routine.py#L299) | `_usar_package_courage` | Quanto esperar a bolsa CONFIRMAR que abriu, lendo a memória. |
| `PASSO_DA_ESPERA_DA_BOLSA` | 0.05 s | = | PASSO | [routine.py:324](blazesbot/bot/bc/routine.py#L324) | `_usar_package_courage` | De quanto em quanto tempo perguntar se a bolsa já abriu. Era 0,15 s, o que |
| `ASSENTAMENTO_DA_BOLSA` | 0.14 s | = | FIXO | [routine.py:330](blazesbot/bot/bc/routine.py#L330) | `_usar_package_courage` | Depois que a MEMÓRIA confirma a bolsa aberta, o quanto esperar o DESENHO dela. |
| *literal em* `_do_situar` | 1 s | = | FIXO | [routine.py:527](blazesbot/bot/bc/routine.py#L527) | `_do_situar` | Olha onde o personagem está e entra no estado que faz sentido. |
| *literal em* `_do_preparar` | 0.2 s | = | FIXO | [routine.py:620](blazesbot/bot/bc/routine.py#L620) | `_do_preparar` |  |
| *literal em* `_do_recuperar` | 3 s | = | FIXO | [routine.py:2342](blazesbot/bot/bc/routine.py#L2342) | `_do_recuperar` | Recuperação após morte ou falhas em sequência. |


## DENTRO DA CAVE — combate

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `SEGUNDOS_SENTADO_APOS_GUARDAS` | 4 s | = | FIXO | [combat.py:75](blazesbot/bot/bc/combat.py#L75) | `sentar_para_recuperar` | Quatro segundos sentado recuperam vida e mana de graça, e é o único momento da |
| `SEGUNDOS_DA_POCAO_DE_VIDA` | 15 s | = | FIXO | [combat.py:91](blazesbot/bot/bc/combat.py#L91) | `curar_ao_entrar, _beber_ate_encher (+1)` | A POÇÃO DE VIDA LEVA 15 SEGUNDOS, E ANDAR CANCELA |
| `SEGUNDOS_DEPOIS_DA_SUPER_SKILL` | 12 s | = | FIXO | [combat.py:95](blazesbot/bot/bc/combat.py#L95) | `curar_ao_entrar, curar_antes_do_boss` | Respiro depois da Super Skill de cura. Ela é instantânea; isto é só o tempo de |
| `ESPERA_DEPOIS_DO_TAB` | 0.6 s | = | FIXO | [combat.py:115](blazesbot/bot/bc/combat.py#L115) | `atacar_ate_sair_de_combate, fase_do_boss_por_combate` | Espera depois de UM TAB, para a seleção chegar da rede antes de conferir. |
| `FATIA_DA_ESPERA_DA_POCAO` | 0.5 s | = | PASSO | [combat.py:147](blazesbot/bot/bc/combat.py#L147) | `_esperar_o_efeito_da_pocao` | Fatia da espera da poção. O TOTAL é medido por relógio (ver acima), então esta |
| `SEGUNDOS_DE_CONJURACAO_DA_CURA` | 1.6 s | = | FIXO | [combat.py:237](blazesbot/bot/bc/combat.py#L237) | `_a_cura_subiu` | Conjuração da skill de cura. Informado pelo usuário em 19/08/2026. |
| `INTERVALO_DE_CONFERENCIA` | 0.1 s | = | FIXO | [combat.py:243](blazesbot/bot/bc/combat.py#L243) | `_a_cura_subiu` | De quanto em quanto tempo perguntar se a vida subiu. É leitura de memória -- |
| `SEGUNDOS_SEM_ALVO_PARA_MORTE` | 3 s | = | FIXO | [combat.py:295](blazesbot/bot/bc/combat.py#L295) |  | 2. TEMPO -- segundos contínuos sem nada vivo selecionado. Dá lastro à contagem: |
| `PASSO_DA_VIGIA_DE_COMBATE` | 0.05 s | = | PASSO | [combat.py:375](blazesbot/bot/bc/combat.py#L375) | `esperar_entrar_em_combate, atacar_ate_sair_de_combate` | Passo da vigia da flag. É o que "não bloqueante" significa na prática: o laço |
| `ESPERA_PARA_ENTRAR_EM_COMBATE` | 5 s | = | FIXO | [combat.py:382](blazesbot/bot/bc/combat.py#L382) | `esperar_entrar_em_combate` | Quanto esperar a flag LIGAR depois de chegar no waypoint. |
| `ESPERA_ENTRAR_EM_COMBATE_GUARDAS` | 5 s | = | FIXO | [combat.py:391](blazesbot/bot/bc/combat.py#L391) | `_fase_dos_guardas_com_tab, _fase_dos_guardas_sem_tab` | Prazo curto para os GUARDAS (os 4 mobs no waypoint antes do boss). |
| `AVISO_DA_ESPERA_SEM_PRAZO` | 10 s | = | TETO | [combat.py:408](blazesbot/bot/bc/combat.py#L408) | `esperar_entrar_em_combate` | Cadência do aviso enquanto espera sem prazo. Uma espera sem limite PRECISA |
| `CARENCIA_SEM_LER_O_NOME` | 3 s | = | FIXO | [combat.py:679](blazesbot/bot/bc/combat.py#L679) | `atacar_ate_sair_de_combate` | Quantos TAB gastar tentando SAIR de um alvo errado, por luta. |
| `CADENCIA_DA_LEITURA_DO_ALVO` | 0.15 s | = | PASSO | [combat.py:798](blazesbot/bot/bc/combat.py#L798) | `atacar_ate_sair_de_combate` | De quanto em quanto tempo olhar a barra do alvo durante a luta. |
| `CARENCIA_APOS_O_TAB` | 2.4 s | = | FIXO | [combat.py:807](blazesbot/bot/bc/combat.py#L807) | `atacar_ate_sair_de_combate` | Depois de apertar TAB, quanto tempo ignorar a leitura. |
| `SEGUNDOS_ANTES_DO_TAB_NO_BOSS` | 4 s | = | FIXO | [combat.py:808](blazesbot/bot/bc/combat.py#L808) | `fase_do_boss_por_combate` |  |
| *literal em* `auto_selecionar` | 0.125 s | = | FIXO | [combat.py:1013](blazesbot/bot/bc/combat.py#L1013) | `auto_selecionar` | Seleciona o próprio personagem (F1), para skill em si mesmo. |
| *literal em* `maintain` | 0.15 s | = | FIXO | [combat.py:1143](blazesbot/bot/bc/combat.py#L1143) | `maintain` | Poções e cura, escolhendo o item certo para a situação. |
| *literal em* `maintain` | 0.2 s | = | FIXO | [combat.py:1165](blazesbot/bot/bc/combat.py#L1165) | `maintain` | Poções e cura, escolhendo o item certo para a situação. |
| *literal em* `maintain` | 0.15 s | = | FIXO | [combat.py:1170](blazesbot/bot/bc/combat.py#L1170) | `maintain` | Poções e cura, escolhendo o item certo para a situação. |
| *literal em* `_manter_vida_caminho_antigo` | 0.2 s | = | FIXO | [combat.py:1200](blazesbot/bot/bc/combat.py#L1200) | `_manter_vida_caminho_antigo` | O comportamento anterior a 19/08/2026, inteiro. |
| *literal em* `_manter_vida_caminho_antigo` | 0.15 s | = | FIXO | [combat.py:1207](blazesbot/bot/bc/combat.py#L1207) | `_manter_vida_caminho_antigo` | O comportamento anterior a 19/08/2026, inteiro. |
| *literal em* `_manter_vida_caminho_antigo` | 0.15 s | = | FIXO | [combat.py:1212](blazesbot/bot/bc/combat.py#L1212) | `_manter_vida_caminho_antigo` | O comportamento anterior a 19/08/2026, inteiro. |
| *literal em* `esperar_entrar_em_combate` | 0.2 s | = | FIXO | [combat.py:1595](blazesbot/bot/bc/combat.py#L1595) | `esperar_entrar_em_combate` | Espera a flag de combate LIGAR. NÃO aperta TAB, não mira nada. |
| *literal em* `_travar_no_cemetery_guard` | 0.28 s | *novo* | FIXO | [combat.py:1827](blazesbot/bot/bc/combat.py#L1827) | `_travar_no_cemetery_guard` | A ÚNICA trava do waypoint dos guardas -- UMA porta, duas fontes. |
| *literal em* `sentar_para_recuperar` | 0.25 s | = | FIXO | [combat.py:2853](blazesbot/bot/bc/combat.py#L2853) | `sentar_para_recuperar` | Senta alguns segundos para recuperar vida e mana, e levanta. |
| *literal em* `_curar_antes_da_segunda_fase` | 0.3 s | = | FIXO | [combat.py:2872](blazesbot/bot/bc/combat.py#L2872) | `_curar_antes_da_segunda_fase` | Cura antes de encostar na fase seguinte, se a conta pedir. |
| *literal em* `heal_to_full` | 0.125 s | = | FIXO | [combat.py:3240](blazesbot/bot/bc/combat.py#L3240) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.125 s | = | FIXO | [combat.py:3243](blazesbot/bot/bc/combat.py#L3243) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.125 s | = | FIXO | [combat.py:3246](blazesbot/bot/bc/combat.py#L3246) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.3 s | = | FIXO | [combat.py:3249](blazesbot/bot/bc/combat.py#L3249) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.25 s | = | FIXO | [combat.py:3278](blazesbot/bot/bc/combat.py#L3278) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.6 s | = | FIXO | [combat.py:3291](blazesbot/bot/bc/combat.py#L3291) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.15 s | = | FIXO | [combat.py:3300](blazesbot/bot/bc/combat.py#L3300) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.15 s | = | FIXO | [combat.py:3304](blazesbot/bot/bc/combat.py#L3304) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.4 s | = | FIXO | [combat.py:3308](blazesbot/bot/bc/combat.py#L3308) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.5 s | = | FIXO | [combat.py:3310](blazesbot/bot/bc/combat.py#L3310) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `ensure_pet` | 1.5 s | = | FIXO | [combat.py:3338](blazesbot/bot/bc/combat.py#L3338) | `ensure_pet` | Garante que o pet está invocado. |
| *literal em* `ensure_pet` | 1.5 s | = | FIXO | [combat.py:3351](blazesbot/bot/bc/combat.py#L3351) | `ensure_pet` | Garante que o pet está invocado. |
| *literal em* `apply_buffs` | 0.6 s | = | FIXO | [combat.py:3378](blazesbot/bot/bc/combat.py#L3378) | `apply_buffs` | Aplica os buffs configurados, em si mesmo. |


## DENTRO DA CAVE — outros

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `PASSO_DO_GRID` | 6 s | = | PASSO | [amostragem_de_cliques.py:121](blazesbot/bot/bc/amostragem_de_cliques.py#L121) | `gerar_grid` |  |
| `TETO_DA_AMOSTRA` | 1.5 s | = | TETO | [amostragem_de_cliques.py:140](blazesbot/bot/bc/amostragem_de_cliques.py#L140) | `rodar, amostrar` | Teto da medição. Largo de propósito -- ver o cabeçalho. As aberturas reais |
| `PASSO_DA_MEDICAO` | 0.03 s | = | PASSO | [amostragem_de_cliques.py:145](blazesbot/bot/bc/amostragem_de_cliques.py#L145) | `amostrar` | Passo do laço que pergunta se o diálogo abriu. Cada volta custa uma captura |
| `ASSENTAMENTO_APOS_O_CLIQUE` | 0.125 s | = | FIXO | [amostragem_de_cliques.py:150](blazesbot/bot/bc/amostragem_de_cliques.py#L150) | `amostrar` | Assentamento depois da amostra, antes de reler a posição. É o tempo de o |
| `ESPERA_APOS_O_ESC` | 0.075 s | = | FIXO | [amostragem_de_cliques.py:153](blazesbot/bot/bc/amostragem_de_cliques.py#L153) | `fechar_dialogo` | Espera depois de cada ESC, antes de reconferir se o diálogo fechou. |
| `SEGUNDOS_POR_TENTATIVA_DE_ANCORAR` | 3 s | = | FIXO | [amostragem_de_cliques.py:168](blazesbot/bot/bc/amostragem_de_cliques.py#L168) | `ancorar` |  |
| `RECARGA` | 5 s | = | FIXO | [hotbar.py:101](blazesbot/bot/bc/hotbar.py#L101) | `garantir_pagina_1` | Recarga do caminho com `ctx`. Os momentos-chave acontecem em rajada -- o portão |
| `INTERVALO_DO_BATIMENTO` | 15 s | = | FIXO | [localizacao.py:67](blazesbot/bot/bc/localizacao.py#L67) | `_registrar` | Cadência do batimento no diário. Uma linha a cada meio minuto dá uma trilha |
| `SEGUNDOS_PARA_DESCONFIAR` | 3 s | = | FIXO | [localizacao.py:72](blazesbot/bot/bc/localizacao.py#L72) | `_registrar_falha` | Tempo com o nome ilegível a partir do qual o bot passa a tratar a fonte de |
| *literal em* `rodar` | 0.2 s | = | FIXO | [teste_venda.py:125](blazesbot/bot/bc/teste_venda.py#L125) | `rodar` | Executa a venda na janela JÁ ABERTA desta conta. Bloqueia até terminar. |
| `SEGUNDOS_ANDANDO_ANTES` | 0.5 s | = | FIXO | [velocidade.py:45](blazesbot/bot/bc/velocidade.py#L45) | `usar_se_puder` | Quanto o personagem precisa ter andado antes de valer a pena acionar. |


## ECOSSISTEMA APP

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `SEGUNDOS_ENTRE_POCOES` | 15 s | = | FIXO | [cura.py:104](blazesbot/bot/app/cura.py#L104) | `_curar_com_pocao` | Quanto esperar entre uma poção e a próxima. |
| `SEGUNDOS_PARA_VOLTAR_AO_PONTO` | 5 s | = | TETO | [cura.py:121](blazesbot/bot/app/cura.py#L121) | `_voltar_ao_ponto` | Teto da caminhada de volta ao ponto inicial. |
| `SEGUNDOS_SENTADO` | 30 s | = | TETO | [cura.py:128](blazesbot/bot/app/cura.py#L128) | `_curar_sentado` | Teto sentado, para quem não tem tecla de poção configurada. |
| `SEGUNDOS_ESPERANDO_SAIR_DE_BATALHA` | 2 s | = | FIXO | [cura.py:135](blazesbot/bot/app/cura.py#L135) | `_esperar_sair_de_batalha` | Quanto esperar a flag de batalha baixar depois que a macro termina. |
| `SEGUNDOS_PARA_SENTAR_COM_A_POCAO` | 1 s | *novo* | FIXO | [cura.py:146](blazesbot/bot/app/cura.py#L146) | `_a_pocao_saiu` | Quanto esperar o personagem SENTAR depois de apertar a tecla de poção. |
| `PASSO_DA_PERGUNTA` | 0.1 s | = | PASSO | [cura.py:151](blazesbot/bot/app/cura.py#L151) | `_esperar_sair_de_batalha, _voltar_ao_ponto (+2)` | Cadência de toda pergunta deste módulo. Leitura de memória é ~1 µs; o custo é |
| `TETO_DE_SEGUNDOS` | 10 s | = | TETO | [deletador.py:135](blazesbot/bot/app/deletador.py#L135) | `deletar_lixo, limpar_a_bolsa` | Teto do passo inteiro (verificar + apagar), pedido do usuário. |
| `TETO_DA_CAIXA` | 1 s | = | TETO | [deletador.py:138](blazesbot/bot/app/deletador.py#L138) | `_esperar_a_caixa` | Espera pela caixa de confirmação aparecer, depois do clique no ícone. |
| `PASSO_DA_ESPERA` | 0.05 s | = | PASSO | [deletador.py:139](blazesbot/bot/app/deletador.py#L139) | `_esperar_a_caixa` |  |
| `ESPERA_DA_BOLSA_ABRIR` | 0.35 s | = | FIXO | [deletador.py:146](blazesbot/bot/app/deletador.py#L146) | `limpar_a_bolsa, _fechar_a_bolsa` | A janela do inventário terminar de pintar depois da tecla. A memória confirma |
| *literal em* `_apagar_um` | 0.05 s | = | FIXO | [deletador.py:378](blazesbot/bot/app/deletador.py#L378) | `_apagar_um` | Uma exclusão completa: item -> ícone -> Ok. |
| `FATIA_DE_ESPERA` | 0.05 s | = | PASSO | [executor.py:88](blazesbot/bot/app/executor.py#L88) | `_esperar, _dormir (+1)` | Fatia máxima de espera antes de conferir se é para continuar. 0,05 s dá parada |
| `INTERVALO_ENTRE_INVOCACOES` | 10 s | = | FIXO | [executor.py:148](blazesbot/bot/app/executor.py#L148) | `garantir_pet` | Intervalo mínimo entre dois toques na tecla do pet. |
| `ESPERA_DEPOIS_DE_INVOCAR` | 1 s | = | FIXO | [executor.py:153](blazesbot/bot/app/executor.py#L153) | `garantir_pet` | Espera depois de apertar a tecla do pet, antes de seguir para as teclas da |
| `SEGUNDOS_PARA_O_ALVO_APARECER` | 0.6 s | *novo* | FIXO | [executor.py:184](blazesbot/bot/app/executor.py#L184) | `_esperar_o_alvo_trocar` | O TAB DEIXOU DE SER LINHA DA MACRO |
| `PASSO_DA_CONFERENCIA_DO_ALVO` | 0.1 s | *novo* | PASSO | [executor.py:219](blazesbot/bot/app/executor.py#L219) | `_esperar, _observar_depois_da_morte` | De quanto em quanto tempo perguntar "o alvo morreu?" DENTRO da espera de uma |
| `SEGUNDOS_PARA_A_RODA_REINICIAR` | 3 s | *novo* | FIXO | [executor.py:276](blazesbot/bot/app/executor.py#L276) | `_garantir_alvo` | Quanto esperar depois de uma aquisição FRACASSADA, antes da volta seguinte. |
| `ESPERA_SEM_ALVO` | 0.3 s | *novo* | FIXO | [executor.py:444](blazesbot/bot/app/executor.py#L444) | `uma_volta` | Quanto esperar antes de tentar de novo quando NÃO HÁ alvo vivo. |
| `ESPERA_ANTES_DO_TAB` | 0.6 s | *novo* | FIXO | [executor.py:471](blazesbot/bot/app/executor.py#L471) | `_tab_simples, _garantir_alvo` | PAGO UMA VEZ POR AQUISIÇÃO, NÃO UMA VEZ POR TECLA |
| `ESPERA_DEPOIS_DO_TAB` | 1 s | *novo* | FIXO | [executor.py:491](blazesbot/bot/app/executor.py#L491) | `_respiro_depois_do_tab` | Respiro entre o TAB e a PRIMEIRA linha da macro. |
| `SEGUNDOS_PARA_A_TRAVA_DEVOLVER` | 2 s | = | FIXO | [executor.py:493](blazesbot/bot/app/executor.py#L493) | `_voltar_para_base` |  |
| `MINIMO_DE_ESPERA_DO_APP_MS` | 100 s (2 min) | *novo* | FIXO | [executor.py:500](blazesbot/bot/app/executor.py#L500) | `_respiro_depois_do_tab` | Piso de qualquer tempo do APP, em milissegundos. O MESMO número vive em |
| `SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE` | 3 s | *novo* | FIXO | [executor.py:556](blazesbot/bot/app/executor.py#L556) | `_observar_depois_da_morte` | DEPOIS DE MATAR, O BOT OBSERVA -- E O QUE ELE OBSERVA É A BATALHA |
| `INTERVALO_MINIMO_DA_TELA` | 0.5 s | *novo* | FIXO | [executor.py:620](blazesbot/bot/app/executor.py#L620) | `_olhar_a_tela` | Intervalo minimo entre duas capturas. |
| `ESPERA_ENTRE_TABS` | 0.6 s | *novo* | FIXO | [executor.py:659](blazesbot/bot/app/executor.py#L659) | `_garantir_alvo` | Espaçamento entre um salto da roda do TAB e o seguinte. |
| `PASSO_DA_ESPERA_DA_BASE` | 0.1 s | = | PASSO | [executor.py:674](blazesbot/bot/app/executor.py#L674) | `_esperar_chegar_na_base` | Cadência da pergunta "já cheguei?". Leitura de posição é de microssegundos; o |
| `PASSO_DA_CONFIRMACAO_DO_TAB` | 0.01 s | *novo* | PASSO | [executor.py:698](blazesbot/bot/app/executor.py#L698) | `_esperar_o_alvo_trocar` | ERA AQUI O ATRASO ENTRE O TAB E A LINHA 1 -- 26/08/2026 |
| `SEGUNDOS_DO_PASSO_DO_SHUFFLE` | 2 s | *novo* | PASSO | [executor.py:704](blazesbot/bot/app/executor.py#L704) | `_fazer_shuffle_anti_afk` | Cada perna do shuffle anti-AFK (ida e volta). Era `time.sleep(1.0)` cego duas |
| *literal em* `rodar` | 0.25 s | = | FIXO | [executor.py:2826](blazesbot/bot/app/executor.py#L2826) | `rodar` | Laço contínuo: volta após volta, até `continuar()` devolver False. |
| `ESPERA_ENTRE_TABS_DO_ALINHAMENTO` | 0.4 s | *novo* | FIXO | [sincronia.py:97](blazesbot/bot/app/sincronia.py#L97) | `_alinhar_no_alvo` | Cadência do TAB durante o alinhamento. |
| `PASSO_DA_ESPERA_DA_LARGADA` | 0.05 s | *novo* | PASSO | [sincronia.py:100](blazesbot/bot/app/sincronia.py#L100) | `_esperar_os_seguidores, _entrar_na_largada` | De quanto em quanto tempo o seguidor confere se a largada saiu. |
| `SEGUNDOS_SEM_MUDANCA_PARA_TAB` | 4 s | *novo* | FIXO | [sincronia.py:108](blazesbot/bot/app/sincronia.py#L108) | `conferir_a_parada` | Sem trocar de estado de batalha por este tempo, dá TAB. |
| `TETO_DA_LINHA_SEGUNDOS` | 2 s | *novo* | TETO | [sincronia.py:116](blazesbot/bot/app/sincronia.py#L116) | `linha_a_enviar` | Quanto o seguidor espera a marca de UMA linha antes de mandar assim mesmo. |
| `PASSO_DA_ESPERA_DA_LINHA` | 0.05 s | *novo* | PASSO | [sincronia.py:121](blazesbot/bot/app/sincronia.py#L121) | `linha_a_enviar` | De quanto em quanto tempo a espera da linha acorda para conferir o botão |


## LOGIN E RELOGIN

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `PRE_SERVER_TIMEOUT` | 600 s (10 min) | = | TETO | [login.py:63](blazesbot/bot/login.py#L63) | `run` | NÃO EXISTE LIMITE DE TEMPO NA FILA. |
| `ESPERA_CEGA_SEGUNDOS` | 90 s (2 min) | = | FIXO | [login.py:79](blazesbot/bot/login.py#L79) | `_advance_phase` | Depois de esgotar as tentativas às cegas, o bot NÃO desiste -- ele espaça. |
| `ESPERA_SERVIDOR_FORA` | 10 s | = | FIXO | [login.py:95](blazesbot/bot/login.py#L95) | `_handle_acquiring_ip` | Espera depois de fechar "Acquiring server IP address." (servidores fora do ar). |
| `ESPERA_SERVIDOR_FORA_MAX` | 60 s (1 min) | = | TETO | [login.py:96](blazesbot/bot/login.py#L96) | `_handle_acquiring_ip` |  |
| `SEGUNDOS_CONECTANDO` | 6 s | = | FIXO | [login.py:122](blazesbot/bot/login.py#L122) | `_handle_connecting` | "Connecting to the server, please wait a moment." -- espera LEGÍTIMA, com |
| `FATIA_DA_ESPERA_DO_LOGIN` | 0.05 s | = | PASSO | [login.py:127](blazesbot/bot/login.py#L127) | `_esperar` | Fatia da espera do login. A espera é cumprida em pedaços para que Parar e |
| *literal em* `_abort_if_stopped` | 0.075 s | = | FIXO | [login.py:292](blazesbot/bot/login.py#L292) | `_abort_if_stopped` | Verifica parada E pausa. |
| *literal em* `_do_credentials` | 0.35 s | = | FIXO | [login.py:364](blazesbot/bot/login.py#L364) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.15 s | = | FIXO | [login.py:366](blazesbot/bot/login.py#L366) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.3 s | = | FIXO | [login.py:368](blazesbot/bot/login.py#L368) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.25 s | = | FIXO | [login.py:371](blazesbot/bot/login.py#L371) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.15 s | = | FIXO | [login.py:377](blazesbot/bot/login.py#L377) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.3 s | = | FIXO | [login.py:379](blazesbot/bot/login.py#L379) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 1.25 s | = | FIXO | [login.py:382](blazesbot/bot/login.py#L382) | `_do_credentials` |  |
| *literal em* `_do_server` | 0.4 s | = | FIXO | [login.py:419](blazesbot/bot/login.py#L419) | `_do_server` | Seleciona o servidor da conta e confirma. |
| *literal em* `_do_server` | 1.75 s | = | FIXO | [login.py:449](blazesbot/bot/login.py#L449) | `_do_server` | Seleciona o servidor da conta e confirma. |
| *literal em* `_try_enter_world` | 0.6 s | = | FIXO | [login.py:481](blazesbot/bot/login.py#L481) | `_try_enter_world` | Seleciona o personagem e entra. Chamado a cada 20 s. |
| *literal em* `_try_enter_world` | 1.5 s | = | FIXO | [login.py:490](blazesbot/bot/login.py#L490) | `_try_enter_world` | Seleciona o personagem e entra. Chamado a cada 20 s. |
| *literal em* `_handle_login_error` | 0.6 s | = | FIXO | [login.py:504](blazesbot/bot/login.py#L504) | `_handle_login_error` |  |
| *literal em* `_handle_login_error` | 0.6 s | = | FIXO | [login.py:509](blazesbot/bot/login.py#L509) | `_handle_login_error` |  |
| *literal em* `_handle_conn_interrupted` | 1 s | = | FIXO | [login.py:534](blazesbot/bot/login.py#L534) | `_handle_conn_interrupted` | Fecha o aviso de conexão interrompida. |
| *literal em* `_handle_login_busy` | 0.75 s | = | FIXO | [login.py:557](blazesbot/bot/login.py#L557) | `_handle_login_busy` | Fecha o aviso "Login server is busy now, please try again." |
| *literal em* `_handle_connecting` | 0.5 s | = | FIXO | [login.py:588](blazesbot/bot/login.py#L588) | `_handle_connecting` | "Connecting to the server, please wait a moment." — espera COM PRAZO. |
| *literal em* `_handle_connecting` | 0.5 s | = | FIXO | [login.py:591](blazesbot/bot/login.py#L591) | `_handle_connecting` | "Connecting to the server, please wait a moment." — espera COM PRAZO. |
| *literal em* `_handle_acquiring_ip` | 0.6 s | = | FIXO | [login.py:646](blazesbot/bot/login.py#L646) | `_handle_acquiring_ip` | Fecha o aviso "Acquiring server IP address." e volta a tentar. |
| *literal em* `_modal_travando_antes_do_servidor` | 0.3 s | = | FIXO | [login.py:703](blazesbot/bot/login.py#L703) | `_modal_travando_antes_do_servidor` | Aviso na tela ANTES de conectar, reconhecido só pela memória. |
| *literal em* `_modal_travando_antes_do_servidor` | 0.5 s | = | FIXO | [login.py:705](blazesbot/bot/login.py#L705) | `_modal_travando_antes_do_servidor` | Aviso na tela ANTES de conectar, reconhecido só pela memória. |
| *literal em* `_handle_conn_failed` | 0.75 s | = | FIXO | [login.py:718](blazesbot/bot/login.py#L718) | `_handle_conn_failed` | Fecha o aviso "Connection failed, please try again later." |
| *literal em* `_handle_queue` | 5 s | = | FIXO | [login.py:733](blazesbot/bot/login.py#L733) | `_handle_queue` | Na fila, apenas esperar. |
| *literal em* `_finish` | 0.25 s | = | FIXO | [login.py:784](blazesbot/bot/login.py#L784) | `_finish` | Confirma a entrada no mundo e batiza a janela. |
| *literal em* `_advance_phase` | 2.5 s | = | FIXO | [login.py:889](blazesbot/bot/login.py#L889) | `_advance_phase` | Executa a fase atual quando nada excepcional foi detectado. |
| *literal em* `_advance_phase` | 1 s | = | FIXO | [login.py:900](blazesbot/bot/login.py#L900) | `_advance_phase` | Executa a fase atual quando nada excepcional foi detectado. |


## O SISTEMA — supervisor e watchdog

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `FATIA_DA_ESPERA` | 0.25 s | = | PASSO | [context.py:211](blazesbot/bot/context.py#L211) | `tick` | Fatia máxima de sono dentro de um `tick`. |
| *literal em* `wait_if_paused` | 0.075 s | = | FIXO | [context.py:471](blazesbot/bot/context.py#L471) | `wait_if_paused` | Bloqueia enquanto a pausa estiver ativa. |
| `PASSO_DA_SONDA` | 0.012 s | = | PASSO | [instrumentar_clique.py:110](blazesbot/bot/instrumentar_clique.py#L110) | `_sondar_ate_mudar` | De quanto em quanto tempo a sonda fotografa o minimapa esperando o efeito. |
| `TETO_DA_SONDA` | 1.2 s | = | TETO | [instrumentar_clique.py:113](blazesbot/bot/instrumentar_clique.py#L113) | `_sondar_ate_mudar, _um_modo` | Teto da espera pelo efeito. Passou disso, o clique é dado como PERDIDO. |
| *literal em* `rodar` | 0.05 s | = | FIXO | [instrumentar_clique.py:390](blazesbot/bot/instrumentar_clique.py#L390) | `rodar` |  |
| *literal em* `main` | 8 s | = | FIXO | [instrumentar_clique.py:488](blazesbot/bot/instrumentar_clique.py#L488) | `main` |  |
| `CONVITE_VALIDO_SEGUNDOS` | 60 s (1 min) | = | FIXO | [mural.py:63](blazesbot/bot/mural.py#L63) | `convite_pendente` | Validade do anúncio. Cobre a fila de resposta do outro cliente com folga; mais |
| `ACEITE_VALIDO_SEGUNDOS` | 15 s | = | FIXO | [mural.py:185](blazesbot/bot/mural.py#L185) | `aceite_pendente` | Validade do aceite. Curta de propósito: ele confirma UM convite recém-enviado, |
| `LARGADA_VALIDA_SEGUNDOS` | 3 s | *novo* | FIXO | [mural.py:269](blazesbot/bot/mural.py#L269) | `largada_pendente` | Quanto tempo uma largada anunciada continua valendo. |
| `ESTADO_VALIDO_SEGUNDOS` | 30 s | *novo* | FIXO | [mural.py:277](blazesbot/bot/mural.py#L277) | `estado_da_conta` | Quanto tempo o estado publicado por uma conta continua valendo. |
| `PASSO_VERTICAL` | 4 s | = | PASSO | [recorte_do_time.py:90](blazesbot/bot/recorte_do_time.py#L90) | `_candidatos` |  |
| `TETO_DA_FATIA_DE_ESPERA` | 0.25 s | = | TETO | [supervisor.py:70](blazesbot/bot/supervisor.py#L70) | `wait` | Teto de uma fatia dentro de `_AnyEvent.wait`. É REDE, não o caminho normal -- |
| *literal em* `_sleep_interruptible` | 0.125 s | = | FIXO | [supervisor.py:247](blazesbot/bot/supervisor.py#L247) | `_sleep_interruptible` |  |
| *literal em* `_launch_client` | 1 s | = | FIXO | [supervisor.py:335](blazesbot/bot/supervisor.py#L335) | `_launch_client` | Lança o Client.bat e devolve o PID da nova instância. |
| *literal em* `_find_window` | 1 s | = | FIXO | [supervisor.py:352](blazesbot/bot/supervisor.py#L352) | `_find_window` | Localiza a janela de nível superior pertencente ao PID. |
| *literal em* `_run_session` | 1.5 s | = | FIXO | [supervisor.py:919](blazesbot/bot/supervisor.py#L919) | `_run_session` | Uma sessão: obter uma janela, logar se preciso, e operar. |
| *literal em* `_operate` | 0.5 s | = | FIXO | [supervisor.py:1113](blazesbot/bot/supervisor.py#L1113) | `_operate` | Opera a conta logada, respeitando o farm ligado/desligado ao vivo. |
| `ESPERA_DO_MENU` | 0.35 s | = | FIXO | [team.py:134](blazesbot/bot/team.py#L134) | `_enviar_convite` | Tempo para o menu de contexto aparecer depois do clique direito. |
| `ESPERA_PELA_RESPOSTA` | 4 s | = | FIXO | [team.py:139](blazesbot/bot/team.py#L139) | `montar_time` | Quanto esperar a outra conta aceitar. Ela recebe o anúncio interno e clica no |
| `PASSO_DA_ESPERA_DO_TIME` | 0.1 s | = | PASSO | [team.py:147](blazesbot/bot/team.py#L147) | `montar_time` | De quanto em quanto tempo conferir se o time já formou. |
| *literal em* `_abrir_lista` | 0.6 s | = | FIXO | [team.py:277](blazesbot/bot/team.py#L277) | `_abrir_lista` | Abre a lista de amigos e vai para a aba Block. |
| *literal em* `_abrir_lista` | 0.45 s | = | FIXO | [team.py:282](blazesbot/bot/team.py#L282) | `_abrir_lista` | Abre a lista de amigos e vai para a aba Block. |
| *literal em* `_fechar_janelas` | 0.35 s | = | FIXO | [team.py:310](blazesbot/bot/team.py#L310) | `_fechar_janelas` | Fecha a caixa de nick e a lista de amigos, CONFIRMANDO que fecharam. |
| *literal em* `_fechar_janelas` | 0.4 s | = | FIXO | [team.py:318](blazesbot/bot/team.py#L318) | `_fechar_janelas` | Fecha a caixa de nick e a lista de amigos, CONFIRMANDO que fecharam. |
| *literal em* `_fechar_janelas` | 0.3 s | = | FIXO | [team.py:326](blazesbot/bot/team.py#L326) | `_fechar_janelas` | Fecha a caixa de nick e a lista de amigos, CONFIRMANDO que fecharam. |
| *literal em* `_limpar_lista` | 0.15 s | = | FIXO | [team.py:356](blazesbot/bot/team.py#L356) | `_limpar_lista` | Remove todas as entradas da Block list. |
| *literal em* `_limpar_lista` | 0.25 s | = | FIXO | [team.py:358](blazesbot/bot/team.py#L358) | `_limpar_lista` | Remove todas as entradas da Block list. |
| *literal em* `_limpar_lista` | 0.2 s | = | FIXO | [team.py:362](blazesbot/bot/team.py#L362) | `_limpar_lista` | Remove todas as entradas da Block list. |
| *literal em* `_adicionar_nick` | 0.5 s | = | FIXO | [team.py:373](blazesbot/bot/team.py#L373) | `_adicionar_nick` | Adiciona um nick à Block list pelo botão Block. |
| *literal em* `_adicionar_nick` | 0.2 s | = | FIXO | [team.py:381](blazesbot/bot/team.py#L381) | `_adicionar_nick` | Adiciona um nick à Block list pelo botão Block. |
| *literal em* `_adicionar_nick` | 0.1 s | = | FIXO | [team.py:383](blazesbot/bot/team.py#L383) | `_adicionar_nick` | Adiciona um nick à Block list pelo botão Block. |
| *literal em* `_adicionar_nick` | 0.2 s | = | FIXO | [team.py:385](blazesbot/bot/team.py#L385) | `_adicionar_nick` | Adiciona um nick à Block list pelo botão Block. |
| *literal em* `_adicionar_nick` | 0.6 s | = | FIXO | [team.py:387](blazesbot/bot/team.py#L387) | `_adicionar_nick` | Adiciona um nick à Block list pelo botão Block. |
| *literal em* `_enviar_convite` | 0.5 s | = | FIXO | [team.py:520](blazesbot/bot/team.py#L520) | `_enviar_convite` | Envia o convite pelo MENU DE CONTEXTO da entrada na Block list. |
| *literal em* `sair_do_time` | 0.4 s | = | FIXO | [team.py:683](blazesbot/bot/team.py#L683) | `sair_do_time` | Sai do time por DOIS CLIQUES medidos no cliente. |
| *literal em* `sair_do_time` | 0.5 s | = | FIXO | [team.py:698](blazesbot/bot/team.py#L698) | `sair_do_time` | Sai do time por DOIS CLIQUES medidos no cliente. |
| *literal em* `_aceitar` | 0.5 s | = | FIXO | [team.py:936](blazesbot/bot/team.py#L936) | `_aceitar` |  |
| *literal em* `_recusar` | 0.5 s | = | FIXO | [team.py:943](blazesbot/bot/team.py#L943) | `_recusar` |  |
| `ESPERA_DEPOIS_DO_CLIQUE` | 0.35 s | = | FIXO | [teste_do_cursor.py:100](blazesbot/bot/teste_do_cursor.py#L100) | `_uma_fase` |  |
| *literal em* `main` | 8 s | = | FIXO | [teste_do_cursor.py:476](blazesbot/bot/teste_do_cursor.py#L476) | `main` |  |


## CORE — capacidades compartilhadas

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `ESPERA_ENTRE_CLIQUES` | 0.1 s | = | FIXO | [catador.py:96](blazesbot/core/catador.py#L96) | `catar` | Espera entre dois cliques direitos. Também do T-R0XX. Não é tempo de abrir a |
| `ESPERA_APOS_PEGAR` | 4 s | = | FIXO | [catador.py:112](blazesbot/core/catador.py#L112) | `_pegar` | Espera entre o clique no botão e a próxima conferência. NÚMERO DO USUÁRIO. |
| `TETO_DE_CLIQUES` | 10 s | = | TETO | [catador.py:124](blazesbot/core/catador.py#L124) | `_pegar` | Teto de cliques no botão. REDE DE SEGURANÇA, não estratégia -- mesmo papel do |
| `ESPERA_ENTRE_PASSOS` | 0.3 s | = | PASSO | [esconder_jogadores.py:109](blazesbot/core/esconder_jogadores.py#L109) | `esconder_jogadores` | Espera entre os passos da sequência. O cliente precisa processar a abertura do |
| `TETO_DO_BLOQUEIO_MS` | 80 s (1 min) | = | TETO | [inputs.py:130](blazesbot/core/inputs.py#L130) | `_click_sendmessage_rapido, _click_postmessage_puro` | TETO do bloqueio do mouse físico, em milissegundos -- e TETO, não gasto: o |
| `INTERVALO_ENTRE_CLIQUES_DIREITOS` | 0.044 s | = | FIXO | [inputs.py:269](blazesbot/core/inputs.py#L269) | `right_click` | Espaço entre um clique e o seguinte. Curto de propósito: a aposta é que a |
| `SEGUNDOS_ENTRE_CONFERENCIAS_DO_PROCESSO` | 2 s | = | FIXO | [inputs.py:356](blazesbot/core/inputs.py#L356) | `_motivo_para_nao_enviar` | De quanto em quanto tempo o NOME do processo é reconferido. |
| *literal em* `_click_postmessage_com_delay` | 0.015 s | = | FIXO | [inputs.py:800](blazesbot/core/inputs.py#L800) | `_click_postmessage_com_delay` | 5ms (insuficiente) |
| *literal em* `_click_sendmessage_rapido` | 0.002 s | = | FIXO | [inputs.py:886](blazesbot/core/inputs.py#L886) | `_click_sendmessage_rapido` | TESTE 2 (2026-08-14): SendMessage com sleep reduzido de 15ms → 1ms. |
| *literal em* `_click_sendmessage_rapido` | 0.002 s | = | FIXO | [inputs.py:896](blazesbot/core/inputs.py#L896) | `_click_sendmessage_rapido` | TESTE 2 (2026-08-14): SendMessage com sleep reduzido de 15ms → 1ms. |
| *literal em* `_click_rapido_reafirmado` | 0.002 s | = | FIXO | [inputs.py:952](blazesbot/core/inputs.py#L952) | `_click_rapido_reafirmado` | O rápido, mais a coordenada REAFIRMADA entre o down e o up. |
| *literal em* `_click_postmessage_puro` | 0.002 s | = | FIXO | [inputs.py:1061](blazesbot/core/inputs.py#L1061) | `_click_postmessage_puro` | AS QUATRO mensagens por `PostMessageW`. Nenhuma síncrona. |
| `TETO_DA_PROVA_DA_CAMERA` | 1 s | = | TETO | [memory.py:247](blazesbot/core/memory.py#L247) | `_esperar_o_termometro` | Teto da espera pelo termômetro depois de uma escrita na câmera. |
| `PASSO_DA_PROVA_DA_CAMERA` | 0.05 s | = | PASSO | [memory.py:248](blazesbot/core/memory.py#L248) | `_esperar_o_termometro` |  |
| *literal em* `_ensure_hook_installed` | 0.05 s | = | FIXO | [mouse_shield.py:223](blazesbot/core/mouse_shield.py#L223) | `_ensure_hook_installed` | Sobe o hook uma vez. NADA aqui bloqueia o callback. |
| `SEGUNDOS_PARA_A_COMIDA_SER_USADA` | 1.5 s | *novo* | FIXO | [pet.py:131](blazesbot/core/pet.py#L131) |  | QUANTO TEMPO A COMIDA PRECISA ANTES DA PRÓXIMA AÇÃO |
| `INTERVALO_MINIMO` | 30 s | = | FIXO | [petbug.py:172](blazesbot/core/petbug.py#L172) | `aplicar_patch` | Tempos |
| `SEGUNDOS_PARA_A_JANELA_ABRIR` | 10 s | = | FIXO | [petbug.py:175](blazesbot/core/petbug.py#L175) | `_abrir_o_programa` | Espera pela janela aparecer depois de lançar o programa. |
| `SEGUNDOS_PARA_O_LOG_CONFIRMAR` | 5 s | = | FIXO | [petbug.py:177](blazesbot/core/petbug.py#L177) | `aplicar_patch, _esperar_a_confirmacao` | Espera pela confirmação no log depois do clique. |
| `FATIA_DA_ESPERA` | 0.25 s | = | PASSO | [petbug.py:178](blazesbot/core/petbug.py#L178) | `_abrir_o_programa, _esperar_a_confirmacao` |  |
| `PASSO_DA_AMOSTRAGEM_DO_QUADRO` | 8 s | = | PASSO | [vision.py:33](blazesbot/core/vision.py#L33) | `frame_is_blank` | De quantos em quantos pixels o `frame_is_blank` amostra o quadro. |


## OUTROS

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `PET_FEED_MINUTOS_MIN` | 40 s | *novo* | FIXO | [config.py:236](blazesbot/config.py#L236) | `pet_feed_na_faixa, validate` | FAIXA FECHADA DO INTERVALO DE COMIDA (26/08/2026, decisão do usuário). |
| `PET_FEED_MINUTOS_MAX` | 60 s (1 min) | *novo* | TETO | [config.py:237](blazesbot/config.py#L237) | `pet_feed_na_faixa, validate` |  |
| `PASSOS_DO_APP` | 20 s | **16 s** ⚠ | PASSO | [config.py:449](blazesbot/config.py#L449) | `_app_from_dict` | Linhas oferecidas na aba APP. Dezesseis cobre com folga a macro mais longa que |
| `MINIMO_DELAY_MS` | 100 s (2 min) | *novo* | FIXO | [config.py:468](blazesbot/config.py#L468) | `segundos_para_ms, ms_para_segundos` | Espera mínima de QUALQUER campo de tempo do APP, em milissegundos. |
| `SPEED_DURACAO_SEGUNDOS` | 30 s | = | FIXO | [config.py:734](blazesbot/config.py#L734) |  | Skill de velocidade da montaria, valores do jogo. Ficam aqui e não na |
| `INTERVALO_DE_DESCARGA_MS` | 200 s (3 min) | = | FIXO | [main_window.py:96](blazesbot/gui/main_window.py#L96) | `__init__` | Cadência com que a interface esvazia a fila de log. 5 vezes por segundo é |
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

