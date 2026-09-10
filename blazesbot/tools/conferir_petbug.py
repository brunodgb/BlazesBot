"""O pet bug está aplicado NESTE instante? Pergunta ao cliente, não ao log.

=========================================================================
POR QUE ISTO EXISTE
=========================================================================

O patch nativo (`core/patch_do_cliente.py`) escreve seis NOPs em dois sítios do
`client.exe` e loga o que fez. Mas o log tem 500 linhas e gira, o efeito no jogo
é indireto ("pets parados espalhados") e a aplicação é condicional -- só em
conta com farm de cave ligado. Juntando as três coisas, "não estou vendo o
petbug funcionar" não tinha resposta objetiva.

Esta ferramenta LÊ os dois sítios em cada `client.exe` aberto e diz o que está
lá agora: os NOPs, a instrução original, ou outra coisa.

=========================================================================
SÓ LÊ. NUNCA ESCREVE.
=========================================================================

Abre cada processo com `PROCESS_QUERY_INFORMATION | PROCESS_VM_READ` -- não pede
escrita nem sabe escrever. Quem aplica o patch é o supervisor, no login; aqui só
se confere. Rodar isto com o bot no meio de um farm é seguro.

Uso:

    python -m blazesbot.tools.conferir_petbug
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w

from ..core.patch_do_cliente import (
    _MODULEENTRY32,
    ASSINATURAS,
    NOME_DO_MODULO,
    SUBSTITUICAO,
    TH32CS_SNAPMODULE,
    TH32CS_SNAPMODULE32,
)

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


class _PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", w.DWORD), ("cntThreads", w.DWORD),
        ("th32ParentProcessID", w.DWORD), ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", w.DWORD), ("szExeFile", ctypes.c_char * 260),
    ]


def clientes_abertos() -> list[int]:
    """PIDs de todo `client.exe` rodando agora."""
    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap in (0, -1, 0xFFFFFFFF):
        return []
    pids: list[int] = []
    try:
        pe = _PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(_PROCESSENTRY32)
        ok = k32.Process32First(snap, ctypes.byref(pe))
        while ok:
            if pe.szExeFile.lower() == NOME_DO_MODULO.encode():
                pids.append(int(pe.th32ProcessID))
            ok = k32.Process32Next(snap, ctypes.byref(pe))
    finally:
        k32.CloseHandle(snap)
    return pids


def _base_do_modulo(pid: int) -> int | None:
    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(
        TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap in (0, -1, 0xFFFFFFFF):
        return None
    try:
        me = _MODULEENTRY32()
        me.dwSize = ctypes.sizeof(_MODULEENTRY32)
        ok = k32.Module32First(snap, ctypes.byref(me))
        while ok:
            if me.szModule.lower() == NOME_DO_MODULO.encode():
                return int(ctypes.cast(
                    me.modBaseAddr, ctypes.c_void_p).value or 0)
            ok = k32.Module32Next(snap, ctypes.byref(me))
    finally:
        k32.CloseHandle(snap)
    return None


def conferir(pid: int) -> dict[str, str]:
    """O que está em cada sítio deste cliente. Só leitura."""
    k32 = ctypes.windll.kernel32
    handle = k32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        return {"__erro__": "não consegui abrir o processo para LER "
                            "(rode como administrador)"}
    try:
        base = _base_do_modulo(pid)
        if not base:
            return {"__erro__": f"não achei o módulo {NOME_DO_MODULO}"}
        saida: dict[str, str] = {"__base__": f"0x{base:X}"}
        for assinatura in ASSINATURAS:
            endereco = base + assinatura.rva
            buf = ctypes.create_string_buffer(len(SUBSTITUICAO))
            lidos = ctypes.c_size_t(0)
            ok = k32.ReadProcessMemory(handle, ctypes.c_void_p(endereco), buf,
                                       len(SUBSTITUICAO), ctypes.byref(lidos))
            bytes_lidos = buf.raw[:lidos.value] if ok else b""
            if bytes_lidos == SUBSTITUICAO:
                estado = "PATCHEADO (6 NOPs)"
            elif bytes_lidos == assinatura.bytes_:
                estado = f"ORIGINAL (`{assinatura.instrucao}`) — patch NÃO foi aplicado"
            elif not bytes_lidos:
                estado = "não consegui ler"
            else:
                estado = (f"OUTRA COISA: {bytes_lidos.hex(' ')} — o cliente "
                          "pode ter sido atualizado")
            saida[assinatura.nome] = f"0x{endereco:X}  {estado}"
        return saida
    finally:
        k32.CloseHandle(handle)


def _escolher(pids: list[int]) -> list[int]:
    """Qual cliente conferir. Devolve a lista a olhar.

    O PID SOZINHO NÃO DIZ QUAL CONTA É -- todos os processos se chamam
    `client.exe`. Por isso a lista traz o título da janela
    (`core/janelas.titulo_do_pid`), que é o nome do personagem logado.

    Enter confere TODOS: quem só quer o retrato geral não precisa escolher nada.
    """
    from ..core.janelas import titulo_do_pid

    print("Clientes abertos:\n")
    for i, pid in enumerate(pids, start=1):
        print(f"   [{i}]  PID {pid:<8} {titulo_do_pid(pid)}")
    print()
    try:
        resposta = input("Número da lista, PID, ou Enter para TODOS: ").strip()
    except EOFError:
        return pids
    if not resposta:
        return pids
    if resposta.isdigit():
        numero = int(resposta)
        if 1 <= numero <= len(pids):
            return [pids[numero - 1]]
        if numero in pids:
            return [numero]
    print(f"\n{resposta!r} não é um número da lista nem um PID aberto; "
          "conferindo TODOS.")
    return pids


def main(argv: list[str] | None = None) -> int:
    import sys

    argv = sys.argv[1:] if argv is None else argv
    pids = clientes_abertos()
    if not pids:
        print("Nenhum client.exe aberto.")
        return 1

    # `--pid N` pula a pergunta -- para quem chama isto de um script.
    if "--pid" in argv:
        escolhido = int(argv[argv.index("--pid") + 1])
        pids = [escolhido] if escolhido in pids else pids
    elif len(pids) > 1:
        pids = _escolher(pids)

    print(f"\nConferindo {len(pids)} cliente(s).\n")
    # "NÃO PUDE LER" e "LI E NÃO ESTÁ LÁ" são coisas diferentes, e misturá-las
    # daria a resposta errada para a pergunta que traz alguém aqui.
    sem_leitura = 0
    sem_patch = 0
    from ..core.janelas import titulo_do_pid

    for pid in pids:
        print(f"PID {pid}   {titulo_do_pid(pid)}")
        leitura = conferir(pid)
        if "__erro__" in leitura:
            print(f"   {leitura['__erro__']}")
            sem_leitura += 1
            continue
        for nome, texto in leitura.items():
            if nome.startswith("__"):
                continue
            print(f"   {nome:8s} {texto}")
            if "PATCHEADO" not in texto:
                sem_patch += 1
        print()
    if sem_leitura:
        print(f"{sem_leitura} cliente(s) não pude LER — sem isso não há "
              "resposta. Rode este conferidor como ADMINISTRADOR, do mesmo "
              "jeito que o bot roda.")
    if sem_patch:
        print("Sítio(s) SEM o patch. Ele é aplicado no LOGIN e só em conta com "
              "farm de cave (BC ou HH) ligado — conta em modo APP não recebe, "
              "por decisão do usuário.")
    if not sem_leitura and not sem_patch:
        print("Todos os sítios estão com os NOPs: o pet bug está ativo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
