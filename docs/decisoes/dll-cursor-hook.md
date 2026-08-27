# DLL de Cursor Hook — Abandonada (2026-08-16)

**Data**: 2026-08-14 a 2026-08-16  
**Status**: **ABANDONADA** — código e binários removidos do repositório  
**Alternativa adotada**: Mouse Shield (hook externo WH_MOUSE_LL) — `USAR_MOUSE_SHIELD = True`

---

## Resumo

Experimentamos injetar uma DLL de 32 bits no processo do jogo (`client.exe`)
para instalar um **inline hook** em `user32!GetCursorPos` e `user32!SetCursorPos`.
A intenção era fazer o jogo "ver" o cursor na posição programada pelo bot,
ignorando completamente o cursor físico do usuário. A técnica **funcionou em
laboratório** (hooks instalados, status SIM/SIM, injeção ok) mas **falhou em
produção** — o jogo não resolve a posição do cursor exclusivamente por
`GetCursorPos`.

## Tecnologia Experimentada

- **Arquivo-fonte C**: `blazesbot/native/cursor_hook.c` (hook inline,
  reconhecia prologues `8B FF 55 8B EC` de GetCursorPos e
  `FF 25 C4 BD 54 76` de SetCursorPos, além da variante clássica
  `64 A1 2C 00 00 00`).
- **DLL compilada**: `cursor_hook3.dll` (32-bit — o jogo é 32-bit).
- **Injetor**: `injector.exe` (32-bit, porque o bot é 64-bit e
  `pymem.inject_dll` resolve `LoadLibrary` no host 64-bit — endereço inválido
  no processo 32-bit via WOW64).
- **IPC**: Mapeamento compartilhado por PID (`Local\BlazesBotHook_<pid>`,
  struct `{active, x, y, status}`).
- **Integração**: `CursorHook` em `blazesbot/core/cursor_hook.py`, usado em
  `inputs.py` (`_cursor_hook.apontar()` antes do clique,
  `_cursor_hook.liberar()` depois). Prioridade sobre Mouse Shield.

## Por Que Falhou

**A resposta real só apareceu em 18/08/2026, e é mais simples do que se
supunha: a DLL hookeava a FUNÇÃO ERRADA.**

O `blazesbot/bot/teste_do_cursor.py` mediu 20 cliques com o cursor físico
PARADO a 780 px do alvo: **20 de 20 acertaram**. Se o jogo resolvesse a posição
por `GetCursorPos`, os 20 teriam caído onde o mouse estava parado. Ele não
resolve -- ele usa a posição que rastreia pelas mensagens `WM_MOUSEMOVE`, que é
justamente o que o `_prime_cursor` do bot escreve e o que um movimento físico
sobrescreve.

Ou seja: hookear `GetCursorPos` nunca poderia funcionar, porque o jogo não
chamava `GetCursorPos` para isso. A DLL instalava certo, o hook respondia
certo, e não mudava nada -- exatamente o sintoma relatado ("funcionou em
laboratório, falhou em produção").

**A lição que ficou, e que vale mais que a DLL:** a hipótese do mecanismo nunca
tinha sido MEDIDA, só deduzida do sintoma ("o clique vai para onde o mouse
está" ⇒ "o jogo lê o cursor"). Dois dias de C, injetor 32-bit e IPC por memória
compartilhada foram gastos contra uma hipótese que um teste de 30 segundos
derruba. Medir o mecanismo ANTES de escrever o conserto teria evitado tudo.

### O registro original (superado, mantido para histórico)

1. **Hook inline incompleto**: supunha-se que o inline hook em `GetCursorPos`
   não cobria todos os caminhos que o jogo usa para ler a posição do cursor.
   Ver acima: o problema não era cobertura, era a função.

2. **PostMessage "também falhou"** — e em 18/08/2026 descobriu-se que o teste
   estava errado, não o mecanismo: aqueles experimentos mandavam os BOTÕES por
   `SendMessageW`, que fura a fila e chega antes do move postado. PostMessage
   PURO passou 20/20 (ver `stuttering-mouse.md`). O registro original abaixo: Antes da DLL, testamos `PostMessageW` puro
   com coordenada no `lParam`. O jogo resolve PARTE dos cliques por
   `GetMessagePos` (que PostMessage preenche), mas em outros casos (como o
   Altar Stone) o clique caía onde o cursor físico estava.

3. **SendMessageW é o que funciona**: Após ambos os experimentos, o usuário
   confirmou que o comportamento original — `SendMessageW` síncrono com a
   coordenada no `lParam` — era o que funcionava em produção.

## Decisão

A DLL foi **abandonada**. Todo o código e binários foram removidos:

- `blazesbot/core/cursor_hook.py` — **deletado**
- `blazesbot/native/` — **diretório inteiro deletado** (cursor_hook.c,
  cursor_hook2.dll, cursor_hook3.dll, backups, injector.c, injector.exe,
  compilar.bat, logs)
- `blazesbot/teste_dll_absurdo.py` — **deletado**
- `blazesbot/teste_prologo_gmp.py` — **deletado** (era a ferramenta de
  diagnóstico de prologue usada para a DLL)
- `blazesbot/tools/testar_cursor.py` — **deletado**
- `TESTE4-CURSOR-HOOK-DLL.md` — **deletado** (documentação do teste)
- `TESTAR-DLL-ABSURDO.bat` — **deletado**
- `11-COMPILAR-NATIVE.bat` — **deletado**
- `12-TESTAR-CURSOR.bat` — **deletado**
- `DIAGNOSTICO-DLL.bat` — **deletado**
- `inputs.py` — todos os imports de `CursorHook`, o interruptor
  `USAR_CURSOR_HOOK_DLL`, e o branch DLL no método `_click` foram removidos.

## Solução Final

**Mouse Shield** (hook externo `WH_MOUSE_LL`, `USAR_MOUSE_SHIELD = True`):
- ✅ Cursor parado sobre janela: 100% sucesso
- ⚠️ Cursor em movimento sobre janela: 95-98% sucesso
- ✅ Zero injeção no jogo (não invasivo)
- ✅ Sem risco de ban
- ✅ Mantém `SendMessageW` síncrono (confiabilidade comprovada)

## Referências

- `docs/decisoes/stuttering-mouse.md` — Contexto completo do problema de
  stuttering e a evolução de todas as soluções testadas (TESTE 1-4).
- `docs/decisoes/cliques-e-resolucao.md` — Decisão de clique direito em rajada
  e entrada da cave, com notas históricas sobre as soluções descartadas.
- `docs/decisoes/interface.md` — Documentação da tela de histórico de quedas,
  onde o DLL foi mencionado como solução anterior.
