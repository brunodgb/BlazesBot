"""FERRAMENTA TEMPORÁRIA -- vigia a struct da câmera AO VIVO. Só LÊ.

Módulo FOLHA: nada do bot importa daqui. Existe para responder uma pergunta que
não dá para responder sem o jogo na frente:

    **QUAIS são os três números quando a câmera está na pose CERTA?**

O bot nunca soube. Ele herdou `set_camera(380, 0, 40)` do T-R0XX da versão 6139
e escrevia isso num ponteiro que, na 6400, resolve NULO -- ou seja, escrevia em
lugar nenhum, e ninguém tinha como saber porque a câmera nunca apareceu no
diagnóstico.

COMO SE USA
-----------
1. Rode isto com o jogo aberto.
2. Arraste a câmera com o botão direito, dê View Reset, marque o **Lock the
   View** nas opções de Gráficos -- faça o que você já faz na mão.
3. Cada mudança vira UMA LINHA aqui. Quando a câmera estiver na pose em que os
   cliques funcionam, a última linha impressa é a POSE DE REFERÊNCIA.

A SEGUNDA PERGUNTA, e ela é mais importante que a primeira
----------------------------------------------------------
**O termômetro muda quando o personagem ANDA, sem ninguém tocar na câmera?**

Dois `2-DIAGNOSTICO` do MESMO personagem, em 25/08/2026, com a câmera intocada
entre eles, leram `1220.339355` e `756.339355` -- 464,000000 cravados de
diferença, e a fração idêntica nos dois. Se for a posição que manda, então
`ANGULO_DA_CAMERA = 956.720459` não é constante do jogo: é o valor DAQUELE
lugar, e conferir contra ele em outro ponto do mapa não quer dizer nada.

Para responder: rode isto, **NÃO toque na câmera**, e ande. Cada linha traz o
delta e a posição lado a lado.

NÃO ESCREVE NADA. É a diferença entre esta ferramenta e o
`Memory.diagnostico_da_camera`, que escreve e restaura para provar quem move a
câmera.
"""
from __future__ import annotations

import time

from blazesbot.core.memory import (
    ADDR_ANGULO_DA_CAMERA,
    ADDR_CAMERA,
    ADDR_CAMERA_VIVA,
    Memory,
)

# Cadência da leitura. Barata: são 8 leituras de 4 bytes por volta.
PASSO = 0.25

# Teto padrão, para a ferramenta fechar sozinha se você esquecer dela aberta.
SEGUNDOS_PADRAO = 300.0

# O que conta como "mudou". Menor que isto é ruído de interpolação -- andando, o
# termômetro oscila 0,0005 e volta sozinho.
MUDOU = 0.0005

# Os campos da struct, na ordem em que o GhostBot os escrevia.
CAMPOS = (("rotacao", 0x5C), ("angulo", 0x60), ("zoom", 0x64))


def _pose(memoria: Memory, base: int) -> dict[str, float | None] | None:
    """Os três floats da struct, ou `None` se o ponteiro não resolve."""
    ponteiro = memoria.read_uint(base)
    if ponteiro is None or ponteiro < 0x10000:
        return None
    pose: dict[str, float | None] = {}
    for nome, offset in CAMPOS:
        endereco = memoria.resolve(base, [offset])
        pose[nome] = None if endereco is None else memoria.read_float(endereco)
    return pose


def _mudou(antes: dict[str, float | None] | None,
           agora: dict[str, float | None] | None) -> bool:
    if antes is None or agora is None:
        return antes is not agora
    for nome in agora:
        a, b = antes.get(nome), agora.get(nome)
        if (a is None) != (b is None):
            return True
        if a is not None and b is not None and abs(a - b) > MUDOU:
            return True
    return False


def _texto(pose: dict[str, float | None] | None) -> str:
    if pose is None:
        return "<ponteiro nulo>"
    return "  ".join(
        f"{nome}={'?' if v is None else f'{v:.6f}'}" for nome, v in pose.items())


def run_ler_camera(pid: int, segundos: float = SEGUNDOS_PADRAO) -> int:
    """Imprime uma linha a cada MUDANÇA da câmera. Fecha sozinha no teto."""
    try:
        memoria = Memory(pid)
    except Exception as exc:
        print(f"Não consegui abrir o PID {pid}: {exc}")
        return 1

    bases = (("ADDR_CAMERA", ADDR_CAMERA), ("ADDR_CAMERA+0x60", ADDR_CAMERA + 0x60))

    print(f"Vigiando a câmera do PID {pid} por {segundos:.0f}s. Ctrl+C para "
          f"parar.")
    print(f"Termômetro (diagnóstico): {ADDR_ANGULO_DA_CAMERA:#010x}   |   "
          f"struct viva: {ADDR_CAMERA_VIVA:#010x}")
    print("Mexa a câmera / dê View Reset / marque o Lock the View. Cada mudança "
          "vira uma linha.")
    print("-" * 78)

    anterior: dict[str, object] = {}
    ultimo_termometro: float | None = None
    ultima_linha = ""
    comeco = time.monotonic()

    try:
        while time.monotonic() - comeco < segundos:
            termometro = memoria.camera_angulo()
            poses = {rotulo: _pose(memoria, base) for rotulo, base in bases}

            mudou = any(_mudou(anterior.get(r), p) for r, p in poses.items())
            if (ultimo_termometro is None) != (termometro is None):
                mudou = True
            elif (termometro is not None and ultimo_termometro is not None
                  and abs(termometro - ultimo_termometro) > MUDOU):
                mudou = True

            if mudou:
                marca = time.strftime("%H:%M:%S")
                t = "?" if termometro is None else f"{termometro:.6f}"
                # O DELTA e a POSIÇÃO na mesma linha. É o que responde a
                # pergunta aberta: o termômetro muda quando o personagem ANDA,
                # sem ninguém tocar na câmera? Se muda, `ANGULO_DA_CAMERA` não
                # é constante do jogo -- é o valor daquele lugar, e comparar
                # contra ele em outro ponto do mapa não quer dizer nada.
                delta = ""
                if termometro is not None and ultimo_termometro is not None:
                    delta = f"  ({termometro - ultimo_termometro:+.6f})"
                pos = memoria.position()
                onde = "?" if pos is None else f"({pos[0]}, {pos[1]})"
                ultima_linha = f"termômetro={t}"
                print(f"[{marca}] termômetro = {t}{delta}   posição = {onde}")
                for rotulo, pose in poses.items():
                    print(f"           {rotulo:<18} {_texto(pose)}")
                    if pose is not None:
                        ultima_linha += "  " + _texto(pose)
                anterior = dict(poses)
                ultimo_termometro = termometro

            time.sleep(PASSO)
    except KeyboardInterrupt:
        print("\n(parado por Ctrl+C)")

    print("-" * 78)
    ultima_pose = anterior.get("ADDR_CAMERA+0x60")
    if ultima_pose is not None and all(v is not None for v in ultima_pose.values()):
        print("POSE DE REFERÊNCIA -- a última que você viu na tela:")
        print()
        print(f"   {ultima_linha}")
        print()
        print("Se a câmera estava CERTA quando esta linha saiu, é ESTA a linha")
        print("que vai para `blazesbot/core/memory.py`:")
        print()
        print(f"   POSE_DA_CAMERA = ({ultima_pose['zoom']!r}, "
              f"{ultima_pose['rotacao']!r}, {ultima_pose['angulo']!r})")
        print()
        print("A ordem é (zoom, rotacao, angulo) -- a mesma de `set_camera`.")
        print("Trocar o `None` por essa tupla é o que LIGA a correção da")
        print("câmera: enquanto ela for `None`, o bot não escreve para valer.")
    elif ultima_linha:
        print("A struct não respondeu neste cliente -- só o termômetro mudou.")
        print(f"   {ultima_linha}")
    else:
        print("Nada mudou no período. Ou a câmera não se mexeu, ou o ponteiro "
              "não resolve neste cliente.")
    memoria.close()
    return 0
