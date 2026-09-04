"""
Verifica se todas as bibliotecas necessárias estão instaladas e funcionando.

Roda no fim da instalação. Se este script passa, o erro
"ModuleNotFoundError" não vai acontecer.
"""
from __future__ import annotations

import importlib
import sys

# (nome amigável, módulo a importar, pacote do pip)
CHECKS = [
    ("pymem (leitura de memória)", "pymem", "pymem"),
    ("psutil (processos)", "psutil", "psutil"),
    ("OpenCV (reconhecimento de imagem)", "cv2", "opencv-python"),
    ("NumPy (cálculo)", "numpy", "numpy"),
    ("pywin32 / janelas", "win32gui", "pywin32"),
    ("pywin32 / criptografia", "win32crypt", "pywin32"),
    ("PyQt6 (interface)", "PyQt6.QtWidgets", "PyQt6"),
]


def main() -> int:
    print()
    print(f"Interpretador em uso: {sys.executable}")
    print(f"Versão do Python:     {sys.version.split()[0]}")
    print()

    missing: list[str] = []
    for label, module, package in CHECKS:
        try:
            importlib.import_module(module)
        except Exception as exc:
            print(f"  [FALHA] {label}")
            print(f"          {type(exc).__name__}: {exc}")
            missing.append(package)
        else:
            print(f"  [ ok  ] {label}")

    print()
    if missing:
        unique = sorted(set(missing))
        print("Bibliotecas faltando:", ", ".join(unique))
        print()
        print("Tente instalar manualmente, dentro desta pasta:")
        print(f"  .venv\\Scripts\\python.exe -m pip install {' '.join(unique)}")
        return 1

    # Confere também que o próprio BlazesBot importa
    try:
        from blazesbot.config import BotConfig  # noqa: F401
    except Exception as exc:
        print(f"  [FALHA] módulos do BlazesBot: {exc}")
        print()
        print("A pasta 'blazesbot' provavelmente não está do lado do main.py.")
        print("Extraia o zip novamente sem mover arquivos de lugar.")
        return 1

    print("  [ ok  ] módulos do BlazesBot")
    print()
    print("Tudo pronto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
