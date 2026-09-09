# Constantes ajustáveis do BlazesBot

> **ARQUIVO GERADO.** Não edite à mão -- ele é reconstruído de
> `blazesbot/core/indice_de_constantes.py` e conferido por
> `tests/test_indice_de_constantes.py`. Editar aqui não muda o bot;
> muda o valor no arquivo indicado na coluna *onde*.

Para regenerar:

```
./.venv/Scripts/python.exe -m blazesbot.core.indice_de_constantes
```

O *porquê* resumido vem do comentário logo acima da constante; o porquê
COMPLETO (a medição, a alternativa que reprovou, o log de produção) mora
no próprio arquivo e em `docs/decisoes/`. **Nenhum destes números é
arredondamento** -- mexer sem ler a medição é repetir um experimento que
já custou runs.

---

## Interruptores -- escolhem ENTRE CAMINHOS

São os que trocam comportamento inteiro com uma palavra. Todo caminho
desligado continua no código e testado, para que voltar atrás não seja
ligar código não testado.

| constante | valor | onde | quem lê | porquê (resumo) |
|---|---|---|---|---|
| `ANDAR_SO_FORA_DE_BATALHA` | `True` | [blazesbot/bot/app/executor.py:585](blazesbot/bot/app/executor.py#L585) | — | A CAMINHADA DE VOLTA À BASE NÃO ACONTECE EM BATALHA |
| `EXIGIR_ALVO_INTEIRO` | `False` | [blazesbot/bot/app/executor.py:427](blazesbot/bot/app/executor.py#L427) | — | ALVO INTEIRO (100/100): EXIGÊNCIA REVOGADA PELO USUÁRIO -- 26/08/2026 |
| `INTERROMPER_A_MACRO_QUANDO_O_ALVO_MORRE` | `True` | [blazesbot/bot/app/executor.py:256](blazesbot/bot/app/executor.py#L256) | — | O MOB MORREU: A MACRO PARA NO MEIO E VAI PARA O PRÓXIMO |
| `LACO_SIMPLES` | `True` | [blazesbot/bot/app/executor.py:155](blazesbot/bot/app/executor.py#L155) | — | O QUE FICOU PARADO, E POR QUE NAO FOI APAGADO |
| `USAR_A_SAIDA_DE_BATALHA_PARA_CORTAR` | `True` | [blazesbot/bot/app/executor.py:634](blazesbot/bot/app/executor.py#L634) | — | SAIR DE BATALHA CORTA A MACRO NO MEIO |
| `USAR_A_TELA_COMO_SEGUNDA_PORTA` | `True` | [blazesbot/bot/app/executor.py:656](blazesbot/bot/app/executor.py#L656) | — | A SEGUNDA PORTA: A VIDA PELA TELA -- 26/08/2026 |
| `USAR_COMBATE_COMO_RESERVA_DE_MORTE` | `True` | [blazesbot/bot/app/executor.py:488](blazesbot/bot/app/executor.py#L488) | supervisor.py | A RESERVA: QUANDO O HP É ILEGÍVEL, QUEM RESPONDE É A FLAG DE COMBATE |
| `ATIVADO` | `True` | [blazesbot/bot/bc/diagnostico_do_link.py:62](blazesbot/bot/bc/diagnostico_do_link.py#L62) | deletador.py, supervisor.py, esconder_jogadores.py, patch_do_cliente.py, petbug.py | Interruptor, no padrão do `USAR_TAB_NOS_GUARDAS`: desligar é trocar uma |
| `ATACAR_DURANTE_A_CONFIRMACAO_NO_BOSS` | `True` | [blazesbot/bot/combate.py:519](blazesbot/bot/combate.py#L519) | — | SÓ NO BOSS, e a razão é o motivo pelo qual o golpe parava |
| `DESMONTAR_FORA_DA_CAVE_SO_SEM_PET` | `True` | [blazesbot/bot/combate.py:1006](blazesbot/bot/combate.py#L1006) | — | FORA DA CAVE, SÓ DESMONTA SE O PET NÃO ESTIVER ATIVO |
| `DESTRAVAMENTO_BATE_NO_ALVO_PROIBIDO` | `True` | [blazesbot/bot/combate.py:820](blazesbot/bot/combate.py#L820) | — | O DESTRAVAMENTO BATE NO CEMETERY GUARD? Decisao do usuario, 01/09/2026. |
| `EXIGIR_SAIR_DE_COMBATE_NOS_GUARDAS` | `True` | [blazesbot/bot/combate.py:578](blazesbot/bot/combate.py#L578) | — | O CUSTO, DITO INTEIRO |
| `MODO_DE_CURA` | `'skill_em_laco'` | [blazesbot/bot/combate.py:255](blazesbot/bot/combate.py#L255) | — | O TETO É POR TENTATIVA SEM EFEITO, NÃO POR RELÓGIO |
| `SO_A_MEMORIA_DECLARA_MORTE` | `True` | [blazesbot/bot/combate.py:892](blazesbot/bot/combate.py#L892) | executor.py, target_hybrid.py | SÓ A MEMÓRIA DECLARA MORTE. A TELA SÓ SABE DIZER "AINDA VIVO". |
| `SO_O_ALVO_PROIBIDO_PARA_O_GOLPE` | `True` | [blazesbot/bot/combate.py:632](blazesbot/bot/combate.py#L632) | combat.py | O QUE MUDA |
| `TAB_ATE_SAIR_DE_COMBATE_NOS_GUARDAS` | `True` | [blazesbot/bot/combate.py:649](blazesbot/bot/combate.py#L649) | mapa_hh.py | O TETO DE TAB DEIXA DE BARRAR A TROCA ENQUANTO A FLAG ESTIVER ALTA. |
| `USAR_BREAK_SOUL_SO_NA_FASE_2` | `True` | [blazesbot/bot/combate.py:299](blazesbot/bot/combate.py#L299) | combat.py | BREAK SOUL -- SÓ NA SEGUNDA FASE DO BOSS |
| `USAR_IMAGEM_DA_FASE_2` | `True` | [blazesbot/bot/combate.py:914](blazesbot/bot/combate.py#L914) | combat.py | A SEGUNDA FASE DO BOSS TAMBÉM É VISTA NA TELA |
| `USAR_PORTAO_DE_NOME` | `True` | [blazesbot/bot/combate.py:860](blazesbot/bot/combate.py#L860) | memory.py, target_hybrid.py | RELIGADO EM 25/08/2026 -- O NOME VOLTOU |
| `USAR_TAB_NOS_GUARDAS` | `True` | [blazesbot/bot/combate.py:681](blazesbot/bot/combate.py#L681) | combat.py, diagnostico_do_link.py, inputs.py | >>>  INTERRUPTOR DO EXPERIMENTO -- TROCA DE ALVO POR TAB NOS GUARDAS  <<< |
| `ATIVADO` | `True` | [blazesbot/bot/deletador.py:74](blazesbot/bot/deletador.py#L74) | diagnostico_do_link.py, supervisor.py, esconder_jogadores.py, patch_do_cliente.py, petbug.py | O caminho continua inteiro com ele em False -- desligado não é apagado. |
| `CIRCULO_POR_RAIO` | `True` | [blazesbot/bot/navegacao.py:265](blazesbot/bot/navegacao.py#L265) | — | True = raio por raio (1,2,3,5; em cada raio os 8 pontos); False = bússola por |
| `MATAR_JANELA_TRAVADA` | `True` | [blazesbot/bot/sentinela.py:166](blazesbot/bot/sentinela.py#L166) | — | INTERRUPTOR (a convenção do projeto: caminho fora de uso não vira comentário) |
| `OLHAR_A_TELA` | `False` | [blazesbot/bot/sentinela.py:201](blazesbot/bot/sentinela.py#L201) | — | O VIGIA NÃO LÊ A TELA. INTERRUPTOR DESLIGADO, com o número que o desligou. |
| `CONFIRMAR_CHEGADA_POR_COORDENADA` | `False` | [blazesbot/bot/ui_do_jogo.py:520](blazesbot/bot/ui_do_jogo.py#L520) | — | INTERRUPTOR: a coordenada do painel CONFIRMA a chegada? |
| `CONFERIR_SLOT_VAZIO` | `False` | [blazesbot/bot/vendedor.py:236](blazesbot/bot/vendedor.py#L236) | — | INTERRUPTOR -- A CONFERÊNCIA DE SLOT VAZIO ESTÁ DESLIGADA (decisão do usuário, |
| `MODO_FADA_DA_HH` | `'fada'` | [blazesbot/config.py:924](blazesbot/config.py#L924) | routine.py, supervisor.py, account_dialog.py | — |
| `MODO_PADRAO_DO_TIME` | `'largada'` | [blazesbot/config.py:602](blazesbot/config.py#L602) | — | — |
| `MODO_SOLO_DA_HH` | `'solo'` | [blazesbot/config.py:923](blazesbot/config.py#L923) | account_dialog.py | Os dois modos de reset da HH. A cave não renasce sozinha -- regra do jogo. |
| `NAO_LIMPAR_DUAS_VEZES_NA_MESMA_VOLTA` | `True` | [blazesbot/core/cadencia_da_bolsa.py:43](blazesbot/core/cadencia_da_bolsa.py#L43) | — | Interruptor do piso do conserto -- 06/09/2026. |
| `ATIVADA` | `True` | [blazesbot/core/calibracao.py:82](blazesbot/core/calibracao.py#L82) | routine.py, vendedor.py | INTERRUPTOR |
| `TELEMETRIA_LIGADA` | `True` | [blazesbot/core/cronometro.py:85](blazesbot/core/cronometro.py#L85) | instrumentacao.py | O INTERRUPTOR |
| `LIGADO` | `True` | [blazesbot/core/diagnostico_fino.py:28](blazesbot/core/diagnostico_fino.py#L28) | manutencao.py, instrumentar_clique.py, supervisor.py, config.py, log_limitado.py, account_dialog.py | — |
| `ATIVADO` | `False` | [blazesbot/core/esconder_jogadores.py:102](blazesbot/core/esconder_jogadores.py#L102) | diagnostico_do_link.py, deletador.py, supervisor.py, patch_do_cliente.py, petbug.py | INTERRUPTOR -- DESLIGADO EM 19/08/2026 |
| `PRENDER_A_TECLA` | `True` | [blazesbot/core/esconder_jogadores.py:75](blazesbot/core/esconder_jogadores.py#L75) | — | A TECLA PRESA PARA SEMPRE -- o caminho do patcher, trazido em 07/09/2026 |
| `SEGURAR_ATIVADO` | `False` | [blazesbot/core/esconder_jogadores.py:120](blazesbot/core/esconder_jogadores.py#L120) | petbug.py | INTERRUPTOR DO F12 PRESO -- DESLIGADO EM 19/08/2026 |
| `CONFERIR_A_JANELA_ANTES_DE_ENVIAR` | `True` | [blazesbot/core/inputs.py:295](blazesbot/core/inputs.py#L295) | — | INTERRUPTOR. Desligar volta ao comportamento anterior (mandar sem conferir), e |
| `MODO_DE_CLIQUE` | `'postmessage_puro'` | [blazesbot/core/inputs.py:133](blazesbot/core/inputs.py#L133) | ui_service.py, instrumentar_clique.py, teste_do_cursor.py | INTERRUPTOR DO MODO DE CLIQUE |
| `MODO_DE_TECLA` | `'postmessage'` | [blazesbot/core/inputs.py:177](blazesbot/core/inputs.py#L177) | — | INTERRUPTOR DO TECLADO -- "sendmessage" \| "postmessage" |
| `USAR_MOUSE_SHIELD` | `False` | [blazesbot/core/inputs.py:65](blazesbot/core/inputs.py#L65) | instrumentar_clique.py, teste_do_cursor.py | INTERRUPTOR DO MOUSE SHIELD |
| `INSTRUMENTAR_O_PACOTE_INTEIRO` | `True` | [blazesbot/core/instrumentacao.py:77](blazesbot/core/instrumentacao.py#L77) | — | O INTERRUPTOR |
| `COMPRIMIR_ARQUIVO_MORTO` | `True` | [blazesbot/core/log_limitado.py:108](blazesbot/core/log_limitado.py#L108) | — | O arquivo morto de DIAS ANTERIORES é comprimido. Medido no arquivo da noite de |
| `USAR_PAINEL_POR_MEMORIA` | `True` | [blazesbot/core/memory.py:579](blazesbot/core/memory.py#L579) | — | ESTADO DE PAINEL DE UI POR MEMÓRIA -- o que sobreviveu ao campo |
| `USAR_REGIOES_QUENTES` | `True` | [blazesbot/core/memory.py:434](blazesbot/core/memory.py#L434) | — | REGIÕES QUENTES -- a rota que fecha os 38% que o array de entidades perde |
| `ATIVADO` | `True` | [blazesbot/core/patch_do_cliente.py:132](blazesbot/core/patch_do_cliente.py#L132) | diagnostico_do_link.py, deletador.py, supervisor.py, esconder_jogadores.py, petbug.py | INTERRUPTOR |
| `ATIVADO` | `False` | [blazesbot/core/petbug.py:125](blazesbot/core/petbug.py#L125) | diagnostico_do_link.py, deletador.py, supervisor.py, esconder_jogadores.py, patch_do_cliente.py | DESLIGADO EM 07/09/2026 -- o bot passou a fazer isto sozinho |
| `NOVA_INSTANCIA_SEMPRE` | `True` | [blazesbot/core/petbug.py:218](blazesbot/core/petbug.py#L218) | — | INSTÂNCIA NOVA A CADA APLICAÇÃO -- 07/09/2026 |
| `USAR_OFFSET_FIXO_DA_BARRA` | `True` | [blazesbot/core/vision/barra.py:259](blazesbot/core/vision/barra.py#L259) | __init__.py | INTERRUPTOR: o offset fixo é a régua; a âncora azul é a reserva |

---

## Números medidos -- tolerância, limiar, teto, cadência

606 constantes, agrupadas por arquivo.

| constante | valor | onde | quem lê | porquê (resumo) |
|---|---|---|---|---|
| `PASSO_DA_MEDICAO` | `0.02` | [blazesbot/bot/app/afericao_do_aliado.py:85](blazesbot/bot/app/afericao_do_aliado.py#L85) | amostragem_de_cliques.py | De quanto em quanto tempo perguntar. 20 ms é fino o bastante para o número |
| `TETO_DA_ESPERA_DO_ALVO` | `2.0` | [blazesbot/bot/app/afericao_do_aliado.py:81](blazesbot/bot/app/afericao_do_aliado.py#L81) | — | Quanto esperar, no máximo, a memória refletir o alvo novo depois do clique. |
| `MAXIMO_DE_POCOES` | `5` | [blazesbot/bot/app/cura.py:151](blazesbot/bot/app/cura.py#L151) | — | Teto de poções por ciclo de cura. |
| `PASSO_DA_PERGUNTA` | `0.1` | [blazesbot/bot/app/cura.py:192](blazesbot/bot/app/cura.py#L192) | — | Cadência de toda pergunta deste módulo. Leitura de memória é ~1 µs; o custo é |
| `SEGUNDOS_ENTRE_POCOES` | `15.0` | [blazesbot/bot/app/cura.py:141](blazesbot/bot/app/cura.py#L141) | — | Quanto esperar entre uma poção e a próxima. |
| `SEGUNDOS_ESPERANDO_SAIR_DE_BATALHA` | `2.0` | [blazesbot/bot/app/cura.py:176](blazesbot/bot/app/cura.py#L176) | — | Quanto esperar a flag de batalha baixar depois que a macro termina. |
| `SEGUNDOS_PARA_SENTAR_COM_A_POCAO` | `1.0` | [blazesbot/bot/app/cura.py:187](blazesbot/bot/app/cura.py#L187) | — | Quanto esperar o personagem SENTAR depois de apertar a tecla de poção. |
| `SEGUNDOS_PARA_VOLTAR_AO_PONTO` | `5.0` | [blazesbot/bot/app/cura.py:158](blazesbot/bot/app/cura.py#L158) | — | Teto da caminhada de volta ao ponto inicial. |
| `SEGUNDOS_SENTADO` | `30.0` | [blazesbot/bot/app/cura.py:169](blazesbot/bot/app/cura.py#L169) | — | Teto sentado, para quem não tem tecla de poção configurada. |
| `VIDA_ALVO_DA_CURA` | `90.0` | [blazesbot/bot/app/cura.py:134](blazesbot/bot/app/cura.py#L134) | — | Até onde curar. Acima disso não se bebe mais nada. |
| `VIDA_PARA_CURAR` | `30.0` | [blazesbot/bot/app/cura.py:131](blazesbot/bot/app/cura.py#L131) | — | Abaixo de quanta vida a proteção dispara. |
| `VOLTAS_PRESAS_PARA_AVISAR` | `5` | [blazesbot/bot/app/cura.py:228](blazesbot/bot/app/cura.py#L228) | — | Quantas voltas presas em batalha com vida baixa antes de gritar. |
| `ESPERA_ANTES_DO_TAB` | `0.4` | [blazesbot/bot/app/executor.py:533](blazesbot/bot/app/executor.py#L533) | — | PAGO UMA VEZ POR AQUISIÇÃO, NÃO UMA VEZ POR TECLA |
| `ESPERA_DEPOIS_DE_INVOCAR` | `1` | [blazesbot/bot/app/executor.py:169](blazesbot/bot/app/executor.py#L169) | — | Espera depois de apertar a tecla do pet, antes de seguir para as teclas da |
| `ESPERA_DEPOIS_DO_TAB` | `0.01` | [blazesbot/bot/app/executor.py:553](blazesbot/bot/app/executor.py#L553) | combate.py, config.py | Respiro entre o TAB e a PRIMEIRA linha da macro. |
| `ESPERA_ENTRE_TABS` | `0.6` | [blazesbot/bot/app/executor.py:725](blazesbot/bot/app/executor.py#L725) | — | Espaçamento entre um salto da roda do TAB e o seguinte. |
| `ESPERA_SEM_ALVO` | `0.4` | [blazesbot/bot/app/executor.py:506](blazesbot/bot/app/executor.py#L506) | — | Quanto esperar antes de tentar de novo quando NÃO HÁ alvo vivo. |
| `FATIA_DE_ESPERA` | `0.08` | [blazesbot/bot/app/executor.py:104](blazesbot/bot/app/executor.py#L104) | __init__.py | Fatia máxima de espera antes de conferir se é para continuar. 0,05 s dá parada |
| `INTERVALO_ENTRE_INVOCACOES` | `6.0` | [blazesbot/bot/app/executor.py:164](blazesbot/bot/app/executor.py#L164) | — | Intervalo mínimo entre dois toques na tecla do pet. |
| `INTERVALO_MINIMO_DA_TELA` | `0.5` | [blazesbot/bot/app/executor.py:686](blazesbot/bot/app/executor.py#L686) | supervisor.py, target_hybrid.py | Intervalo minimo entre duas capturas. |
| `LIMIAR_DE_MORTE_NA_TELA` | `0.02` | [blazesbot/bot/app/executor.py:713](blazesbot/bot/app/executor.py#L713) | — | Abaixo de quanto a barra desenhada conta como morte. |
| `LINHAS_ANTES_DE_OLHAR_A_TELA` | `3` | [blazesbot/bot/app/executor.py:672](blazesbot/bot/app/executor.py#L672) | supervisor.py | Quantas LINHAS da macro passam antes de a tela ser consultada pela primeira |
| `LINHAS_BATENDO_CEGO_DEPOIS_DA_TELA` | `3` | [blazesbot/bot/app/executor.py:705](blazesbot/bot/app/executor.py#L705) | — | Quantas linhas o bot continua batendo DEPOIS de a tela dizer que o mob morreu. |
| `LINHAS_SEM_DANO_PARA_TROCAR` | `4` | [blazesbot/bot/app/executor.py:439](blazesbot/bot/app/executor.py#L439) | — | Quantas LINHAS da macro sem ENTRAR EM BATALHA antes de trocar de alvo. |
| `MINIMO_DE_ESPERA_DO_APP_MS` | `100` | [blazesbot/bot/app/executor.py:562](blazesbot/bot/app/executor.py#L562) | sincronia.py, config.py, account_dialog.py, web_app.py | Piso de qualquer tempo do APP, em milissegundos. O MESMO número vive em |
| `PASSO_DA_CONFERENCIA_DO_ALVO` | `0.16` | [blazesbot/bot/app/executor.py:267](blazesbot/bot/app/executor.py#L267) | fada.py | De quanto em quanto tempo perguntar "o alvo morreu?" DENTRO da espera de uma |
| `PASSO_DA_ESPERA_DA_BASE` | `0.1` | [blazesbot/bot/app/executor.py:740](blazesbot/bot/app/executor.py#L740) | — | Cadência da pergunta "já cheguei?". Leitura de posição é de microssegundos; o |
| `PASSO_DA_SAIDA_DE_BATALHA` | `0.1` | [blazesbot/bot/app/executor.py:196](blazesbot/bot/app/executor.py#L196) | — | Passo da conferência ativa acima. É leitura de memória; 0,1 s dá 20 amostras |
| `SEGUNDOS_DO_PASSO_DO_SHUFFLE` | `3.0` | [blazesbot/bot/app/executor.py:776](blazesbot/bot/app/executor.py#L776) | — | Cada perna do shuffle anti-AFK (ida e volta). Era `time.sleep(1.0)` cego duas |
| `SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE` | `2.5` | [blazesbot/bot/app/executor.py:618](blazesbot/bot/app/executor.py#L618) | — | DEPOIS DE MATAR, O BOT OBSERVA -- E O QUE ELE OBSERVA É A BATALHA |
| `SEGUNDOS_PARA_A_RODA_REINICIAR` | `1.6` | [blazesbot/bot/app/executor.py:326](blazesbot/bot/app/executor.py#L326) | — | Quanto esperar depois de uma aquisição FRACASSADA, antes da volta seguinte. |
| `SEGUNDOS_PARA_A_TRAVA_DEVOLVER` | `2.0` | [blazesbot/bot/app/executor.py:555](blazesbot/bot/app/executor.py#L555) | — | — |
| `SEGUNDOS_PARA_CONFIRMAR_A_SAIDA` | `2.5` | [blazesbot/bot/app/executor.py:192](blazesbot/bot/app/executor.py#L192) | — | Quanto se espera a flag de combate BAIXAR depois de o alvo cair. |
| `SEGUNDOS_PARA_O_ALVO_APARECER` | `0.35` | [blazesbot/bot/app/executor.py:229](blazesbot/bot/app/executor.py#L229) | — | O TAB DEIXOU DE SER LINHA DA MACRO |
| `SHUFFLE_DEFAULT_PIXELS` | `5` | [blazesbot/bot/app/executor.py:771](blazesbot/bot/app/executor.py#L771) | — | — |
| `TABS_SEM_RESPOSTA_PARA_DESISTIR` | `1` | [blazesbot/bot/app/executor.py:362](blazesbot/bot/app/executor.py#L362) | — | Quantos TABs seguidos SEM O ID MUDAR antes de desistir. |
| `TENTATIVAS_DE_TAB` | `1` | [blazesbot/bot/app/executor.py:312](blazesbot/bot/app/executor.py#L312) | — | A RODA É ORDENADA POR DISTÂNCIA, E ISSO MUDA TUDO -- 26/08/2026 |
| `VOLTAS_COM_ALVO_ILEGIVEL_PARA_TROCAR` | `2` | [blazesbot/bot/app/executor.py:500](blazesbot/bot/app/executor.py#L500) | — | Quantas VOLTAS inteiras com o alvo selecionado e o HP ilegível antes de |
| `VOLTAS_SEM_ALVO_ANTES_DE_DESCANSAR` | `3` | [blazesbot/bot/app/executor.py:337](blazesbot/bot/app/executor.py#L337) | — | Quantas voltas SEGUIDAS sem conseguir alvo antes de pagar a pausa acima. |
| `VOLTAS_SEM_BATALHA_PARA_TROCAR` | `3` | [blazesbot/bot/app/executor.py:736](blazesbot/bot/app/executor.py#L736) | — | Quantas voltas seguidas COM alvo e FORA de batalha antes de trocar de alvo. |
| `ESPERA_ENTRE_TABS_DO_ALINHAMENTO` | `0.5` | [blazesbot/bot/app/sincronia.py:97](blazesbot/bot/app/sincronia.py#L97) | — | Cadência do TAB durante o alinhamento. |
| `PASSO_DA_ESPERA_DA_LARGADA` | `0.04` | [blazesbot/bot/app/sincronia.py:100](blazesbot/bot/app/sincronia.py#L100) | — | De quanto em quanto tempo o seguidor confere se a largada saiu. |
| `PASSO_DA_ESPERA_DA_LINHA` | `0.05` | [blazesbot/bot/app/sincronia.py:121](blazesbot/bot/app/sincronia.py#L121) | — | De quanto em quanto tempo a espera da linha acorda para conferir o botão |
| `SEGUNDOS_SEM_MUDANCA_PARA_TAB` | `3.0` | [blazesbot/bot/app/sincronia.py:108](blazesbot/bot/app/sincronia.py#L108) | — | Sem trocar de estado de batalha por este tempo, dá TAB. |
| `TETO_DA_LINHA_SEGUNDOS` | `2.0` | [blazesbot/bot/app/sincronia.py:116](blazesbot/bot/app/sincronia.py#L116) | — | Quanto o seguidor espera a marca de UMA linha antes de mandar assim mesmo. |
| `AMOSTRAS_POR_COORDENADA` | `3` | [blazesbot/bot/bc/amostragem_de_cliques.py:126](blazesbot/bot/bc/amostragem_de_cliques.py#L126) | — | Quantas vezes cada coordenada é testada. Três é o mínimo que separa "abriu |
| `ANCORA_PADRAO` | `1.9` | [blazesbot/bot/bc/amostragem_de_cliques.py:163](blazesbot/bot/bc/amostragem_de_cliques.py#L163) | — | Precisão aceita nos pontos que o próprio bot não exige exatos (Fay, entrada |
| `ASSENTAMENTO_APOS_O_CLIQUE` | `0.125` | [blazesbot/bot/bc/amostragem_de_cliques.py:150](blazesbot/bot/bc/amostragem_de_cliques.py#L150) | — | Assentamento depois da amostra, antes de reler a posição. É o tempo de o |
| `ESPERA_APOS_O_ESC` | `0.075` | [blazesbot/bot/bc/amostragem_de_cliques.py:153](blazesbot/bot/bc/amostragem_de_cliques.py#L153) | — | Espera depois de cada ESC, antes de reconferir se o diálogo fechou. |
| `FALHAS_SEGUIDAS_PARA_ABORTAR` | `20` | [blazesbot/bot/bc/amostragem_de_cliques.py:188](blazesbot/bot/bc/amostragem_de_cliques.py#L188) | — | Amostras seguidas SEM o diálogo abrir em NENHUMA coordenada. Numa varredura |
| `INVALIDAS_SEGUIDAS_PARA_ABORTAR` | `6` | [blazesbot/bot/bc/amostragem_de_cliques.py:193](blazesbot/bot/bc/amostragem_de_cliques.py#L193) | — | Amostras inválidas (captura preta / sem template) seguidas. A ferramenta |
| `PASSO_DA_MEDICAO` | `0.03` | [blazesbot/bot/bc/amostragem_de_cliques.py:145](blazesbot/bot/bc/amostragem_de_cliques.py#L145) | afericao_do_aliado.py | Passo do laço que pergunta se o diálogo abriu. Cada volta custa uma captura |
| `PASSO_DO_GRID` | `6` | [blazesbot/bot/bc/amostragem_de_cliques.py:121](blazesbot/bot/bc/amostragem_de_cliques.py#L121) | — | — |
| `RAIO_DO_GRID` | `12` | [blazesbot/bot/bc/amostragem_de_cliques.py:120](blazesbot/bot/bc/amostragem_de_cliques.py#L120) | — | Raio e passo, em PIXELS da janela do cliente. 12/6 dá 5 valores por eixo |
| `RAIO_PARA_RECONHECER` | `45.0` | [blazesbot/bot/bc/amostragem_de_cliques.py:173](blazesbot/bot/bc/amostragem_de_cliques.py#L173) | — | Quão perto o personagem precisa estar para a ferramenta RECONHECER o ponto. |
| `SEGUNDOS_POR_TENTATIVA_DE_ANCORAR` | `3.0` | [blazesbot/bot/bc/amostragem_de_cliques.py:168](blazesbot/bot/bc/amostragem_de_cliques.py#L168) | — | — |
| `SEMENTE_DA_ORDEM` | `20260812` | [blazesbot/bot/bc/amostragem_de_cliques.py:131](blazesbot/bot/bc/amostragem_de_cliques.py#L131) | — | Semente do embaralhamento das rodadas. Fixa DE PROPÓSITO: a ordem precisa |
| `TENTATIVAS_DE_ANCORAR` | `6` | [blazesbot/bot/bc/amostragem_de_cliques.py:167](blazesbot/bot/bc/amostragem_de_cliques.py#L167) | — | Tentativas de encostar na âncora, e o orçamento de cada uma. Mesmo desenho |
| `TENTATIVAS_DE_FECHAR` | `4` | [blazesbot/bot/bc/amostragem_de_cliques.py:181](blazesbot/bot/bc/amostragem_de_cliques.py#L181) | esconder_jogadores.py | ESCs seguidos sem o diálogo fechar. Passado isto, algo está engolindo o |
| `TETO_DA_AMOSTRA` | `1.5` | [blazesbot/bot/bc/amostragem_de_cliques.py:140](blazesbot/bot/bc/amostragem_de_cliques.py#L140) | — | Teto da medição. Largo de propósito -- ver o cabeçalho. As aberturas reais |
| `NOME_DOS_GUARDAS` | `'Gun Witch'` | [blazesbot/bot/bc/combat.py:49](blazesbot/bot/bc/combat.py#L49) | routine.py, config.py | — |
| `NOME_DO_BOSS` | `'Blaze Skull Marshal'` | [blazesbot/bot/bc/combat.py:50](blazesbot/bot/bc/combat.py#L50) | — | — |
| `NOME_DO_CEMETERY_GUARD` | `'Cemetery Guard'` | [blazesbot/bot/bc/combat.py:56](blazesbot/bot/bc/combat.py#L56) | — | O ÚNICO nome que faz o bot parar de bater no waypoint dos guardas. Ver |
| `MAXIMO_DE_EPISODIOS` | `12` | [blazesbot/bot/bc/diagnostico_do_link.py:72](blazesbot/bot/bc/diagnostico_do_link.py#L72) | — | Episódios por processo. Doze dá para ver o padrão se repetir e ainda cabe em |
| `INTERVALO_DO_BATIMENTO` | `15.0` | [blazesbot/bot/bc/localizacao.py:67](blazesbot/bot/bc/localizacao.py#L67) | — | Cadência do batimento no diário. Uma linha a cada meio minuto dá uma trilha |
| `RAIO_DA_CHEGADA` | `40.0` | [blazesbot/bot/bc/localizacao.py:79](blazesbot/bot/bc/localizacao.py#L79) | — | Quão perto da coordenada de chegada da cave conta como "entrei". |
| `SALTO_DE_TELEPORTE` | `150.0` | [blazesbot/bot/bc/localizacao.py:76](blazesbot/bot/bc/localizacao.py#L76) | — | Salto de posição que caracteriza teleporte (entrada na cave, portal do altar, |
| `SEGUNDOS_PARA_DESCONFIAR` | `3.0` | [blazesbot/bot/bc/localizacao.py:72](blazesbot/bot/bc/localizacao.py#L72) | — | Tempo com o nome ilegível a partir do qual o bot passa a tratar a fonte de |
| `FOLGA_DA_CAIXA` | `25` | [blazesbot/bot/bc/mapa_bc.py:399](blazesbot/bot/bc/mapa_bc.py#L399) | mapa_hh.py | Caixa que contém TODO o interior da cave, com folga. |
| `MARGEM_PARA_CONTRADIZER` | `40` | [blazesbot/bot/bc/mapa_bc.py:434](blazesbot/bot/bc/mapa_bc.py#L434) | — | Folga exigida para a coordenada CONTRADIZER o nome lido da memória. Estar um |
| `PRECISAO_NO_PATAMAR_DO_ALTAR` | `0.7` | [blazesbot/bot/bc/mapa_bc.py:156](blazesbot/bot/bc/mapa_bc.py#L156) | routine.py, ui_service.py | Quão perto de (220,43) o clique no Altar Stone ainda acerta. |
| `PRECISAO_NO_PONTO_DA_SAIDA` | `0.7` | [blazesbot/bot/bc/mapa_bc.py:223](blazesbot/bot/bc/mapa_bc.py#L223) | routine.py, ui_service.py, entrada.py, mapa_hh.py | Precisão EXIGIDA no ponto da saída, e ela é UMA SÓ. |
| `PRECISAO_NO_PONTO_DO_VENDEDOR` | `0.7` | [blazesbot/bot/bc/mapa_bc.py:249](blazesbot/bot/bc/mapa_bc.py#L249) | amostragem_de_cliques.py, vendor.py, vendedor.py, coords.py | Precisão EXIGIDA no ponto do vendedor, e ela é UMA SÓ. |
| `SEGUNDOS_DESENCALHANDO_O_ALTAR` | `3` | [blazesbot/bot/bc/mapa_bc.py:183](blazesbot/bot/bc/mapa_bc.py#L183) | routine.py | Quanto esperar no ponto de vai-e-volta antes de retornar. |
| `SEGUNDOS_POR_TENTATIVA_NA_SAIDA` | `1.8` | [blazesbot/bot/bc/mapa_bc.py:229](blazesbot/bot/bc/mapa_bc.py#L229) | routine.py | — |
| `TENTATIVAS_DE_ENCOSTAR_NA_SAIDA` | `6` | [blazesbot/bot/bc/mapa_bc.py:228](blazesbot/bot/bc/mapa_bc.py#L228) | routine.py | Orçamento para encostar no ponto da saída. Mesmo desenho do patamar do Altar |
| `ASSENTAMENTO_DA_BOLSA` | `0.14` | [blazesbot/bot/bc/routine.py:317](blazesbot/bot/bc/routine.py#L317) | — | Depois que a MEMÓRIA confirma a bolsa aberta, o quanto esperar o DESENHO dela. |
| `CAPTURAS_INVALIDAS_PACKAGE` | `3` | [blazesbot/bot/bc/routine.py:249](blazesbot/bot/bc/routine.py#L249) | — | Se a captura do inventário vier preta/None por estas vezes seguidas, NÃO é |
| `DEPOIS_DE_FECHAR_A_BOLSA` | `0.05` | [blazesbot/bot/bc/routine.py:328](blazesbot/bot/bc/routine.py#L328) | — | Depois de fechar o inventário. Nada depende deste tempo -- o passo seguinte é |
| `ENTRE_CLIQUES_NO_PACKAGE` | `0.05` | [blazesbot/bot/bc/routine.py:323](blazesbot/bot/bc/routine.py#L323) | — | Entre um clique direito e o seguinte. Curto porque o clique deste bot é |
| `ESPERA_ENTRE_TENTATIVAS` | `0.025` | [blazesbot/bot/bc/routine.py:131](blazesbot/bot/bc/routine.py#L131) | — | E O INTERVALO ENTRE TENTATIVAS quase desaparece: a janela de reconhecimento já |
| `JANELA_DE_RECONHECIMENTO` | `0.25` | [blazesbot/bot/bc/routine.py:116](blazesbot/bot/bc/routine.py#L116) | — | para reconhecer e reagir ..........   0,607 s |
| `LIMIAR_DO_CHAT_ABERTO` | `0.9` | [blazesbot/bot/bc/routine.py:228](blazesbot/bot/bc/routine.py#L228) | — | Limiar do casamento da carinha. Alto porque ela é um ícone pequeno e fixo: no |
| `LIMIAR_DO_PACKAGE_EM_COR` | `0.92` | [blazesbot/bot/bc/routine.py:270](blazesbot/bot/bc/routine.py#L270) | — | Limiar do casamento EM COR do ícone do item. |
| `LIMIAR_DO_PICK_UP_ALL` | `0.85` | [blazesbot/bot/bc/routine.py:223](blazesbot/bot/bc/routine.py#L223) | routine.py | Limiar do botão. 0.85 e não 0.90: é um botão de UI com texto, e o fundo atrás |
| `PASSO_DA_ESPERA_DA_BOLSA` | `0.05` | [blazesbot/bot/bc/routine.py:311](blazesbot/bot/bc/routine.py#L311) | — | De quanto em quanto tempo perguntar se a bolsa já abriu. Era 0,15 s, o que |
| `PASSO_DO_RECONHECIMENTO` | `0.04` | [blazesbot/bot/bc/routine.py:121](blazesbot/bot/bc/routine.py#L121) | — | PASSO: de quanto em quanto tempo perguntar, dentro da janela. A pergunta é uma |
| `RODADAS_DE_USO_DO_PACKAGE` | `5` | [blazesbot/bot/bc/routine.py:244](blazesbot/bot/bc/routine.py#L244) | — | Rodadas de "procurar -> clicar em todos -> reconferir". |
| `RODADAS_DE_VENDA_ANTES_DE_DESLIGAR` | `3` | [blazesbot/bot/bc/routine.py:393](blazesbot/bot/bc/routine.py#L393) | — | Quantas rodadas de "não vendeu ⇒ roda mais uma run de BC ⇒ tenta de novo" |
| `SEGUNDOS_ESPERANDO_A_BOLSA` | `0.2` | [blazesbot/bot/bc/routine.py:286](blazesbot/bot/bc/routine.py#L286) | — | Quanto esperar a bolsa CONFIRMAR que abriu, lendo a memória. |
| `SEGUNDOS_POR_TENTATIVA_NO_ALTAR` | `1.5` | [blazesbot/bot/bc/routine.py:167](blazesbot/bot/bc/routine.py#L167) | — | — |
| `TEMPLATE_CHAT_ABERTO` | `'state_chat_aberto.png'` | [blazesbot/bot/bc/routine.py:196](blazesbot/bot/bc/routine.py#L196) | — | Carinha amarela no fim da barra de digitação do chat. Ela SÓ existe com o chat |
| `TEMPLATE_PACKAGE_COURAGE` | `'package_courage.png'` | [blazesbot/bot/bc/routine.py:190](blazesbot/bot/bc/routine.py#L190) | — | USO DO PACKAGE_COURAGE (pós-boss, ANTES de ativar a montaria e sair) |
| `TEMPLATE_PICK_UP_ALL` | `'btn_pick_up_all.png'` | [blazesbot/bot/bc/routine.py:202](blazesbot/bot/bc/routine.py#L202) | routine.py | Botão "Pick up all" da janela de loot. É ELE que autoriza o clique esquerdo do |
| `TENTATIVAS_ANTES_DE_DESENCALHAR` | `6` | [blazesbot/bot/bc/routine.py:152](blazesbot/bot/bc/routine.py#L152) | — | Quantas tentativas de clique no Altar Stone por CICLO, antes do vai-e-volta. |
| `TENTATIVAS_DE_ENCOSTAR_NO_ALTAR` | `6` | [blazesbot/bot/bc/routine.py:166](blazesbot/bot/bc/routine.py#L166) | — | Orçamento do ajuste fino do patamar: quantos `goto` apertados tentamos e por |
| `TENTATIVAS_POR_LINHA_DE_LOG` | `15` | [blazesbot/bot/bc/routine.py:141](blazesbot/bot/bc/routine.py#L141) | routine.py, indice_de_tempos.py | A cada quantas tentativas o log conta como vai a disputa. Uma linha por |
| `TOLERANCIA_DA_ENTRADA` | `12` | [blazesbot/bot/bc/routine.py:336](blazesbot/bot/bc/routine.py#L336) | — | DUAS PERGUNTAS DIFERENTES sobre a mesma coordenada, e por isso dois números. |
| `TOLERANCIA_DO_PONTO_DO_BOSS` | `15` | [blazesbot/bot/bc/routine.py:176](blazesbot/bot/bc/routine.py#L176) | routine.py | Quão perto do ponto do boss conta como "estou no waypoint". |
| `FALHAS_MECANICAS_PARA_REAPLICAR_O_PETBUG` | `20` | [blazesbot/bot/bc/ui_service.py:105](blazesbot/bot/bc/ui_service.py#L105) | — | REAPLICAR O PETBUG QUANDO A ENTRADA NÃO ABRE -- 07/09/2026 |
| `LINK_ENTRAR_BC` | `'link_enter_bc.png'` | [blazesbot/bot/bc/ui_service.py:33](blazesbot/bot/bc/ui_service.py#L33) | — | — |
| `LINK_GHOST_DIN_WOODS` | `'link_ghost_din_woods.png'` | [blazesbot/bot/bc/ui_service.py:32](blazesbot/bot/bc/ui_service.py#L32) | — | Links dentro dos diálogos, localizados por imagem. |
| `PASSO_DA_ESPERA_DO_TELEPORTE` | `0.08` | [blazesbot/bot/bc/ui_service.py:55](blazesbot/bot/bc/ui_service.py#L55) | entrada.py, vendedor.py | — |
| `SEGUNDOS_ENTRE_REAPLICACOES` | `120.0` | [blazesbot/bot/bc/ui_service.py:114](blazesbot/bot/bc/ui_service.py#L114) | — | Espaço mínimo entre duas reaplicações vindas DAQUI. |
| `TENTATIVAS_DE_POSICIONAR_NA_ENTRADA` | `3` | [blazesbot/bot/bc/ui_service.py:82](blazesbot/bot/bc/ui_service.py#L82) | — | Quantas vezes refazer a caminhada pelo painel de arredores antes de desistir de |
| `TETO_DO_TELEPORTE_DA_FAY` | `2.0` | [blazesbot/bot/bc/ui_service.py:54](blazesbot/bot/bc/ui_service.py#L54) | — | TELEPORTE DA FAY (Stone City -> Ghost Din Woods) |
| `TOLERANCIA_DO_NPC_DA_ENTRADA` | `2` | [blazesbot/bot/bc/ui_service.py:77](blazesbot/bot/bc/ui_service.py#L77) | routine.py | O SKULL HERALD DA ENTRADA EXIGE A COORDENADA EXATA |
| `ALVO_DO_TOPUP_ANTES_DO_BOSS` | `100.0` | [blazesbot/bot/combate.py:163](blazesbot/bot/combate.py#L163) | — | TOP-UP ANTES DO BOSS: ATÉ 100%, SENTADO, E OS 15 s INTEIROS |
| `AVISO_DA_ESPERA_SEM_PRAZO` | `10` | [blazesbot/bot/combate.py:458](blazesbot/bot/combate.py#L458) | — | Cadência do aviso enquanto espera sem prazo. Uma espera sem limite PRECISA |
| `CADENCIA_DA_LEITURA_DO_ALVO` | `0.15` | [blazesbot/bot/combate.py:926](blazesbot/bot/combate.py#L926) | routine.py | De quanto em quanto tempo olhar a barra do alvo durante a luta. |
| `CARENCIA_APOS_O_TAB` | `2.4` | [blazesbot/bot/combate.py:935](blazesbot/bot/combate.py#L935) | — | Depois de apertar TAB, quanto tempo ignorar a leitura. |
| `CARENCIA_SEM_LER_O_NOME` | `3.0` | [blazesbot/bot/combate.py:722](blazesbot/bot/combate.py#L722) | — | Quantos TAB gastar tentando SAIR de um alvo errado, por luta. |
| `CONFIRMACAO_DE_SAIDA_DE_COMBATE` | `2.5` | [blazesbot/bot/combate.py:466](blazesbot/bot/combate.py#L466) | — | Por quanto tempo CONTÍNUO a flag precisa ficar em falso para a saída valer. |
| `CONFIRMACOES_DE_MORTE` | `6` | [blazesbot/bot/combate.py:312](blazesbot/bot/combate.py#L312) | — | CONFIRMAÇÃO DA MORTE DO BOSS -- três exigências, e cada uma cobre uma falha |
| `ESPERA_APOS_A_MORTE_ANTES_DO_TAB` | `3.0` | [blazesbot/bot/combate.py:796](blazesbot/bot/combate.py#L796) | — | Quanto esperar PARADO, sem bater, depois de cada morte, antes de gastar o TAB |
| `ESPERA_DA_AUTO_SELECAO` | `0.125` | [blazesbot/bot/combate.py:74](blazesbot/bot/combate.py#L74) | — | Espera depois da auto-seleção, para a seleção chegar da rede. Era literal |
| `ESPERA_DEPOIS_DO_TAB` | `0.6` | [blazesbot/bot/combate.py:136](blazesbot/bot/combate.py#L136) | executor.py, config.py | Espera depois de UM TAB, para a seleção chegar da rede antes de conferir. |
| `ESPERA_ENTRAR_EM_COMBATE_GUARDAS` | `5.0` | [blazesbot/bot/combate.py:441](blazesbot/bot/combate.py#L441) | combat.py | Prazo curto para os GUARDAS (os 4 mobs no waypoint antes do boss). |
| `ESPERA_PARA_ENTRAR_EM_COMBATE` | `5.0` | [blazesbot/bot/combate.py:432](blazesbot/bot/combate.py#L432) | — | Quanto esperar a flag LIGAR depois de chegar no waypoint. |
| `FATIA_DA_ESPERA_DA_POCAO` | `0.5` | [blazesbot/bot/combate.py:168](blazesbot/bot/combate.py#L168) | — | Fatia da espera da poção. O TOTAL é medido por relógio (ver acima), então esta |
| `INTERVALO_DE_CONFERENCIA` | `0.1` | [blazesbot/bot/combate.py:264](blazesbot/bot/combate.py#L264) | — | De quanto em quanto tempo perguntar se a vida subiu. É leitura de memória -- |
| `LIMIAR_CEMETERY_GUARD` | `0.85` | [blazesbot/bot/combate.py:735](blazesbot/bot/combate.py#L735) | combat.py | Limiar para detecção do Cemetery Guard (guarda do cemitério) na tela. |
| `LIMINAR_TOPUP_ANTES_DO_BOSS` | `50.0` | [blazesbot/bot/combate.py:133](blazesbot/bot/combate.py#L133) | routine.py | TOP-UP PRÉ-BOSS ESTÁ FORA DE COMBATE, NÃO NA ESPERA DO BOSS |
| `LIMITE_DA_FASE_DOS_GUARDAS` | `40.0` | [blazesbot/bot/combate.py:656](blazesbot/bot/combate.py#L656) | combat.py | Prazo total de cada fase. Contrapeso da ressalva (c): flag presa em ligado. |
| `LIMITE_PARA_A_LUTA_COMECAR` | `10.0` | [blazesbot/bot/combate.py:945](blazesbot/bot/combate.py#L945) | — | Depois de forçar o TAB no boss, quanto tempo a flag tem para subir. |
| `LIMITE_POR_MOB_NO_DESTRAVAMENTO` | `20.0` | [blazesbot/bot/combate.py:804](blazesbot/bot/combate.py#L804) | — | Teto para UM mob dentro do destravamento. |
| `LIMITE_SEM_LER_A_FLAG` | `5.0` | [blazesbot/bot/combate.py:664](blazesbot/bot/combate.py#L664) | — | A flag ILEGÍVEL (`None`) não conta como "fora de combate". |
| `MARGEM_DA_CONJURACAO` | `0.6` | [blazesbot/bot/combate.py:261](blazesbot/bot/combate.py#L261) | — | Folga sobre a conjuração: latência da mensagem mais o jogo processar e a |
| `PASSO_DA_VIGIA_DE_COMBATE` | `0.05` | [blazesbot/bot/combate.py:396](blazesbot/bot/combate.py#L396) | — | Passo da vigia da flag. É o que "não bloqueante" significa na prática: o laço |
| `PREFIXO_DA_VARREDURA` | `'varredura:'` | [blazesbot/bot/combate.py:829](blazesbot/bot/combate.py#L829) | combat.py | A FAIXA cobre a struct do personagem. Os offsets conhecidos vão até |
| `SEGUNDOS_ANTES_DO_TAB_NO_BOSS` | `4.0` | [blazesbot/bot/combate.py:936](blazesbot/bot/combate.py#L936) | — | — |
| `SEGUNDOS_DA_POCAO_DE_VIDA` | `15.0` | [blazesbot/bot/combate.py:112](blazesbot/bot/combate.py#L112) | account_dialog.py | A POÇÃO DE VIDA LEVA 15 SEGUNDOS, E ANDAR CANCELA |
| `SEGUNDOS_DEPOIS_DA_SUPER_SKILL` | `12.0` | [blazesbot/bot/combate.py:116](blazesbot/bot/combate.py#L116) | — | Respiro depois da Super Skill de cura. Ela é instantânea; isto é só o tempo de |
| `SEGUNDOS_DE_CONJURACAO_DA_CURA` | `1.6` | [blazesbot/bot/combate.py:258](blazesbot/bot/combate.py#L258) | — | Conjuração da skill de cura. Informado pelo usuário em 19/08/2026. |
| `SEGUNDOS_SEM_ALVO_PARA_MORTE` | `3.0` | [blazesbot/bot/combate.py:316](blazesbot/bot/combate.py#L316) | — | 2. TEMPO -- segundos contínuos sem nada vivo selecionado. Dá lastro à contagem: |
| `SEGUNDOS_SENTADO_APOS_GUARDAS` | `4.0` | [blazesbot/bot/combate.py:96](blazesbot/bot/combate.py#L96) | — | Quatro segundos sentado recuperam vida e mana de graça, e é o único momento da |
| `SUBIDA_MINIMA_PARA_CONTAR` | `1.0` | [blazesbot/bot/combate.py:270](blazesbot/bot/combate.py#L270) | — | Quanto a vida precisa subir para a conjuração contar como bem-sucedida. Um |
| `TABS_NOS_GUARDAS` | `3` | [blazesbot/bot/combate.py:729](blazesbot/bot/combate.py#L729) | combat.py, mapa_hh.py | Quantos TAB no máximo. São 4 mobs e o primeiro vira alvo sozinho quando ataca, |
| `TABS_PARA_REFUTAR_A_MORTE` | `4` | [blazesbot/bot/combate.py:325](blazesbot/bot/combate.py#L325) | — | 3. REFUTAÇÃO ATIVA -- antes de declarar vitória, o bot TENTA achar algo vivo. |
| `TECLA_AUTO_SELECAO` | `'F1'` | [blazesbot/bot/combate.py:69](blazesbot/bot/combate.py#L69) | — | Tecla que seleciona o PRÓPRIO personagem. É padrão do cliente e não é |
| `TEMPLATE_FASE_2_DO_BOSS` | `'boss_2_fase.png'` | [blazesbot/bot/combate.py:919](blazesbot/bot/combate.py#L919) | combat.py | O recorte é o PEDAÇO DO MEIO do par vida+mana do quadro do alvo, com a vida |
| `TEMPLATE_INIMIGO_MORTO` | `'EnemyDead.png'` | [blazesbot/bot/combate.py:894](blazesbot/bot/combate.py#L894) | — | Nome do template do marcador. Veio do usuário em 19/08/2026. |
| `TENTATIVAS_DE_AUTO_SELECAO` | `2` | [blazesbot/bot/combate.py:91](blazesbot/bot/combate.py#L91) | — | Quantas vezes apertar a auto-seleção antes de dar o TAB, quando a primeira |
| `TENTATIVAS_DE_LARGAR_A_MIRA` | `2` | [blazesbot/bot/combate.py:416](blazesbot/bot/combate.py#L416) | — | LARGAR A MIRA ANTES DE ANDAR -- e conferir na MEMORIA que ela caiu |
| `TENTATIVAS_SEM_EFEITO` | `3` | [blazesbot/bot/combate.py:266](blazesbot/bot/combate.py#L266) | — | Conjurações seguidas sem a vida subir antes de concluir que a cura não sai. |
| `TETO_DO_DESTRAVAMENTO` | `60.0` | [blazesbot/bot/combate.py:782](blazesbot/bot/combate.py#L782) | — | Teto de UMA rodada de destravamento. Palavra do usuario: *"no maximo atrasar 1 |
| `TETO_PARA_A_MIRA_CAIR` | `0.6` | [blazesbot/bot/combate.py:425](blazesbot/bot/combate.py#L425) | — | Quanto esperar o `target_id` zerar depois de cada ESC. |
| `CUTUCADAS` | `2` | [blazesbot/bot/congelamento.py:95](blazesbot/bot/congelamento.py#L95) | — | Quantas cutucadas por congelamento. |
| `SEGUNDOS_PARA_A_SEGUNDA` | `22.5` | [blazesbot/bot/congelamento.py:82](blazesbot/bot/congelamento.py#L82) | — | A segunda cutucada, no MEIO do que resta até aquele teto. |
| `SEGUNDOS_PARA_CUTUCAR` | `15.0` | [blazesbot/bot/congelamento.py:76](blazesbot/bot/congelamento.py#L76) | — | Quanto tempo na MESMA coordenada, tentando andar, antes de mexer na montaria. |
| `FATIA_DA_ESPERA` | `0.25` | [blazesbot/bot/context.py:212](blazesbot/bot/context.py#L212) | petbug.py | Fatia máxima de sono dentro de um `tick`. |
| `TENTATIVAS_DE_AJUSTE_DA_CAMERA` | `3` | [blazesbot/bot/context.py:245](blazesbot/bot/context.py#L245) | — | Quantas vezes insistir para a câmera ficar no ângulo certo. |
| `DEPOIS_DO_OK` | `0.18` | [blazesbot/bot/deletador.py:166](blazesbot/bot/deletador.py#L166) | — | Assentamento depois do Ok, para o item sumir antes do clique seguinte. |
| `DISTANCIA_QUE_E_O_MESMO_ITEM` | `12` | [blazesbot/bot/deletador.py:141](blazesbot/bot/deletador.py#L141) | — | Dois casamentos a menos de tanto um do outro são o MESMO item, contado duas |
| `ESPERA_DA_BOLSA_ABRIR` | `0.58` | [blazesbot/bot/deletador.py:173](blazesbot/bot/deletador.py#L173) | afericao.py | A janela do inventário terminar de pintar depois da tecla. |
| `LIMIAR_DA_CAIXA` | `0.8` | [blazesbot/bot/deletador.py:196](blazesbot/bot/deletador.py#L196) | — | — |
| `LIMIAR_DA_REGIAO` | `0.8` | [blazesbot/bot/deletador.py:264](blazesbot/bot/deletador.py#L264) | — | — |
| `LIMIAR_DO_ICONE` | `0.8` | [blazesbot/bot/deletador.py:195](blazesbot/bot/deletador.py#L195) | — | — |
| `LIMIAR_EM_COR` | `0.92` | [blazesbot/bot/deletador.py:133](blazesbot/bot/deletador.py#L133) | — | Limiar do casamento EM COR dos itens. Vem do `package_courage`, que mediu o |
| `MAXIMO_DE_EXCLUSOES` | `20` | [blazesbot/bot/deletador.py:136](blazesbot/bot/deletador.py#L136) | — | Teto de exclusões por chamada. Um template ruim não pode esvaziar a bolsa. |
| `PASSO_DA_BOLSA_ABRIR` | `0.15` | [blazesbot/bot/deletador.py:189](blazesbot/bot/deletador.py#L189) | — | Passo entre duas perguntas pelo ícone. Cada uma custa uma captura de janela, |
| `PASSO_DA_ESPERA` | `0.08` | [blazesbot/bot/deletador.py:163](blazesbot/bot/deletador.py#L163) | fada_reviver.py, morte.py | — |
| `TEMPLATE_DO_ICONE` | `'btn_delete_item.png'` | [blazesbot/bot/deletador.py:198](blazesbot/bot/deletador.py#L198) | — | — |
| `TENTATIVAS_DE_FECHAR_A_BOLSA` | `2` | [blazesbot/bot/deletador.py:193](blazesbot/bot/deletador.py#L193) | — | Quantas vezes insistir para FECHAR a bolsa. Duas, porque a tecla é síncrona: |
| `TETO_DA_BOLSA_ABRIR` | `2.0` | [blazesbot/bot/deletador.py:185](blazesbot/bot/deletador.py#L185) | — | Teto da espera pela bolsa APARECER depois da tecla -- 07/09/2026. |
| `TETO_DA_CAIXA` | `1.2` | [blazesbot/bot/deletador.py:162](blazesbot/bot/deletador.py#L162) | — | Espera pela caixa de confirmação aparecer, depois do clique no ícone. |
| `TETO_DE_SEGUNDOS` | `10.0` | [blazesbot/bot/deletador.py:159](blazesbot/bot/deletador.py#L159) | fada_ociosa.py | Teto do passo inteiro (verificar + apagar), pedido do usuário. |
| `INTERVALO_DO_AVISO_DO_RESETER` | `300.0` | [blazesbot/bot/espera_do_reseter.py:87](blazesbot/bot/espera_do_reseter.py#L87) | — | De quanto em quanto tempo repetir o aviso enquanto a trava dura. |
| `PASSO_DA_ESPERA_DO_RESETER` | `1.0` | [blazesbot/bot/espera_do_reseter.py:80](blazesbot/bot/espera_do_reseter.py#L80) | — | Cadência da espera pela conta de reset. |
| `ESPERA_DEPOIS_DE_ERRAR` | `0.333` | [blazesbot/bot/fada.py:120](blazesbot/bot/fada.py#L120) | — | Depois de uma tentativa que não pegou, espera antes da seguinte. |
| `ESPERA_ENTRE_CURAS` | `0.34` | [blazesbot/bot/fada.py:102](blazesbot/bot/fada.py#L102) | — | Entre uma tecla de cura e a seguinte. |
| `MAXIMO_DE_TENTATIVAS_POR_VITIMA` | `3` | [blazesbot/bot/fada.py:112](blazesbot/bot/fada.py#L112) | — | Quantas vezes tentar selecionar a MESMA vítima antes de desistir dela. |
| `PASSO_DA_CONFERENCIA_DO_ALVO` | `0.02` | [blazesbot/bot/fada.py:88](blazesbot/bot/fada.py#L88) | executor.py | — |
| `PASSO_DA_FADA` | `0.1` | [blazesbot/bot/fada.py:80](blazesbot/bot/fada.py#L80) | — | Cadência do laço da Fada quando não há nada a fazer. |
| `TETO_DA_CURA_SEGUNDOS` | `20.0` | [blazesbot/bot/fada.py:95](blazesbot/bot/fada.py#L95) | — | Quanto tempo insistir numa cura antes de desistir daquela vítima. |
| `TETO_PARA_O_ALVO_VIRAR` | `0.4` | [blazesbot/bot/fada.py:87](blazesbot/bot/fada.py#L87) | — | Depois do clique no retrato, quanto esperar a memória mostrar o alvo novo. |
| `SEGUNDOS_ENTRE_TENTATIVAS` | `1.0` | [blazesbot/bot/fada_montagem.py:35](blazesbot/bot/fada_montagem.py#L35) | — | Respiro quando a Fada não consegue nem começar (memória fechada, por exemplo). |
| `SEGUNDOS_DE_CUIDADO_LONGO` | `12.0` | [blazesbot/bot/fada_ociosa.py:66](blazesbot/bot/fada_ociosa.py#L66) | — | Por quanto tempo vale a batida dada ANTES de uma tarefa longa da ociosa. |
| `SEGUNDOS_ENTRE_CONFERENCIAS_DO_PONTO` | `3.0` | [blazesbot/bot/fada_ociosa.py:59](blazesbot/bot/fada_ociosa.py#L59) | fada_montagem.py | De quanto em quanto tempo a Fada confere se saiu do ponto inicial. |
| `SEGUNDOS_ENTRE_CUIDADOS` | `30.0` | [blazesbot/bot/fada_ociosa.py:45](blazesbot/bot/fada_ociosa.py#L45) | — | De quanto em quanto tempo a Fada cuida do pet e da bolsa, ESTANDO OCIOSA. |
| `JANELA_DE_TENTATIVAS` | `10.0` | [blazesbot/bot/fada_reviver.py:71](blazesbot/bot/fada_reviver.py#L71) | — | Por quanto tempo a Fada insiste num mesmo morto antes de passar adiante. |
| `MAXIMO_DE_TOQUES` | `3` | [blazesbot/bot/fada_reviver.py:89](blazesbot/bot/fada_reviver.py#L89) | — | Teto de TOQUES na janela, independente do relógio. |
| `PASSO_DA_ESPERA` | `0.2` | [blazesbot/bot/fada_reviver.py:80](blazesbot/bot/fada_reviver.py#L80) | deletador.py, morte.py | Passo entre duas perguntas enquanto o feitiço prepara. |
| `TETO_DO_FEITICO` | `8.0` | [blazesbot/bot/fada_reviver.py:77](blazesbot/bot/fada_reviver.py#L77) | — | Quanto se espera o feitiço pegar depois de apertar a tecla. |
| `ENTRE_TENTATIVAS_DA_MUTUAL` | `1.0` | [blazesbot/bot/hh/entrada.py:87](blazesbot/bot/hh/entrada.py#L87) | — | Entre uma tentativa do painel e a seguinte. Curto: o custo da volta é o |
| `LINK_ENTRAR_HH` | `'link_enter_hh.png'` | [blazesbot/bot/hh/entrada.py:65](blazesbot/bot/hh/entrada.py#L65) | — | — |
| `LINK_SAIR_HH` | `'link_leave_hh.png'` | [blazesbot/bot/hh/entrada.py:67](blazesbot/bot/hh/entrada.py#L67) | — | O link do diálogo do `Servant Child`, DENTRO da cave. |
| `LINK_WEST_SUBURB` | `'link_west_suburb.png'` | [blazesbot/bot/hh/entrada.py:64](blazesbot/bot/hh/entrada.py#L64) | — | Links dentro dos diálogos, localizados por imagem. |
| `PASSO_DA_ESPERA_DA_ENTRADA` | `0.04` | [blazesbot/bot/hh/entrada.py:111](blazesbot/bot/hh/entrada.py#L111) | — | — |
| `PASSO_DA_ESPERA_DO_TELEPORTE` | `0.08` | [blazesbot/bot/hh/entrada.py:124](blazesbot/bot/hh/entrada.py#L124) | ui_service.py, vendedor.py | — |
| `SEGUNDOS_POR_TENTATIVA_DE_ENCOSTAR` | `1.8` | [blazesbot/bot/hh/entrada.py:90](blazesbot/bot/hh/entrada.py#L90) | routine.py | Quanto tempo dar a cada tentativa de encostar no ponto exato. |
| `TENTATIVAS_DE_CHEGAR_PELA_MUTUAL` | `3` | [blazesbot/bot/hh/entrada.py:83](blazesbot/bot/hh/entrada.py#L83) | — | Quantas vezes reabrir o painel de arredores e reclicar no NPC da porta. |
| `TENTATIVAS_DE_POSICIONAR` | `3` | [blazesbot/bot/hh/entrada.py:72](blazesbot/bot/hh/entrada.py#L72) | — | Quantas vezes refazer a caminhada pelo painel de arredores antes de desistir |
| `TETO_DA_ENTRADA` | `0.25` | [blazesbot/bot/hh/entrada.py:110](blazesbot/bot/hh/entrada.py#L110) | routine.py | Teto da espera pela troca de mapa depois de clicar no link de entrar. |
| `TETO_DA_SAIDA` | `3.0` | [blazesbot/bot/hh/entrada.py:120](blazesbot/bot/hh/entrada.py#L120) | — | A CONFIRMAÇÃO DA SAÍDA é mais generosa que a da entrada, e de propósito. |
| `TETO_DO_TELEPORTE` | `2.0` | [blazesbot/bot/hh/entrada.py:123](blazesbot/bot/hh/entrada.py#L123) | — | Teto da espera pelo teleporte do Fay. |
| `INTERVALO_DE_REAFIRMAR_O_FOLLOW` | `4.0` | [blazesbot/bot/hh/fada.py:80](blazesbot/bot/hh/fada.py#L80) | — | De quanto em quanto tempo reafirmar a tecla de seguir. |
| `PASSO_DO_ACOMPANHAMENTO` | `0.3` | [blazesbot/bot/hh/fada.py:73](blazesbot/bot/hh/fada.py#L73) | — | Quanto esperar entre duas leituras enquanto acompanha o líder. |
| `PASSO_ESPERANDO_O_LIDER` | `0.5` | [blazesbot/bot/hh/fada.py:87](blazesbot/bot/hh/fada.py#L87) | — | — |
| `AREA_DA_SAIDA` | `'Happiness Hall Main Hall'` | [blazesbot/bot/hh/mapa_hh.py:121](blazesbot/bot/hh/mapa_hh.py#L121) | — | — |
| `AREA_INTERNA_NAO_MEDIDA` | `'HH (área não medida)'` | [blazesbot/bot/hh/mapa_hh.py:96](blazesbot/bot/hh/mapa_hh.py#L96) | — | Marcador para a área que ainda não foi medida. Ver o cabeçalho do módulo: é |
| `BOSS_1` | `'Fa-Yuan'` | [blazesbot/bot/hh/mapa_hh.py:215](blazesbot/bot/hh/mapa_hh.py#L215) | bosses.py | Os quatro bosses |
| `BOSS_2` | `'Dupla'` | [blazesbot/bot/hh/mapa_hh.py:216](blazesbot/bot/hh/mapa_hh.py#L216) | bosses.py | — |
| `BOSS_3` | `'Green Robmaster'` | [blazesbot/bot/hh/mapa_hh.py:217](blazesbot/bot/hh/mapa_hh.py#L217) | bosses.py | — |
| `BOSS_4` | `'Purple'` | [blazesbot/bot/hh/mapa_hh.py:218](blazesbot/bot/hh/mapa_hh.py#L218) | bosses.py | — |
| `DESTINO_DO_TRANSPORTE` | `'West Suburb of Stone City'` | [blazesbot/bot/hh/mapa_hh.py:147](blazesbot/bot/hh/mapa_hh.py#L147) | — | O destino no diálogo do Fay. **SÓ APARECE ROLANDO A LISTA ATÉ O FIM.** |
| `ETAPA_DENTRO` | `'dentro da cave'` | [blazesbot/bot/hh/mapa_hh.py:696](blazesbot/bot/hh/mapa_hh.py#L696) | routine.py | EM QUE ETAPA DA VIAGEM O PERSONAGEM ESTÁ |
| `ETAPA_LONGE` | `'longe, viagem completa'` | [blazesbot/bot/hh/mapa_hh.py:699](blazesbot/bot/hh/mapa_hh.py#L699) | — | — |
| `ETAPA_NA_PORTA` | `'na porta da cave'` | [blazesbot/bot/hh/mapa_hh.py:697](blazesbot/bot/hh/mapa_hh.py#L697) | routine.py | — |
| `ETAPA_NA_VIZINHANCA` | `'já passei do teleporte'` | [blazesbot/bot/hh/mapa_hh.py:698](blazesbot/bot/hh/mapa_hh.py#L698) | routine.py | — |
| `FOLGA_DA_CAIXA` | `25` | [blazesbot/bot/hh/mapa_hh.py:602](blazesbot/bot/hh/mapa_hh.py#L602) | mapa_bc.py | A caixa que envolve o interior da cave |
| `GRUPO_DOS_ARREDORES` | `'Outside Black Wind Camp'` | [blazesbot/bot/hh/mapa_hh.py:81](blazesbot/bot/hh/mapa_hh.py#L81) | — | O grupo do painel de arredores naquele lugar. Serve para conferir que o painel |
| `LUGAR_FORA_DA_HH` | `'Black Wind Camp Dungeon'` | [blazesbot/bot/hh/mapa_hh.py:77](blazesbot/bot/hh/mapa_hh.py#L77) | — | A zona de FORA da cave, lida da tela em 01/09/2026 (o rótulo do canto superior |
| `NOME_DA_INSTANCIA` | `'Happiness Hall'` | [blazesbot/bot/hh/mapa_hh.py:92](blazesbot/bot/hh/mapa_hh.py#L92) | — | O QUE "HH" SIGNIFICA: **Happiness Hall**. |
| `NPC_DA_ENTRADA` | `'Elite Axe Monk Soldier'` | [blazesbot/bot/hh/mapa_hh.py:187](blazesbot/bot/hh/mapa_hh.py#L187) | entrada.py | O NPC com quem se fala para entrar na cave. |
| `NPC_DA_SAIDA` | `'Servant Child'` | [blazesbot/bot/hh/mapa_hh.py:480](blazesbot/bot/hh/mapa_hh.py#L480) | entrada.py, routine.py | Do boss 4 até o ponto de onde se sai da cave pelo NPC. |
| `PRECISAO_NO_PONTO_DA_ENTRADA` | `1.5` | [blazesbot/bot/hh/mapa_hh.py:184](blazesbot/bot/hh/mapa_hh.py#L184) | entrada.py, routine.py | Folga aceita para considerar que já se está no ponto de conversa. |
| `PRECISAO_PARA_ABRIR_OS_ARREDORES` | `12` | [blazesbot/bot/hh/mapa_hh.py:668](blazesbot/bot/hh/mapa_hh.py#L668) | entrada.py | Com que precisão é preciso estar em cada um deles. |
| `RAIO_DA_PORTA` | `30` | [blazesbot/bot/hh/mapa_hh.py:719](blazesbot/bot/hh/mapa_hh.py#L719) | entrada.py | Quão perto da porta ainda conta como "estou nela". |
| `ROTULO_DE_TELA_DA_CHEGADA` | `'Happiness Hall Dungeon'` | [blazesbot/bot/hh/mapa_hh.py:120](blazesbot/bot/hh/mapa_hh.py#L120) | — | NÃO COMPARE ESTES NOMES COM `Memory.location()` |
| `TABS_ENTRE_OS_ALVOS_DO_PONTO` | `2` | [blazesbot/bot/hh/mapa_hh.py:301](blazesbot/bot/hh/mapa_hh.py#L301) | — | Quantos TABs dar depois de cada morte, num ponto com mais de um alvo. |
| `ENTRE_TENTATIVAS_DE_ENTRAR` | `0.025` | [blazesbot/bot/hh/routine.py:103](blazesbot/bot/hh/routine.py#L103) | — | Entre uma tentativa de entrada e a seguinte. É o RESTO do orçamento da |
| `ENTRE_TENTATIVAS_DE_SAIR` | `1.0` | [blazesbot/bot/hh/routine.py:160](blazesbot/bot/hh/routine.py#L160) | — | Entre uma tentativa de sair e a seguinte. Maior que o da entrada porque cada |
| `LIMIAR_DO_PICK_UP_ALL` | `0.85` | [blazesbot/bot/hh/routine.py:177](blazesbot/bot/hh/routine.py#L177) | routine.py | — |
| `PASSO_DENTRO_DA_CAVE` | `0.05` | [blazesbot/bot/hh/routine.py:120](blazesbot/bot/hh/routine.py#L120) | — | Quanto esperar entre estados DENTRO da cave. |
| `PASSO_FORA_DA_CAVE` | `0.4` | [blazesbot/bot/hh/routine.py:121](blazesbot/bot/hh/routine.py#L121) | — | — |
| `SEGUNDOS_PARA_ENGAJAR` | `5.0` | [blazesbot/bot/hh/routine.py:140](blazesbot/bot/hh/routine.py#L140) | — | Quanto esperar, num ponto de batalha, para a flag de combate LIGAR. |
| `SEGUNDOS_POR_TENTATIVA_DE_VOLTAR` | `1.8` | [blazesbot/bot/hh/routine.py:147](blazesbot/bot/hh/routine.py#L147) | — | Quanto esperar, por tentativa, a volta ao ponto depois da luta. |
| `TEMPLATE_PICK_UP_ALL` | `'btn_pick_up_all.png'` | [blazesbot/bot/hh/routine.py:176](blazesbot/bot/hh/routine.py#L176) | routine.py | O botão "Pick up all" da janela de loot, achado por template. |
| `TENTATIVAS_POR_LINHA_DE_LOG` | `15` | [blazesbot/bot/hh/routine.py:110](blazesbot/bot/hh/routine.py#L110) | routine.py, indice_de_tempos.py | De quantas em quantas tentativas escrever uma linha no log. |
| `TOLERANCIA_DO_PONTO` | `15` | [blazesbot/bot/hh/routine.py:168](blazesbot/bot/hh/routine.py#L168) | — | Quanto o personagem pode estar longe do ponto do boss e ainda contar como |
| `VOLTAS_ANTES_DE_RECUPERAR` | `3` | [blazesbot/bot/hh/routine.py:124](blazesbot/bot/hh/routine.py#L124) | — | Quantas voltas do laço sem sair do estado antes de desconfiar. |
| `PRECISAO_NO_PONTO_DA_VENDA` | `1.5` | [blazesbot/bot/hh/vendedor.py:64](blazesbot/bot/hh/vendedor.py#L64) | — | Folga aceita para considerar que se está no ponto de clicar no vendedor. |
| `SEGUNDOS_POR_TENTATIVA` | `1.8` | [blazesbot/bot/hh/vendedor.py:68](blazesbot/bot/hh/vendedor.py#L68) | — | — |
| `TEMPLATE_DO_LINK_DE_VENDER` | `'link_sell_item.png'` | [blazesbot/bot/hh/vendedor.py:56](blazesbot/bot/hh/vendedor.py#L56) | — | O link "Sell Item" dentro do diálogo do vendedor, achado por IMAGEM. |
| `TENTATIVAS_DE_ENCOSTAR` | `4` | [blazesbot/bot/hh/vendedor.py:67](blazesbot/bot/hh/vendedor.py#L67) | — | Quantas vezes tentar encostar no ponto antes de desistir da venda. |
| `RECARGA` | `5.0` | [blazesbot/bot/hotbar.py:63](blazesbot/bot/hotbar.py#L63) | velocidade.py, hotbar.py, indice_de_tempos.py | Recarga do caminho com `ctx`. Os momentos-chave acontecem em rajada -- o portão |
| `CLIQUES_POR_MODO` | `40` | [blazesbot/bot/instrumentar_clique.py:105](blazesbot/bot/instrumentar_clique.py#L105) | — | Quantos cliques por modo. 40 e não 20: aqui não se está separando "funciona" de |
| `DIFERENCA_QUE_E_EFEITO` | `3.0` | [blazesbot/bot/instrumentar_clique.py:118](blazesbot/bot/instrumentar_clique.py#L118) | teste_do_cursor.py | — |
| `DISTANCIA_MINIMA_DO_ALVO` | `120` | [blazesbot/bot/instrumentar_clique.py:119](blazesbot/bot/instrumentar_clique.py#L119) | teste_do_cursor.py | — |
| `ENTRE_CLIQUES` | `0.25` | [blazesbot/bot/instrumentar_clique.py:116](blazesbot/bot/instrumentar_clique.py#L116) | hotbar.py, hotbar.py | Descanso entre cliques, para o jogo assentar e a próxima medida começar limpa. |
| `HC_ACTION` | `0` | [blazesbot/bot/instrumentar_clique.py:128](blazesbot/bot/instrumentar_clique.py#L128) | mouse_shield.py | — |
| `PASSO_DA_SONDA` | `0.012` | [blazesbot/bot/instrumentar_clique.py:110](blazesbot/bot/instrumentar_clique.py#L110) | — | De quanto em quanto tempo a sonda fotografa o minimapa esperando o efeito. |
| `TETO_DA_SONDA` | `1.2` | [blazesbot/bot/instrumentar_clique.py:113](blazesbot/bot/instrumentar_clique.py#L113) | — | Teto da espera pelo efeito. Passou disso, o clique é dado como PERDIDO. |
| `WH_MOUSE_LL` | `14` | [blazesbot/bot/instrumentar_clique.py:127](blazesbot/bot/instrumentar_clique.py#L127) | supervisor.py, inputs.py, mouse_shield.py | O SENSOR — o mesmo WH_MOUSE_LL do shield, com o sinal trocado |
| `ENTER_RETRY_SECONDS` | `10.0` | [blazesbot/bot/login.py:78](blazesbot/bot/login.py#L78) | — | Cadência de tentativa de entrar enquanto conectado. |
| `ESPERA_CEGA_SEGUNDOS` | `90.0` | [blazesbot/bot/login.py:91](blazesbot/bot/login.py#L91) | — | Depois de esgotar as tentativas às cegas, o bot NÃO desiste -- ele espaça. |
| `ESPERA_SERVIDOR_FORA` | `10.0` | [blazesbot/bot/login.py:107](blazesbot/bot/login.py#L107) | — | Espera depois de fechar "Acquiring server IP address." (servidores fora do ar). |
| `ESPERA_SERVIDOR_FORA_MAX` | `60.0` | [blazesbot/bot/login.py:108](blazesbot/bot/login.py#L108) | — | — |
| `FATIA_DA_ESPERA_DO_LOGIN` | `0.05` | [blazesbot/bot/login.py:139](blazesbot/bot/login.py#L139) | — | Fatia da espera do login. A espera é cumprida em pedaços para que Parar e |
| `LOGIN_SCREEN_MAX_SECONDS` | `150.0` | [blazesbot/bot/login.py:116](blazesbot/bot/login.py#L116) | — | Tempo máximo parado na tela de usuário e senha antes de reabrir o cliente. |
| `MAX_ANCHOR_DEVIATION` | `60` | [blazesbot/bot/login.py:96](blazesbot/bot/login.py#L96) | — | Divergência a partir da qual a âncora é considerada suspeita. É folgada de |
| `MAX_BLIND_ENTER_ATTEMPTS` | `4` | [blazesbot/bot/login.py:84](blazesbot/bot/login.py#L84) | — | Quantas tentativas de "Enter Game" fazer sem conseguir confirmar a entrada. |
| `MAX_CREDENTIAL_ERRORS` | `5` | [blazesbot/bot/login.py:57](blazesbot/bot/login.py#L57) | — | Recusas de usuário/senha antes de desistir da conta. |
| `MODAL_CONFIRM_SECONDS` | `7.5` | [blazesbot/bot/login.py:98](blazesbot/bot/login.py#L98) | — | Persistência do flag de modal para concluir que há um aviso na tela. |
| `MODAL_PRE_SERVER_SECONDS` | `3.5` | [blazesbot/bot/login.py:102](blazesbot/bot/login.py#L102) | — | O mesmo, mas ANTES de conectar ao servidor. Bem menor: as telas de login e de |
| `PRE_SERVER_TIMEOUT` | `600.0` | [blazesbot/bot/login.py:75](blazesbot/bot/login.py#L75) | — | NÃO EXISTE LIMITE DE TEMPO NA FILA. |
| `SEGUNDOS_CONECTANDO` | `6.0` | [blazesbot/bot/login.py:134](blazesbot/bot/login.py#L134) | — | "Connecting to the server, please wait a moment." -- espera LEGÍTIMA, com |
| `WAIT_HEARTBEAT_SECONDS` | `150.0` | [blazesbot/bot/login.py:110](blazesbot/bot/login.py#L110) | — | Cadência do aviso de "continuo esperando", só para o log não ficar mudo. |
| `THRESHOLD` | `0.8` | [blazesbot/bot/login_states.py:35](blazesbot/bot/login_states.py#L35) | — | — |
| `CADENCIA_DO_CONVITE` | `0.5` | [blazesbot/bot/morte.py:72](blazesbot/bot/morte.py#L72) | — | Cadência da conferência do convite da Fada na TELA. |
| `EXTENSAO_PELO_FEITICO` | `15.0` | [blazesbot/bot/morte.py:59](blazesbot/bot/morte.py#L59) | — | Quanto o prazo estica quando a Fada avisa que COMEÇOU a conjurar. |
| `MORTES_SEGUIDAS_PARA_PARAR` | `3` | [blazesbot/bot/morte.py:93](blazesbot/bot/morte.py#L93) | — | Mortes seguidas SEM conseguir voltar ao ponto antes de parar a conta. |
| `PASSO_DA_ESPERA` | `0.3` | [blazesbot/bot/morte.py:64](blazesbot/bot/morte.py#L64) | deletador.py, fada_reviver.py | Passo entre duas perguntas durante a espera. Tudo o que ele pergunta é |
| `PRAZO_PARA_A_FADA` | `60.0` | [blazesbot/bot/morte.py:54](blazesbot/bot/morte.py#L54) | mural_da_morte.py | Quanto o morto espera pela Fada antes de se reviver sozinho. |
| `TETO_DA_REGENERACAO` | `60.0` | [blazesbot/bot/morte.py:82](blazesbot/bot/morte.py#L82) | — | Teto da regeneração sentada antes de andar de volta. |
| `TETO_DO_RETORNO` | `180.0` | [blazesbot/bot/morte.py:90](blazesbot/bot/morte.py#L90) | — | Teto da caminhada de volta ao ponto inicial. |
| `TETO_PARA_O_REVIVE_PEGAR` | `10.0` | [blazesbot/bot/morte.py:75](blazesbot/bot/morte.py#L75) | — | Quanto se espera o `hp` subir depois de um clique que deveria reviver. |
| `ACEITE_VALIDO_SEGUNDOS` | `15.0` | [blazesbot/bot/mural.py:202](blazesbot/bot/mural.py#L202) | — | Validade do aceite. Curta de propósito: ele confirma UM convite recém-enviado, |
| `CONVITE_VALIDO_SEGUNDOS` | `60.0` | [blazesbot/bot/mural.py:80](blazesbot/bot/mural.py#L80) | — | Validade do anúncio. Cobre a fila de resposta do outro cliente com folga; mais |
| `ESTADO_VALIDO_SEGUNDOS` | `30.0` | [blazesbot/bot/mural.py:294](blazesbot/bot/mural.py#L294) | sincronia.py, supervisor.py | Quanto tempo o estado publicado por uma conta continua valendo. |
| `LARGADA_VALIDA_SEGUNDOS` | `5.0` | [blazesbot/bot/mural.py:286](blazesbot/bot/mural.py#L286) | sincronia.py | Quanto tempo uma largada anunciada continua valendo. |
| `SILENCIO_DA_FADA` | `5.0` | [blazesbot/bot/mural.py:501](blazesbot/bot/mural.py#L501) | — | Quanto silêncio já é "a Fada não está lá". |
| `SILENCIO_MAXIMO` | `5.0` | [blazesbot/bot/mural.py:146](blazesbot/bot/mural.py#L146) | — | Quanto silêncio já é "caiu". |
| `TETO_DA_BATIDA_LONGA` | `15.0` | [blazesbot/bot/mural.py:515](blazesbot/bot/mural.py#L515) | fada_ociosa.py | Quanto uma batida pode valer, no MÁXIMO, quando a Fada avisa que vai sumir. |
| `VALIDADE_DA_DESISTENCIA` | `20.0` | [blazesbot/bot/mural.py:590](blazesbot/bot/mural.py#L590) | — | Por quanto tempo a desistência da Fada continua valendo. |
| `SEGUNDOS_DE_MORTO_PARA_FURAR_A_FILA` | `40.0` | [blazesbot/bot/mural_da_morte.py:42](blazesbot/bot/mural_da_morte.py#L42) | fada.py, fada_reviver.py, mural.py | A partir de quantos segundos de morto a vítima FURA a fila dos feridos. |
| `VALIDADE_DO_FEITICO` | `8.0` | [blazesbot/bot/mural_da_morte.py:133](blazesbot/bot/mural_da_morte.py#L133) | mural.py | Por quanto tempo o aviso "estou conjurando" continua de pé. |
| `ALCANCE_DA_EXPANSAO` | `4` | [blazesbot/bot/navegacao.py:218](blazesbot/bot/navegacao.py#L218) | — | ATÉ ONDE A MANOBRA SE AFASTA NA ROTA quando os vizinhos imediatos falham. |
| `AVISAR_A_PE_NO_TRAJETO` | `4.0` | [blazesbot/bot/navegacao.py:291](blazesbot/bot/navegacao.py#L291) | — | Depois de quanto tempo a pé, no meio de um trajeto, o log passa a dizer isso em |
| `CICLOS_ANTES_DE_DESTRAVAR` | `2` | [blazesbot/bot/navegacao.py:393](blazesbot/bot/navegacao.py#L393) | — | Depois de quantos ciclos sem montar o portao para de insistir MUDO e vai |
| `CICLOS_ANTES_DE_GRITAR` | `5` | [blazesbot/bot/navegacao.py:322](blazesbot/bot/navegacao.py#L322) | — | Quantos ciclos do portão sem montar antes de o log passar a GRITAR. |
| `CICLOS_ANTES_DE_IR_A_PE` | `20` | [blazesbot/bot/navegacao.py:337](blazesbot/bot/navegacao.py#L337) | — | Quantos ciclos o portão insiste antes de aceitar ir A PÉ. |
| `CIRCULO_TETO_SEGUNDOS` | `6.5` | [blazesbot/bot/navegacao.py:268](blazesbot/bot/navegacao.py#L268) | — | Teto de tempo TOTAL do círculo antes de desistir e devolver o controle. É a |
| `DEFAULT_TOLERANCE` | `3` | [blazesbot/bot/navegacao.py:65](blazesbot/bot/navegacao.py#L65) | — | — |
| `FOLGA_ROLLBACK` | `1` | [blazesbot/bot/navegacao.py:132](blazesbot/bot/navegacao.py#L132) | — | Folga do detector de rollback: voltar ATÉ 1 índice é ruído normal de leitura; |
| `INTERVALO_MANUTENCAO` | `0.6` | [blazesbot/bot/navegacao.py:272](blazesbot/bot/navegacao.py#L272) | — | Cadência da manutenção durante o deslocamento (poção). |
| `INTERVALO_PARADA_POCAO` | `10.0` | [blazesbot/bot/navegacao.py:438](blazesbot/bot/navegacao.py#L438) | — | Recarga da PARADA para tomar poção durante o trajeto. |
| `INTERVALO_RECLIQUE` | `1.1` | [blazesbot/bot/navegacao.py:97](blazesbot/bot/navegacao.py#L97) | — | Intervalo MÁXIMO entre cliques enquanto anda. Não é a cadência normal -- o |
| `INTERVALO_REMONTAR` | `3.0` | [blazesbot/bot/navegacao.py:283](blazesbot/bot/navegacao.py#L283) | — | A MONTARIA É PRÉ-REQUISITO DE ANDAR, NÃO UMA OTIMIZAÇÃO -- tudo que este bot |
| `JANELA_ADIANTE` | `2` | [blazesbot/bot/navegacao.py:415](blazesbot/bot/navegacao.py#L415) | — | Quantos waypoints à frente podem ser aproveitados de uma vez. |
| `MANOBRAS_DE_PARADO` | `2` | [blazesbot/bot/navegacao.py:240](blazesbot/bot/navegacao.py#L240) | — | Quantas vezes a manobra pode rodar no mesmo trajeto. |
| `MARGEM_RECLIQUE` | `2.0` | [blazesbot/bot/navegacao.py:102](blazesbot/bot/navegacao.py#L102) | — | Distância do fim do trecho já clicado em que o próximo clique é disparado. |
| `PASSADAS_DO_DESTRAVAMENTO` | `2` | [blazesbot/bot/navegacao.py:198](blazesbot/bot/navegacao.py#L198) | — | Quantas voltas a manobra dá sobre os dois candidatos: frente, trás, frente, trás. |
| `PASSO_PARA_DESTRAVAR_A_MONTARIA` | `6` | [blazesbot/bot/navegacao.py:378](blazesbot/bot/navegacao.py#L378) | — | O tamanho do passo, em unidades de posicao. Numero do usuario ("6px"). |
| `POLL_MOVIMENTO` | `0.22` | [blazesbot/bot/navegacao.py:105](blazesbot/bot/navegacao.py#L105) | — | Intervalo de leitura de posição. É o que define quanto tempo o personagem fica |
| `RUIDO_DA_POSICAO` | `1.0` | [blazesbot/bot/navegacao.py:163](blazesbot/bot/navegacao.py#L163) | — | Quanto a posição pode variar e ainda contar como "não saiu do lugar". Uma |
| `SEGUNDOS_ANTES_DE_CUTUCAR` | `10.0` | [blazesbot/bot/navegacao.py:370](blazesbot/bot/navegacao.py#L370) | — | Quanto esperar, desde a PRIMEIRA tentativa, antes de andar um passo. Numero do |
| `SEGUNDOS_PARADO_DE_VERDADE` | `1.5` | [blazesbot/bot/navegacao.py:157](blazesbot/bot/navegacao.py#L157) | — | PERSONAGEM COMPLETAMENTE PARADO DENTRO DA CAVE |
| `SEGUNDOS_POR_CLIQUE_CIRCULO` | `1.0` | [blazesbot/bot/navegacao.py:270](blazesbot/bot/navegacao.py#L270) | — | Janela por ponto do círculo para saber se o clique fez o personagem andar. |
| `SEGUNDOS_POR_TENTATIVA_DE_DESTRAVAR` | `4.0` | [blazesbot/bot/navegacao.py:186](blazesbot/bot/navegacao.py#L186) | — | Prazo para alcançar CADA candidato da manobra de destravamento. |
| `SEM_PROGRESSO_SEGUNDOS` | `1.2` | [blazesbot/bot/navegacao.py:111](blazesbot/bot/navegacao.py#L111) | — | Sem aproximar-se do alvo por este tempo, considera travado. |
| `TETO_DO_PORTAO` | `6.0` | [blazesbot/bot/navegacao.py:310](blazesbot/bot/navegacao.py#L310) | — | A ORDEM DO PORTÃO: CONFERIR -> ATIVAR -> CONFIRMAR -> ANDAR |
| `TETO_PRESO_NO_MESMO_PONTO` | `30.0` | [blazesbot/bot/navegacao.py:127](blazesbot/bot/navegacao.py#L127) | congelamento.py | TETO PARA FICAR PRESO NO MESMO WAYPOINT, sem conseguir manobra nenhuma. |
| `TOLERANCIA_DE_VOLTA_AO_CAMINHO` | `2` | [blazesbot/bot/navegacao.py:231](blazesbot/bot/navegacao.py#L231) | — | Tolerância para VOLTAR ao caminho, no candidato mais próximo da manobra. |
| `TOLERANCIA_ROTA` | `7` | [blazesbot/bot/navegacao.py:109](blazesbot/bot/navegacao.py#L109) | mapa_bc.py | Tolerância dos waypoints de rota. Waypoint de rota não é destino: é só uma |
| `TRICKY_TOLERANCE` | `8` | [blazesbot/bot/navegacao.py:66](blazesbot/bot/navegacao.py#L66) | mapa_bc.py, routine.py | — |
| `DESVIO_MINIMO` | `12.0` | [blazesbot/bot/recorte_do_time.py:109](blazesbot/bot/recorte_do_time.py#L109) | — | Recorte liso casa em todo lugar. `region_is_uniform` já é o teste que o |
| `FOLGA_DO_ESPACAMENTO` | `6.0` | [blazesbot/bot/recorte_do_time.py:105](blazesbot/bot/recorte_do_time.py#L105) | — | Espaçamento vertical: desvio máximo aceito entre os intervalos, em pixels. As |
| `LARGURA_DO_RECORTE` | `120` | [blazesbot/bot/recorte_do_time.py:91](blazesbot/bot/recorte_do_time.py#L91) | — | — |
| `LIMIAR` | `0.9` | [blazesbot/bot/recorte_do_time.py:95](blazesbot/bot/recorte_do_time.py#L95) | cura.py, combate.py, navegacao.py, watchdog.py | Um casamento fraco não conta. 0.90 é o mesmo patamar que o deletador usa para |
| `MINIMO_DE_LINHAS` | `2` | [blazesbot/bot/recorte_do_time.py:99](blazesbot/bot/recorte_do_time.py#L99) | — | Menos de dois casamentos não prova repetição -- prova que o recorte se achou a |
| `NOME_DO_TEMPLATE` | `'state_team_member.png'` | [blazesbot/bot/recorte_do_time.py:73](blazesbot/bot/recorte_do_time.py#L73) | — | Nome que `bot/team.py` procura. Mudar aqui sem mudar lá deixa o arquivo |
| `PASSO_VERTICAL` | `4` | [blazesbot/bot/recorte_do_time.py:90](blazesbot/bot/recorte_do_time.py#L90) | — | — |
| `CADENCIA_DO_VIGIA` | `6.0` | [blazesbot/bot/sentinela.py:129](blazesbot/bot/sentinela.py#L129) | — | O ORÇAMENTO DE 20 SEGUNDOS, repartido |
| `STRIKES_PARA_JANELA_SUMIDA` | `2` | [blazesbot/bot/sentinela.py:146](blazesbot/bot/sentinela.py#L146) | — | AS CONFIRMAÇÕES -- a defesa contra derrubar conta boa por causa de lag |
| `STRIKES_PARA_JANELA_TRAVADA` | `3` | [blazesbot/bot/sentinela.py:155](blazesbot/bot/sentinela.py#L155) | — | JANELA TRAVADA é o sinal ruidoso, e é o único que precisa de defesa de |
| `LIMIAR_DO_CONVITE` | `0.9` | [blazesbot/bot/supervisor.py:94](blazesbot/bot/supervisor.py#L94) | — | Limiar do casamento do convite. Mais exigente que o limiar geral de telas |
| `TETO_DA_ESPERA_PELA_FADA` | `60.0` | [blazesbot/bot/supervisor.py:81](blazesbot/bot/supervisor.py#L81) | — | Quanto uma vítima espera pela Fada antes de voltar para a poção. |
| `TETO_DA_FATIA_DE_ESPERA` | `0.25` | [blazesbot/bot/supervisor.py:72](blazesbot/bot/supervisor.py#L72) | — | Teto de uma fatia dentro de `_AnyEvent.wait`. É REDE, não o caminho normal -- |
| `ANCHOR_THRESHOLD` | `0.8` | [blazesbot/bot/team.py:91](blazesbot/bot/team.py#L91) | vendedor.py, ui_do_jogo.py, janelas_abertas.py | — |
| `ESPERA_DO_MENU` | `0.35` | [blazesbot/bot/team.py:134](blazesbot/bot/team.py#L134) | — | Tempo para o menu de contexto aparecer depois do clique direito. |
| `ESPERA_PELA_RESPOSTA` | `4.0` | [blazesbot/bot/team.py:139](blazesbot/bot/team.py#L139) | — | Quanto esperar a outra conta aceitar. Ela recebe o anúncio interno e clica no |
| `INVITE_TEMPLATE` | `'state_team_invite.png'` | [blazesbot/bot/team.py:88](blazesbot/bot/team.py#L88) | — | — |
| `INVITE_TEXT_TEMPLATE` | `'state_team_invite_texto.png'` | [blazesbot/bot/team.py:89](blazesbot/bot/team.py#L89) | — | — |
| `INVITE_THRESHOLD` | `0.8` | [blazesbot/bot/team.py:90](blazesbot/bot/team.py#L90) | janelas_abertas.py | — |
| `MAX_CLIQUES_DE_ACEITE` | `5` | [blazesbot/bot/team.py:159](blazesbot/bot/team.py#L159) | — | Quantas vezes clicar no Ok para o MESMO convite anunciado. |
| `MAX_ENTRADAS` | `12` | [blazesbot/bot/team.py:150](blazesbot/bot/team.py#L150) | — | Quantas linhas da lista limpar antes de desistir. |
| `MENU_LEAVE_TEMPLATE` | `'menu_leave_team.png'` | [blazesbot/bot/team.py:92](blazesbot/bot/team.py#L92) | — | — |
| `MENU_TEAM_UP_TEMPLATE` | `'menu_team_up.png'` | [blazesbot/bot/team.py:108](blazesbot/bot/team.py#L108) | — | Item "Team up" do menu de contexto da entrada na lista. |
| `PASSO_DA_ESPERA_DO_TIME` | `0.1` | [blazesbot/bot/team.py:147](blazesbot/bot/team.py#L147) | — | De quanto em quanto tempo conferir se o time já formou. |
| `SEMELHANCA_MINIMA` | `0.9` | [blazesbot/bot/team.py:105](blazesbot/bot/team.py#L105) | — | Semelhança a partir da qual um recorte aprendido é considerado o mesmo texto. |
| `TEAM_MEMBER_TEMPLATE` | `'state_team_member.png'` | [blazesbot/bot/team.py:100](blazesbot/bot/team.py#L100) | recorte_do_time.py | Painel do companheiro de time, desenhado abaixo do retrato do próprio |
| `CLIQUES_POR_FASE` | `20` | [blazesbot/bot/teste_do_cursor.py:91](blazesbot/bot/teste_do_cursor.py#L91) | — | Quantos cliques por fase. 20 dá resolução de 5 pontos percentuais -- suficiente |
| `DIFERENCA_QUE_E_EFEITO` | `3.0` | [blazesbot/bot/teste_do_cursor.py:95](blazesbot/bot/teste_do_cursor.py#L95) | instrumentar_clique.py | Quanto o minimapa precisa mudar para o clique contar como surtido efeito. O |
| `DISTANCIA_MINIMA_DO_ALVO` | `120` | [blazesbot/bot/teste_do_cursor.py:98](blazesbot/bot/teste_do_cursor.py#L98) | instrumentar_clique.py | Distância mínima entre o cursor físico e o alvo, em pixels do cliente. |
| `ESPERA_DEPOIS_DO_CLIQUE` | `0.35` | [blazesbot/bot/teste_do_cursor.py:100](blazesbot/bot/teste_do_cursor.py#L100) | — | — |
| `ABERTURAS_POR_TRAJETO` | `4` | [blazesbot/bot/ui_do_jogo.py:564](blazesbot/bot/ui_do_jogo.py#L564) | — | Teto de aberturas do painel por TRAJETO. |
| `ANCHOR_THRESHOLD` | `0.8` | [blazesbot/bot/ui_do_jogo.py:100](blazesbot/bot/ui_do_jogo.py#L100) | vendedor.py, team.py, janelas_abertas.py | — |
| `BUSCAS_ANTES_DE_DESISTIR_DA_LEITURA` | `3` | [blazesbot/bot/ui_do_jogo.py:424](blazesbot/bot/ui_do_jogo.py#L424) | — | Quantas buscas seguidas sem a memória responder antes de desistir dela. Duas, e |
| `CLIQUES_ATE_O_BATENTE` | `5` | [blazesbot/bot/ui_do_jogo.py:156](blazesbot/bot/ui_do_jogo.py#L156) | — | ZOOM DO MINIMAPA -- cinco níveis, o padrão no meio. |
| `CLIQUES_DO_BATENTE_ATE_O_PADRAO` | `2` | [blazesbot/bot/ui_do_jogo.py:157](blazesbot/bot/ui_do_jogo.py#L157) | — | — |
| `DIGITACAO_POR_CARACTERE` | `0.01` | [blazesbot/bot/ui_do_jogo.py:388](blazesbot/bot/ui_do_jogo.py#L388) | — | Intervalo entre caracteres. 40 ms davam meio segundo só para digitar |
| `ENTRE_CLIQUES_DE_ZOOM` | `0.025` | [blazesbot/bot/ui_do_jogo.py:158](blazesbot/bot/ui_do_jogo.py#L158) | — | — |
| `ESPERA_ANTES_DE_CONFERIR` | `0.15` | [blazesbot/bot/ui_do_jogo.py:592](blazesbot/bot/ui_do_jogo.py#L592) | ui_service.py | — |
| `ESPERA_CEGA_DO_RESULTADO` | `0.3` | [blazesbot/bot/ui_do_jogo.py:419](blazesbot/bot/ui_do_jogo.py#L419) | — | Quando a leitura de arredores por memória não funciona neste cliente, a lista |
| `ESPERA_DA_ROLAGEM` | `0.08` | [blazesbot/bot/ui_do_jogo.py:623](blazesbot/bot/ui_do_jogo.py#L623) | — | A lista redesenhar depois do clique na seta. Uma volta de laço do cliente, não |
| `ESPERA_DA_TROCA_DE_ABA` | `0.05` | [blazesbot/bot/ui_do_jogo.py:374](blazesbot/bot/ui_do_jogo.py#L374) | — | Assentar depois de clicar na aba NPC. Não é "esperar a aba renderizar": é só dar |
| `ESPERA_DEPOIS_DE_CLICAR_NO_RESULTADO` | `0.15` | [blazesbot/bot/ui_do_jogo.py:464](blazesbot/bot/ui_do_jogo.py#L464) | — | — |
| `ESPERA_DEPOIS_DE_FECHAR` | `0.2` | [blazesbot/bot/ui_do_jogo.py:590](blazesbot/bot/ui_do_jogo.py#L590) | — | — |
| `ESPERA_DEPOIS_DO_LINK` | `0.2` | [blazesbot/bot/ui_do_jogo.py:290](blazesbot/bot/ui_do_jogo.py#L290) | — | Servidor processar o pedido de entrada. Zero na disputa: quem confirma a entrada |
| `FALHAS_ANTES_DE_REDESCOBRIR` | `5` | [blazesbot/bot/ui_do_jogo.py:108](blazesbot/bot/ui_do_jogo.py#L108) | ui_service.py | Falhas seguidas na tentativa rápida antes de redescobrir tudo por imagem. |
| `FALHAS_SEGUIDAS_ANTES_DE_AFROUXAR` | `5` | [blazesbot/bot/ui_do_jogo.py:240](blazesbot/bot/ui_do_jogo.py#L240) | — | O TETO TAMBÉM APRENDE COM A FALHA -- 07/09/2026 |
| `FATOR_DE_AFROUXAMENTO` | `2.0` | [blazesbot/bot/ui_do_jogo.py:243](blazesbot/bot/ui_do_jogo.py#L243) | — | Quanto o teto dobra a cada degrau de falhas. |
| `FOLGA_DA_REDESCOBERTA` | `1.5` | [blazesbot/bot/ui_do_jogo.py:277](blazesbot/bot/ui_do_jogo.py#L277) | — | Folga da REDESCOBERTA sobre o teto normal. Ali o clique pode ter errado o NPC |
| `FOLGA_SOBRE_O_PIOR_DIALOGO` | `2.0` | [blazesbot/bot/ui_do_jogo.py:198](blazesbot/bot/ui_do_jogo.py#L198) | — | Folga sobre a pior abertura observada. 1,6 dá espaço para uma variação sem |
| `INTERVALO_DO_GUARDA_DE_JANELA` | `3.0` | [blazesbot/bot/ui_do_jogo.py:326](blazesbot/bot/ui_do_jogo.py#L326) | — | CLIQUE ENGOLIDO = JANELA NA FRENTE. E O GUARDA VALE PARA A SAIDA TAMBEM |
| `INTERVALO_ENTRE_USOS_DO_PAINEL` | `2.0` | [blazesbot/bot/ui_do_jogo.py:546](blazesbot/bot/ui_do_jogo.py#L546) | — | CADÊNCIA MÍNIMA ENTRE UM USO DO PAINEL DE ARREDORES E O SEGUINTE |
| `LEITURAS_ANTES_DE_DESISTIR_DE_VER` | `3` | [blazesbot/bot/ui_do_jogo.py:586](blazesbot/bot/ui_do_jogo.py#L586) | — | Fechar o painel. Era 0,6 s. |
| `LEITURAS_PARA_CONSIDERAR_PARADO` | `3` | [blazesbot/bot/ui_do_jogo.py:495](blazesbot/bot/ui_do_jogo.py#L495) | — | Quantas leituras iguais seguidas contam como PARADO. |
| `LIMITE_DA_ESPERA_DO_ANDAR` | `0.4` | [blazesbot/bot/ui_do_jogo.py:463](blazesbot/bot/ui_do_jogo.py#L463) | — | — |
| `LIMITE_DA_ESPERA_DO_DIALOGO_LENTA` | `0.65` | [blazesbot/bot/ui_do_jogo.py:268](blazesbot/bot/ui_do_jogo.py#L268) | — | Diálogo aparecer na REDESCOBERTA, depois de cada clique direito. Era `tick(1.3)` |
| `LIMITE_DA_ESPERA_DO_FECHAMENTO` | `0.4` | [blazesbot/bot/ui_do_jogo.py:589](blazesbot/bot/ui_do_jogo.py#L589) | — | — |
| `LIMITE_DA_ESPERA_DO_PAINEL` | `0.8` | [blazesbot/bot/ui_do_jogo.py:370](blazesbot/bot/ui_do_jogo.py#L370) | — | O teto é EXATAMENTE a espera fixa que havia antes (1,2 s), e isso é de propósito: |
| `LIMITE_DA_ESPERA_DO_RESULTADO` | `0.8` | [blazesbot/bot/ui_do_jogo.py:393](blazesbot/bot/ui_do_jogo.py#L393) | — | — |
| `LIMITE_INICIAL_DA_ESPERA_DO_DIALOGO` | `0.65` | [blazesbot/bot/ui_do_jogo.py:186](blazesbot/bot/ui_do_jogo.py#L186) | — | TETO DA ESPERA DO DIÁLOGO -- ajustado pelo que foi MEDIDO, não chutado |
| `LIMITE_MAXIMO_DA_ESPERA_DO_DIALOGO` | `0.6` | [blazesbot/bot/ui_do_jogo.py:194](blazesbot/bot/ui_do_jogo.py#L194) | combate.py | Teto do teto. Passado disto, o diálogo não vai abrir mesmo, e insistir só |
| `LIMITE_MINIMO_DA_ESPERA_DO_DIALOGO` | `0.18` | [blazesbot/bot/ui_do_jogo.py:190](blazesbot/bot/ui_do_jogo.py#L190) | — | Piso: o valor que valia antes. Abaixo disto não se aperta nem com evidência -- |
| `LIMPEZA_DO_CAMPO` | `8` | [blazesbot/bot/ui_do_jogo.py:384](blazesbot/bot/ui_do_jogo.py#L384) | — | Quantos BACKSPACE para limpar o campo. O texto buscado é curto ("Fay", "Skull", |
| `MEMORIA_DE_ABERTURAS_DO_DIALOGO` | `12` | [blazesbot/bot/ui_do_jogo.py:203](blazesbot/bot/ui_do_jogo.py#L203) | — | Quantas aberturas guardar. Poucas de propósito: o que interessa é a condição |
| `PASSOS_DE_ROLAGEM` | `12` | [blazesbot/bot/ui_do_jogo.py:618](blazesbot/bot/ui_do_jogo.py#L618) | — | Quantas rolagens no máximo antes de aceitar que o link não está na lista. |
| `PASSO_DA_ESPERA_DA_CHEGADA` | `0.25` | [blazesbot/bot/ui_do_jogo.py:570](blazesbot/bot/ui_do_jogo.py#L570) | — | Passo da leitura de posição enquanto se espera a chegada. Ler memória custa |
| `PASSO_DA_ESPERA_DO_ANDAR` | `0.04` | [blazesbot/bot/ui_do_jogo.py:462](blazesbot/bot/ui_do_jogo.py#L462) | — | Depois de clicar no resultado o personagem já saiu andando -- o pathfinding do |
| `PASSO_DA_ESPERA_DO_DIALOGO` | `0.08` | [blazesbot/bot/ui_do_jogo.py:147](blazesbot/bot/ui_do_jogo.py#L147) | — | Diálogo do NPC aparecer. Era 0,30 s fixos, gastos inteiros mesmo quando o |
| `PASSO_DA_ESPERA_DO_FECHAMENTO` | `0.04` | [blazesbot/bot/ui_do_jogo.py:588](blazesbot/bot/ui_do_jogo.py#L588) | — | — |
| `PASSO_DA_ESPERA_DO_PAINEL` | `0.08` | [blazesbot/bot/ui_do_jogo.py:364](blazesbot/bot/ui_do_jogo.py#L364) | — | Passo e teto da espera pelo painel aparecer. Cada volta custa uma captura de |
| `PASSO_DA_ESPERA_DO_RESULTADO` | `0.08` | [blazesbot/bot/ui_do_jogo.py:392](blazesbot/bot/ui_do_jogo.py#L392) | — | De quanto em quanto tempo perguntar à memória se o resultado apareceu, e por |
| `PROXIMIDADE_DO_DESTINO` | `8` | [blazesbot/bot/ui_do_jogo.py:488](blazesbot/bot/ui_do_jogo.py#L488) | — | O AUTO-PATH DO SURROUNDINGS É CONFIRMADO POR COORDENADA |
| `TEMPLATE_DA_SETA_DE_ROLAGEM` | `'dialogo_seta_baixo.png'` | [blazesbot/bot/ui_do_jogo.py:610](blazesbot/bot/ui_do_jogo.py#L610) | — | A seta de rolagem PARA BAIXO do diálogo, achada por template como os links. |
| `TETO_DO_DESESPERO` | `1.2` | [blazesbot/bot/ui_do_jogo.py:253](blazesbot/bot/ui_do_jogo.py#L253) | — | O teto do desespero. Passado daqui não é mais latência: é NPC errado, cliente |
| `TOLERANCIA_DA_POSICAO` | `4` | [blazesbot/bot/ui_do_jogo.py:646](blazesbot/bot/ui_do_jogo.py#L646) | — | NUNCA CLICAR NO LINK SEM O DIÁLOGO ABERTO |
| `SEGUNDOS_ANDANDO_ANTES` | `0.5` | [blazesbot/bot/velocidade.py:45](blazesbot/bot/velocidade.py#L45) | — | Quanto o personagem precisa ter andado antes de valer a pena acionar. |
| `CICLOS_DE_VENDA` | `10` | [blazesbot/bot/vendedor.py:157](blazesbot/bot/vendedor.py#L157) | vendor.py | Quantos CICLOS COMPLETOS de venda (reposicionar -> abrir diálogo -> vender) |
| `CONTRASTE_QUE_E_SLOT_VAZIO` | `25.0` | [blazesbot/bot/vendedor.py:271](blazesbot/bot/vendedor.py#L271) | — | Abaixo disto o slot está vazio. Fica a 2,5x do pior vazio (9.76) e a menos da |
| `ESPERA_ANTES_DO_SELL` | `0.4` | [blazesbot/bot/vendedor.py:316](blazesbot/bot/vendedor.py#L316) | — | O RESPIRO EM VOLTA DO BOTÃO "SELL" |
| `ESPERA_DEPOIS_DO_SELL` | `0.6` | [blazesbot/bot/vendedor.py:317](blazesbot/bot/vendedor.py#L317) | — | — |
| `ESPERA_DO_TELEPORTE` | `5.0` | [blazesbot/bot/vendedor.py:99](blazesbot/bot/vendedor.py#L99) | indice_de_tempos.py | TETO da espera do teleporte -- não é mais o tempo gasto, é o limite. |
| `ESPERA_ENTRE_CLIQUES_DA_VENDA` | `0.065` | [blazesbot/bot/vendedor.py:213](blazesbot/bot/vendedor.py#L213) | — | Espera entre um clique e o seguinte na grade. Era 200 ms. |
| `ESPERA_ENTRE_TENTATIVAS_DE_RETORNO` | `8.0` | [blazesbot/bot/vendedor.py:135](blazesbot/bot/vendedor.py#L135) | vendor.py | — |
| `ESPERA_PARA_CONFIRMAR_VAZIO` | `0.5` | [blazesbot/bot/vendedor.py:284](blazesbot/bot/vendedor.py#L284) | — | As leituras de confirmação são ESPAÇADAS, não coladas: veja |
| `LADO_DO_MIOLO_DA_CELULA` | `24` | [blazesbot/bot/vendedor.py:267](blazesbot/bot/vendedor.py#L267) | — | COMO SE SABE QUE O SLOT ESTÁ VAZIO: pelo CONTRASTE DO MIOLO da célula. |
| `LEITURAS_VAZIAS_PARA_PARAR` | `6` | [blazesbot/bot/vendedor.py:280](blazesbot/bot/vendedor.py#L280) | — | Quantas leituras VAZIAS SEGUIDAS encerram a venda. **SEMPRE NO MESMO SLOT** -- |
| `LIMIAR_DA_CAIXA_PRECIOSA` | `0.8` | [blazesbot/bot/vendedor.py:167](blazesbot/bot/vendedor.py#L167) | — | Limiar do template do TEXTO da caixa "It's precious item, please confirm!". |
| `LIMIAR_DO_VENDEDOR` | `0.8` | [blazesbot/bot/vendedor.py:86](blazesbot/bot/vendedor.py#L86) | vendor.py, indice_de_tempos.py | Limiar do casamento. Sprite de NPC contra cenário 3D é mais difícil que ícone |
| `PASSO_DA_ESPERA_DO_TELEPORTE` | `0.12` | [blazesbot/bot/vendedor.py:103](blazesbot/bot/vendedor.py#L103) | ui_service.py, entrada.py | Entre leituras. A posição vem da memória e custa microssegundos; o passo é |
| `RAIO_DA_BUSCA_DO_VENDEDOR` | `200` | [blazesbot/bot/vendedor.py:80](blazesbot/bot/vendedor.py#L80) | vendor.py | Onde procurar: um retângulo em volta de onde ele DEVERIA estar. Não é a posição |
| `SALTO_QUE_CONFIRMA` | `200.0` | [blazesbot/bot/vendedor.py:112](blazesbot/bot/vendedor.py#L112) | — | Salto de posição que confirma o teleporte para a cidade. |
| `SEGUNDOS_POR_TENTATIVA_NO_VENDEDOR` | `4` | [blazesbot/bot/vendedor.py:144](blazesbot/bot/vendedor.py#L144) | vendor.py | — |
| `TEMPLATE_VENDEDOR` | `'vendedor.png'` | [blazesbot/bot/vendedor.py:71](blazesbot/bot/vendedor.py#L71) | vendor.py | O RICH É PROCURADO NA TELA, NÃO DECORADO NUMA COORDENADA |
| `TENTATIVAS_DA_PEDRA` | `3` | [blazesbot/bot/vendedor.py:134](blazesbot/bot/vendedor.py#L134) | vendor.py | — |
| `TENTATIVAS_DE_ENCOSTAR_NO_VENDEDOR` | `6` | [blazesbot/bot/vendedor.py:143](blazesbot/bot/vendedor.py#L143) | vendor.py | Orçamento do ajuste fino no ponto do vendedor. Pequeno porque o passo real é |
| `TENTATIVAS_DO_TOKEN` | `10` | [blazesbot/bot/vendedor.py:133](blazesbot/bot/vendedor.py#L133) | vendor.py | CHEGAR A STONE CITY -- números do usuário (18/08/2026) |
| `TENTATIVAS_NO_OK` | `3` | [blazesbot/bot/vendedor.py:162](blazesbot/bot/vendedor.py#L162) | — | Quantas vezes reclicar o Ok da caixa "It's precious item" antes de desistir. |
| `TOLERANCIA_DA_CAMINHADA_ATE_O_VENDEDOR` | `2` | [blazesbot/bot/vendedor.py:139](blazesbot/bot/vendedor.py#L139) | vendor.py | Folga da CAMINHADA até o vendedor. O painel de arredores caminha até perto e |
| `ESPERA_PELA_MORTE` | `2.0` | [blazesbot/bot/watchdog.py:297](blazesbot/bot/watchdog.py#L297) | — | Quanto tempo esperar o Windows realmente derrubar o processo depois do |
| `PASSO_DA_CONFIRMACAO_DA_MORTE` | `0.05` | [blazesbot/bot/watchdog.py:301](blazesbot/bot/watchdog.py#L301) | — | Passo entre as conferências de "já morreu?". Fatia curta porque a resposta |
| `RAIO_DA_BUSCA_DO_AVISO` | `120` | [blazesbot/bot/watchdog.py:74](blazesbot/bot/watchdog.py#L74) | — | Meio-lado da janela de busca, em volta de `coords.aviso_de_conexao`. A caixa |
| `RECONNECT_TEMPLATE` | `'state_conn_prefix.png'` | [blazesbot/bot/watchdog.py:37](blazesbot/bot/watchdog.py#L37) | coords.py | Template do aviso "Connection interrupted[, please open client again]". |
| `RECONNECT_THRESHOLD` | `0.92` | [blazesbot/bot/watchdog.py:69](blazesbot/bot/watchdog.py#L69) | sentinela.py | POR QUE A BUSCA É PRESA À CAIXA, E NÃO NA TELA INTEIRA |
| `VISUAL_CHECK_SECONDS` | `10.0` | [blazesbot/bot/watchdog.py:77](blazesbot/bot/watchdog.py#L77) | executor.py, context.py, supervisor.py, target_hybrid.py | Este virou o sinal principal de queda, então roda numa cadência curta. |
| `CAVE_BC` | `'bc'` | [blazesbot/config.py:917](blazesbot/config.py#L917) | routine.py, context.py, supervisor.py | COMO CADA CAVE SE CHAMA no código. Existe para "qual cave está rodando" ser |
| `CAVE_HH` | `'hh'` | [blazesbot/config.py:918](blazesbot/config.py#L918) | context.py, routine.py, supervisor.py | — |
| `CLIQUES_POR_PASSADA` | `24` | [blazesbot/config.py:796](blazesbot/config.py#L796) | vendedor.py | Limite do jogo: a janela mostra 24 itens e só dá para marcar 24 por venda. |
| `CONFIG_VERSION` | `4` | [blazesbot/config.py:35](blazesbot/config.py#L35) | — | Versão 4: o caminho da cave saiu do arquivo e passou a viver em |
| `CURA_PARAR_PCT_PADRAO` | `90` | [blazesbot/config.py:640](blazesbot/config.py#L640) | — | — |
| `CURA_PEDIR_PCT_PADRAO` | `30` | [blazesbot/config.py:639](blazesbot/config.py#L639) | — | Padrões das duas barras de cura do time. Pedido do usuário em 28/08/2026: |
| `DEFAULT_MOUNT_SPEED` | `90` | [blazesbot/config.py:50](blazesbot/config.py#L50) | — | — |
| `FOLGA_PADRAO_DE_SLOTS` | `6` | [blazesbot/config.py:445](blazesbot/config.py#L445) | — | Espaços livres a partir dos quais já vale voltar para vender. |
| `GUARDAS_DO_COVIL` | `4` | [blazesbot/config.py:854](blazesbot/config.py#L854) | — | Quantos mobs de guarda esperam na entrada do covil do boss. Contados no jogo. |
| `LIMITE_DO_NOME_DO_GRUPO` | `40` | [blazesbot/config.py:530](blazesbot/config.py#L530) | account_dialog.py, web_app.py | Teto do nome de um grupo de contas (`Account.grupo`). |
| `MAXIMO_DE_SEGUIDORES_DO_TIME` | `4` | [blazesbot/config.py:583](blazesbot/config.py#L583) | — | Quantas contas o líder arrasta junto. Pedido do usuário em 27/08/2026: |
| `MAX_BOLSAS` | `3` | [blazesbot/config.py:438](blazesbot/config.py#L438) | account_dialog.py, web_app.py | — |
| `MINIMO_DELAY_MS` | `100` | [blazesbot/config.py:507](blazesbot/config.py#L507) | account_dialog.py | Espera mínima de QUALQUER campo de tempo do APP, em milissegundos. |
| `NOME_DOS_GUARDAS` | `'Gun Witch'` | [blazesbot/config.py:874](blazesbot/config.py#L874) | combat.py, routine.py | Como os quatro guardas se chamam no jogo. Lido no quadro do alvo, no print do |
| `PASSOS_DO_APP` | `20` | [blazesbot/config.py:488](blazesbot/config.py#L488) | account_dialog.py, web_app.py | Linhas oferecidas na aba APP. Dezesseis cobre com folga a macro mais longa que |
| `PET_FEED_MINUTES` | `50` | [blazesbot/config.py:266](blazesbot/config.py#L266) | account_dialog.py, web_app.py | Cada comida de pet dá 5 de felicidade, o máximo é 100, e o pet perde 1 a cada |
| `PET_FEED_MINUTOS_MAX` | `60` | [blazesbot/config.py:276](blazesbot/config.py#L276) | account_dialog.py | — |
| `PET_FEED_MINUTOS_MIN` | `40` | [blazesbot/config.py:275](blazesbot/config.py#L275) | account_dialog.py | FAIXA FECHADA DO INTERVALO DE COMIDA (26/08/2026, decisão do usuário). |
| `SLOTS_POR_BOLSA` | `30` | [blazesbot/config.py:437](blazesbot/config.py#L437) | account_dialog.py, web_app.py | Cada bolsa do jogo tem 30 espaços. O personagem começa com uma e pode ter até |
| `SPEED_DURACAO_SEGUNDOS` | `30` | [blazesbot/config.py:850](blazesbot/config.py#L850) | velocidade.py | Skill de velocidade da montaria, valores do jogo. Ficam aqui e não na |
| `AMOSTRAS_ENTRE_GRAVACOES` | `40` | [blazesbot/core/calibracao.py:167](blazesbot/core/calibracao.py#L167) | combate.py | De quantas em quantas amostras o placar vai para o disco. |
| `AMOSTRAS_PARA_GABARITAR` | `50` | [blazesbot/core/calibracao.py:102](blazesbot/core/calibracao.py#L102) | — | Para um candidato ser declarado `gabaritou`. |
| `AMOSTRAS_PARA_REPROVAR` | `100` | [blazesbot/core/calibracao.py:109](blazesbot/core/calibracao.py#L109) | — | Para um candidato ser declarado `reprovado` e PARAR de ser amostrado. Não é |
| `DISCRIMINANTES_PARA_GABARITAR` | `20` | [blazesbot/core/calibracao.py:103](blazesbot/core/calibracao.py#L103) | — | — |
| `MUDANCA_MINIMA_PARA_FILTRAR` | `5.0` | [blazesbot/core/calibracao.py:754](blazesbot/core/calibracao.py#L754) | — | Quanto a vida da tela precisa ter mudado (em pontos percentuais) para a |
| `PASSADAS_PARA_PROMOVER` | `3` | [blazesbot/core/calibracao.py:750](blazesbot/core/calibracao.py#L750) | — | Quantas passadas com vida DIFERENTE antes de promover. Uma passada só elimina |
| `PISO_DE_PONTEIRO` | `65536` | [blazesbot/core/calibracao.py:1013](blazesbot/core/calibracao.py#L1013) | — | Piso para um valor parecer ponteiro de entidade. Abaixo disto é zero, flag ou |
| `RUNS_PARA_GABARITAR` | `10` | [blazesbot/core/calibracao.py:104](blazesbot/core/calibracao.py#L104) | — | — |
| `SOBREVIVENTES_PARA_PROMOVER` | `8` | [blazesbot/core/calibracao.py:745](blazesbot/core/calibracao.py#L745) | — | Quantos sobreviventes bastam para promover a candidatos de verdade. Acima |
| `TAXA_DE_ERRO_PARA_REPROVAR` | `0.2` | [blazesbot/core/calibracao.py:110](blazesbot/core/calibracao.py#L110) | — | — |
| `TENTATIVAS_SEM_LEITURA_PARA_DESISTIR` | `30` | [blazesbot/core/calibracao.py:159](blazesbot/core/calibracao.py#L159) | — | `sem_resposta`: QUEM NUNCA RESPONDE TAMBÉM TEM DE SAIR DE CENA |
| `TOLERANCIA_DO_HP` | `3.0` | [blazesbot/core/calibracao.py:95](blazesbot/core/calibracao.py#L95) | — | OS CRITÉRIOS |
| `ESPERA_APOS_PEGAR` | `4.0` | [blazesbot/core/catador.py:112](blazesbot/core/catador.py#L112) | — | Espera entre o clique no botão e a próxima conferência. NÚMERO DO USUÁRIO. |
| `ESPERA_ENTRE_CLIQUES` | `0.1` | [blazesbot/core/catador.py:96](blazesbot/core/catador.py#L96) | — | Espera entre dois cliques direitos. Também do T-R0XX. Não é tempo de abrir a |
| `TETO_DE_CLIQUES` | `10` | [blazesbot/core/catador.py:124](blazesbot/core/catador.py#L124) | — | Teto de cliques no botão. REDE DE SEGURANÇA, não estratégia -- mesmo papel do |
| `FRIEND_ROW_HEIGHT` | `15` | [blazesbot/core/coords.py:345](blazesbot/core/coords.py#L345) | — | Altura de linha nas listas da janela de amigos. |
| `MAXIMO_DE_RETRATOS_DO_TIME` | `4` | [blazesbot/core/coords.py:113](blazesbot/core/coords.py#L113) | afericao_do_aliado.py | — |
| `PASSO_ENTRE_RETRATOS_DO_TIME` | `80` | [blazesbot/core/coords.py:112](blazesbot/core/coords.py#L112) | afericao_do_aliado.py | — |
| `SELL_CELL_H` | `35` | [blazesbot/core/coords.py:341](blazesbot/core/coords.py#L341) | — | — |
| `SELL_CELL_W` | `34` | [blazesbot/core/coords.py:340](blazesbot/core/coords.py#L340) | — | — |
| `SELL_COLUMNS` | `6` | [blazesbot/core/coords.py:338](blazesbot/core/coords.py#L338) | — | Geometria da grade de venda, medida no print real. |
| `SELL_ROWS` | `4` | [blazesbot/core/coords.py:339](blazesbot/core/coords.py#L339) | — | — |
| `SERVER_ROW_HEIGHT` | `20` | [blazesbot/core/coords.py:334](blazesbot/core/coords.py#L334) | — | — |
| `VALIDATED_RESOLUTION` | `'1024x768'` | [blazesbot/core/coords.py:43](blazesbot/core/coords.py#L43) | main_window.py, web_app.py | — |
| `INTERVALO_DE_DESPEJO` | `30.0` | [blazesbot/core/cronometro.py:98](blazesbot/core/cronometro.py#L98) | — | De quanto em quanto tempo a thread despeja o que foi acumulado. |
| `LINHAS_NO_ARQUIVO_QUENTE` | `3000` | [blazesbot/core/cronometro.py:110](blazesbot/core/cronometro.py#L110) | — | Quantas linhas o arquivo quente guarda. O `ArquivoDeLogLimitado` cuida do |
| `PISO_PARA_CRONOMETRAR` | `1e-05` | [blazesbot/core/cronometro.py:89](blazesbot/core/cronometro.py#L89) | instrumentacao.py | Abaixo disto, NÃO se cronometra. Ver o bloco "O PISO DE 10 µs" acima: a 1 µs o |
| `LINHAS_MAXIMAS_DO_DIARIO` | `20000` | [blazesbot/core/diario.py:39](blazesbot/core/diario.py#L39) | — | Teto de linhas por diário. Generoso de propósito -- o diário existe para ser |
| `HP_MAXIMO_PLAUSIVEL` | `5000000` | [blazesbot/core/entidades.py:40](blazesbot/core/entidades.py#L40) | — | Teto de HP que ainda é HP. Cinco milhões é folgado de sobra para qualquer |
| `NIVEL_MAXIMO_PLAUSIVEL` | `200` | [blazesbot/core/entidades.py:43](blazesbot/core/entidades.py#L43) | — | Faixa de nível. 200 é folga: o jogo vai a 8x, e o boss da cave é nv51. |
| `ESPERA_ENTRE_PASSOS` | `0.3` | [blazesbot/core/esconder_jogadores.py:153](blazesbot/core/esconder_jogadores.py#L153) | — | Espera entre os passos da sequência. O cliente precisa processar a abertura do |
| `LEITURAS_SEM_RESPOSTA` | `2` | [blazesbot/core/esconder_jogadores.py:161](blazesbot/core/esconder_jogadores.py#L161) | — | Leituras seguidas sem resposta antes de desistir de conferir. A captura falha |
| `TECLA_DO_CHAT` | `'ENTER'` | [blazesbot/core/esconder_jogadores.py:149](blazesbot/core/esconder_jogadores.py#L149) | — | Tecla que abre e fecha o chat. Não é configurável: é o Enter, e ele não muda. |
| `TENTATIVAS_DE_FECHAR` | `3` | [blazesbot/core/esconder_jogadores.py:157](blazesbot/core/esconder_jogadores.py#L157) | amostragem_de_cliques.py | Enters de fechamento antes de desistir. Enter ALTERNA o chat, então cada |
| `ASSENTAR_A_PAGINA` | `0.08` | [blazesbot/core/hotbar.py:94](blazesbot/core/hotbar.py#L94) | combate.py, hotbar.py | DEPOIS DE CHEGAR NA PÁGINA 1, ANTES DE DEVOLVER |
| `CLIQUES_PARA_VOLTAR_A_PAGINA_1` | `2` | [blazesbot/core/hotbar.py:62](blazesbot/core/hotbar.py#L62) | hotbar.py | Três páginas: do pior caso (página 3) até a 1 são dois cliques para cima. |
| `ENTRE_CLIQUES` | `0.025` | [blazesbot/core/hotbar.py:66](blazesbot/core/hotbar.py#L66) | hotbar.py, instrumentar_clique.py | Entre um clique e o outro. Curto porque o clique deste bot é SÍNCRONO |
| `IDIOMA_PADRAO` | `'pt-br'` | [blazesbot/core/i18n.py:16](blazesbot/core/i18n.py#L16) | web_app.py | — |
| `CABECALHO` | `'# TEMPOS — tudo que o bot ESPERA\n\n> **GERADO. Não edite à mão.**\n> `./.venv/Scripts/python.exe -m blazesbot.core.indice_de_tempos`\n> Travado por `tests/test_indice_de_tempos.py`: mexeu num tempo e não regerou,\n> a suíte reprova.\n\n## REGRA PERMANENTE\n\n**Todo tempo novo — constante OU literal no meio de uma função — entra aqui.**\nNão por disciplina: a extração acha sozinha, e o teste reprova se o arquivo\nestiver velho. Basta regerar.\n\nO que NÃO se faz sozinho é o **ponto de restauração**. Ver a seção\n"Se você mudou um tempo e deu errado", no fim.\n\n## Como ler a coluna NATUREZA\n\n| natureza | o que é | mexer nele significa |\n|---|---|---|\n| **TETO** | prazo máximo; quem responde antes não paga | encurtar arrisca **o caso lento**, não o comum |\n| **PASSO** | cadência de uma pergunta em laço | encurtar gasta **CPU**, não relógio |\n| **FIXO** | espera **CEGA**: paga sempre, inteira | é **aqui** que há tempo a ganhar |\n\nA regra do projeto é *"onde havia espera cega, agora se PERGUNTA"*. Cada **FIXO**\ndesta lista é ou uma exceção justificada, ou dívida que ninguém converteu ainda.\n\n## A coluna ORIGINAL\n\n`=` significa que o valor está como o de referência. **`⚠` significa que alguém\nmudou** — e a coluna mostra de quanto era. É o ponto de restauração.\n\n'` | [blazesbot/core/indice_de_tempos.py:311](blazesbot/core/indice_de_tempos.py#L311) | — | — |
| `RODAPE` | `'\n---\n\n## Se você mudou um tempo e deu errado\n\n1. Ache a linha aqui pelo nome (ou pelo arquivo).\n2. A coluna **ORIGINAL** com `⚠` traz o valor de referência.\n3. Volte para ele no arquivo apontado pela coluna ONDE.\n\nO ponto de restauração vive em `docs/tempos-originais.json`.\n\n**Ele NÃO é atualizado sozinho, e isso é de propósito**: se toda geração\nrefotografasse os valores, o "original" seria sempre o de agora e o arquivo não\nserviria para nada. Refotografar é ato deliberado:\n\n```python\nfrom blazesbot.core.indice_de_tempos import extrair, gravar_originais\ngravar_originais(extrair())\n```\n\nFaça isso **só** quando um valor novo já estiver provado em produção e você\nquiser que ele passe a ser a referência.\n\n## O que este catálogo NÃO cobre\n\n* **Tempo que vem da configuração** (`attack_delay`, `max_fight_seconds`,\n  `launch_delay`, `time_factor`, os `delay_ms` da macro do APP): muda por conta,\n  na interface, e não tem "valor original" único. Está em `blazesbot/config.py`.\n* **Tempo que o JOGO impõe** (animação de montar, teleporte, efeito de poção):\n  não é nosso, e o bot só pode medir.\n* **Esperas calculadas** (`tick(resto)`, `tick(segundos * fator)`): o valor não\n  é literal, então não há número para catalogar. Elas aparecem indiretamente,\n  pelas constantes que as alimentam.\n'` | [blazesbot/core/indice_de_tempos.py:345](blazesbot/core/indice_de_tempos.py#L345) | — | — |
| `CLIQUES_DIREITOS_POR_TENTATIVA` | `10` | [blazesbot/core/inputs.py:211](blazesbot/core/inputs.py#L211) | — | QUANTOS CLIQUES DIREITOS POR TENTATIVA |
| `INTERVALO_ENTRE_CLIQUES_DIREITOS` | `0.044` | [blazesbot/core/inputs.py:215](blazesbot/core/inputs.py#L215) | — | Espaço entre um clique e o seguinte. Curto de propósito: a aposta é que a |
| `NOME_DO_PROCESSO_DO_JOGO` | `'client.exe'` | [blazesbot/core/inputs.py:285](blazesbot/core/inputs.py#L285) | — | NENHUMA MENSAGEM SAI PARA UMA JANELA QUE NÃO É O JOGO |
| `SEGUNDOS_ENTRE_CONFERENCIAS_DO_PROCESSO` | `2.0` | [blazesbot/core/inputs.py:302](blazesbot/core/inputs.py#L302) | — | De quanto em quanto tempo o NOME do processo é reconferido. |
| `TETO_DO_BLOQUEIO_MS` | `80.0` | [blazesbot/core/inputs.py:76](blazesbot/core/inputs.py#L76) | — | TETO do bloqueio do mouse físico, em milissegundos -- e TETO, não gasto: o |
| `AMOSTRAS_PARA_DECIDIR` | `20` | [blazesbot/core/instrumentacao.py:84](blazesbot/core/instrumentacao.py#L84) | — | Quantas chamadas medir antes de decidir se o embrulho fica. |
| `SEM_JANELA` | `'(sem janela)'` | [blazesbot/core/janelas.py:36](blazesbot/core/janelas.py#L36) | — | O TÍTULO DE QUEM NÃO TEM JANELA. Texto, e não `None`, porque todo chamador |
| `TIMEOUT_DA_SONDA_MS` | `1500` | [blazesbot/core/janelas.py:116](blazesbot/core/janelas.py#L116) | — | A SONDA DE TRAVAMENTO -- "Não Está Respondendo", medido em vez de suposto |
| `LIMIAR_DA_MOLDURA` | `0.65` | [blazesbot/core/janelas_abertas.py:107](blazesbot/core/janelas_abertas.py#L107) | — | Limiar da moldura, e ele NÃO é o 0.80 do projeto -- de propósito. |
| `LIMIAR_DO_X` | `0.8` | [blazesbot/core/janelas_abertas.py:95](blazesbot/core/janelas_abertas.py#L95) | — | Limiar do X. É o 0.80 que o projeto inteiro já usa (`INVITE_THRESHOLD`, |
| `MAXIMO_DE_JANELAS` | `4` | [blazesbot/core/janelas_abertas.py:115](blazesbot/core/janelas_abertas.py#L115) | — | Quantas janelas fechar numa chamada antes de desistir. |
| `TEMPLATE_DA_MOLDURA` | `'janela_moldura.png'` | [blazesbot/core/janelas_abertas.py:90](blazesbot/core/janelas_abertas.py#L90) | — | — |
| `TEMPLATE_DO_X` | `'janela_fechar.png'` | [blazesbot/core/janelas_abertas.py:89](blazesbot/core/janelas_abertas.py#L89) | — | Templates. Medidos e recortados em 26/08/2026 -- ver o cabeçalho. |
| `LOG_JSON_MAXIMO` | `4000` | [blazesbot/core/log_json.py:27](blazesbot/core/log_json.py#L27) | — | Quantos registros o JSON dev guarda (reusa a poda por linha do arquivo). |
| `DIAS_DE_ARQUIVO_MORTO` | `2` | [blazesbot/core/log_limitado.py:77](blazesbot/core/log_limitado.py#L77) | log_json.py | O ARQUIVO MORTO: o que a poda descarta deixou de ser PERDIDO |
| `FOLGA_ANTES_DE_PODAR` | `100` | [blazesbot/core/log_limitado.py:38](blazesbot/core/log_limitado.py#L38) | log_json.py | Quanto ele pode passar antes de a poda acontecer. Podar de cem em cem em vez de |
| `INTERVALO_ENTRE_LIMPEZAS` | `3600.0` | [blazesbot/core/log_limitado.py:89](blazesbot/core/log_limitado.py#L89) | — | De quanto em quanto tempo varrer a pasta do arquivo morto. |
| `LINHAS_MAXIMAS` | `500` | [blazesbot/core/log_limitado.py:34](blazesbot/core/log_limitado.py#L34) | — | Quantas linhas o arquivo guarda. As mais antigas são descartadas. |
| `SEGUNDOS_DE_SILENCIO_ANTES_DE_COMPRIMIR` | `60.0` | [blazesbot/core/log_limitado.py:97](blazesbot/core/log_limitado.py#L97) | — | Quanto tempo um arquivo precisa estar QUIETO para poder ser comprimido. |
| `LUGAR_FORA_DA_CAVE` | `'Ghost Din Woods'` | [blazesbot/core/lugares.py:102](blazesbot/core/lugares.py#L102) | localizacao.py, routine.py | O lugar em que o personagem está quando NÃO está na cave e o X é grande. |
| `MINIMO_CAUDA` | `5` | [blazesbot/core/lugares.py:126](blazesbot/core/lugares.py#L126) | — | Menor cauda que ainda identifica um lugar com segurança. Abaixo disso, |
| `ANGULO_DA_CAMERA` | `956.720459` | [blazesbot/core/memory.py:313](blazesbot/core/memory.py#L313) | ler_camera.py | O ângulo em que os cliques na cena 3D foram medidos. |
| `BAG_CLOSED_VALUE` | `902` | [blazesbot/core/memory.py:636](blazesbot/core/memory.py#L636) | — | Valor da bolsa FECHADA. Medido em 02/09/2026 alternando a tecla `I` e lido em |
| `BAG_OPEN_VALUE` | `903` | [blazesbot/core/memory.py:632](blazesbot/core/memory.py#L632) | — | — |
| `DIALOGO_ABERTO_VALOR` | `16775` | [blazesbot/core/memory.py:564](blazesbot/core/memory.py#L564) | — | — |
| `DIALOGO_FECHADO_VALOR` | `16774` | [blazesbot/core/memory.py:565](blazesbot/core/memory.py#L565) | — | — |
| `ESCALA_DE_INIMIGO` | `100` | [blazesbot/core/memory.py:641](blazesbot/core/memory.py#L641) | afericao_do_aliado.py | HP máximo padrão de inimigos do covil (Gun Witch, Cemetery Guard, etc.) |
| `ESPELHO_DELTA` | `928` | [blazesbot/core/memory.py:110](blazesbot/core/memory.py#L110) | — | O BLOCO ATRASADO EM +0x3A0 -- o passado do estado, nao uma segunda fonte |
| `JANELA_DE_COMBATE` | `16` | [blazesbot/core/memory.py:71](blazesbot/core/memory.py#L71) | — | Quantos bytes ler de cada lado de `OFF_BATTLE` em `battle_window()`. Serve para |
| `LIMITE_DE_ENTIDADES` | `512` | [blazesbot/core/memory.py:421](blazesbot/core/memory.py#L421) | target_hybrid.py | Quantos slots do array de entidades varrer. 512 cobre com folga o que o |
| `MAXIMO_DE_MEMBROS_LIDOS` | `4` | [blazesbot/core/memory.py:374](blazesbot/core/memory.py#L374) | — | O time do Talisman vai a cinco (o personagem mais quatro), mas a tabela lida |
| `PASSO_DA_PROVA_DA_CAMERA` | `0.05` | [blazesbot/core/memory.py:338](blazesbot/core/memory.py#L338) | — | — |
| `PASSO_ENTRE_MEMBROS` | `136` | [blazesbot/core/memory.py:368](blazesbot/core/memory.py#L368) | — | — |
| `PROVA_DA_CAMERA` | `5.0` | [blazesbot/core/memory.py:325](blazesbot/core/memory.py#L325) | — | Quanto o diagnóstico soma ao ângulo para PROVAR que a escrita move a câmera. |
| `SIT_VALUE` | `200` | [blazesbot/core/memory.py:631](blazesbot/core/memory.py#L631) | — | Valores sentinela observados no cliente |
| `SYSTEM_MENU_VALUE` | `1610612736` | [blazesbot/core/memory.py:637](blazesbot/core/memory.py#L637) | — | — |
| `TETO_DA_PROVA_DA_CAMERA` | `1.0` | [blazesbot/core/memory.py:337](blazesbot/core/memory.py#L337) | — | Teto da espera pelo termômetro depois de uma escrita na câmera. |
| `TOLERANCIA_DA_POSE` | `0.001` | [blazesbot/core/memory.py:270](blazesbot/core/memory.py#L270) | — | Quanto cada campo da pose pode variar e ainda contar como certo. |
| `TOLERANCIA_DO_ANGULO` | `0.001` | [blazesbot/core/memory.py:319](blazesbot/core/memory.py#L319) | — | Quanto o ângulo pode variar e ainda contar como certo. |
| `HC_ACTION` | `0` | [blazesbot/core/mouse_shield.py:126](blazesbot/core/mouse_shield.py#L126) | instrumentar_clique.py | — |
| `VALIDADE_DO_RETANGULO` | `2.0` | [blazesbot/core/mouse_shield.py:130](blazesbot/core/mouse_shield.py#L130) | — | Quanto tempo o retângulo da janela vale antes de ser relido. A janela do jogo |
| `WH_MOUSE_LL` | `14` | [blazesbot/core/mouse_shield.py:118](blazesbot/core/mouse_shield.py#L118) | instrumentar_clique.py, supervisor.py, inputs.py | Constantes Win32 |
| `NOME_DO_MODULO` | `'client.exe'` | [blazesbot/core/patch_do_cliente.py:134](blazesbot/core/patch_do_cliente.py#L134) | — | — |
| `SEGUNDOS_PARA_A_COMIDA_SER_USADA` | `1.5` | [blazesbot/core/pet.py:131](blazesbot/core/pet.py#L131) | executor.py, combate.py | QUANTO TEMPO A COMIDA PRECISA ANTES DA PRÓXIMA AÇÃO |
| `BM_CLICK` | `245` | [blazesbot/core/petbug.py:184](blazesbot/core/petbug.py#L184) | — | — |
| `CLASSE_DO_BOTAO` | `'TButton'` | [blazesbot/core/petbug.py:170](blazesbot/core/petbug.py#L170) | — | Como o botão é reconhecido: classe e texto, medidos na janela real. |
| `CLASSE_DO_LOG` | `'TMemo'` | [blazesbot/core/petbug.py:173](blazesbot/core/petbug.py#L173) | — | O log do programa. |
| `FATIA_DA_ESPERA` | `0.25` | [blazesbot/core/petbug.py:236](blazesbot/core/petbug.py#L236) | context.py | — |
| `INTERVALO_MINIMO` | `30.0` | [blazesbot/core/petbug.py:227](blazesbot/core/petbug.py#L227) | ui_service.py | Tempos |
| `PEDACO_DO_TITULO` | `'PetBug'` | [blazesbot/core/petbug.py:144](blazesbot/core/petbug.py#L144) | — | A JANELA É PROCURADA PELO PEDAÇO COMUM, e é isso que permite renomeá-la. |
| `SEGUNDOS_PARA_A_JANELA_ABRIR` | `10.0` | [blazesbot/core/petbug.py:230](blazesbot/core/petbug.py#L230) | — | Espera pela janela aparecer depois de lançar o programa. |
| `SEGUNDOS_PARA_O_LOG_CONFIRMAR` | `5.0` | [blazesbot/core/petbug.py:235](blazesbot/core/petbug.py#L235) | — | Espera pela confirmação no log depois do clique. |
| `SEGUNDOS_PARA_O_PROGRAMA_MORRER` | `3.0` | [blazesbot/core/petbug.py:233](blazesbot/core/petbug.py#L233) | — | Espera o processo antigo MORRER antes de abrir o novo. Curto: é um formulário |
| `TEXTO_DO_BOTAO` | `'Patch'` | [blazesbot/core/petbug.py:171](blazesbot/core/petbug.py#L171) | — | — |
| `DIAS_GUARDADOS` | `3` | [blazesbot/core/quedas.py:57](blazesbot/core/quedas.py#L57) | main_window.py, web_app.py | Por TEMPO, e não por contagem: a pergunta é "o que aconteceu essa noite", e |
| `FASE_DESCONHECIDA` | `'Estava começando a rodar'` | [blazesbot/core/quedas.py:123](blazesbot/core/quedas.py#L123) | — | — |
| `LARGURA_DA_MINIATURA` | `320` | [blazesbot/core/quedas.py:79](blazesbot/core/quedas.py#L79) | — | Largura da MINIATURA, gravada ao lado do print inteiro. |
| `LINHAS_DE_LOG_GUARDADAS` | `20` | [blazesbot/core/quedas.py:64](blazesbot/core/quedas.py#L64) | — | Linhas de log guardadas por conta. NÃO aparecem na tela (ver `FASES`); vão |
| `MOTIVO_DESCONHECIDO` | `'O jogo parou de responder'` | [blazesbot/core/quedas.py:96](blazesbot/core/quedas.py#L96) | — | — |
| `QUALIDADE_DO_JPEG` | `85` | [blazesbot/core/quedas.py:70](blazesbot/core/quedas.py#L70) | — | Qualidade do JPEG. O print aqui é para OLHO HUMANO ler um aviso, não para |
| `DESLOCAMENTO_6139_PARA_6400` | `96` | [blazesbot/core/rebase.py:91](blazesbot/core/rebase.py#L91) | — | Deslocamento MEDIDO entre a versão 6139 e a 6400 do cliente, em dois |
| `EMPATE_ENTRE_VIZINHOS` | `8.0` | [blazesbot/core/rota.py:141](blazesbot/core/rota.py#L141) | — | Diferença de distância abaixo da qual dois waypoints VIZINHOS contam como |
| `NA_ROTA` | `12.0` | [blazesbot/core/rota.py:137](blazesbot/core/rota.py#L137) | mapa_bc.py, routine.py, mapa_hh.py | Distância até o waypoint mais próximo abaixo da qual o personagem é considerado |
| `RAIO_DA_AREA` | `55.0` | [blazesbot/core/rota.py:131](blazesbot/core/rota.py#L131) | mapa_bc.py | Distância máxima até um waypoint para aceitar a área dele como resposta. |
| `DIAS_RETIDOS` | `7` | [blazesbot/core/stats_diarias.py:49](blazesbot/core/stats_diarias.py#L49) | — | Quantos dias de histórico manter (hoje + os 6 anteriores = uma semana). |
| `NOME_DE_STONE_CITY` | `'Stone City'` | [blazesbot/core/stone_city.py:64](blazesbot/core/stone_city.py#L64) | mapa_bc.py | — |
| `PRECISAO_NO_PONTO_DA_FAY` | `1.5` | [blazesbot/core/stone_city.py:51](blazesbot/core/stone_city.py#L51) | mapa_bc.py, ui_service.py, entrada.py | Folga aceita para considerar que já se está no ponto de falar com ela. |
| `SEGUNDOS_POR_TENTATIVA_NA_FAY` | `1.8` | [blazesbot/core/stone_city.py:55](blazesbot/core/stone_city.py#L55) | mapa_bc.py, ui_service.py, entrada.py | — |
| `TENTATIVAS_DE_ENCOSTAR_NA_FAY` | `6` | [blazesbot/core/stone_city.py:54](blazesbot/core/stone_city.py#L54) | mapa_bc.py, ui_service.py, entrada.py | Quantas vezes tentar encostar no ponto exato antes de desistir da viagem. |
| `X_MAXIMO_DENTRO_DA_CAVE` | `500` | [blazesbot/core/stone_city.py:72](blazesbot/core/stone_city.py#L72) | mapa_bc.py | O X MÁXIMO QUE PODE EXISTIR NUMA INSTÂNCIA. |
| `CASAS_DO_DESENHO` | `10` | [blazesbot/core/target_hybrid.py:116](blazesbot/core/target_hybrid.py#L116) | — | Casas do desenho da barra no log. |
| `FAIXA_PARA_OLHAR_O_MARCADOR` | `0.1` | [blazesbot/core/target_hybrid.py:105](blazesbot/core/target_hybrid.py#L105) | — | Abaixo desta fração de vida vale a pena procurar o `EnemyDead.png`. |
| `LIMIAR_VIDA_TELA` | `0.02` | [blazesbot/core/target_hybrid.py:94](blazesbot/core/target_hybrid.py#L94) | executor.py | Abaixo desta fração a barra conta como VAZIA. |
| `MAXIMO_DE_ACHADOS` | `12` | [blazesbot/core/target_hybrid.py:584](blazesbot/core/target_hybrid.py#L584) | — | Quantos endereços mostrar por id. Mais que isto vira parede de texto. |
| `PASSO_DA_CONFIRMACAO_DO_TAB` | `0.01` | [blazesbot/core/target_hybrid.py:697](blazesbot/core/target_hybrid.py#L697) | executor.py | De quanto em quanto tempo perguntar. A leitura do id e UM `read_int` (~1 us): |
| `TETO_PARA_O_ALVO_TROCAR` | `0.35` | [blazesbot/core/target_hybrid.py:692](blazesbot/core/target_hybrid.py#L692) | combate.py | Teto da espera. Passado isto, a tecla nao pegou -- insistir e trabalho do |
| `MAXIMO_DE_RELOGINS` | `2` | [blazesbot/core/teclado_mudo.py:106](blazesbot/core/teclado_mudo.py#L106) | — | Quantos relogins por teclado mudo antes de desistir e só gritar. |
| `SEGUNDOS_ATE_O_ESC` | `30.0` | [blazesbot/core/teclado_mudo.py:84](blazesbot/core/teclado_mudo.py#L84) | — | Quanto tempo as duas teclas precisam estar mudas antes de o ESC sair. |
| `SEGUNDOS_ATE_O_RELOGIN` | `300.0` | [blazesbot/core/teclado_mudo.py:95](blazesbot/core/teclado_mudo.py#L95) | — | Quanto tempo mudo até declarar queda e mandar relogar. |
| `SEGUNDOS_ENTRE_AVISOS` | `60.0` | [blazesbot/core/teclado_mudo.py:225](blazesbot/core/teclado_mudo.py#L225) | — | De quanto em quanto tempo o TAB MUDO volta a falar -- 06/09/2026. |
| `SEGUNDOS_ENTRE_RELOGINS` | `900.0` | [blazesbot/core/teclado_mudo.py:103](blazesbot/core/teclado_mudo.py#L103) | — | Espaço mínimo entre dois relogins automáticos por teclado mudo. |
| `BARRA_DO_ALVO_X0` | `466` | [blazesbot/core/vision/barra.py:52](blazesbot/core/vision/barra.py#L52) | __init__.py | A BARRA DO ALVO POR OFFSET FIXO -- medida pelo usuário em 25/08/2026 |
| `BARRA_DO_ALVO_X1` | `600` | [blazesbot/core/vision/barra.py:53](blazesbot/core/vision/barra.py#L53) | __init__.py | — |
| `BARRA_DO_ALVO_Y0` | `46` | [blazesbot/core/vision/barra.py:54](blazesbot/core/vision/barra.py#L54) | __init__.py | — |
| `BARRA_DO_ALVO_Y1` | `49` | [blazesbot/core/vision/barra.py:55](blazesbot/core/vision/barra.py#L55) | __init__.py | — |
| `MINIMO_RECONHECIDO_NA_FAIXA` | `0.7` | [blazesbot/core/vision/barra.py:65](blazesbot/core/vision/barra.py#L65) | __init__.py | A fração da faixa que precisa ser reconhecida (vida ou vazio) para a leitura |
| `PASSO_DA_AMOSTRAGEM_DO_QUADRO` | `8` | [blazesbot/core/vision/captura.py:27](blazesbot/core/vision/captura.py#L27) | __init__.py | De quantos em quantos pixels o `frame_is_blank` amostra o quadro. |
| `ALTURA_DA_BARRA` | `8` | [blazesbot/core/vision/marcadores.py:41](blazesbot/core/vision/marcadores.py#L41) | __init__.py, barra.py | — |
| `LARGURA_MINIMA_DA_BARRA` | `100` | [blazesbot/core/vision/marcadores.py:37](blazesbot/core/vision/marcadores.py#L37) | __init__.py, barra.py | Largura mínima da corrida azul para ela ser a barra de mana do alvo. Não é a |
| `LIMIAR_DA_FASE_2_DO_BOSS` | `0.92` | [blazesbot/core/vision/marcadores.py:233](blazesbot/core/vision/marcadores.py#L233) | combate.py, __init__.py | A SEGUNDA FASE DO BOSS, LIDA NA TELA. |
| `LIMIAR_DO_MARCADOR_DE_MORTE` | `0.85` | [blazesbot/core/vision/marcadores.py:78](blazesbot/core/vision/marcadores.py#L78) | __init__.py | Limiar do marcador de inimigo morto. Sprite pequeno (26x22) num quadro de UI, |
| `LINHAS_ENTRE_HP_E_MP` | `7` | [blazesbot/core/vision/marcadores.py:40](blazesbot/core/vision/marcadores.py#L40) | __init__.py, barra.py | Distância da barra vermelha para a azul, em linhas, e altura da faixa. |
| `DEFAULT_THRESHOLD` | `0.87` | [blazesbot/core/vision/templates.py:21](blazesbot/core/vision/templates.py#L21) | __init__.py | — |
| `RAIO` | `40` | [blazesbot/core/vizinhanca.py:34](blazesbot/core/vizinhanca.py#L34) | — | Raio, em unidades de jogo, do que conta como "em volta". |
| `TOLERANCIA` | `1` | [blazesbot/core/volta_ao_ponto.py:32](blazesbot/core/volta_ao_ponto.py#L32) | executor.py | Quanto o personagem pode estar fora do ponto e ainda contar como "chegou". |
| `MAP_DISTANCE_THRESHOLD` | `50` | [blazesbot/core/zones.py:222](blazesbot/core/zones.py#L222) | navegacao.py | Distância em unidades de coordenada a partir da qual vale usar o mapa-múndi |
| `MINIMAP_MAX_PIXELS` | `30` | [blazesbot/core/zones.py:218](blazesbot/core/zones.py#L218) | — | Deslocamento máximo, em pixels, a partir do centro do minimapa. Clique além |
| `MINIMAP_SCALE` | `1.7` | [blazesbot/core/zones.py:214](blazesbot/core/zones.py#L214) | ui_do_jogo.py, coords.py | Escala do minimapa: pixels por unidade de coordenada. |
| `AJUDA_ESC` | `'Clique no campo e aperte a tecla que você usa no jogo.\n\nESC apaga o atalho e deixa como “não usar”.\n\nAceita: 1-9 e 0, A-Z, F1-F12, teclado numérico,\nSPACE, TAB, ENTER, SHIFT, CTRL, ALT.'` | [blazesbot/gui/account_dialog.py:102](blazesbot/gui/account_dialog.py#L102) | — | — |
| `AJUDA_ESCONDER` | `'Esconde os outros jogadores da tela.\n\nComo configurar no jogo:\n\n  1. Aperte ESC\n  2. Clique em Keys\n  3. Procure a tecla de esconder personagens\n     (F12 costuma ser o padrão)\n\nPARA QUE SERVE AQUI: o catador de loot clica no CHÃO, e\noutro personagem em cima do cadáver muda o que o clique\nacerta. O bot segura esta tecla e abre o chat, o que faz\no esconder GRUDAR até o fim da sessão — e refaz isso\nantes de cada entrada na cave, porque apertar a tecla de\nnovo desfaz.\n\nÉ OPCIONAL: sem tecla configurada o bot não mexe nisso.'` | [blazesbot/gui/account_dialog.py:66](blazesbot/gui/account_dialog.py#L66) | — | — |
| `AJUDA_HOTBAR` | `'Faz o bot voltar à página 1 da barra de atalhos,\nque é a usada pelo bot.\n\nComo configurar no jogo:\n\n  1. Aperte ESC\n  2. Clique em Keys\n  3. Procure “Main Hotkey Page 1” e escolha uma tecla livre\n  4. Apague as teclas de Page 2 e Page 3 — sem elas, nada\n     tira a barra da página 1 por acidente\n\nÉ OPCIONAL: sem tecla configurada o bot continua clicando\nno botão, como sempre fez.'` | [blazesbot/gui/account_dialog.py:86](blazesbot/gui/account_dialog.py#L86) | — | — |
| `ALTURA_LINHA` | `40` | [blazesbot/gui/main_window.py:79](blazesbot/gui/main_window.py#L79) | — | — |
| `INTERVALO_DE_DESCARGA_MS` | `200` | [blazesbot/gui/main_window.py:96](blazesbot/gui/main_window.py#L96) | — | Cadência com que a interface esvazia a fila de log. 5 vezes por segundo é |
| `LARGURA_DA_CAIXA` | `46` | [blazesbot/gui/main_window.py:78](blazesbot/gui/main_window.py#L78) | — | Largura das colunas que só têm uma caixa de marcar. É o tamanho da caixa |
| `MAX_LINHAS_GUARDADAS` | `12000` | [blazesbot/gui/main_window.py:105](blazesbot/gui/main_window.py#L105) | web_app.py | Linhas mantidas em memória para permitir refiltrar por conta. |
| `MAX_LINHAS_POR_DESCARGA` | `400` | [blazesbot/gui/main_window.py:102](blazesbot/gui/main_window.py#L102) | — | Máximo de linhas escritas no widget por descarga. Existe porque um pico de |
| `ACCENT` | `'#E08A4C'` | [blazesbot/gui/theme.py:50](blazesbot/gui/theme.py#L50) | help_tip.py, key_capture.py, widgets.py | Destaque: âmbar quente, análogo ao vermelho da base |
| `ACCENT_HOVER` | `'#F0A063'` | [blazesbot/gui/theme.py:51](blazesbot/gui/theme.py#L51) | — | — |
| `ACCENT_PRESSED` | `'#BE7038'` | [blazesbot/gui/theme.py:52](blazesbot/gui/theme.py#L52) | — | — |
| `ACCENT_SOFT` | `'#8A5030'` | [blazesbot/gui/theme.py:53](blazesbot/gui/theme.py#L53) | — | — |
| `BASE` | `'#541E1B'` | [blazesbot/gui/theme.py:37](blazesbot/gui/theme.py#L37) | executor.py, supervisor.py, watchdog.py, widgets.py | Base pedida |
| `BG` | `'#1F0C0B'` | [blazesbot/gui/theme.py:41](blazesbot/gui/theme.py#L41) | — | — |
| `BG_DEEP` | `'#150807'` | [blazesbot/gui/theme.py:40](blazesbot/gui/theme.py#L40) | help_tip.py, key_capture.py, widgets.py | Fundos, do mais profundo ao mais claro (mesmo matiz da base) |
| `BORDER` | `'#7A322C'` | [blazesbot/gui/theme.py:46](blazesbot/gui/theme.py#L46) | help_tip.py, widgets.py | Bordas e separadores |
| `BORDER_SOFT` | `'#4A201C'` | [blazesbot/gui/theme.py:47](blazesbot/gui/theme.py#L47) | key_capture.py, widgets.py | — |
| `ERR` | `'#F07A6E'` | [blazesbot/gui/theme.py:64](blazesbot/gui/theme.py#L64) | — | — |
| `FONT` | `'Segoe UI'` | [blazesbot/gui/theme.py:66](blazesbot/gui/theme.py#L66) | — | — |
| `OK` | `'#8FC46A'` | [blazesbot/gui/theme.py:62](blazesbot/gui/theme.py#L62) | — | Estados. Claros o bastante para serem lidos sobre fundo escuro, e não apenas |
| `PANEL` | `'#2C1311'` | [blazesbot/gui/theme.py:42](blazesbot/gui/theme.py#L42) | — | — |
| `PANEL_ALT` | `'#3A1815'` | [blazesbot/gui/theme.py:43](blazesbot/gui/theme.py#L43) | — | — |
| `TEXT` | `'#F7F5F5'` | [blazesbot/gui/theme.py:56](blazesbot/gui/theme.py#L56) | key_capture.py, widgets.py | Texto -- NEUTRO de propósito. Ver o comentário no topo do arquivo. |
| `TEXT_DIM` | `'#BEB7B6'` | [blazesbot/gui/theme.py:57](blazesbot/gui/theme.py#L57) | account_dialog.py, widgets.py | — |
| `TEXT_FAINT` | `'#8E8483'` | [blazesbot/gui/theme.py:58](blazesbot/gui/theme.py#L58) | key_capture.py | — |
| `WARN` | `'#F0C24A'` | [blazesbot/gui/theme.py:63](blazesbot/gui/theme.py#L63) | key_capture.py | — |
| `COR_HP` | `'#8E2B22'` | [blazesbot/gui/widgets.py:25](blazesbot/gui/widgets.py#L25) | — | Cores por tipo de recurso |
| `COR_HP_BORDA` | `'#C4544A'` | [blazesbot/gui/widgets.py:26](blazesbot/gui/widgets.py#L26) | — | — |
| `COR_MP` | `'#22488E'` | [blazesbot/gui/widgets.py:27](blazesbot/gui/widgets.py#L27) | — | — |
| `COR_MP_BORDA` | `'#4A7BC4'` | [blazesbot/gui/widgets.py:28](blazesbot/gui/widgets.py#L28) | — | — |
| `CHUNK` | `1048576` | [blazesbot/tools/find_base.py:57](blazesbot/tools/find_base.py#L57) | — | — |
| `MUDOU` | `0.0005` | [blazesbot/tools/ler_camera.py:57](blazesbot/tools/ler_camera.py#L57) | afericao_do_aliado.py, executor.py, localizacao.py, routine.py, combate.py, context.py, fada.py, config.py, calibracao.py, memory.py, target_hybrid.py | O que conta como "mudou". Menor que isto é ruído de interpolação -- andando, o |
| `PASSO` | `0.25` | [blazesbot/tools/ler_camera.py:50](blazesbot/tools/ler_camera.py#L50) | routine.py, entrada.py, mapa_hh.py, supervisor.py, ui_do_jogo.py, indice_de_tempos.py, relatorio_de_latencia.py, vigiar_combate.py | Cadência da leitura. Barata: são 8 leituras de 4 bytes por volta. |
| `SEGUNDOS_PADRAO` | `300.0` | [blazesbot/tools/ler_camera.py:53](blazesbot/tools/ler_camera.py#L53) | vigiar_combate.py | Teto padrão, para a ferramenta fechar sozinha se você esquecer dela aberta. |
| `PASSO` | `0.1` | [blazesbot/tools/vigiar_combate.py:48](blazesbot/tools/vigiar_combate.py#L48) | routine.py, entrada.py, mapa_hh.py, supervisor.py, ui_do_jogo.py, indice_de_tempos.py, relatorio_de_latencia.py, ler_camera.py | Cadência da leitura. É memória pura -- algumas leituras de 4 bytes por volta, |
| `SEGUNDOS_ENTRE_ECOS` | `5.0` | [blazesbot/tools/vigiar_combate.py:58](blazesbot/tools/vigiar_combate.py#L58) | — | De quanto em quanto tempo repetir uma linha que NÃO mudou. |
| `SEGUNDOS_PADRAO` | `900.0` | [blazesbot/tools/vigiar_combate.py:51](blazesbot/tools/vigiar_combate.py#L51) | ler_camera.py | Teto padrão, para a ferramenta fechar sozinha se você esquecer dela aberta. |
| `MAX_LINHAS_GUARDADAS` | `12000` | [blazesbot/web_app.py:84](blazesbot/web_app.py#L84) | main_window.py | Linhas guardadas em memória para permitir refiltrar por conta, espelho do |
