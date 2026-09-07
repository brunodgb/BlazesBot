# O `BlazesBot - PetBug.exe`, por dentro — 07/09/2026

Pedido do usuário: *"é possível ao executar o 'BlazesBot - PetBug.exe' entender
o que ele faz por trás? Eu queria entender a função dele, fazer leitura de
memória, fazer um trabalho reverso nesse cara para a gente entender e aplicar
dentro do nosso sistema."*

Resposta curta: **sim, e é pequeno.** O programa faz duas coisas, e as duas
cabem em meia página de código. Este documento é o registro de como se chegou
lá e o que exatamente ele escreve, para ninguém precisar refazer o caminho.

## O binário

| | |
|---|---|
| arquivo | `BlazesBot - PetBug.exe`, 3.081.728 bytes |
| compilador | Embarcadero RAD Studio 29.1 (C++Builder), VCL |
| arquitetura | 32 bits, `ImageBase` 0x400000 |
| APIs que importam | `OpenProcess`, `ReadProcessMemory`, `WriteProcessMemory`, `VirtualProtectEx`, `CreateToolhelp32Snapshot`, `Process32*W`, `Module32*W`, `EnumWindows`, `PostMessageA` |

Sem rede, sem driver, sem injeção de DLL: é um patcher externo de memória, do
mesmo tipo que o bot já é para LER.

## Como o código foi localizado

O caminho que funcionou, em três passos:

1. **As mensagens.** O pool de literais está em 0x282084–0x282153 do arquivo:

   ```
   [!] Error: Insufficient privileges for PID
   [-] Warning: Could not find game window for F12.
   === Starting Pet Bug Fix & F12 Hide ===
   [!] client.exe is not running.
   [OK] Patch applied to all running clients.
   === Completed ===
   ```

   O título já entrega o desenho: **Pet Bug Fix _&_ F12 Hide** — são dois
   mecanismos independentes num botão só.

2. **A tabela de métodos publicados do formulário.** Em C++Builder ela guarda
   `[endereço][tamanho do nome][nome]`. Os quatro bytes antes de
   `"btnPatchClick"` (offset 0x2821b5) dão **`0x00404100`** — o handler do
   botão, sem precisar adivinhar alinhamento de desmontagem.

3. **A desmontagem** a partir daí, seguindo as chamadas.

## O que o botão `Patch` faz

`TfrmMain::btnPatchClick` em `0x00404100`:

```
CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS)
Process32FirstW/NextW, comparando com "client.exe" (UTF-16, em 0x683268)
  -> para cada PID: chama 0x00403ca4
nenhum achado -> "[!] client.exe is not running."
fim                -> "[OK] Patch applied to all running clients."
```

A rotina por processo, `0x00403ca4`:

```
OpenProcess(0x1FFFFF)                     -- PROCESS_ALL_ACCESS
  falhou -> "[!] Error: Insufficient privileges for PID ..."
CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid)
Module32FirstW/NextW -> "client.exe": pega modBaseAddr e modBaseSize
0x00403afc(handle, base, tamanho, &padrão)   -- lê o módulo INTEIRO e procura
  achou -> VirtualProtectEx(PAGE_EXECUTE_READWRITE)
           WriteProcessMemory(seis bytes)
           VirtualProtectEx(proteção antiga)
  (duas vezes: um padrão por sítio)
EnumWindows -> a janela daquele PID
PostMessage(hwnd, WM_KEYDOWN=0x100, VK_F12=0x7B, 0)
  não achou -> "[-] Warning: Could not find game window for F12."
```

## Os bytes, e de onde eles saem

Não estão num arquivo de configuração: são montados na mão pelo inicializador
estático, a partir de `0x004037fa`. Três `std::vector<uint8_t>` de 6 bytes:

```asm
; padrão A -- global 0x68dca0
mov dword ptr [esp], 6 ; call operator new
mov word  ptr [eax+4], 0
mov dword ptr [eax],   0x10A88F89        ->  89 8F A8 10 00 00

; padrão B -- global 0x68dcb0
mov word  ptr [eax+4], 0
mov dword ptr [eax],   0x10A8BE89        ->  89 BE A8 10 00 00

; substituição -- global 0x68dcc0
mov word  ptr [eax+4], 0x9090
mov dword ptr [eax],   0x90909090        ->  90 90 90 90 90 90
```

Traduzindo:

| | bytes | instrução x86 |
|---|---|---|
| padrão A | `89 8F A8 10 00 00` | `mov dword ptr [edi+0x10A8], ecx` |
| padrão B | `89 BE A8 10 00 00` | `mov dword ptr [esi+0x10A8], edi` |
| escreve | `90 90 90 90 90 90` | seis `nop` |

## Onde eles caem no `client.exe`

Conferido byte a byte no arquivo em disco (13.127.680 bytes,
`C:\Program Files (x86)\TalismanOnline\client.exe`). **Cada padrão aparece
exatamente uma vez:**

| padrão | offset no arquivo | RVA | VA |
|---|---|---|---|
| A | 0x5CFA0B | 0x5CFA0B | **0x009CFA0B** |
| B | 0x057A02 | 0x057A02 | **0x00457A02** |

O `client.exe` **não tem ASLR** (`DllCharacteristics = 0x0000`), então esses VAs
valem em toda máquina e em todo cliente aberto.

### O que o jogo faz nesses dois pontos

**Sítio A** (0x009CFA0B) — no meio de uma rotina que copia campos de um objeto
para outro:

```asm
mov ecx, [edi+0x24C]
mov [esi+0x24C], ecx
mov edx, [edi+0x250]
mov ecx, [esi+8]
mov [esi+0x250], edx
mov eax, [edi+0x254]
mov [esi+0x254], eax
mov [edi+0x10A8], ecx      ; <<< grava no objeto de ORIGEM algo lido do destino
mov edx, [esi]
call [edx+0x11C]
```

**Sítio B** (0x00457A02) — no fim de um método (`ret 4`), e `edi` foi zerado
antes:

```asm
xor edi, edi               ; edi = 0
...
call 0xA00EB0
mov [esi+0x10A8], edi      ; <<< ZERA o campo
pop edi
pop esi
add esp, 0x10
ret 4
```

Ou seja: **`+0x10A8` é um vínculo que o cliente grava num lugar e limpa no
outro**, e o patch faz o cliente parar de mexer nele nos dois.

### O que `+0x10A8` É: o campo do SMALL PET no personagem

Três evidências, e as três apontam para o mesmo lugar.

**1. O nome, dado pelo próprio jogo.** No sítio B, logo antes de zerar o campo,
há um `push 0x105DC20`. Esse endereço é um global de runtime (BSS: não existe no
arquivo, só com o jogo aberto), e lido em memória viva ele aponta para a string
**`user_small_pet_changed`**. Está na tabela de eventos do cliente, ao lado de
`user_small_pet_read`, `s2c_small_pet_changed`, `msg_small_pet_attr` e
`small_pet.csv` — o vocabulário do jogo para o pet de companhia.

**2. O assembly.** O sítio B está dentro do handler que dispara esse evento e
termina com `mov [esi+0x10A8], edi` com `edi = 0`: **zera o small pet do
personagem**. O sítio A está numa rotina que copia campos de um objeto para
outro e faz `mov [edi+0x10A8], ecx` com `ecx = [esi+8]`: **grava o small pet**.
Um escreve, o outro limpa — e o patch NOPa os dois.

**3. O que se vê na tela**, descrito pelo usuário:

> *"O petbug faz os pets bugarem pelo mapa, eles travam em posições, pois o pet
> sempre segue o dono, mas depois de ativar o petbug todos os pets de outros
> personagens ficam em lugares aleatórios parados, inclusive muitos deles em
> Stone (...) vários pets parados sem seus donos."*

Com o campo nunca escrito, o cliente não associa o small pet ao personagem: o
pet fica sem dono a quem seguir e para onde estava. É literalmente o "pet bug"
do nome do programa.

**A PISTA DO TERCEIRO ENCAIXA.** O usuário ouviu de quem já resolveu isso que a
causa é *"erro de textura no pet"*. Bate: o estrago original acontece quando o
cliente carrega o asset de um small pet defeituoso. Não atribuindo o pet ao
personagem, o cliente **nunca carrega aquele asset** — e o erro não tem como
acontecer. O programa não conserta a textura; ele impede o cliente de chegar
nela. É um contorno, e é por isso que o efeito colateral visível são pets
parados pelo mapa.

**É LOCAL.** A escrita é na memória do NOSSO cliente, então quem vê os pets
parados é só ele; para os donos, nada mudou.

**E É POR ISSO QUE IMPORTA PARA O BOT.** Além de evitar a queda, ele limpa o
caminho: o F12 esconde JOGADORES, não os pets deles — e pet parado na frente do
Skull Herald bloqueia o clique direito igual a um jogador. Sem o patch, os pets
seguem os donos e se acumulam exatamente onde todo mundo vai. As duas metades do
programa resolvem estorvos diferentes, e faltar uma já estraga a entrada.

## A descoberta lateral que vale por si: o F12

O patcher manda **`PostMessage(hwnd, WM_KEYDOWN, VK_F12, 0)` sem o `WM_KEYUP`**.

Isso não é descuido — é o truque inteiro. A tecla de esconder jogadores esconde
**enquanto está apertada** (ver `core/esconder_jogadores.py`, que resolvia o
mesmo problema prendendo a tecla e abrindo o chat). Um KEYDOWN que nunca recebe
KEYUP deixa o cliente achando que ela continua pressionada: os jogadores somem e
ficam sumidos, sem o truque do chat e sem o risco de o chat ficar aberto.

E responde uma pergunta que o conserto de hoje de manhã deixou no ar:
**reaplicar o patch é seguro, não alterna.** Um segundo KEYDOWN com a tecla
logicamente presa é auto-repetição, não uma borda nova. Só um KEYUP desfaria.

## O que foi trazido para dentro do bot

`blazesbot/core/patch_do_cliente.py` — o patch de memória, nativo, com quatro
diferenças deliberadas em relação ao original:

1. **Exige ocorrência única.** O patcher pega a primeira e segue. Aqui, zero ou
   mais de uma RECUSA o sítio e grita. Seis bytes NOPados no lugar errado
   derrubam o cliente, e "o jogo atualizou" é exatamente quando o padrão deixa
   de ser único.
2. **Confere depois de escrever**, relendo os seis bytes.
3. **É idempotente e diz isso** — sítio já com NOPs responde "já estava".
4. **Olha o sítio CONHECIDO primeiro**, e usa a busca como reserva. O RVA é
   constante medida (sem ASLR ele não muda), e os bytes são conferidos antes de
   escrever -- é a conferência que torna o atalho seguro. Ver
   "a conferência derrubou uma suposição" mais abaixo: a ordem inversa fazia
   um cliente já patcheado parecer um cliente atualizado.

**O F12 continua sendo do programa.** Só o patch de memória subiu.

### Ele roda JUNTO com o `.exe`, não no lugar dele

Regra da casa para mecanismo novo: mede-se contra a fonte antiga no mesmo
instante, e a antiga vira reserva em vez de sair. Como o patch é idempotente,
quem chegar depois lê "já estava" — e é essa linha no log que vai dizer se o
nativo pode assumir sozinho:

```
PET BUG: padrão 'guardar' (mov dword ptr [edi+0x10A8], ecx) encontrado em rva 0x5CFA0B.
PET BUG: guardar NOPado em 0x9CFA0B (era `mov dword ptr [edi+0x10A8], ecx`).
PET BUG (nativo): 2 sítio(s) patcheado(s) agora
```

Se aparecer `2 já estava(m)`, o `.exe` chegou primeiro — e os dois concordam.
Se aparecer `RECUSADO`, o nativo achou algo diferente do esperado e **não
escreveu**; nesse caso o `.exe` é quem está patchando, e há o que investigar.

### Só BC e HH — nunca APP

Decisão do usuário no mesmo dia: *"vamos executar apenas nos que tiverem
executando cave, HH e BC. Os APP não precisa aplicar."*

Já era o portão que existia: a chamada mora atrás de `if self.account.farms:`, e
`farms` é exatamente `bc_farm or hh_farm`. Conta de APP puro responde `False` e
fica de fora sozinha. Travado por `tests/test_patch_do_cliente.py`, porque
mover a chamada para fora daquele `if` passaria despercebido.

## CONFERIDO EM MEMÓRIA VIVA — 07/09/2026, seis clientes

O usuário rodou o patcher como administrador e pediu a conferência. Com o shell
elevado (o `OpenProcess` de antes falhava por causa do MEU processo, não do
patcher), a leitura dos seis `client.exe` abertos deu isto, **igual em todos**:

```
6 cliente(s): 75820, 65504, 8512, 26996, 37572, 34072
base 0x00400000        -> o ASLR não moveu nada, em nenhum
imagem 15.835.136 bytes, lida em ~7 ms
guardar  rva 0x5CFA0B  PATCHEADO (6 NOPs)
limpar   rva 0x057A02  PATCHEADO (6 NOPs)
padrão original ainda na imagem: 0x
sequências de 6 NOPs na imagem inteira: 2x
```

**As duas últimas linhas são o fecho da conta.** O padrão sumiu (era único e foi
patcheado) e existem **exatamente duas** sequências de seis NOPs em 15,8 MB de
imagem: os nossos dois sítios, e mais nada. Os endereços deduzidos do arquivo em
disco batem com a memória, byte a byte, nos seis processos.

*(15.835.136 é o tamanho VIRTUAL do módulo; o arquivo em disco tem 13.127.680.
A diferença é alinhamento de seção, e o `.text` mapeia RVA = offset, que é por
isso que os dois endereços coincidem nas duas medições.)*

### E a conferência derrubou uma suposição do nosso código

A primeira versão do patch nativo **procurava o padrão primeiro**. Só que em
produção o `.exe` roda no login, então quando o nativo chega **o padrão original
já não está lá** — a busca achava ZERO e o código concluía *"o cliente pode ter
sido atualizado"*. Alarme falso a cada sessão, e no melhor caso ruído no log.

A ordem foi invertida: **olha-se o sítio conhecido primeiro** (o RVA agora é uma
constante medida, não uma suposição), e a busca ficou como reserva para quando
o que está lá não é nem o padrão nem os NOPs. Três desfechos, todos travados por
teste:

| o que está no sítio | o que acontece |
|---|---|
| os seis NOPs | "já estava" — não escreve, não varre |
| o padrão original | patcheia e confere a releitura |
| outra coisa | varre a imagem; único candidato → patcheia e AVISA que o sítio mudou de lugar; zero ou dois → RECUSA |

## O que falta, se um dia interessar

- **Descobrir o que é `+0x10A8`.** Precisa do jogo rodando: achar o objeto que
  chega em `esi`/`edi` nesses dois sítios e acompanhar o campo. Daria o nome
  certo para o mecanismo, hoje herdado do autor do programa.
- **Trazer o F12.** É uma linha (`PostMessage(hwnd, 0x100, 0x7B, 0)`), e aí o
  `.exe` sai de cena. Não foi feito hoje porque o KEYDOWN sem KEYUP mexe com o
  estado de tecla do cliente, e isso merece ser ligado com o usuário olhando.
- **Ver o nativo patchar um cliente LIMPO.** A conferência de hoje pegou os
  clientes já patcheados pelo `.exe`, então o que ficou provado é que os
  endereços estão certos e que o nativo os reconhece. Falta o log de uma sessão
  em que ele chegue primeiro -- `PET BUG: guardar NOPado em 0x9CFA0B`.
