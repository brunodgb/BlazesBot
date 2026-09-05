# MEMORY

- [Analisar logs primeiro](analisar-logs-primeiro.md) — ao investigar problema, ler os logs antes de mexer no código (log de dev é JSONL enriquecido por id_run/conta/fase).
- [Ambiente token-efficiency](ambiente-token-efficiency.md) — RTK/Headroom/Perplexity MCP instalados; Headroom deliberadamente NÃO ligado por causa do gateway BlazesBot-IA (localhost:20128/v1); Perplexity aguarda chave.
- [Interface web = pywebview/WebView2 agora, autônomo](interface-web-pywebview.md) — o usuário migrou da Eel p/ pywebview+WebView2; deve ficar sem depender de navegador instalado.
- [Alteração de tempos — halvamento + reavaliação](alteracao-tempos-halvados.md) — Sessão 1: halvamento de todos os tempos fixos. Sessão 2: teclado reevelado para orig. combat.py mecânicas de jogo revertidas (7 constantes), mouse_shield e deletador revertidos pelo usuário, vendor ESPERA_PARA_CONFIRMAR_VAZIO ajustado para 0.5 (invariante), vendor retry de janela de venda implementado. Arquivo `alteracao_tempo.md` na raiz.
- [Investigação do alvo: onde parou](investigacao-do-alvo-onde-parou.md) — 21/08/2026: o HP da memória está certo, falta a IDENTIDADE; a régua da tela erra calada. Passagem de bastão em docs/decisoes/alvo-continuar-daqui.md.
- [ALVO log removido](log-hp_tela-masks-None.md) — log ALVO removido integralmente de combat.py; `hp_tela=0.0%` mascarava None e `ptr=` duplicado; `texto_do_ponteiro()` e `_anotar_ponteiro()` mantidos (ainda usados).
