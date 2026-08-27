# ATIVAR MODO POSTMESSAGE HÍBRIDO

## O Que É

Solução experimental para **stuttering do cursor físico** quando o bot está rodando.

## Como Ativar

1. Abrir o arquivo: `blazesbot\core\inputs.py`

2. Ir até a **linha 52** e trocar:
   ```python
   MODO_DE_CLIQUE = "sendmessage"
   ```
   
   Por:
   ```python
   MODO_DE_CLIQUE = "postmessage_hibrido"
   ```

3. Salvar o arquivo

4. **Reiniciar o bot** (fechar e abrir de novo)

## O Que Esperar

✅ **Deve melhorar:**
- Stuttering do mouse físico (micro-travadas)
- "Teleportes" de poucos pixels ao mexer o cursor
- Fluidez ao usar outras janelas enquanto bot roda

✅ **Não deve mudar:**
- Funcionamento do bot (navegação, combate, venda)
- Taxa de sucesso de entrada da cave
- Velocidade das runs

## Como Voltar Atrás

Se algo der errado (bot não clica corretamente, runs falhando):

1. Abrir `blazesbot\core\inputs.py` linha 52

2. Trocar de volta:
   ```python
   MODO_DE_CLIQUE = "sendmessage"
   ```

3. Reiniciar o bot

## Testar por Quanto Tempo?

- **Mínimo**: 10-15 minutos (1-2 runs completas)
- **Ideal**: 1-2 horas (verificar estabilidade)
- **Confirmar**: 1 semana sem problemas → pode virar padrão

## O Que Reportar

Se funcionar bem:
- ✅ "Stuttering sumiu, bot rodando normal"

Se der problema:
- ❌ Descrição do problema (ex: "bot não entra na cave")
- ❌ Quantas runs antes de falhar
- ❌ Log da falha (`logs/dev/blazes-dev.jsonl`)
