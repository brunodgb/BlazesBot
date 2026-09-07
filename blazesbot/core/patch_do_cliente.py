"""O PET BUG, NATIVO -- o que o `BlazesBot - PetBug.exe` faz, feito aqui.

=========================================================================
DE ONDE VEIO: engenharia reversa do patcher, 07/09/2026
=========================================================================

O usuário pediu: *"é possível ao executar o 'BlazesBot - PetBug.exe' entender o
que ele faz por trás? (...) fazer um trabalho reverso nesse cara para a gente
entender e aplicar dentro do nosso sistema"*.

O programa é um Delphi/C++Builder de 32 bits (RAD Studio 29.1). O botão `Patch`
é `TfrmMain::btnPatchClick`, em `0x00404100`, e faz exatamente três coisas:

    1. CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS) e procura "client.exe";
    2. para cada PID achado, chama a rotina de patch (`0x00403ca4`);
    3. escreve no memo "[OK] Patch applied to all running clients.".

A rotina por processo (`0x00403ca4`):

    OpenProcess(0x1FFFFF)                    -- PROCESS_ALL_ACCESS
    CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid)
    Module32FirstW/NextW  -> acha "client.exe", pega base e tamanho
    ReadProcessMemory(base, tamanho)         -- lê o módulo INTEIRO
    procura o padrão A; achou -> VirtualProtectEx(PAGE_EXECUTE_READWRITE)
                                 WriteProcessMemory(90 90 90 90 90 90)
                                 VirtualProtectEx(proteção antiga)
    idem para o padrão B
    EnumWindows -> acha a janela daquele PID
    PostMessage(hwnd, WM_KEYDOWN, VK_F12, 0)

=========================================================================
OS DOIS PADRÕES, E O QUE ELES SÃO NO JOGO
=========================================================================

Os bytes saem do inicializador estático do programa (`0x004037fa` em diante),
onde três `std::vector<uint8_t>` de 6 bytes são montados na mão:

    padrão A      89 8F A8 10 00 00   =  mov dword ptr [edi+0x10A8], ecx
    padrão B      89 BE A8 10 00 00   =  mov dword ptr [esi+0x10A8], edi
    substituição  90 90 90 90 90 90   =  seis NOPs

**Cada padrão aparece UMA vez** no `client.exe` desta instalação (13.127.680
bytes) -- conferido byte a byte no arquivo em disco:

    A  ->  arquivo 0x5CFA0B   rva 0x5CFA0B   va 0x009CFA0B
    B  ->  arquivo 0x057A02   rva 0x057A02   va 0x00457A02

E o contexto diz o que o campo `+0x10A8` é. No sítio A, dentro de uma rotina que
COPIA campos de um objeto para outro:

    mov ecx, [esi+8]
    mov [edi+0x10A8], ecx        <-- guarda no objeto de origem quem é o dono

No sítio B, no fim de um método (`ret 4`), com `edi` zerado logo antes
(`xor edi, edi`):

    mov [esi+0x10A8], edi        <-- ZERA o campo

`+0x10A8` É O CAMPO DO SMALL PET no personagem -- e quem deu o nome foi o
próprio jogo. No sítio B, antes de zerar o campo, há um `push 0x105DC20`; esse
global aponta (em memória viva) para a string **`user_small_pet_changed`**, que
está na tabela de eventos do cliente ao lado de `user_small_pet_read`,
`s2c_small_pet_changed` e `small_pet.csv`.

Então: o sítio A GRAVA o small pet do personagem, o sítio B ZERA, e o patch
NOPa os dois. O cliente deixa de associar o pet ao dono -- e é isso que o
usuário vê: *"todos os pets de outros personagens ficam em lugares aleatórios
parados (...) vários pets parados sem seus donos"*.

A PISTA DE QUEM JÁ RESOLVEU ISSO -- *"erro de textura no pet"* -- encaixa: o
estrago original vem de carregar o asset de um pet defeituoso, e sem a
associação o cliente nunca chega nele. O programa não conserta a textura;
impede o cliente de alcançá-la.

**É LOCAL:** a escrita é na memória do NOSSO cliente, então quem vê os pets
parados é só ele.

**E É POR ISSO QUE IMPORTA AQUI:** além de evitar a queda, limpa o caminho. O
F12 esconde JOGADORES, não os pets deles -- e pet parado na frente do Skull
Herald bloqueia o clique direito igual a um jogador.

=========================================================================
O F12 NÃO ESTÁ AQUI -- e o motivo é uma descoberta à parte
=========================================================================

O patcher manda `PostMessage(WM_KEYDOWN, VK_F12)` **sem o WM_KEYUP**. Não é
descuido: a tecla de esconder jogadores esconde ENQUANTO ESTÁ APERTADA (ver
`core/esconder_jogadores.py`), então um KEYDOWN sem KEYUP deixa o cliente
achando que ela nunca foi solta -- e os jogadores somem para sempre, sem o
truque do chat.

Isso também responde por que reaplicar o patch é seguro: **não alterna**. Um
segundo KEYDOWN com a tecla logicamente presa é auto-repetição, não uma nova
borda. Só um KEYUP desfaria.

=========================================================================
O QUE ESTA IMPLEMENTAÇÃO FAZ DIFERENTE, E POR QUÊ
=========================================================================

1. **EXIGE OCORRÊNCIA ÚNICA.** O patcher pega a primeira e segue. Aqui, achar
   zero OU mais de uma RECUSA o sítio e grita. NOPar seis bytes no lugar errado
   derruba o cliente, e "o jogo atualizou" é justamente quando o padrão deixa
   de ser único.
2. **CONFERE DEPOIS DE ESCREVER**, relendo os seis bytes. A regra da casa: a
   cada ação, conferir o efeito.
3. **É IDEMPOTENTE E DIZ ISSO.** Sítio que já está com NOPs devolve
   "já estava" em vez de escrever de novo.
4. **NÃO ESCANEIA O MÓDULO INTEIRO TODA VEZ.** O `client.exe` não tem ASLR
   (`DllCharacteristics = 0x0000`), então o endereço é o mesmo em toda máquina e
   em todo cliente. A primeira busca guarda o RVA e as seguintes vão direto --
   conferindo os bytes antes de escrever, que é o que torna o atalho seguro.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as w
from dataclasses import dataclass, field

__all__ = ["ASSINATURAS", "ATIVADO", "SUBSTITUICAO", "Resultado", "aplicar"]

# ===========================================================================
# INTERRUPTOR
# ===========================================================================
#
# `False` = ninguém escreve em memória de cliente nenhum, e quem chama recebe
#           um resultado dizendo isso.
#
# Ele existe porque isto ESCREVE NO CÓDIGO do jogo. Todo o resto do bot lê
# memória; aqui se altera instrução, e um engano derruba o cliente. Desligar tem
# de ser mais rápido que entender.
ATIVADO = True

NOME_DO_MODULO = "client.exe"

# Seis NOPs -- os mesmos bytes que o patcher escreve.
SUBSTITUICAO = b"\x90" * 6


@dataclass(frozen=True, slots=True)
class Assinatura:
    nome: str
    bytes_: bytes
    instrucao: str
    # RVA MEDIDO, não suposto -- ver `O SÍTIO É CONHECIDO` abaixo.
    rva: int


# ===========================================================================
# O SÍTIO É CONHECIDO -- medido em memória viva, 07/09/2026
# ===========================================================================
#
# Conferido nos SEIS clientes abertos da máquina do usuário, com o patcher já
# aplicado, lendo a imagem do módulo de cada processo:
#
#     6 cliente(s): base 0x00400000 em todos (o ASLR não moveu nada)
#     guardar  rva 0x5CFA0B  PATCHEADO (6 NOPs)   em todos
#     limpar   rva 0x057A02  PATCHEADO (6 NOPs)   em todos
#     padrão original ainda na imagem: 0x         em todos
#     sequências de 6 NOPs na imagem inteira: 2x  em todos
#
# As duas últimas linhas são o que dá confiança: o padrão sumiu (era único e
# foi patcheado) e existem EXATAMENTE DUAS sequências de seis NOPs em 15,8 MB
# de imagem -- os nossos dois sítios, e mais nada.
#
# POR QUE O RVA PRECISOU VIRAR CONSTANTE: sem ele, um cliente JÁ PATCHEADO (o
# caso normal, porque o `.exe` roda no login) fazia a busca encontrar ZERO
# ocorrências do padrão -- e a recusa dizia "o cliente pode ter sido
# atualizado", que é falso. Com o RVA, olha-se o sítio primeiro; a busca ficou
# para quando o que está lá não é nem o padrão nem os NOPs.
ASSINATURAS = (
    Assinatura("guardar", bytes.fromhex("898fa8100000"),
               "mov dword ptr [edi+0x10A8], ecx", 0x5CFA0B),
    Assinatura("limpar", bytes.fromhex("89bea8100000"),
               "mov dword ptr [esi+0x10A8], edi", 0x057A02),
)


@dataclass
class Resultado:
    aplicou: int = 0            # sítios escritos AGORA
    ja_estavam: int = 0         # sítios que já tinham os NOPs
    recusados: list[str] = field(default_factory=list)
    erro: str | None = None

    @property
    def ok(self) -> bool:
        """Todos os sítios estão com os NOPs -- escritos agora ou antes."""
        return (self.erro is None and not self.recusados
                and (self.aplicou + self.ja_estavam) == len(ASSINATURAS))

    def __str__(self) -> str:
        if self.erro:
            return self.erro
        partes = []
        if self.aplicou:
            partes.append(f"{self.aplicou} sítio(s) patcheado(s) agora")
        if self.ja_estavam:
            partes.append(f"{self.ja_estavam} já estava(m)")
        for r in self.recusados:
            partes.append(f"RECUSADO: {r}")
        return "; ".join(partes) or "nada a fazer"


# ===========================================================================
# As peças Win32 -- isoladas para o teste poder substituí-las
# ===========================================================================

TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
PROCESS_ALL_ACCESS = 0x1FFFFF
PAGE_EXECUTE_READWRITE = 0x40


class _MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", w.DWORD), ("th32ModuleID", w.DWORD),
        ("th32ProcessID", w.DWORD), ("GlblcntUsage", w.DWORD),
        ("ProccntUsage", w.DWORD),
        ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
        ("modBaseSize", w.DWORD), ("hModule", w.HMODULE),
        ("szModule", ctypes.c_char * 256), ("szExePath", ctypes.c_char * 260),
    ]


class _Win32:
    """As peças de verdade. Substituída por um dublê nos testes."""

    def __init__(self) -> None:
        self.k32 = ctypes.windll.kernel32

    def abrir(self, pid: int) -> int:
        return self.k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)

    def fechar(self, handle: int) -> None:
        self.k32.CloseHandle(handle)

    def modulo(self, pid: int) -> tuple[int, int] | None:
        """(base, tamanho) do `client.exe` naquele processo."""
        snap = self.k32.CreateToolhelp32Snapshot(
            TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
        if snap in (0, -1, 0xFFFFFFFF):
            return None
        try:
            me = _MODULEENTRY32()
            me.dwSize = ctypes.sizeof(_MODULEENTRY32)
            ok = self.k32.Module32First(snap, ctypes.byref(me))
            while ok:
                if me.szModule.lower() == NOME_DO_MODULO.encode():
                    base = ctypes.cast(me.modBaseAddr, ctypes.c_void_p).value
                    return int(base or 0), int(me.modBaseSize)
                ok = self.k32.Module32Next(snap, ctypes.byref(me))
        finally:
            self.k32.CloseHandle(snap)
        return None

    def ler(self, handle: int, endereco: int, tamanho: int) -> bytes | None:
        buf = ctypes.create_string_buffer(tamanho)
        lidos = ctypes.c_size_t(0)
        ok = self.k32.ReadProcessMemory(handle, ctypes.c_void_p(endereco), buf,
                                        tamanho, ctypes.byref(lidos))
        return buf.raw[:lidos.value] if ok else None

    def proteger(self, handle: int, endereco: int, tamanho: int,
                 protecao: int) -> int | None:
        antiga = w.DWORD(0)
        ok = self.k32.VirtualProtectEx(handle, ctypes.c_void_p(endereco),
                                       tamanho, protecao, ctypes.byref(antiga))
        return antiga.value if ok else None

    def escrever(self, handle: int, endereco: int, dados: bytes) -> bool:
        escritos = ctypes.c_size_t(0)
        ok = self.k32.WriteProcessMemory(handle, ctypes.c_void_p(endereco),
                                         dados, len(dados),
                                         ctypes.byref(escritos))
        return bool(ok) and escritos.value == len(dados)


# RVA aprendido na primeira busca. Ver o item 4 do cabeçalho: sem ASLR, o mesmo
# valor serve para todo cliente desta máquina -- e os bytes são conferidos antes
# de escrever, então o atalho não pode patchear o lugar errado.
_RVA_CONHECIDO: dict[str, int] = {}


def esquecer_o_que_aprendeu() -> None:
    """Descarta os RVAs guardados. Para teste e para depois de atualizar o jogo."""
    _RVA_CONHECIDO.clear()


def _achar_rva(imagem: bytes, assinatura: Assinatura) -> int | list[int]:
    """RVA do sítio, ou a LISTA de candidatos quando não é único."""
    achados = []
    inicio = 0
    while True:
        i = imagem.find(assinatura.bytes_, inicio)
        if i < 0:
            break
        achados.append(i)
        inicio = i + 1
    return achados[0] if len(achados) == 1 else achados


def aplicar(pid: int, log, pecas=None) -> Resultado:
    """Aplica os dois patches no `client.exe` do processo `pid`.

    NUNCA LEVANTA: devolve `Resultado` com o motivo. Quem chama está no meio de
    um farm, e um patcher que derruba a sessão é pior que um patch que faltou.
    """
    if not ATIVADO:
        return Resultado(erro="pet bug DESLIGADO (patch_do_cliente.ATIVADO)")

    j = pecas if pecas is not None else _Win32()
    handle = j.abrir(pid)
    if not handle:
        return Resultado(erro=f"sem permissão para abrir o PID {pid} "
                              "(o bot precisa rodar como administrador)")
    try:
        mod = j.modulo(pid)
        if mod is None:
            return Resultado(erro=f"não achei o módulo {NOME_DO_MODULO} "
                                  f"no PID {pid}")
        base, tamanho = mod
        return _patchar(j, handle, base, tamanho, log)
    finally:
        j.fechar(handle)


def _patchar(j, handle: int, base: int, tamanho: int, log) -> Resultado:
    """OLHA O SÍTIO CONHECIDO PRIMEIRO; a busca é a reserva.

    A ordem importa e foi corrigida em 07/09/2026, depois da conferência em
    memória viva: buscar primeiro fazia um cliente JÁ PATCHEADO parecer um
    cliente atualizado, porque o padrão original não está mais lá.
    """
    resultado = Resultado()
    imagem: bytes | None = None

    for assinatura in ASSINATURAS:
        rva = _RVA_CONHECIDO.get(assinatura.nome, assinatura.rva)
        endereco = base + rva
        atual = j.ler(handle, endereco, len(SUBSTITUICAO))

        if atual == SUBSTITUICAO:
            resultado.ja_estavam += 1
            continue

        if atual != assinatura.bytes_:
            # O SÍTIO CONHECIDO NÃO TEM NEM O PADRÃO NEM OS NOPs. Aí sim vale
            # procurar: ou o cliente foi atualizado e o código andou, ou a
            # leitura veio errada. Escrever no escuro está fora de questão.
            if imagem is None:
                imagem = j.ler(handle, base, tamanho)
                if imagem is None:
                    return Resultado(erro="não consegui ler o módulo do "
                                          "cliente para procurar os padrões")
            achado = _achar_rva(imagem, assinatura)
            if isinstance(achado, list):
                # ZERO OU MAIS DE UM: os dois são recusa, e pelo mesmo motivo.
                # Com zero não há o que patchear; com dois, não se sabe qual --
                # e NOPar o errado derruba o cliente.
                resultado.recusados.append(
                    f"{assinatura.nome}: em 0x{endereco:X} li "
                    f"{atual.hex(' ') if atual else '<nada>'} e o padrão "
                    f"{assinatura.bytes_.hex(' ')} aparece {len(achado)} "
                    "vez(es) na imagem (esperava exatamente 1). O cliente "
                    "pode ter sido atualizado.")
                log.warning(
                    "PET BUG: o sítio %r não tem o padrão nem os NOPs, e a "
                    "busca achou %d candidato(s) — NÃO vou escrever. Seis "
                    "bytes no lugar errado derrubam o cliente.",
                    assinatura.nome, len(achado))
                continue
            rva = achado
            _RVA_CONHECIDO[assinatura.nome] = rva
            endereco = base + rva
            log.warning(
                "PET BUG: o sítio %r saiu do lugar conhecido (0x%X) e foi "
                "achado em rva 0x%X. O cliente provavelmente foi atualizado — "
                "vale conferir `docs/decisoes/pet-bug-engenharia-reversa.md`.",
                assinatura.nome, assinatura.rva, rva)

        antiga = j.proteger(handle, endereco, len(SUBSTITUICAO),
                            PAGE_EXECUTE_READWRITE)
        if antiga is None:
            resultado.recusados.append(
                f"{assinatura.nome}: VirtualProtectEx recusou 0x{endereco:X}")
            continue
        try:
            if not j.escrever(handle, endereco, SUBSTITUICAO):
                resultado.recusados.append(
                    f"{assinatura.nome}: a escrita em 0x{endereco:X} falhou")
                continue
            # CONFERE O EFEITO -- regra da casa. Escrita que "deu certo" sem
            # releitura é a classe de defeito que este projeto persegue.
            conferido = j.ler(handle, endereco, len(SUBSTITUICAO))
            if conferido != SUBSTITUICAO:
                resultado.recusados.append(
                    f"{assinatura.nome}: escrevi e a releitura trouxe "
                    f"{conferido.hex(' ') if conferido else '<nada>'}")
                continue
            resultado.aplicou += 1
            log.info("PET BUG: %s NOPado em 0x%X (era `%s`).",
                     assinatura.nome, endereco, assinatura.instrucao)
        finally:
            j.proteger(handle, endereco, len(SUBSTITUICAO), antiga)

    return resultado
