"""GERA O PACOTE PARA ENTREGAR A OUTRA PESSOA — `.exe` + ZIP.

    python -m blazesbot.tools.empacotar

Sai um `entrega/BlazesBot-<data>.zip`: quem recebe descompacta e clica no
`BlazesBot.exe`. Não precisa de Python, nem de `1-INSTALAR.bat`, nem de npm.

=========================================================================
PASTA, E NÃO UM ARQUIVO SÓ -- a decisão que manda em todo o resto
=========================================================================

O PyInstaller sabe gerar um `.exe` único, e seria o mais bonito de mandar. Ele
não serve aqui, por dois motivos que não são de gosto:

1. **O BOT ESCREVE EM `data/`.** É lá que ficam o `config.json` com as contas, o
   placar de calibração e as estatísticas do dia. No modo arquivo-único, tudo
   que vem embutido é descompactado numa pasta TEMPORÁRIA que o Windows apaga
   ao fechar -- a configuração do usuário sumiria a cada partida.
2. **21 MB de template.** Eles seriam descompactados A CADA PARTIDA, e o
   usuário não poderia acrescentar um PNG na pasta de deletar, que é justamente
   o que a janela de escolha existe para deixá-lo fazer.

Então o `.exe` fica ao lado de `data/` e `dist/`, e é a pasta inteira que vai no
ZIP. Para quem recebe, a diferença é descompactar antes de clicar.

=========================================================================
O QUE NÃO VAI JUNTO
=========================================================================

**`data/config.json` NUNCA ENTRA.** Ele tem os logins e as senhas cifradas de
quem empacotou. `BotConfig.load` já trata arquivo ausente criando configuração
vazia, então quem recebe começa limpo, cadastrando as contas dele.

Também ficam de fora `logs/`, `data/memory/` (dumps de diagnóstico),
`data/stats_diarias.json` e `data/calibracao.json` -- medições da máquina de
quem empacotou, que não descrevem a de ninguém mais.
"""
from __future__ import annotations

import datetime as _dt
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from ..core.raiz import raiz_do_bot

RAIZ = raiz_do_bot()
SAIDA = RAIZ / "entrega"
NOME = "BlazesBot"

# O que o `.exe` precisa ter DENTRO (é lido, nunca escrito).
#
# `i18n` e o ícone da janela resolvem o caminho pelo `__file__` deles, então o
# destino no bundle tem que ser o MESMO caminho relativo da origem.
EMBUTIDOS = [
    ("blazesbot/locales", "blazesbot/locales"),
    ("web/public/favicon.ico", "web/public"),
]

# O que fica AO LADO do `.exe` (é lido e escrito, ou o usuário mexe).
AO_LADO = ["dist", "data/templates"]

# PyQt6 é a interface ANTIGA, descontinuada pelo usuário em 19/09/2026. Ela não
# é importada pelo `web_app`, mas o PyInstaller varre o pacote inteiro e acharia
# `gui/main_window.py` -- são ~120 MB de Qt para código que não roda.
FORA = ["PyQt6", "matplotlib", "pytest", "PIL.ImageQt"]


def _pyinstaller() -> list[str]:
    return [sys.executable, "-m", "PyInstaller"]


def _conferir() -> None:
    if not (RAIZ / "dist" / "index.html").exists():
        raise SystemExit(
            "Não achei `dist/index.html`. Rode `npm run build` antes: o .exe\n"
            "leva a tela JÁ COMPILADA, e quem recebe não tem npm.")
    try:
        subprocess.run([*_pyinstaller(), "--version"], check=True,
                       capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise SystemExit(
            "PyInstaller não está instalado neste ambiente. Instale com:\n"
            f"  {sys.executable} -m pip install pyinstaller") from None


def _limpar_a_saida_anterior() -> None:
    """A pasta da entrega anterior sai ANTES de o PyInstaller começar.

    MEDIDO em 19/09/2026: a primeira execução depois de mexer na pasta falhava
    e a segunda passava, sempre. O PyInstaller escreve por cima do que está lá,
    e o `.exe` de 9 MB recém-gravado costuma estar com um handle aberto --
    antivírus varrendo, Explorer gerando miniatura, um shell parado dentro da
    pasta. Apagar primeiro, com espera, troca "falha misteriosa uma vez sim,
    uma não" por uma mensagem que diz o que fazer.
    """
    pasta = SAIDA / NOME
    for tentativa in range(3):
        if not pasta.exists():
            return
        try:
            shutil.rmtree(pasta)
            return
        except OSError as erro:
            if tentativa == 2:
                raise SystemExit(
                    f"Não consegui apagar a entrega anterior:\n  {pasta}\n"
                    f"  {erro}\n\nFeche o que estiver usando a pasta (Explorer,"
                    " terminal, o próprio .exe) e rode de novo.") from None
            print(f"  ... a pasta anterior está presa, tentando de novo "
                  f"({tentativa + 1}/2)")
            time.sleep(3)


def _construir() -> Path:
    """Roda o PyInstaller. Devolve a pasta com o `.exe` dentro."""
    _limpar_a_saida_anterior()
    trabalho = RAIZ / "build" / "empacotar"
    comando = [
        *_pyinstaller(), "--noconfirm", "--clean",
        "--name", NOME,
        "--distpath", str(SAIDA),
        "--workpath", str(trabalho),
        "--specpath", str(trabalho),
        # SEM CONSOLE -- *"preferia que fosse só o bot aberto"* (19/09/2026).
        #
        # O terminal era a rede de segurança: sem ele, `sys.stdout` é `None` e o
        # log do bot não tem para onde ir. Quem assumiu esse papel foi o ponto
        # de partida (`tools/iniciar_exe.py`), que manda a saída para
        # `logs/console.txt` e transforma queda em CAIXA DE MENSAGEM. Tirar o
        # console sem isso é voltar ao "não abre e não diz nada".
        "--windowed",
        # ADMINISTRADOR. O bot lê a memória do cliente do jogo; sem elevação,
        # `Memory` falha na primeira conta e o resto não acontece.
        "--uac-admin",
        # O MESMO ÍCONE DO RESTO DO BOT. `web/public/favicon.ico` é o que a
        # janela já usa (`config.ICONE_DO_APP`) e o que a aba do navegador
        # mostra -- sem esta linha o Explorer mostraria o ícone genérico do
        # PyInstaller, e o arquivo entregue não pareceria o programa.
        #
        # Ele tem os SETE tamanhos que o Windows pede (16, 20, 24, 32, 40, 48 e
        # 64, todos 32 bits): a lista grande importa porque cada lugar puxa um
        # -- 16 na barra de tarefas, 32 no Explorer em "Ícones médios", 48 em
        # "Ícones grandes". Faltando o tamanho, o Windows reduz outro na mão e
        # o resultado é o ícone borrado.
        "--icon", str(RAIZ / "web" / "public" / "favicon.ico"),
    ]
    for origem, destino in EMBUTIDOS:
        comando += ["--add-data", f"{RAIZ / origem}{os_sep()}{destino}"]
    for modulo in FORA:
        comando += ["--exclude-module", modulo]
    comando.append(str(RAIZ / "blazesbot" / "tools" / "iniciar_exe.py"))

    print("  PyInstaller:", " ".join(comando[2:6]), "...")
    # SEM `check=True`: ele levanta `CalledProcessError`, e o traceback dele
    # enterra a mensagem que o PyInstaller acabou de escrever -- que é a única
    # que diz o que houve.
    if subprocess.run(comando).returncode != 0:
        raise SystemExit(
            "\nO PyInstaller falhou. O motivo está nas linhas acima.")
    return SAIDA / NOME


def os_sep() -> str:
    """O separador do `--add-data`: `;` no Windows, `:` no resto."""
    return ";" if sys.platform == "win32" else ":"


def _copiar_o_que_fica_ao_lado(pasta: Path) -> None:
    for relativo in AO_LADO:
        origem = RAIZ / relativo
        destino = pasta / relativo
        if not origem.exists():
            print(f"  ! {relativo}: não existe aqui, pulei")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            shutil.rmtree(destino)
        shutil.copytree(origem, destino,
                        ignore=shutil.ignore_patterns("*.md", "*.bmp", "*.jpg"))
        print(f"  + {relativo}")
    (pasta / "logs").mkdir(exist_ok=True)


def _zipar(pasta: Path) -> Path:
    dia = _dt.date.today().strftime("%Y-%m-%d")
    alvo = SAIDA / f"{NOME}-{dia}.zip"
    if alvo.exists():
        alvo.unlink()
    with zipfile.ZipFile(alvo, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for arquivo in sorted(pasta.rglob("*")):
            if arquivo.is_file():
                z.write(arquivo, Path(NOME) / arquivo.relative_to(pasta))
    return alvo


def main() -> int:
    print("BlazesBot -- empacotando para entrega\n")
    _conferir()
    pasta = _construir()
    print("\n  o que fica ao lado do .exe:")
    _copiar_o_que_fica_ao_lado(pasta)
    alvo = _zipar(pasta)
    mb = alvo.stat().st_size / (1024 * 1024)
    print(f"\nPRONTO: {alvo}  ({mb:.1f} MB)")
    print("Quem recebe: descompacta a pasta inteira e clica em "
          f"{NOME}.exe (ele pede administrador).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
