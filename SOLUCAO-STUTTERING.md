# ✅ SOLUÇÃO IMPLEMENTADA: Stuttering do Mouse Físico

## Resumo

**Problema**: Cursor físico do usuário trava/teleporta quando bot BC está rodando  
**Causa**: `SendMessageW` bloqueante congestionando message loop do Windows  
**Solução**: Modo `"postmessage_hibrido"` (PostMessage para WM_MOUSEMOVE, SendMessage para botões)  
**Status**: ✅ Implementado, pronto para teste

---

## Como Ativar (2 minutos)

1. Abrir `blazesbot\core\inputs.py`
2. Linha 52: trocar `"sendmessage"` por `"postmessage_hibrido"`
3. Salvar e reiniciar o bot

**Instruções detalhadas**: Ver `ATIVAR-POSTMESSAGE.md`

---

## O Que Esperar

### ✅ Deve Melhorar
- Stuttering do cursor físico (eliminar >90%)
- Teleportes de poucos pixels
- Fluidez ao usar outras janelas

### ✅ Não Deve Mudar
- Funcionamento do bot (navegação, combate, venda)
- Taxa de entrada da cave (~78%)
- Velocidade das runs

---

## Arquivos Alterados

1. `blazesbot/core/inputs.py`
   - Linha 52: Novo modo no interruptor `MODO_DE_CLIQUE`
   - Linha 55: Declaração `user32.PostMessageW.argtypes`
   - Linha 228-268: Novo método `_click_postmessage_hibrido()`

2. `docs/decisoes/stuttering-mouse.md` (novo)
   - Diagnóstico completo
   - Medição de sucesso
   - Alternativas descartadas

3. `ATIVAR-POSTMESSAGE.md` (novo)
   - Instruções simples de ativação
   - O que reportar

4. `CLAUDE.md`
   - Seção "Cliques e entrada da cave" atualizada
   - Referência à nova decisão

---

## Teste Sugerido

**Mínimo (10-15 min)**:
- Rodar 1 conta BC
- Mexer cursor livremente em outras janelas
- Verificar se stuttering sumiu

**Ideal (1-2 horas)**:
- Verificar estabilidade
- Confirmar runs completam sem erros

**Confirmação (1 semana)**:
- Sem regressão → tornar padrão

---

## Reversão (se necessário)

```python
MODO_DE_CLIQUE = "sendmessage"  # linha 52 de inputs.py
```

Reiniciar o bot.

---

## Arquitetura Técnica

### Antes (sendmessage)
```
WM_SETCURSOR   → SendMessageW (bloqueia)
WM_MOUSEMOVE   → SendMessageW (bloqueia)
WM_LBUTTONDOWN → SendMessageW (bloqueia)
WM_LBUTTONUP   → SendMessageW (bloqueia)
```
**Problema**: 4 bloqueios por clique × milhares/seg = congestionamento

### Depois (postmessage_hibrido)
```
WM_SETCURSOR   → PostMessageW  (não bloqueia) ✅
WM_MOUSEMOVE   → PostMessageW  (não bloqueia) ✅
WM_LBUTTONDOWN → SendMessageW  (síncrono)
WM_LBUTTONUP   → SendMessageW  (síncrono)
```
**Solução**: 50% assíncrono, message loop livre, botões garantem ordem

---

## Contato Técnico

**Data da implementação**: 2026-08-14  
**Versão**: BlazesBot22 - Copia  
**Teste realizado**: Não (aguardando usuário)

**Próximo passo**: Usuário ativar e testar por 10-15 min, reportar resultado.
