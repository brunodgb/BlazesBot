"""O SOCORRO EM BATALHA -- três mortes vendo a própria vida cair sem beber.

Da AUDITORIA FORENSE de 13 h de log da madrugada de 07/09/2026 -- o porquê
medido, com os números e o que o council apontou, está em
`docs/decisoes/madrugada-07-09-2026.md`.

    01:07:49  vida em 35% mas ainda em batalha. Rodando mais uma volta.
    01:07:52  vida em 29% mas ainda em batalha. Rodando mais uma volta.
    01:08:06  MORRI

Toda a cura estava atrás da porta "saiu de batalha", e com quatro a oito mobs
batendo essa porta não abre. A terceira morte foi pior: 100% a zero em 21 s, sem
uma leitura de vida no meio -- a rotação da macro não tinha terminado.
"""

from __future__ import annotations

from types import SimpleNamespace

from blazesbot.bot.app import cura as cura_mod

# ---------------------------------------------------------------------------
# 2. A CURA QUE NÃO ACONTECIA EM BATALHA
# ---------------------------------------------------------------------------

class _Personagem:
    """O mínimo para a `CuraDoApp`: vida, batalha e as teclas apertadas."""

    def __init__(self, vida=25.0, em_batalha=True):
        self.vida = vida
        self.batalha = em_batalha
        self.teclas: list[str] = []
        self.linhas: list[tuple[str, str]] = []
        self.cliques_no_minimapa = 0

    @property
    def log(self):
        anotar = self.linhas.append
        return SimpleNamespace(
            info=lambda f, *a: anotar(("INFO", f % a if a else f)),
            warning=lambda f, *a: anotar(("WARNING", f % a if a else f)),
            debug=lambda *a, **k: None)

    def cura(self, **kw):
        campos = dict(
            log=self.log,
            vida_pct=lambda: self.vida,
            em_batalha=lambda: self.batalha,
            alvo_atual=lambda: {"nome": "Mob", "hp": 80, "max_hp": 100},
            distancia_da_base=lambda: 30.0,
            voltar_para_base=self._voltar,
            apertar=self.teclas.append,
            esta_sentado=lambda: False,
            tecla_de_pocao=lambda: "9",
            tecla_de_sentar=lambda: "X",
        )
        campos.update(kw)
        return cura_mod.CuraDoApp(**campos)

    def _voltar(self) -> bool:
        self.cliques_no_minimapa += 1
        return True


def test_preso_em_batalha_com_vida_baixa_BEBE_onde_esta():
    """A morte de 01:08:06 -- vida de 35% a zero sem uma poção.

    Era o `return False` de `cuidar()` quando a flag de batalha não baixava.
    """
    p = _Personagem(vida=25.0, em_batalha=True)
    assert p.cura().cuidar() is True
    assert p.teclas == ["9"], "não bebeu em batalha"


def test_o_socorro_NAO_ANDA_e_NAO_SENTA():
    """Andar em batalha arrasta mob; sentar é para regenerar, não para fugir."""
    p = _Personagem(vida=25.0, em_batalha=True)
    p.cura().cuidar()
    assert p.cliques_no_minimapa == 0, "andou em batalha"
    assert "X" not in p.teclas, "sentou em batalha"


def test_o_socorro_TEM_CADENCIA():
    """Uma poção por vez: beber em série parado é o oposto do que salva."""
    p = _Personagem(vida=25.0, em_batalha=True)
    cura = p.cura()
    assert cura.socorro() is True
    assert cura.socorro() is False, "bebeu duas seguidas"
    assert p.teclas == ["9"]


def test_o_socorro_NAO_dispara_com_vida_boa():
    p = _Personagem(vida=95.0, em_batalha=True)
    assert p.cura().socorro() is False
    assert p.teclas == []


def test_o_socorro_NAO_tenta_curar_um_cadaver():
    """Vida zero é do ciclo da morte, e poção em morto é item jogado fora."""
    p = _Personagem(vida=0.0, em_batalha=True)
    assert p.cura().socorro() is False
    assert p.teclas == []


def test_sem_tecla_de_pocao_o_socorro_avisa_UMA_vez():
    """Sentar é a cura de FORA de batalha; aqui ela não serve."""
    p = _Personagem(vida=25.0, em_batalha=True)
    cura = p.cura(tecla_de_pocao=lambda: "")
    for _ in range(5):
        cura.socorro()
    avisos = [t for n, t in p.linhas if n == "WARNING"]
    assert len(avisos) == 1, avisos
    assert "SEM tecla de poção" in avisos[0]


def test_a_macro_confere_a_vida_DENTRO_da_espera_da_linha():
    """A morte de 12:04:30 -- 100% a zero em 21 s, sem uma leitura no meio.

    `cuidar()` roda uma vez por rotação; a rotação durou 21 s. O socorro tinha
    de entrar na espera fatiada, e é isso que este teste guarda pelo código:
    sem ele, a correção volta a ser "entre linhas" na primeira refatoração.
    """
    import inspect

    from blazesbot.bot.app import executor as mod
    fonte = inspect.getsource(mod.ExecutorDeMacro._esperar)
    assert "self.cura.socorro()" in fonte, (
        "o socorro saiu da espera fatiada -- uma linha longa volta a ser "
        "um buraco cego de vários segundos")
