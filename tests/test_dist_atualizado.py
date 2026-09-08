"""O pacote que o app abre não pode ficar atrás do código.

=========================================================================
POR QUE ESTE TESTE EXISTE
=========================================================================

A interface web roda de `dist/`, não de `web/`: o `3-INICIAR-WEB.bat` chama
`python -m blazesbot.web_app`, que abre `dist/index.html` -- e **não faz build**.
`dist/` só muda quando alguém roda `npm run build`.

O BACKEND, ao contrário, é lido do código-fonte em toda execução. Então dá para
o app rodar com Python de agora e tela de horas atrás, e essa combinação não
existe em lugar nenhum do repositório: ninguém testou, ninguém revisou.

Foi o que aconteceu em 07/09/2026. Duas sessões seguidas mexeram em `web/`
(i18n cobrindo a Web inteira) e nenhuma rodou o build: o `dist/index.html` ficou
com 40 minutos de atraso enquanto o dicionário de traduções do backend seguia em
frente. O usuário relatou "várias funcionalidades visuais que funcionavam
pararam" -- e no código-fonte estava tudo certo, o que é exatamente o pior tipo
de defeito para caçar.

`dist/` é ignorado pelo git (`.gitignore`), então em clone novo ele não existe e
estes testes se pulam sozinhos. Onde ele EXISTE, ele tem de estar em dia.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DIST = RAIZ / "dist" / "index.html"
FONTE_HTML = RAIZ / "web" / "index.html"

so_com_dist = pytest.mark.skipif(
    not DIST.exists(), reason="dist/ ainda não foi gerado (`npm run build`)")

RECADO = ("dist/ está atrasado em relação a web/. O app abre dist/ e o "
          "3-INICIAR-WEB.bat NÃO faz build: rode `npm run build`.")


def _chaves(html: str) -> set[str]:
    return set(re.findall(r'data-i18n(?:-[a-z]+)?="([a-z0-9_]+)"', html))


@so_com_dist
def test_o_dist_tem_TODAS_as_chaves_de_i18n_do_fonte():
    """A comparação é por CONTEÚDO, não por data: mtime não sobrevive a um
    clone e daria reprovação aleatória. Chave de i18n serve bem porque cada
    texto novo da tela cria uma, então o conjunto cresce a cada alteração."""
    faltando = sorted(_chaves(FONTE_HTML.read_text(encoding="utf-8"))
                      - _chaves(DIST.read_text(encoding="utf-8")))
    assert not faltando, f"{RECADO}\nChaves ausentes no pacote: {faltando[:12]}"


@so_com_dist
def test_o_dist_aponta_para_arquivos_que_EXISTEM():
    """`vite build` limpa o `outDir` antes de escrever. Build interrompido no
    meio deixa um `index.html` apontando para assets que não estão lá -- e a
    tela sobe sem CSS e sem JS, sem erro nenhum na janela."""
    html = DIST.read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="\./(assets/[^"]+)"', html)
    assert refs, "o pacote não referencia nenhum asset -- build incompleto"
    for ref in refs:
        assert (DIST.parent / ref).exists(), f"{RECADO}\nfalta {ref}"


@so_com_dist
def test_o_dist_leva_o_ICONE_e_o_TITULO():
    """Os dois vêm de fora do bundle (`web/public/`), e é onde um build parcial
    costuma deixar rastro."""
    html = DIST.read_text(encoding="utf-8")
    assert "<title>" in html
    assert (DIST.parent / "favicon.ico").exists()
