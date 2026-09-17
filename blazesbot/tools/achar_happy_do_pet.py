"""Procura a FELICIDADE DO PET na memória -- e uma cadeia que sobreviva a relogin.

=========================================================================
O PROBLEMA, E POR QUE UM ENDEREÇO SOLTO NÃO RESOLVE
=========================================================================

O usuário achou `0x2DC83FDC` no cliente da `creubo` em 16/09/2026, com a
felicidade do pet (98). O próprio relato já traz o diagnóstico: *"não parece ser
um ponteiro fixo e confiável"*. E não é mesmo -- `0x2DC8xxxx` é HEAP: endereço
que o alocador escolhe na hora, diferente a cada login e a cada pet invocado.

O que serve para o bot é uma CADEIA: um endereço ESTÁTICO dentro do
`client.exe` (que não muda porque o módulo não tem ASLR -- ver
`core/patch_do_cliente.py`) mais uma sequência de deslocamentos até o campo.
É o que `Memory.resolve` sabe percorrer, e é assim que todo o resto do bot lê o
jogo (`CHAIN_LOCATION`, `CHAIN_BAG_1`, ...).

=========================================================================
COMO A BUSCA FUNCIONA -- DA MAIS BARATA PARA A MAIS CARA
=========================================================================

1. **PELO OBJETO DO PERSONAGEM.** O pet é do personagem, e no Talisman quase
   tudo pendura no objeto do jogador. Então: `[PLAYER_BASE]` -> cada campo que
   parece ponteiro -> dentro do objeto apontado, procura o valor da felicidade.
   São dois níveis e um espaço de busca minúsculo. É a primeira tentativa.

2. **VARREDURA DO HEAP.** Não achando, procura o VALOR em toda a memória
   gravável e, para cada acerto, quem aponta para o objeto que o contém.

=========================================================================
O QUE TORNA O RESULTADO CONFIÁVEL: TRÊS CONTAS, TRÊS VALORES
=========================================================================

Felicidade é um número de 0 a 100 -- varrer por "98" acha milhares de lugares.
O que separa o campo certo do acaso é **validar a MESMA cadeia em contas
diferentes com valores diferentes**. Em 16/09/2026 o usuário mediu três:

    BlazesOfGamer (creubo) ... 98
    WizzOfBlazes5 ............ 87
    BlazesAPP1 ............... 89

Uma cadeia que devolva exatamente esses três números nos três clientes não é
coincidência. Uma que acerte um só, é.

=========================================================================
SÓ LÊ. NUNCA ESCREVE.
=========================================================================

Abre os processos com `PROCESS_QUERY_INFORMATION | PROCESS_VM_READ`. Não pede
escrita, não sabe escrever, e pode rodar com o bot farmando.

Uso (COMO ADMINISTRADOR -- ver `20-ACHAR-HAPPY-DO-PET.bat`):

    python -m blazesbot.tools.achar_happy_do_pet BlazesOfGamer=98 WizzOfBlazes5=87
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import json
import struct
import sys
import time
from pathlib import Path

from ..core.janelas import titulo_do_pid
from ..core.memory import IMAGE_BASE, OFF_NAME, PLAYER_BASE
from ..tools.conferir_petbug import clientes_abertos

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GRAVAVEL = (0x04, 0x08, 0x40, 0x80)   # READWRITE, WRITECOPY, EXECUTE_*

# Até onde procurar dentro de um objeto. Os objetos deste cliente que o projeto
# já mapeou têm campos até a casa de 0x2000 (ver `OFF_PET_ACTIVE = 0x10A8`).
TAMANHO_DE_OBJETO = 0x2400

# O módulo não tem ASLR, então tudo abaixo disto é endereço ESTÁTICO -- o tipo
# que vale guardar numa constante. Ver `core/patch_do_cliente.py`.
FIM_DO_MODULO = IMAGE_BASE + 0x1000000

# Quantos candidatos levar adiante na varredura larga. Felicidade é 0..100:
# a varredura acha milhares, e quem separa é a validação cruzada.
MAXIMO_DE_CANDIDATOS = 4000

PASTA = Path("logs") / "memoria"
ARQUIVO = PASTA / "happy-do-pet.json"

# O endereço que o usuário achou em 16/09/2026, na conta `creubo`. É ÂNCORA DE
# DEPURAÇÃO, não resposta: serve para a busca provar que está olhando o lugar
# onde o campo comprovadamente esteve. Vira `None` no dia em que o cliente
# reiniciar -- e é isso mesmo que ele prova.
ANCORA_CONHECIDA: int | None = 0x2DC83FDC

# A DISTÂNCIA DO NOME ATÉ A FELICIDADE, dentro do objeto.
#
# MEDIDA na conta âncora em 16/09/2026: o nome "BlazesOfGamer" está em
# 0x2DC83FC5 e o campo em 0x2DC83FDC -- exatamente 0x17 bytes adiante. É
# propriedade da ESTRUTURA, e por isso vale em qualquer endereço que o alocador
# sorteie; o endereço, não.
OFF_DA_FELICIDADE = 0x17


class _MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", w.DWORD), ("RegionSize", ctypes.c_size_t),
        ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD),
    ]


class Cliente:
    """Um `client.exe` aberto, SÓ para leitura."""

    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.titulo = titulo_do_pid(pid)
        self.k32 = ctypes.windll.kernel32
        self.handle = self.k32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)

    def ok(self) -> bool:
        return bool(self.handle)

    def ler(self, endereco: int, tamanho: int) -> bytes | None:
        buf = ctypes.create_string_buffer(tamanho)
        lidos = ctypes.c_size_t(0)
        if not self.k32.ReadProcessMemory(self.handle, ctypes.c_void_p(endereco),
                                          buf, tamanho, ctypes.byref(lidos)):
            return None
        return buf.raw[:lidos.value]

    def uint(self, endereco: int) -> int | None:
        dados = self.ler(endereco, 4)
        return struct.unpack("<I", dados)[0] if dados and len(dados) == 4 else None

    def regioes(self) -> list[tuple[int, int]]:
        """(base, tamanho) de toda memória COMMITADA e gravável."""
        achadas: list[tuple[int, int]] = []
        endereco = 0x10000
        mbi = _MEMORY_BASIC_INFORMATION()
        while endereco < 0x7FFF0000:
            if not self.k32.VirtualQueryEx(self.handle, ctypes.c_void_p(endereco),
                                           ctypes.byref(mbi), ctypes.sizeof(mbi)):
                break
            base = int(mbi.BaseAddress or 0)
            tamanho = int(mbi.RegionSize or 0)
            if (mbi.State == MEM_COMMIT and mbi.Protect in PAGE_GRAVAVEL
                    and 0 < tamanho <= 64 * 1024 * 1024):
                achadas.append((base, tamanho))
            endereco = base + tamanho if tamanho else endereco + 0x1000
        return achadas

    def fechar(self) -> None:
        if self.handle:
            self.k32.CloseHandle(self.handle)


# ===========================================================================
# 1. A BUSCA BARATA -- pelo objeto do personagem
# ===========================================================================

def cadeias_pelo_personagem(c: Cliente, valor: int) -> list[list[int]]:
    """`[PLAYER_BASE] -> campo ponteiro -> campo com o valor`. Dois níveis.

    Devolve a lista de cadeias de deslocamentos que, a partir de `PLAYER_BASE`,
    chegam no valor procurado.
    """
    achadas: list[list[int]] = []
    jogador = c.uint(PLAYER_BASE)
    if not jogador or jogador < 0x10000:
        return achadas

    corpo = c.ler(jogador, TAMANHO_DE_OBJETO) or b""

    # NÍVEL 1: o valor está no PRÓPRIO objeto do personagem?
    for off in range(0, len(corpo) - 3, 4):
        if struct.unpack_from("<I", corpo, off)[0] == valor:
            achadas.append([off])

    # NÍVEL 2: cada campo que parece ponteiro vira um objeto para olhar dentro.
    for off in range(0, len(corpo) - 3, 4):
        ptr = struct.unpack_from("<I", corpo, off)[0]
        if not (0x10000 < ptr < 0x7FFF0000) or ptr % 4:
            continue
        dentro = c.ler(ptr, TAMANHO_DE_OBJETO)
        if not dentro:
            continue
        for off2 in range(0, len(dentro) - 3, 4):
            if struct.unpack_from("<I", dentro, off2)[0] == valor:
                achadas.append([off, off2])
    return achadas


# ===========================================================================
# 2. A BUSCA LARGA -- varre o heap e sobe pelos ponteiros
# ===========================================================================

def enderecos_com_o_valor(c: Cliente, valor: int) -> list[int]:
    """Todo endereço gravável cujo uint32 é o valor procurado."""
    alvo = struct.pack("<I", valor)
    achados: list[int] = []
    for base, tamanho in c.regioes():
        blob = c.ler(base, tamanho)
        if not blob:
            continue
        i = blob.find(alvo)
        while i >= 0:
            if (base + i) % 4 == 0:
                achados.append(base + i)
                if len(achados) >= MAXIMO_DE_CANDIDATOS:
                    return achados
            i = blob.find(alvo, i + 1)
    return achados


def quem_aponta_para(c: Cliente, alvos: set[int],
                     limite: int = 200) -> dict[int, list[int]]:
    """Mapa {valor apontado: endereços que o contêm}. UMA varredura para todos.

    POR NUMPY, E NÃO POR `bytes.find`. A primeira versão procurava padrão a
    padrão: com 512 alvos e algumas centenas de regiões, são 100 mil varreduras
    de memória -- rodou mais de dez minutos sem terminar. Aqui cada região vira
    um vetor de uint32 e a comparação é uma operação só (`np.isin`), para todos
    os alvos ao mesmo tempo.
    """
    import numpy as np

    procurados = np.array(sorted(alvos), dtype=np.uint32)
    saida: dict[int, list[int]] = {}
    for base, tamanho in c.regioes():
        blob = c.ler(base, tamanho - (tamanho % 4))
        if not blob or len(blob) < 4:
            continue
        # PONTEIRO É ALINHADO: ler como uint32 já descarta o desalinhado, que é
        # o mesmo filtro que a versão antiga fazia com `% 4`.
        palavras = np.frombuffer(blob, dtype=np.uint32,
                                 count=len(blob) // 4)
        for indice in np.flatnonzero(np.isin(palavras, procurados)):
            alvo = int(palavras[indice])
            onde = saida.setdefault(alvo, [])
            if len(onde) < limite:
                onde.append(base + int(indice) * 4)
    return saida


def cadeias_pela_varredura(c: Cliente, valor: int,
                           maximo: int = 40) -> list[list[int]]:
    """Acha o valor no heap e tenta subir até um endereço ESTÁTICO.

    Dois níveis de ponteiro, que é o que cabe num tempo razoável em Python.
    """
    candidatos = enderecos_com_o_valor(c, valor)
    if not candidatos:
        return []

    # O campo mora DENTRO de um objeto: o começo dele é algum múltiplo de 4
    # antes. Procura quem aponta para cada base possível, numa varredura só.
    bases: dict[int, tuple[int, int]] = {}      # base -> (endereco, off)
    for endereco in candidatos[:400]:
        for off in range(0, 0x200, 4):
            bases[endereco - off] = (endereco, off)

    apontadores = quem_aponta_para(c, set(bases))
    achadas: list[list[int]] = []
    for base, ponteiros in apontadores.items():
        _endereco, off = bases[base]
        for p in ponteiros:
            if p < FIM_DO_MODULO:               # ESTÁTICO: acabou a subida
                achadas.append([p, off])
                if len(achadas) >= maximo:
                    return achadas
    return achadas


# ===========================================================================
# A validação cruzada
# ===========================================================================

def resolver(c: Cliente, base: int, offsets: list[int]) -> int | None:
    """`[base] + off1 -> [...] + off2 ...`, igual a `Memory.resolve`."""
    atual = c.uint(base)
    for i, off in enumerate(offsets):
        if atual is None or atual < 0x10000:
            return None
        if i == len(offsets) - 1:
            return c.uint(atual + off)
        atual = c.uint(atual + off)
    return atual


def procurar_pela_assinatura(c: Cliente, esperado: int) -> list[tuple[int, int]]:
    """Acha o campo pela VIZINHANÇA dele, e não por endereço nem por cadeia.

    =====================================================================
    POR QUE A ASSINATURA GANHA DA CADEIA AQUI
    =====================================================================

    O dump de 0x2DC83FDC (16/09/2026) mostrou o NOME DO PERSONAGEM 0x17 bytes
    antes da felicidade. Isso é uma âncora muito melhor que um caminho de
    ponteiros: o nome é único no processo, e a distância dele até o campo é
    propriedade da ESTRUTURA -- não muda com o endereço que o alocador sorteou.

    A cadeia `[PLAYER_BASE]+0xEE8 -> +0xE8` funcionou numa conta e leu lixo nas
    outras duas: o ponteiro daquele deslocamento aponta para objetos diferentes
    conforme o que está carregado. A assinatura não tem esse problema.

    Devolve `[(endereco_do_nome, deslocamento_ate_o_campo)]` para todo lugar em
    que o campo bate com a felicidade informada.
    """
    nome = c.ler(PLAYER_BASE, 4)
    jogador = struct.unpack("<I", nome)[0] if nome else 0
    if not jogador:
        return []
    bruto = c.ler(jogador + OFF_NAME, 32) or b""
    # O TERMINADOR É O BYTE ZERO, e não a sequência literal "\x00" -- este erro
    # de escapamento fez a busca procurar 32 bytes de nome MAIS LIXO, que só
    # existe num lugar, e devolver zero em três clientes seguidos.
    texto = bruto.split(bytes([0]), 1)[0]
    if not texto:
        return []

    # O DUMP MOSTROU O NOME SEM A PRIMEIRA LETRA ("lazesOfGamer"), e não dá para
    # saber ainda se é assim que o cliente guarda ou se foi coincidência do
    # recorte. Então procura os dois, e a busca diz qual apareceu.
    procurados = [texto, texto[1:]] if len(texto) > 4 else [texto]
    print(f"   nome do personagem: {texto.decode('latin-1')!r}")

    # PROVA DE QUE A VARREDURA ENXERGA O QUE PRECISA. Uma busca que devolve zero
    # pode ser "não existe" ou "não olhei lá" -- e as duas se parecem no log.
    # O objeto do personagem É um lugar que tem de estar coberto: o nome saiu
    # dele.
    regioes = c.regioes()
    total = sum(t for _b, t in regioes)
    cobre = any(b <= jogador < b + t for b, t in regioes)
    print(f"   varredura: {len(regioes)} regiões, {total / 1024 / 1024:.0f} MB "
          f"| objeto do personagem (0x{jogador:08X}) "
          f"{'DENTRO' if cobre else 'FORA -- a varredura está cega'}")

    # E O MESMO PARA A ÂNCORA, quando ela é desta conta: é o único endereço em
    # que se SABE que o campo está. Se ele não estiver coberto, o zero da busca
    # não quer dizer nada.
    if ANCORA_CONHECIDA is not None:
        dentro = any(b <= ANCORA_CONHECIDA < b + t for b, t in regioes)
        agora = c.uint(ANCORA_CONHECIDA)
        volta = c.ler(ANCORA_CONHECIDA - 0x18, 0x18) or b""
        print(f"   âncora 0x{ANCORA_CONHECIDA:08X}: valor={agora} | "
              f"{'coberta' if dentro else 'FORA DA VARREDURA'} | "
              f"antes dela: {volta.decode('latin-1')!r}")

    # NÃO SE PROCURA MAIS PELO VALOR, E ISSO É O PONTO.
    #
    # A felicidade cai 1 a cada 10 minutos (medido pelo usuário em 16/09/2026),
    # então o número informado já envelheceu quando a busca termina -- foi o que
    # fez a primeira rodada achar 44 coincidências e perder a cadeia certa.
    #
    # Agora a busca é pela ESTRUTURA: toda ocorrência do nome, e o que está no
    # deslocamento CONFIRMADO na conta âncora (+0x17). Quem decide é a
    # plausibilidade (0 a 100) mais a conferência do usuário na tela.
    achados: list[tuple[int, int]] = []
    for base, tamanho in c.regioes():
        blob = c.ler(base, tamanho)
        if not blob:
            continue
        for alvo in procurados:
            i = blob.find(alvo)
            while i >= 0:
                if i + 0x30 <= len(blob):
                    campos = struct.unpack_from("<8I", blob, i + 0x10)
                    # A ASSINATURA DA `std::string` DO MSVC, que é como este
                    # cliente guarda o nome: 16 bytes de buffer, TAMANHO e
                    # CAPACIDADE. Capacidade 15 é a do buffer curto (SSO), e
                    # tamanho é o do nome -- juntos, separam a cópia que é
                    # estrutura de verdade das centenas que são texto solto.
                    #
                    # E a FELICIDADE é o campo logo DEPOIS dela (+0x18 do começo
                    # do buffer). Foi assim na âncora: `0F 00 00 00` colado no
                    # valor.
                    if (campos[0] == len(alvo) and campos[1] == 15
                            and 1 <= campos[2] <= 100):
                        achados.append((base + i, campos))
                i = blob.find(alvo, i + 1)
    print(f"   informado pelo usuário: {esperado} (pode ter caído desde então)")
    return achados


def conferir_cadeia(clientes: list[tuple[Cliente, int]],
                    offsets: list[int]) -> None:
    """Lê UMA cadeia em todos os clientes. É o teste final de uma hipótese.

    Aqui não há busca: a cadeia vem de fora (do mapa de ponteiros, ou de uma
    leitura anterior) e o que se quer saber é se ela devolve um número PLAUSÍVEL
    de felicidade em TODA conta -- 0 a 100, e batendo com o que o usuário vê na
    tela. Uma cadeia que só funciona numa conta é endereço de heap disfarçado.
    """
    caminho = " -> ".join(f"+0x{o:X}" for o in offsets)
    print(f"\n=== CONFERINDO [PLAYER_BASE] {caminho} ===")
    for c, esperado in clientes:
        lido = resolver(c, PLAYER_BASE, offsets)
        plausivel = lido is not None and 0 <= lido <= 100
        print(f"   {c.titulo:<18} lido: {lido!s:>12} | informado: {esperado}"
              f" | {'PLAUSÍVEL' if plausivel else 'fora de 0..100'}")


def inspecionar(c: Cliente, endereco: int, valor: int) -> None:
    """Disseca o endereço que o usuário achou: vizinhança e quem aponta para lá.

    É a informação mais valiosa da busca inteira. Um endereço CONFIRMADO diz
    três coisas que a varredura cega não diz: em que CODIFICAÇÃO o campo está
    (byte, uint16, uint32, float), onde começa o OBJETO que o contém, e -- uma
    varredura depois -- quem aponta para esse objeto.
    """
    print(f"\n=== DISSECANDO 0x{endereco:08X} em {c.titulo} ===")
    # A PRIMEIRA PERGUNTA É SE ISTO JÁ ESTÁ NUM OBJETO CONHECIDO. O bot acha o
    # objeto do personagem por `PLAYER_BASE`; se o campo estiver dentro dele, a
    # cadeia é de um nível só e o trabalho acabou aqui.
    jogador = c.uint(PLAYER_BASE)
    if jogador:
        dist = endereco - jogador
        print(f"   [PLAYER_BASE] = 0x{jogador:08X} | distância até o campo: "
              f"{dist:+#x} ({'DENTRO do objeto do personagem' if 0 <= dist < 0x4000 else 'FORA -- é outro objeto'})")
    volta = c.ler(endereco - 0x40, 0x100)
    if not volta:
        print("   não consegui ler esse endereço (o pet pode ter sido reinvocado)")
        return

    print(f"   uint32 no endereço ..... {struct.unpack_from('<I', volta, 0x40)[0]}")
    print(f"   byte no endereço ....... {volta[0x40]}")
    print(f"   float no endereço ...... "
          f"{struct.unpack_from('<f', volta, 0x40)[0]:.3f}")
    print("\n   VIZINHANÇA (a linha com o valor procurado vai marcada):")
    for linha in range(0, 0x100, 16):
        off = linha - 0x40
        octetos = " ".join(f"{b:02X}" for b in volta[linha:linha + 16])
        quatro = [struct.unpack_from("<I", volta, linha + i)[0]
                  for i in (0, 4, 8, 12)]
        marca = " <<<" if any(v == valor for v in quatro) else ""
        print(f"   {off:+#07x}  {octetos}{marca}")

    # ONDE COMEÇA O OBJETO: quem aponta para algum lugar logo antes do campo.
    bases = {endereco - off: off for off in range(0, 0x800, 4)}
    print(f"\n   procurando quem aponta para este objeto "
          f"({len(bases)} bases possíveis)...")
    apontadores = quem_aponta_para(c, set(bases), limite=6)
    if not apontadores:
        print("   ninguém aponta para as 0x800 posições antes do campo.")
        return
    for base, ponteiros in sorted(apontadores.items(),
                                  key=lambda kv: bases[kv[0]]):
        off = bases[base]
        onde = ", ".join(f"0x{p:08X}{' (ESTÁTICO)' if p < FIM_DO_MODULO else ''}"
                         for p in ponteiros[:6])
        print(f"   objeto em 0x{base:08X} (campo em +0x{off:X}) <- {onde}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    esperados: dict[str, int] = {}
    for arg in argv:
        if arg.startswith("--"):          # bandeira, não conta
            continue
        if "=" in arg:
            titulo, valor = arg.split("=", 1)
            esperados[titulo.strip().lower()] = int(valor)
    if not esperados:
        print(__doc__)
        return 2

    # O ENDEREÇO QUE O USUÁRIO JÁ ACHOU, quando ele existe: é âncora, não
    # resposta. Ver `inspecionar`.
    ancora = None
    cadeia_pedida: list[int] | None = None
    for arg in argv:
        if arg.startswith("--inspecionar="):
            ancora = int(arg.split("=", 1)[1], 16)
        elif arg.startswith("--conferir="):
            cadeia_pedida = [int(o, 16)
                             for o in arg.split("=", 1)[1].split(",")]

    clientes: list[tuple[Cliente, int]] = []
    for pid in clientes_abertos():
        c = Cliente(pid)
        if not c.ok():
            print(f"PID {pid}: não consegui abrir para LER "
                  f"(rode como ADMINISTRADOR)")
            continue
        alvo = next((v for t, v in esperados.items()
                     if t in c.titulo.lower()), None)
        if alvo is None:
            c.fechar()
            continue
        clientes.append((c, alvo))
        print(f"PID {pid:<7} {c.titulo:<18} felicidade informada: {alvo}")

    if not clientes:
        print("\nNenhum cliente casou com os títulos informados.")
        return 1

    principal, valor = clientes[0]
    if "--por-nome" in argv:
        for c, esperado in clientes:
            print(f"\n=== {c.titulo}: procurando {esperado} perto do nome ===")
            achados = procurar_pela_assinatura(c, esperado)
            if not achados:
                print("   nenhuma cópia do nome com valor de 1 a 100 adiante")
            print(f"   {len(achados)} cópia(s) do nome com valor plausível "
                  f"(campos de +0x10 a +0x2C):")
            for endereco, campos in achados[:25]:
                marca = ""
                if (ANCORA_CONHECIDA
                        and endereco + OFF_DA_FELICIDADE == ANCORA_CONHECIDA):
                    marca = "  <<< A ÂNCORA"
                valores = " ".join(f"{v:>10}" if v < 1000 else f"{v:>10X}"
                                   for v in campos)
                print(f"   0x{endereco:08X} |{valores}{marca}")
        for c, _v in clientes:
            c.fechar()
        return 0
    if cadeia_pedida is not None:
        conferir_cadeia(clientes, cadeia_pedida)
        for c, _v in clientes:
            c.fechar()
        return 0
    if ancora is not None:
        inspecionar(principal, ancora, valor)

    print(f"\n[1/3] Procurando {valor} a partir do objeto do personagem "
          f"({principal.titulo})...")
    comeco = time.time()
    cadeias = [(PLAYER_BASE, offs)
               for offs in cadeias_pelo_personagem(principal, valor)]
    print(f"      {len(cadeias)} cadeia(s) em {time.time() - comeco:.1f}s")

    def validar(candidatas):
        sobra = []
        for base, offs in candidatas:
            placar = [(c.titulo, esperado, resolver(c, base, offs))
                      for c, esperado in clientes]
            if all(lido == esp for _t, esp, lido in placar):
                sobra.append((base, offs, placar))
        return sobra

    print(f"\n[2/3] Validando em {len(clientes) - 1} outra(s) conta(s)...")
    sobreviventes = validar(cadeias)

    # A VARREDURA LARGA TAMBÉM RODA QUANDO A BARATA NÃO VALIDA -- e esse é o
    # caso comum: felicidade é 0..100, então o objeto do personagem tem dezenas
    # de campos que por acaso valem 98 numa conta só.
    if not sobreviventes:
        print("\n[3/3] Nenhuma validou. Varrendo o heap inteiro (demora)...")
        comeco = time.time()
        largas = [(p, [off])
                  for p, off in cadeias_pela_varredura(principal, valor)]
        print(f"      {len(largas)} cadeia(s) em {time.time() - comeco:.1f}s")
        cadeias += largas
        sobreviventes = validar(largas)

    print()
    if sobreviventes:
        print(f"*** {len(sobreviventes)} CADEIA(S) VALIDADA(S) EM TODAS AS "
              f"CONTAS ***\n")
        for base, offs, placar in sobreviventes[:10]:
            caminho = " -> ".join(f"+0x{o:X}" for o in offs)
            print(f"  [0x{base:08X}] {caminho}")
            for titulo, esperado, lido in placar:
                print(f"        {titulo:<18} esperado {esperado:>3} | "
                      f"lido {lido}")
    else:
        print("Nenhuma cadeia serviu para TODAS as contas.")
        if cadeias:
            print(f"({len(cadeias)} serviram só para a primeira -- é o que "
                  f"acontece quando o número bate por acaso.)")

    PASTA.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps({
        "quando": time.strftime("%Y-%m-%d %H:%M:%S"),
        "informado": esperados,
        "candidatas": [{"base": f"0x{b:08X}", "offsets": [f"0x{o:X}" for o in offs]}
                       for b, offs in cadeias[:200]],
        "validadas": [{"base": f"0x{b:08X}",
                       "offsets": [f"0x{o:X}" for o in offs],
                       "placar": [{"conta": t, "esperado": e, "lido": l}
                                  for t, e, l in placar]}
                      for b, offs, placar in sobreviventes],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRelatório em {ARQUIVO}")

    for c, _v in clientes:
        c.fechar()
    return 0 if sobreviventes else 1


if __name__ == "__main__":
    raise SystemExit(main())
