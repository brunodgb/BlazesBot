"""Os campos numéricos da interface web: piso, faixa e unidade.

*"nenhum dos campos deve aceitar 0, e sempre a partir de 1, ou ser for delay é a
partir de 100 ... tudo que for delay ou intervalo de tempo padroniza em MS e
minimo 100 ms"* — usuário, 26/08/2026.

Estes testes leem o `index.html` porque é lá que mora a fonte da verdade de cada
campo (o `min`, o `max` e o `step` que a roda do mouse e as setinhas usam).
Ver `docs/decisoes/interface.md`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
HTML = (RAIZ / "web" / "index.html").read_text(encoding="utf-8")

# Os campos que aceitam 0, e em TODOS eles o 0 é um MODO -- nunca um zero por
# descuido. Cada um tem que aparecer aqui com o motivo, e é essa exigência que
# faz a exceção ser decisão em vez de esquecimento.
EXCECOES_QUE_ACEITAM_ZERO = {
    # "nunca apagar o lixo". Apagar item não tem desfazer, então tirar essa
    # saída seria pior que a inconsistência. Decisão do usuário em 26/08/2026.
    "ed-app-limpar",
    # "não limpar os mobs do caminho" na HH. A limpeza só acontece A PÉ, e
    # atravessar a cave montado é a forma normal -- montado o personagem não
    # para. Quem monta não quer o passo, e 1 seria parar a cada waypoint.
    "ed-hh-limpar",
}


def _campos_numericos() -> list[tuple[str, dict[str, str]]]:
    """Cada `<input>` numérico do HTML com seus atributos."""
    achados = []
    for tag in re.findall(r"<input\b[^>]*>", HTML):
        atributos = dict(re.findall(r'(\w[\w-]*)="([^"]*)"', tag))
        if atributos.get("type") in ("number", "range"):
            achados.append((atributos.get("id", "(sem id)"), atributos))
    return achados


def test_existem_campos_para_conferir():
    """Rede contra o teste passar por não achar nada."""
    assert len(_campos_numericos()) >= 10


@pytest.mark.parametrize("campo, attrs", _campos_numericos())
def test_todo_campo_numerico_declara_min_e_step(campo: str, attrs: dict):
    """Sem `min` a roda do mouse desce para sempre; sem `step` ela chuta 1."""
    assert "min" in attrs, f"{campo} não declara min"
    assert "step" in attrs, f"{campo} não declara step"


@pytest.mark.parametrize("campo, attrs", _campos_numericos())
def test_nenhum_campo_aceita_zero(campo: str, attrs: dict):
    """Mínimo 1, ou 100 se for tempo. As exceções são declaradas e explicadas."""
    minimo = float(attrs["min"])
    if campo in EXCECOES_QUE_ACEITAM_ZERO:
        assert minimo == 0, f"{campo} está na lista de exceções mas não aceita 0"
        return
    assert minimo >= 1, f"{campo} aceita {minimo}"


@pytest.mark.parametrize("campo, attrs", _campos_numericos())
def test_campo_de_tempo_esta_em_ms_com_piso_de_100(campo: str, attrs: dict):
    """Delay e espera falam MILISSEGUNDOS, e o piso é 100.

    Detectado pelo rótulo `(ms)` no HTML, que é o que o usuário lê. O intervalo
    de comida do pet é a única exceção e continua em minutos — ver
    `PET_FEED_MINUTOS_MIN`.
    """
    from blazesbot.config import MINIMO_DELAY_MS

    rotulo_ms = f'{attrs.get("id", "")}" type="number"' in HTML and (
        re.search(rf'\(ms\)</span>\s*<input id="{re.escape(campo)}"', HTML)
        is not None)
    if not rotulo_ms:
        return
    assert float(attrs["min"]) >= MINIMO_DELAY_MS, f"{campo} abaixo do piso"


def test_o_pet_e_a_unica_excecao_de_unidade_e_tem_faixa_fechada():
    """*"pode deixar em minutos, mas coloca o minimo em 40 minutos e no maximo
    60 o de pet food"* — usuário, 26/08/2026."""
    from blazesbot.config import PET_FEED_MINUTOS_MAX, PET_FEED_MINUTOS_MIN

    attrs = dict(_campos_numericos())["ed-pet-feed-min"]
    assert int(attrs["min"]) == PET_FEED_MINUTOS_MIN == 40
    assert int(attrs["max"]) == PET_FEED_MINUTOS_MAX == 60
    # O rótulo tem de dizer minutos, senão o usuário digita ms.
    assert "Alimentar a cada (min)" in HTML


def test_a_faixa_do_pet_e_reaplicada_na_leitura():
    """"A tela impõe" não é garantia, é boa vontade: arquivo antigo sobe
    corrigido em vez de fazer o bot recusar a configuração inteira."""
    from blazesbot.config import (
        PET_FEED_MINUTOS_MAX,
        PET_FEED_MINUTOS_MIN,
        pet_feed_na_faixa,
    )

    assert pet_feed_na_faixa(10) == PET_FEED_MINUTOS_MIN     # combo antigo
    assert pet_feed_na_faixa(30) == PET_FEED_MINUTOS_MIN     # combo antigo
    assert pet_feed_na_faixa(50) == 50
    assert pet_feed_na_faixa(999) == PET_FEED_MINUTOS_MAX
    assert pet_feed_na_faixa(None) == 50
    assert pet_feed_na_faixa("lixo") == 50


def test_max_clients_foi_APOSENTADO_de_ponta_a_ponta():
    """*"o max clientes simultaneos não deve existir, vai ser sempre todas as
    contas"* — usuário, 26/08/2026.

    O campo saiu de vez em vez de virar interruptor porque não guardava um
    caminho de código, guardava um TETO: teto órfão num `config.json` antigo
    continuaria cortando contas ativas sem nenhuma tela para desfazer.
    """
    from blazesbot.config import BotConfig

    assert not hasattr(BotConfig(), "max_clients")

    for arquivo in ("web/index.html", "web/main.js",
                    "blazesbot/bot/supervisor.py",
                    "blazesbot/gui/main_window.py",
                    "blazesbot/web_app.py", "blazesbot/config.py"):
        texto = (RAIZ / arquivo).read_text(encoding="utf-8")
        # Sobra só em comentário, contando a história da aposentadoria.
        vivas = [linha for linha in texto.splitlines()
                 if "max_clients" in linha
                 and not linha.lstrip().startswith(("#", "//", "*"))]
        assert not vivas, f"{arquivo}: {vivas}"
