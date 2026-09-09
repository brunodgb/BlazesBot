"""De QUEM é o slot inicial da venda, e quando a grade NÃO pode ser clicada.

=============================================================================
O DEFEITO QUE ESTE ARQUIVO TRAVA
=============================================================================

`AccountSettings.vendor` é propriedade de compatibilidade: devolve `bc.vendor`,
SEMPRE. `JanelaDeVenda` lia dali, então a venda da HH era feita com o slot da
Bewitcher Cave -- enquanto as duas interfaces gravavam, e mostravam ao usuário,
o `hh.vendor.sell_start_slot`.

MEDIDO em `data/config.json` (09/09/2026): `gamerblazes` tem BC=1 e HH=3. Com o
número da BC, a venda da HH começaria no slot 1 -- e a proteção dos itens bons é
GEOMÉTRICA (`sell_from_slot`: clicar sempre na mesma posição N esvazia de N para
frente). Slot errado não vende de menos: vende o equipamento.

A segunda propriedade é a do Supervisor de Estado: sem a janela de venda na
tela, o clique da grade cai na CENA 3D e o personagem ANDA -- para longe do
único ponto de onde os cliques no vendedor funcionam.
"""
from __future__ import annotations

from types import SimpleNamespace

from blazesbot.bot import vendedor as janela_de_venda
from blazesbot.bot.bc.vendor import VendorService
from blazesbot.bot.hh.vendedor import VendedorDaHH
from blazesbot.config import AccountSettings


class _Log:
    def __init__(self) -> None:
        self.avisos: list[str] = []

    def info(self, *a, **k): ...
    def debug(self, *a, **k): ...
    def error(self, *a, **k): ...

    def warning(self, msg, *a):
        self.avisos.append(str(msg))


class _Templates:
    """A pasta de templates: diz quais PNGs existem."""

    def __init__(self, existentes: set[str]) -> None:
        self.existentes = existentes

    def load(self, nome):
        return object() if nome in self.existentes else None


def _ctx(settings, *, templates: _Templates, log: _Log):
    grade = SimpleNamespace(columns=6, cell_w=50, cell_h=50)
    coords = SimpleNamespace(
        sell_grid=grade,
        sell_slot_xy=lambda slot: (100, 200),
        vendor_sell_button=(474, 710),
        hh_vendor_npc=(467, 377),
        vendor_sell_tab=(266, 430),
    )
    return SimpleNamespace(settings=settings, coords=coords,
                           templates=templates, log=log,
                           memory=SimpleNamespace(position=lambda: None))


def _vendedor_da_hh(settings, *, templates, log):
    """Um `VendedorDaHH` sem construtor -- ele monta navegador e mais mundo."""
    v = VendedorDaHH.__new__(VendedorDaHH)
    v.ctx = _ctx(settings, templates=templates, log=log)
    return v


def _vendedor_da_bc(settings, *, templates, log):
    v = VendorService.__new__(VendorService)
    v.ctx = _ctx(settings, templates=templates, log=log)
    return v


# ==========================================================================
# EIXO 3 -- o slot é da cave que está vendendo
# ==========================================================================

def test_a_HH_vende_pelo_slot_da_HH_e_a_BC_pelo_da_BC():
    """O caso `gamerblazes`: BC=1, HH=3. Cada uma com o seu."""
    s = AccountSettings()
    s.bc.vendor.sell_start_slot = 1
    s.hh.vendor.sell_start_slot = 3

    log = _Log()
    tpl = _Templates(set())
    assert _vendedor_da_hh(s, templates=tpl, log=log)._config_da_venda() \
        is s.hh.vendor
    assert _vendedor_da_bc(s, templates=tpl, log=log)._config_da_venda() \
        is s.bc.vendor


def test_o_ponto_do_slot_da_HH_sai_do_numero_da_HH():
    """Não é só de onde se lê: o PONTO CLICADO tem que mudar junto."""
    s = AccountSettings()
    s.bc.vendor.sell_start_slot = 1
    s.hh.vendor.sell_start_slot = 3
    tpl = _Templates(set())          # sem âncora: coordenadas calculadas

    ponto_hh, _, _ = _vendedor_da_hh(s, templates=tpl, log=_Log())._ponto_do_slot()
    ponto_bc, _, _ = _vendedor_da_bc(s, templates=tpl, log=_Log())._ponto_do_slot()

    # slot 1 = (100,200); slot 3 = duas colunas à direita, 50 px cada.
    assert ponto_bc == (100, 200)
    assert ponto_hh == (200, 200)
    assert ponto_hh != ponto_bc, "a HH estaria clicando no slot da BC"


def test_a_configuracao_da_venda_e_a_MESMA_forma_nas_duas_caves():
    """Slot, cota e teto de passadas vêm do mesmo lugar -- e `passadas_para`
    existe nas duas, senão a HH quebraria ao trocar de fonte."""
    s = AccountSettings()
    for venda in (s.bc.vendor, s.hh.vendor):
        assert hasattr(venda, "sell_start_slot")
        assert hasattr(venda, "runs_before_selling")
        assert venda.passadas_para(72) == min(venda.max_sell_passes, 3)
        assert venda.passadas_para(0) >= 1


def test_slot_fora_da_grade_e_reprovado_nas_DUAS_caves():
    s = AccountSettings()
    s.hh.vendor.sell_start_slot = 99
    assert any("HH" in p and "Slot inicial" in p for p in s.validate())
    s2 = AccountSettings()
    s2.bc.vendor.sell_start_slot = 0
    assert any("BC" in p and "Slot inicial" in p for p in s2.validate())


# ==========================================================================
# EIXO 2 -- sem janela de venda na tela, não se clica na grade
# ==========================================================================

def _sem_ancora(v):
    v._sell_anchor = lambda: None
    return v


def test_com_o_template_e_SEM_a_janela_o_ponto_do_slot_RECUSA():
    """A trava do Supervisor de Estado: recusar é melhor que andar."""
    log = _Log()
    tpl = _Templates({janela_de_venda.TEMPLATE_ANCHORS["sell"][0]})
    v = _sem_ancora(_vendedor_da_hh(AccountSettings(), templates=tpl, log=log))

    assert v._ponto_do_slot() is None
    assert log.avisos, "a recusa tem que aparecer no log"


def test_SEM_o_template_a_venda_continua_pelas_coordenadas_calculadas():
    """Cliente sem captura não pode ficar sem vender -- não há o que perguntar."""
    v = _sem_ancora(_vendedor_da_hh(AccountSettings(),
                                    templates=_Templates(set()), log=_Log()))
    ponto = v._ponto_do_slot()
    assert ponto is not None
    assert ponto[2] == "coordenadas calculadas"


def test_a_venda_NAO_CLICA_quando_a_janela_nao_esta_na_tela(monkeypatch):
    """A prova de ponta a ponta: nenhum clique sai com a janela fechada."""
    cliques: list[tuple[int, int]] = []
    s = AccountSettings()
    log = _Log()
    tpl = _Templates({janela_de_venda.TEMPLATE_ANCHORS["sell"][0]})
    v = _sem_ancora(_vendedor_da_hh(s, templates=tpl, log=log))
    v.ctx.raise_if_stopped = lambda: None
    v.ctx.tick = lambda _s: None
    v.ctx.click = cliques.append
    v.ctx.account_login = "simulacao"
    v.ctx.memory = SimpleNamespace(bag_count=lambda: 40,
                                   position=lambda: None,
                                   location=lambda: "Black Wind Camp Dungeon")
    monkeypatch.setattr(v, "_open_npc", lambda: True, raising=False)

    assert v.sell_from_slot() == 0
    assert cliques == [], f"clicou com a janela fechada: {cliques}"
