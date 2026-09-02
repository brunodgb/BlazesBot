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


**295 tempos catalogados** — 219 FIXOS (espera cega), 76 entre TETO e PASSO.


**6 estão diferentes do original:** `TETO_DA_CAIXA`, `PASSO_DA_ESPERA`, `ESPERA_DA_BOLSA_ABRIR`, `FATIA_DE_ESPERA`, `INTERVALO_ENTRE_INVOCACOES`, `PASSOS_DO_APP`


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
| `TETO_DO_TELEPORTE_DA_FAY` | 2 s | = | TETO | [ui_service.py:52](blazesbot/bot/bc/ui_service.py#L52) | `viajar_para_ghost_din_woods, _esperar_o_teleporte` | TELEPORTE DA FAY (Stone City -> Ghost Din Woods) |
| `PASSO_DA_ESPERA_DO_TELEPORTE` | 0.08 s | = | PASSO | [ui_service.py:53](blazesbot/bot/bc/ui_service.py#L53) | `viajar_para_ghost_din_woods, _esperar_o_teleporte` |  |
| *literal em* `entrar_no_covil_do_boss` | 1.5 s | = | FIXO | [ui_service.py:482](blazesbot/bot/bc/ui_service.py#L482) | `entrar_no_covil_do_boss` | Altar Stone -> "Secret Cemetery", que é a sala do boss. |
| *literal em* `sair_da_cave` | 1.5 s | = | FIXO | [ui_service.py:519](blazesbot/bot/bc/ui_service.py#L519) | `sair_da_cave` | Skull Herald do covil -> "Leave Bewitcher Cave". |


## FORA DA CAVE — montaria e trajeto

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `INTERVALO_RECLIQUE` | 1.1 s | *novo* | FIXO | [navegacao.py:96](blazesbot/bot/navegacao.py#L96) | `follow_path` | Intervalo MÁXIMO entre cliques enquanto anda. Não é a cadência normal -- o |
| `SEM_PROGRESSO_SEGUNDOS` | 1.2 s | *novo* | FIXO | [navegacao.py:110](blazesbot/bot/navegacao.py#L110) | `follow_path` | Sem aproximar-se do alvo por este tempo, considera travado. |
| `SEGUNDOS_PARADO_DE_VERDADE` | 1.5 s | *novo* | FIXO | [navegacao.py:140](blazesbot/bot/navegacao.py#L140) | `follow_path` | PERSONAGEM COMPLETAMENTE PARADO DENTRO DA CAVE |
| `SEGUNDOS_POR_TENTATIVA_DE_DESTRAVAR` | 4 s | *novo* | FIXO | [navegacao.py:168](blazesbot/bot/navegacao.py#L168) | `destravar_pelos_vizinhos, _tentar_circulo` | Prazo para alcançar CADA candidato da manobra de destravamento. |
| `CIRCULO_TETO_SEGUNDOS` | 6.5 s | *novo* | TETO | [navegacao.py:250](blazesbot/bot/navegacao.py#L250) | `_tentar_circulo` | Teto de tempo TOTAL do círculo antes de desistir e devolver o controle. É a |
| `SEGUNDOS_POR_CLIQUE_CIRCULO` | 1 s | *novo* | FIXO | [navegacao.py:252](blazesbot/bot/navegacao.py#L252) | `_clicar_offset_e_verificar` | Janela por ponto do círculo para saber se o clique fez o personagem andar. |
| `INTERVALO_MANUTENCAO` | 0.6 s | *novo* | FIXO | [navegacao.py:254](blazesbot/bot/navegacao.py#L254) | `follow_path` | Cadência da manutenção durante o deslocamento (poção). |
| `INTERVALO_REMONTAR` | 3 s | *novo* | FIXO | [navegacao.py:290](blazesbot/bot/navegacao.py#L290) | `_pode_tocar_na_montaria, _manter_montaria` | A MONTARIA É PRÉ-REQUISITO DE ANDAR, NÃO UMA OTIMIZAÇÃO |
| `TETO_DO_PORTAO` | 6 s | *novo* | TETO | [navegacao.py:317](blazesbot/bot/navegacao.py#L317) | `garantir_montaria_para_andar` | A ORDEM DO PORTÃO: CONFERIR -> ATIVAR -> CONFIRMAR -> ANDAR |
| `INTERVALO_PARADA_POCAO` | 10 s | *novo* | FIXO | [navegacao.py:389](blazesbot/bot/navegacao.py#L389) | `_manutencao_em_movimento` | Recarga da PARADA para tomar poção durante o trajeto. |
| *literal em* `wait_until_still` | 0.25 s | *novo* | FIXO | [navegacao.py:497](blazesbot/bot/navegacao.py#L497) | `wait_until_still` | Espera o personagem parar de andar. |
| *literal em* `_abrir_mapa` | 0.5 s | *novo* | FIXO | [navegacao.py:521](blazesbot/bot/navegacao.py#L521) | `_abrir_mapa` |  |
| *literal em* `_fechar_mapa` | 0.3 s | *novo* | FIXO | [navegacao.py:527](blazesbot/bot/navegacao.py#L527) | `_fechar_mapa` |  |
| *literal em* `_mover_pelo_mapa` | 0.2 s | *novo* | FIXO | [navegacao.py:565](blazesbot/bot/navegacao.py#L565) | `_mover_pelo_mapa` | Anda até `alvo` usando o mapa-múndi. |
| *literal em* `_mover_pelo_mapa` | 1 s | *novo* | FIXO | [navegacao.py:571](blazesbot/bot/navegacao.py#L571) | `_mover_pelo_mapa` | Anda até `alvo` usando o mapa-múndi. |
| *literal em* `_clicar_offset_e_verificar` | 0.1 s | *novo* | FIXO | [navegacao.py:871](blazesbot/bot/navegacao.py#L871) | `_clicar_offset_e_verificar` | Clique curto num offset e medição: o personagem andou? |
| *literal em* `_parada_para_pocao` | 0.25 s | *novo* | FIXO | [navegacao.py:969](blazesbot/bot/navegacao.py#L969) | `_parada_para_pocao` | Desmonta, toma poção e remonta. É a ÚNICA forma que funciona. |
| *literal em* `_parada_para_pocao` | 0.2 s | *novo* | FIXO | [navegacao.py:980](blazesbot/bot/navegacao.py#L980) | `_parada_para_pocao` | Desmonta, toma poção e remonta. É a ÚNICA forma que funciona. |
| *literal em* `follow_path` | 0.25 s | *novo* | FIXO | [navegacao.py:1238](blazesbot/bot/navegacao.py#L1238) | `follow_path` | Percorre waypoints em ordem, SEM parar entre eles. |
| *literal em* `travel_via_surroundings` | 0.5 s | *novo* | FIXO | [navegacao.py:1536](blazesbot/bot/navegacao.py#L1536) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.2 s | *novo* | FIXO | [navegacao.py:1538](blazesbot/bot/navegacao.py#L1538) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.15 s | *novo* | FIXO | [navegacao.py:1540](blazesbot/bot/navegacao.py#L1540) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.4 s | *novo* | FIXO | [navegacao.py:1542](blazesbot/bot/navegacao.py#L1542) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.25 s | *novo* | FIXO | [navegacao.py:1555](blazesbot/bot/navegacao.py#L1555) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.5 s | *novo* | FIXO | [navegacao.py:1561](blazesbot/bot/navegacao.py#L1561) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `travel_via_surroundings` | 0.25 s | *novo* | FIXO | [navegacao.py:1563](blazesbot/bot/navegacao.py#L1563) | `travel_via_surroundings` | Usa o painel Surroundings como teleporte por nome. |
| *literal em* `ensure_mounted` | 1 s | *novo* | FIXO | [navegacao.py:1928](blazesbot/bot/navegacao.py#L1928) | `ensure_mounted` |  |
| *literal em* `ensure_mounted` | 1 s | *novo* | FIXO | [navegacao.py:1939](blazesbot/bot/navegacao.py#L1939) | `ensure_mounted` |  |
| *literal em* `ensure_dismounted` | 0.75 s | *novo* | FIXO | [navegacao.py:1987](blazesbot/bot/navegacao.py#L1987) | `ensure_dismounted` |  |


## FORA DA CAVE — pontos exatos

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `SEGUNDOS_DESENCALHANDO_O_ALTAR` | 3 s | = | FIXO | [mapa_bc.py:157](blazesbot/bot/bc/mapa_bc.py#L157) |  | Quanto esperar no ponto de vai-e-volta antes de retornar. |
| `SEGUNDOS_POR_TENTATIVA_NA_SAIDA` | 1.8 s | = | FIXO | [mapa_bc.py:203](blazesbot/bot/bc/mapa_bc.py#L203) |  |  |
| `SEGUNDOS_POR_TENTATIVA_NA_FAY` | 1.8 s | = | FIXO | [mapa_bc.py:250](blazesbot/bot/bc/mapa_bc.py#L250) |  |  |


## A RUN — passos da rotina

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `PASSO_DO_RECONHECIMENTO` | 0.04 s | = | PASSO | [routine.py:120](blazesbot/bot/bc/routine.py#L120) | `_reconhecer_entrada` | PASSO: de quanto em quanto tempo perguntar, dentro da janela. A pergunta é uma |
| `ESPERA_ENTRE_TENTATIVAS` | 0.025 s | = | FIXO | [routine.py:130](blazesbot/bot/bc/routine.py#L130) | `_do_entrar` | E O INTERVALO ENTRE TENTATIVAS quase desaparece: a janela de reconhecimento já |
| `PASSO_DA_ESPERA_DO_RESETER` | 1 s | *novo* | PASSO | [routine.py:144](blazesbot/bot/bc/routine.py#L144) | `_esperar_o_reseter` | Cadência da espera pela conta de reset (ver `_esperar_o_reseter`). |
| `INTERVALO_DO_AVISO_DO_RESETER` | 300 s (5 min) | *novo* | FIXO | [routine.py:151](blazesbot/bot/bc/routine.py#L151) | `_esperar_o_reseter` | De quanto em quanto tempo repetir o aviso enquanto a trava dura. |
| `SEGUNDOS_POR_TENTATIVA_NO_ALTAR` | 1.5 s | = | FIXO | [routine.py:181](blazesbot/bot/bc/routine.py#L181) | `_encostar_exato_no_patamar` |  |
| `SEGUNDOS_ESPERANDO_A_BOLSA` | 0.2 s | = | FIXO | [routine.py:300](blazesbot/bot/bc/routine.py#L300) | `_usar_package_courage` | Quanto esperar a bolsa CONFIRMAR que abriu, lendo a memória. |
| `PASSO_DA_ESPERA_DA_BOLSA` | 0.05 s | = | PASSO | [routine.py:325](blazesbot/bot/bc/routine.py#L325) | `_usar_package_courage` | De quanto em quanto tempo perguntar se a bolsa já abriu. Era 0,15 s, o que |
| `ASSENTAMENTO_DA_BOLSA` | 0.14 s | = | FIXO | [routine.py:331](blazesbot/bot/bc/routine.py#L331) | `_usar_package_courage` | Depois que a MEMÓRIA confirma a bolsa aberta, o quanto esperar o DESENHO dela. |
| *literal em* `_do_situar` | 1 s | = | FIXO | [routine.py:534](blazesbot/bot/bc/routine.py#L534) | `_do_situar` | Olha onde o personagem está e entra no estado que faz sentido. |
| *literal em* `_do_preparar` | 0.2 s | = | FIXO | [routine.py:627](blazesbot/bot/bc/routine.py#L627) | `_do_preparar` |  |
| *literal em* `_do_recuperar` | 3 s | = | FIXO | [routine.py:2349](blazesbot/bot/bc/routine.py#L2349) | `_do_recuperar` | Recuperação após morte ou falhas em sequência. |


## DENTRO DA CAVE — combate

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `SEGUNDOS_SENTADO_APOS_GUARDAS` | 4 s | = | FIXO | [combat.py:76](blazesbot/bot/bc/combat.py#L76) | `sentar_para_recuperar` | Quatro segundos sentado recuperam vida e mana de graça, e é o único momento da |
| `SEGUNDOS_DA_POCAO_DE_VIDA` | 15 s | = | FIXO | [combat.py:92](blazesbot/bot/bc/combat.py#L92) | `curar_ao_entrar, _beber_ate_encher (+1)` | A POÇÃO DE VIDA LEVA 15 SEGUNDOS, E ANDAR CANCELA |
| `SEGUNDOS_DEPOIS_DA_SUPER_SKILL` | 12 s | = | FIXO | [combat.py:96](blazesbot/bot/bc/combat.py#L96) | `curar_ao_entrar, curar_antes_do_boss` | Respiro depois da Super Skill de cura. Ela é instantânea; isto é só o tempo de |
| `ESPERA_DEPOIS_DO_TAB` | 0.6 s | = | FIXO | [combat.py:116](blazesbot/bot/bc/combat.py#L116) | `_trocar_de_alvo, fase_do_boss_por_combate` | Espera depois de UM TAB, para a seleção chegar da rede antes de conferir. |
| `FATIA_DA_ESPERA_DA_POCAO` | 0.5 s | = | PASSO | [combat.py:148](blazesbot/bot/bc/combat.py#L148) | `_esperar_o_efeito_da_pocao` | Fatia da espera da poção. O TOTAL é medido por relógio (ver acima), então esta |
| `SEGUNDOS_DE_CONJURACAO_DA_CURA` | 1.6 s | = | FIXO | [combat.py:238](blazesbot/bot/bc/combat.py#L238) | `_a_cura_subiu` | Conjuração da skill de cura. Informado pelo usuário em 19/08/2026. |
| `INTERVALO_DE_CONFERENCIA` | 0.1 s | = | FIXO | [combat.py:244](blazesbot/bot/bc/combat.py#L244) | `_a_cura_subiu` | De quanto em quanto tempo perguntar se a vida subiu. É leitura de memória -- |
| `SEGUNDOS_SEM_ALVO_PARA_MORTE` | 3 s | = | FIXO | [combat.py:296](blazesbot/bot/bc/combat.py#L296) |  | 2. TEMPO -- segundos contínuos sem nada vivo selecionado. Dá lastro à contagem: |
| `PASSO_DA_VIGIA_DE_COMBATE` | 0.05 s | = | PASSO | [combat.py:376](blazesbot/bot/bc/combat.py#L376) | `esperar_entrar_em_combate, atacar_ate_sair_de_combate (+2)` | Passo da vigia da flag. É o que "não bloqueante" significa na prática: o laço |
| `ESPERA_PARA_ENTRAR_EM_COMBATE` | 5 s | = | FIXO | [combat.py:383](blazesbot/bot/bc/combat.py#L383) | `esperar_entrar_em_combate` | Quanto esperar a flag LIGAR depois de chegar no waypoint. |
| `ESPERA_ENTRAR_EM_COMBATE_GUARDAS` | 5 s | = | FIXO | [combat.py:392](blazesbot/bot/bc/combat.py#L392) | `_fase_dos_guardas_com_tab, _fase_dos_guardas_sem_tab` | Prazo curto para os GUARDAS (os 4 mobs no waypoint antes do boss). |
| `AVISO_DA_ESPERA_SEM_PRAZO` | 10 s | = | TETO | [combat.py:409](blazesbot/bot/bc/combat.py#L409) | `esperar_entrar_em_combate` | Cadência do aviso enquanto espera sem prazo. Uma espera sem limite PRECISA |
| `CARENCIA_SEM_LER_O_NOME` | 3 s | = | FIXO | [combat.py:680](blazesbot/bot/bc/combat.py#L680) | `atacar_ate_sair_de_combate` | Quantos TAB gastar tentando SAIR de um alvo errado, por luta. |
| `TETO_DO_DESTRAVAMENTO` | 60 s (1 min) | *novo* | TETO | [combat.py:740](blazesbot/bot/bc/combat.py#L740) | `limpar_o_combate` | Teto de UMA rodada de destravamento. Palavra do usuario: *"no maximo atrasar 1 |
| `ESPERA_APOS_A_MORTE_ANTES_DO_TAB` | 3 s | *novo* | FIXO | [combat.py:754](blazesbot/bot/bc/combat.py#L754) | `limpar_o_combate` | Quanto esperar PARADO, sem bater, depois de cada morte, antes de gastar o TAB |
| `CADENCIA_DA_LEITURA_DO_ALVO` | 0.15 s | = | PASSO | [combat.py:884](blazesbot/bot/bc/combat.py#L884) | `atacar_ate_sair_de_combate, _bater_ate_o_alvo_cair` | De quanto em quanto tempo olhar a barra do alvo durante a luta. |
| `CARENCIA_APOS_O_TAB` | 2.4 s | = | FIXO | [combat.py:893](blazesbot/bot/bc/combat.py#L893) | `atacar_ate_sair_de_combate, _bater_ate_o_alvo_cair` | Depois de apertar TAB, quanto tempo ignorar a leitura. |
| `SEGUNDOS_ANTES_DO_TAB_NO_BOSS` | 4 s | = | FIXO | [combat.py:894](blazesbot/bot/bc/combat.py#L894) | `fase_do_boss_por_combate` |  |
| *literal em* `auto_selecionar` | 0.125 s | = | FIXO | [combat.py:1099](blazesbot/bot/bc/combat.py#L1099) | `auto_selecionar` | Seleciona o próprio personagem (F1), para skill em si mesmo. |
| *literal em* `maintain` | 0.15 s | = | FIXO | [combat.py:1229](blazesbot/bot/bc/combat.py#L1229) | `maintain` | Poções e cura, escolhendo o item certo para a situação. |
| *literal em* `maintain` | 0.2 s | = | FIXO | [combat.py:1251](blazesbot/bot/bc/combat.py#L1251) | `maintain` | Poções e cura, escolhendo o item certo para a situação. |
| *literal em* `maintain` | 0.15 s | = | FIXO | [combat.py:1256](blazesbot/bot/bc/combat.py#L1256) | `maintain` | Poções e cura, escolhendo o item certo para a situação. |
| *literal em* `_manter_vida_caminho_antigo` | 0.2 s | = | FIXO | [combat.py:1286](blazesbot/bot/bc/combat.py#L1286) | `_manter_vida_caminho_antigo` | O comportamento anterior a 19/08/2026, inteiro. |
| *literal em* `_manter_vida_caminho_antigo` | 0.15 s | = | FIXO | [combat.py:1293](blazesbot/bot/bc/combat.py#L1293) | `_manter_vida_caminho_antigo` | O comportamento anterior a 19/08/2026, inteiro. |
| *literal em* `_manter_vida_caminho_antigo` | 0.15 s | = | FIXO | [combat.py:1298](blazesbot/bot/bc/combat.py#L1298) | `_manter_vida_caminho_antigo` | O comportamento anterior a 19/08/2026, inteiro. |
| *literal em* `esperar_entrar_em_combate` | 0.2 s | = | FIXO | [combat.py:1681](blazesbot/bot/bc/combat.py#L1681) | `esperar_entrar_em_combate` | Espera a flag de combate LIGAR. NÃO aperta TAB, não mira nada. |
| *literal em* `_travar_no_cemetery_guard` | 0.28 s | *novo* | FIXO | [combat.py:1913](blazesbot/bot/bc/combat.py#L1913) | `_travar_no_cemetery_guard` | A ÚNICA trava do waypoint dos guardas -- UMA porta, duas fontes. |
| *literal em* `sentar_para_recuperar` | 0.25 s | = | FIXO | [combat.py:3217](blazesbot/bot/bc/combat.py#L3217) | `sentar_para_recuperar` | Senta alguns segundos para recuperar vida e mana, e levanta. |
| *literal em* `_curar_antes_da_segunda_fase` | 0.3 s | = | FIXO | [combat.py:3236](blazesbot/bot/bc/combat.py#L3236) | `_curar_antes_da_segunda_fase` | Cura antes de encostar na fase seguinte, se a conta pedir. |
| *literal em* `heal_to_full` | 0.125 s | = | FIXO | [combat.py:3604](blazesbot/bot/bc/combat.py#L3604) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.125 s | = | FIXO | [combat.py:3607](blazesbot/bot/bc/combat.py#L3607) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.125 s | = | FIXO | [combat.py:3610](blazesbot/bot/bc/combat.py#L3610) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.3 s | = | FIXO | [combat.py:3613](blazesbot/bot/bc/combat.py#L3613) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.25 s | = | FIXO | [combat.py:3642](blazesbot/bot/bc/combat.py#L3642) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.6 s | = | FIXO | [combat.py:3655](blazesbot/bot/bc/combat.py#L3655) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.15 s | = | FIXO | [combat.py:3664](blazesbot/bot/bc/combat.py#L3664) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.15 s | = | FIXO | [combat.py:3668](blazesbot/bot/bc/combat.py#L3668) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.4 s | = | FIXO | [combat.py:3672](blazesbot/bot/bc/combat.py#L3672) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `heal_to_full` | 0.5 s | = | FIXO | [combat.py:3674](blazesbot/bot/bc/combat.py#L3674) | `heal_to_full` | Recuperação longa, com poção, Super Skill e sentar. |
| *literal em* `ensure_pet` | 1.5 s | = | FIXO | [combat.py:3702](blazesbot/bot/bc/combat.py#L3702) | `ensure_pet` | Garante que o pet está invocado. |
| *literal em* `ensure_pet` | 1.5 s | = | FIXO | [combat.py:3715](blazesbot/bot/bc/combat.py#L3715) | `ensure_pet` | Garante que o pet está invocado. |
| *literal em* `apply_buffs` | 0.6 s | = | FIXO | [combat.py:3742](blazesbot/bot/bc/combat.py#L3742) | `apply_buffs` | Aplica os buffs configurados, em si mesmo. |


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
| `SEGUNDOS_ENTRE_POCOES` | 15 s | = | FIXO | [cura.py:141](blazesbot/bot/app/cura.py#L141) | `_curar_com_pocao` | Quanto esperar entre uma poção e a próxima. |
| `SEGUNDOS_PARA_VOLTAR_AO_PONTO` | 5 s | = | TETO | [cura.py:158](blazesbot/bot/app/cura.py#L158) | `_voltar_ao_ponto` | Teto da caminhada de volta ao ponto inicial. |
| `SEGUNDOS_SENTADO` | 30 s | = | TETO | [cura.py:169](blazesbot/bot/app/cura.py#L169) | `_curar_sentado` | Teto sentado, para quem não tem tecla de poção configurada. |
| `SEGUNDOS_ESPERANDO_SAIR_DE_BATALHA` | 2 s | = | FIXO | [cura.py:176](blazesbot/bot/app/cura.py#L176) | `_esperar_sair_de_batalha` | Quanto esperar a flag de batalha baixar depois que a macro termina. |
| `SEGUNDOS_PARA_SENTAR_COM_A_POCAO` | 1 s | *novo* | FIXO | [cura.py:187](blazesbot/bot/app/cura.py#L187) | `_a_pocao_saiu` | Quanto esperar o personagem SENTAR depois de apertar a tecla de poção. |
| `PASSO_DA_PERGUNTA` | 0.1 s | = | PASSO | [cura.py:192](blazesbot/bot/app/cura.py#L192) | `_esperar_sair_de_batalha, _voltar_ao_ponto (+2)` | Cadência de toda pergunta deste módulo. Leitura de memória é ~1 µs; o custo é |
| `TETO_DE_SEGUNDOS` | 10 s | = | TETO | [deletador.py:147](blazesbot/bot/app/deletador.py#L147) | `deletar_lixo, limpar_a_bolsa` | Teto do passo inteiro (verificar + apagar), pedido do usuário. |
| `TETO_DA_CAIXA` | 1.2 s | **1 s** ⚠ | TETO | [deletador.py:150](blazesbot/bot/app/deletador.py#L150) | `_esperar_a_caixa` | Espera pela caixa de confirmação aparecer, depois do clique no ícone. |
| `PASSO_DA_ESPERA` | 0.08 s | **0.05 s** ⚠ | PASSO | [deletador.py:151](blazesbot/bot/app/deletador.py#L151) | `_esperar_a_caixa` |  |
| `ESPERA_DA_BOLSA_ABRIR` | 0.58 s | **0.35 s** ⚠ | FIXO | [deletador.py:158](blazesbot/bot/app/deletador.py#L158) | `limpar_a_bolsa, _fechar_a_bolsa` | A janela do inventário terminar de pintar depois da tecla. A memória confirma |
| *literal em* `_apagar_um` | 0.05 s | = | FIXO | [deletador.py:390](blazesbot/bot/app/deletador.py#L390) | `_apagar_um` | Uma exclusão completa: item -> ícone -> Ok. |
| `FATIA_DE_ESPERA` | 0.08 s | **0.05 s** ⚠ | PASSO | [executor.py:88](blazesbot/bot/app/executor.py#L88) | `_esperar, _dormir (+1)` | Fatia máxima de espera antes de conferir se é para continuar. 0,05 s dá parada |
| `INTERVALO_ENTRE_INVOCACOES` | 6 s | **10 s** ⚠ | FIXO | [executor.py:148](blazesbot/bot/app/executor.py#L148) | `garantir_pet` | Intervalo mínimo entre dois toques na tecla do pet. |
| `ESPERA_DEPOIS_DE_INVOCAR` | 1 s | = | FIXO | [executor.py:153](blazesbot/bot/app/executor.py#L153) | `garantir_pet` | Espera depois de apertar a tecla do pet, antes de seguir para as teclas da |
| `SEGUNDOS_PARA_O_ALVO_APARECER` | 0.35 s | *novo* | FIXO | [executor.py:184](blazesbot/bot/app/executor.py#L184) | `_esperar_o_alvo_trocar` | O TAB DEIXOU DE SER LINHA DA MACRO |
| `PASSO_DA_CONFERENCIA_DO_ALVO` | 0.16 s | *novo* | PASSO | [executor.py:222](blazesbot/bot/app/executor.py#L222) | `_esperar, _observar_depois_da_morte` | De quanto em quanto tempo perguntar "o alvo morreu?" DENTRO da espera de uma |
| `SEGUNDOS_PARA_A_RODA_REINICIAR` | 1.6 s | *novo* | FIXO | [executor.py:281](blazesbot/bot/app/executor.py#L281) | `_garantir_alvo` | Quanto esperar depois de uma aquisição FRACASSADA, antes da volta seguinte. |
| `ESPERA_SEM_ALVO` | 0.4 s | *novo* | FIXO | [executor.py:460](blazesbot/bot/app/executor.py#L460) | `uma_volta, _uma_volta_simples` | Quanto esperar antes de tentar de novo quando NÃO HÁ alvo vivo. |
| `ESPERA_ANTES_DO_TAB` | 0.4 s | *novo* | FIXO | [executor.py:487](blazesbot/bot/app/executor.py#L487) | `_tab_simples, _garantir_alvo` | PAGO UMA VEZ POR AQUISIÇÃO, NÃO UMA VEZ POR TECLA |
| `ESPERA_DEPOIS_DO_TAB` | 0.01 s | *novo* | FIXO | [executor.py:507](blazesbot/bot/app/executor.py#L507) | `_respiro_depois_do_tab` | Respiro entre o TAB e a PRIMEIRA linha da macro. |
| `SEGUNDOS_PARA_A_TRAVA_DEVOLVER` | 2 s | = | FIXO | [executor.py:509](blazesbot/bot/app/executor.py#L509) | `_voltar_para_base` |  |
| `MINIMO_DE_ESPERA_DO_APP_MS` | 100 s (2 min) | *novo* | FIXO | [executor.py:516](blazesbot/bot/app/executor.py#L516) | `_respiro_depois_do_tab` | Piso de qualquer tempo do APP, em milissegundos. O MESMO número vive em |
| `SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE` | 2.5 s | *novo* | FIXO | [executor.py:572](blazesbot/bot/app/executor.py#L572) | `_observar_depois_da_morte` | DEPOIS DE MATAR, O BOT OBSERVA -- E O QUE ELE OBSERVA É A BATALHA |
| `INTERVALO_MINIMO_DA_TELA` | 0.5 s | *novo* | FIXO | [executor.py:640](blazesbot/bot/app/executor.py#L640) | `_olhar_a_tela` | Intervalo minimo entre duas capturas. |
| `ESPERA_ENTRE_TABS` | 0.6 s | *novo* | FIXO | [executor.py:679](blazesbot/bot/app/executor.py#L679) | `_garantir_alvo` | Espaçamento entre um salto da roda do TAB e o seguinte. |
| `PASSO_DA_ESPERA_DA_BASE` | 0.1 s | = | PASSO | [executor.py:694](blazesbot/bot/app/executor.py#L694) | `_esperar_chegar_na_base` | Cadência da pergunta "já cheguei?". Leitura de posição é de microssegundos; o |
| `PASSO_DA_CONFIRMACAO_DO_TAB` | 0.01 s | *novo* | PASSO | [executor.py:718](blazesbot/bot/app/executor.py#L718) | `_esperar_o_alvo_trocar` | ERA AQUI O ATRASO ENTRE O TAB E A LINHA 1 -- 26/08/2026 |
| `SEGUNDOS_DO_PASSO_DO_SHUFFLE` | 3 s | *novo* | PASSO | [executor.py:724](blazesbot/bot/app/executor.py#L724) | `_fazer_shuffle_anti_afk` | Cada perna do shuffle anti-AFK (ida e volta). Era `time.sleep(1.0)` cego duas |
| *literal em* `rodar` | 0.25 s | = | FIXO | [executor.py:2823](blazesbot/bot/app/executor.py#L2823) | `rodar` | Laço contínuo: volta após volta, até `continuar()` devolver False. |
| `PASSO_DA_FADA` | 0.1 s | *novo* | PASSO | [fada.py:58](blazesbot/bot/app/fada.py#L58) | `rodar` | Cadência do laço da Fada quando não há nada a fazer. |
| `TETO_PARA_O_ALVO_VIRAR` | 0.4 s | *novo* | TETO | [fada.py:65](blazesbot/bot/app/fada.py#L65) | `_clique_saiu_errado` | Depois do clique no retrato, quanto esperar a memória mostrar o alvo novo. |
| `PASSO_DA_CONFERENCIA_DO_ALVO` | 0.02 s | *novo* | PASSO | [fada.py:66](blazesbot/bot/app/fada.py#L66) | `_clique_saiu_errado` |  |
| `TETO_DA_CURA_SEGUNDOS` | 20 s | *novo* | TETO | [fada.py:73](blazesbot/bot/app/fada.py#L73) | `_me_defender, _curar (+1)` | Quanto tempo insistir numa cura antes de desistir daquela vítima. |
| `ESPERA_ENTRE_CURAS` | 0.34 s | *novo* | FIXO | [fada.py:80](blazesbot/bot/app/fada.py#L80) | `_me_defender, _curar (+1)` | Entre uma tecla de cura e a seguinte. |
| `ESPERA_DEPOIS_DE_ERRAR` | 0.333 s | *novo* | FIXO | [fada.py:98](blazesbot/bot/app/fada.py#L98) | `_atender` | Depois de uma tentativa que não pegou, espera antes da seguinte. |
| `SEGUNDOS_ENTRE_CUIDADOS` | 30 s | *novo* | FIXO | [fada.py:108](blazesbot/bot/app/fada.py#L108) | `_cuidados_de_ociosa` | De quanto em quanto tempo a Fada cuida do pet e da bolsa, ESTANDO OCIOSA. |
| `ESPERA_ENTRE_TABS_DO_ALINHAMENTO` | 0.5 s | *novo* | FIXO | [sincronia.py:97](blazesbot/bot/app/sincronia.py#L97) |  | Cadência do TAB durante o alinhamento. |
| `PASSO_DA_ESPERA_DA_LARGADA` | 0.04 s | *novo* | PASSO | [sincronia.py:100](blazesbot/bot/app/sincronia.py#L100) | `_esperar_os_seguidores, _entrar_na_largada` | De quanto em quanto tempo o seguidor confere se a largada saiu. |
| `SEGUNDOS_SEM_MUDANCA_PARA_TAB` | 3 s | *novo* | FIXO | [sincronia.py:108](blazesbot/bot/app/sincronia.py#L108) | `conferir_a_parada` | Sem trocar de estado de batalha por este tempo, dá TAB. |
| `TETO_DA_LINHA_SEGUNDOS` | 2 s | *novo* | TETO | [sincronia.py:116](blazesbot/bot/app/sincronia.py#L116) | `linha_a_enviar` | Quanto o seguidor espera a marca de UMA linha antes de mandar assim mesmo. |
| `PASSO_DA_ESPERA_DA_LINHA` | 0.05 s | *novo* | PASSO | [sincronia.py:121](blazesbot/bot/app/sincronia.py#L121) | `linha_a_enviar` | De quanto em quanto tempo a espera da linha acorda para conferir o botão |


## LOGIN E RELOGIN

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `PRE_SERVER_TIMEOUT` | 600 s (10 min) | = | TETO | [login.py:75](blazesbot/bot/login.py#L75) | `run` | NÃO EXISTE LIMITE DE TEMPO NA FILA. |
| `ESPERA_CEGA_SEGUNDOS` | 90 s (2 min) | = | FIXO | [login.py:91](blazesbot/bot/login.py#L91) | `_advance_phase` | Depois de esgotar as tentativas às cegas, o bot NÃO desiste -- ele espaça. |
| `ESPERA_SERVIDOR_FORA` | 10 s | = | FIXO | [login.py:107](blazesbot/bot/login.py#L107) | `_handle_acquiring_ip` | Espera depois de fechar "Acquiring server IP address." (servidores fora do ar). |
| `ESPERA_SERVIDOR_FORA_MAX` | 60 s (1 min) | = | TETO | [login.py:108](blazesbot/bot/login.py#L108) | `_handle_acquiring_ip` |  |
| `SEGUNDOS_CONECTANDO` | 6 s | = | FIXO | [login.py:134](blazesbot/bot/login.py#L134) | `_handle_connecting` | "Connecting to the server, please wait a moment." -- espera LEGÍTIMA, com |
| `FATIA_DA_ESPERA_DO_LOGIN` | 0.05 s | = | PASSO | [login.py:139](blazesbot/bot/login.py#L139) | `_esperar` | Fatia da espera do login. A espera é cumprida em pedaços para que Parar e |
| *literal em* `_abort_if_stopped` | 0.075 s | = | FIXO | [login.py:304](blazesbot/bot/login.py#L304) | `_abort_if_stopped` | Verifica parada E pausa. |
| *literal em* `_do_credentials` | 0.35 s | = | FIXO | [login.py:376](blazesbot/bot/login.py#L376) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.15 s | = | FIXO | [login.py:378](blazesbot/bot/login.py#L378) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.3 s | = | FIXO | [login.py:380](blazesbot/bot/login.py#L380) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.25 s | = | FIXO | [login.py:383](blazesbot/bot/login.py#L383) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.15 s | = | FIXO | [login.py:389](blazesbot/bot/login.py#L389) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 0.3 s | = | FIXO | [login.py:391](blazesbot/bot/login.py#L391) | `_do_credentials` |  |
| *literal em* `_do_credentials` | 1.25 s | = | FIXO | [login.py:394](blazesbot/bot/login.py#L394) | `_do_credentials` |  |
| *literal em* `_do_server` | 0.4 s | = | FIXO | [login.py:431](blazesbot/bot/login.py#L431) | `_do_server` | Seleciona o servidor da conta e confirma. |
| *literal em* `_do_server` | 1.75 s | = | FIXO | [login.py:461](blazesbot/bot/login.py#L461) | `_do_server` | Seleciona o servidor da conta e confirma. |
| *literal em* `_try_enter_world` | 0.6 s | = | FIXO | [login.py:493](blazesbot/bot/login.py#L493) | `_try_enter_world` | Seleciona o personagem e entra. Chamado a cada 20 s. |
| *literal em* `_try_enter_world` | 1.5 s | = | FIXO | [login.py:502](blazesbot/bot/login.py#L502) | `_try_enter_world` | Seleciona o personagem e entra. Chamado a cada 20 s. |
| *literal em* `_handle_login_error` | 0.6 s | = | FIXO | [login.py:516](blazesbot/bot/login.py#L516) | `_handle_login_error` |  |
| *literal em* `_handle_login_error` | 0.6 s | = | FIXO | [login.py:521](blazesbot/bot/login.py#L521) | `_handle_login_error` |  |
| *literal em* `_handle_conn_interrupted` | 1 s | = | FIXO | [login.py:546](blazesbot/bot/login.py#L546) | `_handle_conn_interrupted` | Fecha o aviso de conexão interrompida. |
| *literal em* `_handle_login_busy` | 0.75 s | = | FIXO | [login.py:569](blazesbot/bot/login.py#L569) | `_handle_login_busy` | Fecha o aviso "Login server is busy now, please try again." |
| *literal em* `_handle_connecting` | 0.5 s | = | FIXO | [login.py:600](blazesbot/bot/login.py#L600) | `_handle_connecting` | "Connecting to the server, please wait a moment." — espera COM PRAZO. |
| *literal em* `_handle_connecting` | 0.5 s | = | FIXO | [login.py:603](blazesbot/bot/login.py#L603) | `_handle_connecting` | "Connecting to the server, please wait a moment." — espera COM PRAZO. |
| *literal em* `_handle_acquiring_ip` | 0.6 s | = | FIXO | [login.py:658](blazesbot/bot/login.py#L658) | `_handle_acquiring_ip` | Fecha o aviso "Acquiring server IP address." e volta a tentar. |
| *literal em* `_modal_travando_antes_do_servidor` | 0.3 s | = | FIXO | [login.py:715](blazesbot/bot/login.py#L715) | `_modal_travando_antes_do_servidor` | Aviso na tela ANTES de conectar, reconhecido só pela memória. |
| *literal em* `_modal_travando_antes_do_servidor` | 0.5 s | = | FIXO | [login.py:717](blazesbot/bot/login.py#L717) | `_modal_travando_antes_do_servidor` | Aviso na tela ANTES de conectar, reconhecido só pela memória. |
| *literal em* `_handle_conn_failed` | 0.75 s | = | FIXO | [login.py:730](blazesbot/bot/login.py#L730) | `_handle_conn_failed` | Fecha o aviso "Connection failed, please try again later." |
| *literal em* `_handle_queue` | 5 s | = | FIXO | [login.py:745](blazesbot/bot/login.py#L745) | `_handle_queue` | Na fila, apenas esperar. |
| *literal em* `_finish` | 0.25 s | = | FIXO | [login.py:796](blazesbot/bot/login.py#L796) | `_finish` | Confirma a entrada no mundo e batiza a janela. |
| *literal em* `_advance_phase` | 2.5 s | = | FIXO | [login.py:901](blazesbot/bot/login.py#L901) | `_advance_phase` | Executa a fase atual quando nada excepcional foi detectado. |
| *literal em* `_advance_phase` | 1 s | = | FIXO | [login.py:912](blazesbot/bot/login.py#L912) | `_advance_phase` | Executa a fase atual quando nada excepcional foi detectado. |


## O SISTEMA — supervisor e watchdog

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `FATIA_DA_ESPERA` | 0.25 s | = | PASSO | [context.py:211](blazesbot/bot/context.py#L211) | `tick` | Fatia máxima de sono dentro de um `tick`. |
| *literal em* `wait_if_paused` | 0.075 s | = | FIXO | [context.py:471](blazesbot/bot/context.py#L471) | `wait_if_paused` | Bloqueia enquanto a pausa estiver ativa. |
| `RECARGA` | 5 s | *novo* | FIXO | [hotbar.py:63](blazesbot/bot/hotbar.py#L63) | `garantir_pagina_1` | Recarga do caminho com `ctx`. Os momentos-chave acontecem em rajada -- o portão |
| `PASSO_DA_SONDA` | 0.012 s | = | PASSO | [instrumentar_clique.py:110](blazesbot/bot/instrumentar_clique.py#L110) | `_sondar_ate_mudar` | De quanto em quanto tempo a sonda fotografa o minimapa esperando o efeito. |
| `TETO_DA_SONDA` | 1.2 s | = | TETO | [instrumentar_clique.py:113](blazesbot/bot/instrumentar_clique.py#L113) | `_sondar_ate_mudar, _um_modo` | Teto da espera pelo efeito. Passou disso, o clique é dado como PERDIDO. |
| *literal em* `rodar` | 0.05 s | = | FIXO | [instrumentar_clique.py:390](blazesbot/bot/instrumentar_clique.py#L390) | `rodar` |  |
| *literal em* `main` | 8 s | = | FIXO | [instrumentar_clique.py:488](blazesbot/bot/instrumentar_clique.py#L488) | `main` |  |
| `CONVITE_VALIDO_SEGUNDOS` | 60 s (1 min) | = | FIXO | [mural.py:63](blazesbot/bot/mural.py#L63) | `convite_pendente` | Validade do anúncio. Cobre a fila de resposta do outro cliente com folga; mais |
| `ACEITE_VALIDO_SEGUNDOS` | 15 s | = | FIXO | [mural.py:185](blazesbot/bot/mural.py#L185) | `aceite_pendente` | Validade do aceite. Curta de propósito: ele confirma UM convite recém-enviado, |
| `LARGADA_VALIDA_SEGUNDOS` | 5 s | *novo* | FIXO | [mural.py:269](blazesbot/bot/mural.py#L269) | `largada_pendente` | Quanto tempo uma largada anunciada continua valendo. |
| `ESTADO_VALIDO_SEGUNDOS` | 30 s | *novo* | FIXO | [mural.py:277](blazesbot/bot/mural.py#L277) | `estado_da_conta` | Quanto tempo o estado publicado por uma conta continua valendo. |
| `PASSO_VERTICAL` | 4 s | = | PASSO | [recorte_do_time.py:90](blazesbot/bot/recorte_do_time.py#L90) | `_candidatos` |  |
| `TETO_DA_FATIA_DE_ESPERA` | 0.25 s | = | TETO | [supervisor.py:70](blazesbot/bot/supervisor.py#L70) | `wait` | Teto de uma fatia dentro de `_AnyEvent.wait`. É REDE, não o caminho normal -- |
| *literal em* `_sleep_interruptible` | 0.125 s | = | FIXO | [supervisor.py:247](blazesbot/bot/supervisor.py#L247) | `_sleep_interruptible` |  |
| *literal em* `_launch_client` | 1 s | = | FIXO | [supervisor.py:335](blazesbot/bot/supervisor.py#L335) | `_launch_client` | Lança o Client.bat e devolve o PID da nova instância. |
| *literal em* `_find_window` | 1 s | = | FIXO | [supervisor.py:352](blazesbot/bot/supervisor.py#L352) | `_find_window` | Localiza a janela de nível superior pertencente ao PID. |
| *literal em* `_run_session` | 1.5 s | = | FIXO | [supervisor.py:919](blazesbot/bot/supervisor.py#L919) | `_run_session` | Uma sessão: obter uma janela, logar se preciso, e operar. |
| *literal em* `_operate` | 0.5 s | = | FIXO | [supervisor.py:1118](blazesbot/bot/supervisor.py#L1118) | `_operate` | Opera a conta logada, respeitando o farm ligado/desligado ao vivo. |
| *literal em* `_publicar_o_proprio_id` | 0.3 s | *novo* | FIXO | [supervisor.py:1394](blazesbot/bot/supervisor.py#L1394) | `_publicar_o_proprio_id` | o alvo leva ~0,1 s para virar |
| *literal em* `chamar_a_fada` | 0.2 s | *novo* | FIXO | [supervisor.py:1785](blazesbot/bot/supervisor.py#L1785) | `chamar_a_fada` | Pede cura à Fada do time e espera. `False` = não há Fada, beba poção. |
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
| `PASSO_DA_ESPERA_DO_DIALOGO` | 0.08 s | *novo* | PASSO | [ui_do_jogo.py:141](blazesbot/bot/ui_do_jogo.py#L141) | `_esperar_o_dialogo` | Diálogo do NPC aparecer. Era 0,30 s fixos, gastos inteiros mesmo quando o |
| `LIMITE_INICIAL_DA_ESPERA_DO_DIALOGO` | 0.65 s | *novo* | TETO | [ui_do_jogo.py:180](blazesbot/bot/ui_do_jogo.py#L180) | `limite_da_espera_do_dialogo` | TETO DA ESPERA DO DIÁLOGO -- ajustado pelo que foi MEDIDO, não chutado |
| `LIMITE_MINIMO_DA_ESPERA_DO_DIALOGO` | 0.18 s | *novo* | TETO | [ui_do_jogo.py:184](blazesbot/bot/ui_do_jogo.py#L184) | `limite_da_espera_do_dialogo` | Piso: o valor que valia antes. Abaixo disto não se aperta nem com evidência -- |
| `LIMITE_MAXIMO_DA_ESPERA_DO_DIALOGO` | 0.6 s | *novo* | TETO | [ui_do_jogo.py:188](blazesbot/bot/ui_do_jogo.py#L188) | `limite_da_espera_do_dialogo` | Teto do teto. Passado disto, o diálogo não vai abrir mesmo, e insistir só |
| `LIMITE_DA_ESPERA_DO_DIALOGO_LENTA` | 0.65 s | *novo* | TETO | [ui_do_jogo.py:214](blazesbot/bot/ui_do_jogo.py#L214) | `limite_da_espera_do_dialogo_lenta` | Diálogo aparecer na REDESCOBERTA, depois de cada clique direito. Era `tick(1.3)` |
| `ESPERA_DEPOIS_DO_LINK` | 0.2 s | *novo* | FIXO | [ui_do_jogo.py:236](blazesbot/bot/ui_do_jogo.py#L236) | `_abrir_dialogo_e_clicar` | Servidor processar o pedido de entrada. Zero na disputa: quem confirma a entrada |
| `PASSO_DA_ESPERA_DO_PAINEL` | 0.08 s | *novo* | PASSO | [ui_do_jogo.py:274](blazesbot/bot/ui_do_jogo.py#L274) | `_esperar_o_painel` | Passo e teto da espera pelo painel aparecer. Cada volta custa uma captura de |
| `LIMITE_DA_ESPERA_DO_PAINEL` | 0.8 s | *novo* | TETO | [ui_do_jogo.py:280](blazesbot/bot/ui_do_jogo.py#L280) | `abrir_surroundings, _esperar_o_painel` | O teto é EXATAMENTE a espera fixa que havia antes (1,2 s), e isso é de propósito: |
| `ESPERA_DA_TROCA_DE_ABA` | 0.05 s | *novo* | FIXO | [ui_do_jogo.py:284](blazesbot/bot/ui_do_jogo.py#L284) | `abrir_surroundings` | Assentar depois de clicar na aba NPC. Não é "esperar a aba renderizar": é só dar |
| `PASSO_DA_ESPERA_DO_RESULTADO` | 0.08 s | *novo* | PASSO | [ui_do_jogo.py:302](blazesbot/bot/ui_do_jogo.py#L302) | `_esperar_resultado_da_busca` | De quanto em quanto tempo perguntar à memória se o resultado apareceu, e por |
| `LIMITE_DA_ESPERA_DO_RESULTADO` | 0.8 s | *novo* | TETO | [ui_do_jogo.py:303](blazesbot/bot/ui_do_jogo.py#L303) | `_esperar_resultado_da_busca` |  |
| `ESPERA_CEGA_DO_RESULTADO` | 0.3 s | *novo* | FIXO | [ui_do_jogo.py:329](blazesbot/bot/ui_do_jogo.py#L329) | `_esperar_resultado_da_busca` | Quando a leitura de arredores por memória não funciona neste cliente, a lista |
| `PASSO_DA_ESPERA_DO_ANDAR` | 0.04 s | *novo* | PASSO | [ui_do_jogo.py:372](blazesbot/bot/ui_do_jogo.py#L372) | `_saiu_do_lugar` | Depois de clicar no resultado o personagem já saiu andando -- o pathfinding do |
| `LIMITE_DA_ESPERA_DO_ANDAR` | 0.4 s | *novo* | TETO | [ui_do_jogo.py:373](blazesbot/bot/ui_do_jogo.py#L373) | `ir_para_resultado, _saiu_do_lugar` |  |
| `ESPERA_DEPOIS_DE_CLICAR_NO_RESULTADO` | 0.15 s | *novo* | FIXO | [ui_do_jogo.py:374](blazesbot/bot/ui_do_jogo.py#L374) | `_saiu_do_lugar` |  |
| `INTERVALO_ENTRE_USOS_DO_PAINEL` | 2 s | *novo* | FIXO | [ui_do_jogo.py:456](blazesbot/bot/ui_do_jogo.py#L456) | `_respeitar_a_cadencia_do_painel` | CADÊNCIA MÍNIMA ENTRE UM USO DO PAINEL DE ARREDORES E O SEGUINTE |
| `PASSO_DA_ESPERA_DA_CHEGADA` | 0.25 s | *novo* | PASSO | [ui_do_jogo.py:480](blazesbot/bot/ui_do_jogo.py#L480) | `_esperar_chegar` | Passo da leitura de posição enquanto se espera a chegada. Ler memória custa |
| `PASSO_DA_ESPERA_DO_FECHAMENTO` | 0.04 s | *novo* | PASSO | [ui_do_jogo.py:498](blazesbot/bot/ui_do_jogo.py#L498) | `fechar_surroundings` |  |
| `LIMITE_DA_ESPERA_DO_FECHAMENTO` | 0.4 s | *novo* | TETO | [ui_do_jogo.py:499](blazesbot/bot/ui_do_jogo.py#L499) | `fechar_surroundings` |  |
| `ESPERA_DEPOIS_DE_FECHAR` | 0.2 s | *novo* | FIXO | [ui_do_jogo.py:500](blazesbot/bot/ui_do_jogo.py#L500) |  |  |
| `ESPERA_ANTES_DE_CONFERIR` | 0.15 s | *novo* | FIXO | [ui_do_jogo.py:502](blazesbot/bot/ui_do_jogo.py#L502) |  |  |
| `PASSOS_DE_ROLAGEM` | 12 s | *novo* | PASSO | [ui_do_jogo.py:528](blazesbot/bot/ui_do_jogo.py#L528) | `rolar_o_dialogo` | Quantas rolagens no máximo antes de aceitar que o link não está na lista. |
| `ESPERA_DA_ROLAGEM` | 0.08 s | *novo* | FIXO | [ui_do_jogo.py:533](blazesbot/bot/ui_do_jogo.py#L533) | `rolar_o_dialogo` | A lista redesenhar depois do clique na seta. Uma volta de laço do cliente, não |
| *literal em* `resetar_visao` | 0.175 s | *novo* | FIXO | [ui_do_jogo.py:652](blazesbot/bot/ui_do_jogo.py#L652) | `resetar_visao` | Aperta o View Reset para recentrar a câmera. |
| *literal em* `buscar_npc` | 0.5 s | *novo* | FIXO | [ui_do_jogo.py:1098](blazesbot/bot/ui_do_jogo.py#L1098) | `buscar_npc` | Busca um NPC e devolve o primeiro resultado, conferido. |
| *literal em* `fechar_dialogo` | 0.3 s | *novo* | FIXO | [ui_do_jogo.py:1523](blazesbot/bot/ui_do_jogo.py#L1523) | `fechar_dialogo` |  |
| *literal em* `clicar_link` | 0.75 s | *novo* | FIXO | [ui_do_jogo.py:1542](blazesbot/bot/ui_do_jogo.py#L1542) | `clicar_link` | Clica num link do diálogo, localizado pelo texto. Devolve o ponto. |
| *literal em* `clicar_link` | 0.4 s | *novo* | FIXO | [ui_do_jogo.py:1544](blazesbot/bot/ui_do_jogo.py#L1544) | `clicar_link` | Clica num link do diálogo, localizado pelo texto. Devolve o ponto. |
| `SEGUNDOS_ANDANDO_ANTES` | 0.5 s | *novo* | FIXO | [velocidade.py:45](blazesbot/bot/velocidade.py#L45) | `usar_se_puder` | Quanto o personagem precisa ter andado antes de valer a pena acionar. |


## CORE — capacidades compartilhadas

| tempo | atual | original | natureza | onde | função | para que serve |
|---|---|---|---|---|---|---|
| `ESPERA_ENTRE_CLIQUES` | 0.1 s | = | FIXO | [catador.py:96](blazesbot/core/catador.py#L96) | `catar` | Espera entre dois cliques direitos. Também do T-R0XX. Não é tempo de abrir a |
| `ESPERA_APOS_PEGAR` | 4 s | = | FIXO | [catador.py:112](blazesbot/core/catador.py#L112) | `_pegar` | Espera entre o clique no botão e a próxima conferência. NÚMERO DO USUÁRIO. |
| `TETO_DE_CLIQUES` | 10 s | = | TETO | [catador.py:124](blazesbot/core/catador.py#L124) | `_pegar` | Teto de cliques no botão. REDE DE SEGURANÇA, não estratégia -- mesmo papel do |
| `PASSO_ENTRE_RETRATOS_DO_TIME` | 80 s (1 min) | *novo* | PASSO | [coords.py:112](blazesbot/core/coords.py#L112) |  |  |
| `ESPERA_ENTRE_PASSOS` | 0.3 s | = | PASSO | [esconder_jogadores.py:109](blazesbot/core/esconder_jogadores.py#L109) | `esconder_jogadores` | Espera entre os passos da sequência. O cliente precisa processar a abertura do |
| `TETO_DO_BLOQUEIO_MS` | 80 s (1 min) | = | TETO | [inputs.py:74](blazesbot/core/inputs.py#L74) | `_click_sendmessage_rapido, _click_postmessage_puro` | TETO do bloqueio do mouse físico, em milissegundos -- e TETO, não gasto: o |
| `INTERVALO_ENTRE_CLIQUES_DIREITOS` | 0.044 s | = | FIXO | [inputs.py:213](blazesbot/core/inputs.py#L213) | `right_click` | Espaço entre um clique e o seguinte. Curto de propósito: a aposta é que a |
| `SEGUNDOS_ENTRE_CONFERENCIAS_DO_PROCESSO` | 2 s | = | FIXO | [inputs.py:300](blazesbot/core/inputs.py#L300) | `_motivo_para_nao_enviar` | De quanto em quanto tempo o NOME do processo é reconferido. |
| *literal em* `_click_postmessage_com_delay` | 0.015 s | = | FIXO | [inputs.py:760](blazesbot/core/inputs.py#L760) | `_click_postmessage_com_delay` | 5ms (insuficiente) |
| *literal em* `_click_sendmessage_rapido` | 0.002 s | = | FIXO | [inputs.py:846](blazesbot/core/inputs.py#L846) | `_click_sendmessage_rapido` | TESTE 2 (2026-08-14): SendMessage com sleep reduzido de 15ms → 1ms. |
| *literal em* `_click_sendmessage_rapido` | 0.002 s | = | FIXO | [inputs.py:856](blazesbot/core/inputs.py#L856) | `_click_sendmessage_rapido` | TESTE 2 (2026-08-14): SendMessage com sleep reduzido de 15ms → 1ms. |
| *literal em* `_click_rapido_reafirmado` | 0.002 s | = | FIXO | [inputs.py:912](blazesbot/core/inputs.py#L912) | `_click_rapido_reafirmado` | O rápido, mais a coordenada REAFIRMADA entre o down e o up. |
| *literal em* `_click_postmessage_puro` | 0.002 s | = | FIXO | [inputs.py:1021](blazesbot/core/inputs.py#L1021) | `_click_postmessage_puro` | AS QUATRO mensagens por `PostMessageW`. Nenhuma síncrona. |
| `TETO_DA_PROVA_DA_CAMERA` | 1 s | = | TETO | [memory.py:249](blazesbot/core/memory.py#L249) | `_esperar_o_termometro` | Teto da espera pelo termômetro depois de uma escrita na câmera. |
| `PASSO_DA_PROVA_DA_CAMERA` | 0.05 s | = | PASSO | [memory.py:250](blazesbot/core/memory.py#L250) | `_esperar_o_termometro` |  |
| `PASSO_ENTRE_MEMBROS` | 136 s (2 min) | *novo* | PASSO | [memory.py:280](blazesbot/core/memory.py#L280) | `time_do_jogo, vida_do_time` |  |
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
| `PET_FEED_MINUTOS_MIN` | 40 s | *novo* | FIXO | [config.py:246](blazesbot/config.py#L246) | `pet_feed_na_faixa, validate` | FAIXA FECHADA DO INTERVALO DE COMIDA (26/08/2026, decisão do usuário). |
| `PET_FEED_MINUTOS_MAX` | 60 s (1 min) | *novo* | TETO | [config.py:247](blazesbot/config.py#L247) | `pet_feed_na_faixa, validate` |  |
| `PASSOS_DO_APP` | 20 s | **16 s** ⚠ | PASSO | [config.py:459](blazesbot/config.py#L459) | `_app_from_dict` | Linhas oferecidas na aba APP. Dezesseis cobre com folga a macro mais longa que |
| `MINIMO_DELAY_MS` | 100 s (2 min) | *novo* | FIXO | [config.py:478](blazesbot/config.py#L478) | `segundos_para_ms, ms_para_segundos` | Espera mínima de QUALQUER campo de tempo do APP, em milissegundos. |
| `SPEED_DURACAO_SEGUNDOS` | 30 s | = | FIXO | [config.py:807](blazesbot/config.py#L807) |  | Skill de velocidade da montaria, valores do jogo. Ficam aqui e não na |
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

