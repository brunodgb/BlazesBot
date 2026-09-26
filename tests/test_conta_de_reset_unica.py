"""A conta de reset é UMA por conta logada, e vale para todas as caves.

=========================================================================
O QUE MUDOU EM 08/09/2026, E POR QUÊ
=========================================================================

Era um campo POR CAVE -- `bc.reset_nick` e `hh.reset_nick`. Regra do usuário:

> *"Hoje a configuração da 'Conta Reset' está sendo definida separadamente em
> cada aba de Cave (BC, HH). Isso é um erro de design. A conta reset é 1 única
> por conta logada."*

E ele está certo pelo histórico do próprio bot: dois campos criavam três
estados impossíveis --

  1. preencher um e esquecer o outro. Medido em 03/09/2026: o usuário
     configurou o campo da HH, o do BC ficou vazio, `TeamService.montar_time`
     lia o do BC e devolvia `False` na primeira linha. A HH rodava sem time,
     os bosses não renasciam, e a rotina caía em `RECUPERAR` em laço;
  2. preencher os dois com nicks DIFERENTES -- e aí não existe resposta certa;
  3. o código compartilhado sem saber qual ler. `problema_do_reset`, o modo
     estrito do aceitador e `accounts_reset_by` liam o do BC; o aceitador teve
     que passar a olhar OS DOIS para não perder o reseter da HH.

Um campo só não tem nenhuma dessas perguntas.

=========================================================================
O QUE ESTE ARQUIVO PROTEGE
=========================================================================

Sobretudo a MIGRAÇÃO: quem já tinha o reseter configurado não pode abrir o bot
e encontrar o campo em branco. A leitura do config é reconstruída campo a
campo, e o que não é lido é descartado em silêncio -- então a migração precisa
ler do BRUTO, antes do `_filtra`.

Ver `docs/decisoes/reset-de-time.md`.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path

from blazesbot.config import AccountSettings, BCConfig, BotConfig, HHConfig

RAIZ = Path(__file__).resolve().parents[1]


# ===========================================================================
# A hierarquia nova
# ===========================================================================


def test_o_campo_mora_no_PERSONAGEM():
    assert "reset_nick" in AccountSettings.__dataclass_fields__
    assert AccountSettings().reset_nick == "", (
        "Vazio é o padrão, e significa 'não uso reset de time'.")


def test_NENHUMA_cave_tem_conta_de_reset_propria():
    for classe in (BCConfig, HHConfig):
        assert "reset_nick" not in classe.__dataclass_fields__, (
            f"{classe.__name__} voltou a ter conta de reset própria -- e com "
            f"ela voltam os três estados impossíveis.")


def test_o_MODO_da_HH_continua_sendo_da_HH():
    """"Solo ou fada" é decisão DESTA cave: a BC não tem modo nenhum."""
    assert "modo_do_reset" in HHConfig.__dataclass_fields__


# ===========================================================================
# A migração -- o dado do usuário não se perde
# ===========================================================================


def _settings(dados: dict) -> AccountSettings:
    return BotConfig._settings_from_dict(dados)


def test_config_antigo_do_BC_migra():
    st = _settings({"bc": {"reset_nick": "ResetDoBC"}})
    assert st.reset_nick == "ResetDoBC"


def test_config_antigo_da_HH_migra():
    st = _settings({"hh": {"reset_nick": "ResetDaHH"}})
    assert st.reset_nick == "ResetDaHH", (
        "Quem configurou só a HH tem que continuar com reseter -- foi "
        "exatamente esse o caso do defeito de 03/09/2026.")


def test_com_as_DUAS_preenchidas_o_BC_ganha():
    """Era do BC que o bot de fato lia para vetar o farm e travar a entrada."""
    st = _settings({"bc": {"reset_nick": "ResetDoBC"},
                    "hh": {"reset_nick": "ResetDaHH"}})
    assert st.reset_nick == "ResetDoBC"


def test_o_campo_NOVO_ganha_das_chaves_antigas():
    """Config já gravado pela versão nova não pode ser sobrescrito pelo legado."""
    st = _settings({"reset_nick": "ResetDaConta",
                    "bc": {"reset_nick": "Velho"},
                    "hh": {"reset_nick": "MaisVelho"}})
    assert st.reset_nick == "ResetDaConta"


def test_migracao_da_v1_e_v2_tambem_chega_no_personagem():
    st = _settings({"team_reset": {"reset_nick": "MuitoAntigo"}})
    assert st.reset_nick == "MuitoAntigo"


def test_a_v1_NAO_sobrescreve_config_de_hoje():
    st = _settings({"reset_nick": "DeHoje",
                    "team_reset": {"reset_nick": "MuitoAntigo"}})
    assert st.reset_nick == "DeHoje"


def test_espaco_em_branco_e_o_mesmo_que_vazio():
    assert _settings({"reset_nick": "   "}).reset_nick == ""
    assert _settings({"bc": {"reset_nick": "  "}}).reset_nick == ""


def test_a_migracao_LE_DO_BRUTO_e_nao_do_objeto_filtrado():
    """`_filtra` descarta chave que não é campo -- e `reset_nick` não é mais.

    Sem ler do bruto, o valor antigo seria jogado fora em silêncio: nenhum erro,
    nenhum aviso, e o usuário veria a conta de reset em branco.
    """
    fonte = inspect.getsource(BotConfig._settings_from_dict)
    arvore = ast.parse(textwrap.dedent(fonte))
    leituras = {ast.unparse(n) for n in ast.walk(arvore)
                if isinstance(n, ast.Call)}

    assert any('dados.get(bloco)' in leitura for leitura in leituras), (
        "a migração deixou de ler os blocos crus de cave")
    # PELOS CAMPOS DA DATACLASS, e não pelo texto: o comentário de `BCConfig`
    # cita `AccountSettings.reset_nick` para dizer onde o campo foi morar, e
    # uma busca no texto acharia a explicação e reprovaria.
    assert "reset_nick" not in BCConfig.__dataclass_fields__


def test_ida_e_volta_pelo_disco_preserva_o_nick():
    cfg = BotConfig()
    st = _settings({"reset_nick": "ResetDaConta"})
    bruto = BotConfig.to_dict(cfg)  # só para provar que `to_dict` roda
    assert isinstance(bruto, dict)

    # `asdict` grava o campo no nível da conta, e a leitura o encontra lá.
    from dataclasses import asdict
    de_volta = _settings(asdict(st))
    assert de_volta.reset_nick == "ResetDaConta"
    assert "reset_nick" not in asdict(st)["bc"]
    assert "reset_nick" not in asdict(st)["hh"]


# ===========================================================================
# As DUAS interfaces -- regra permanente do projeto
# ===========================================================================


def test_a_WEB_mostra_o_campo_na_aba_PERSONAGEM():
    html = (RAIZ / "web/index.html").read_text(encoding="utf-8")
    aba = html[html.index('id="aba-personagem"'):html.index('id="aba-teclas"')]

    assert '<select id="ed-reset-nick"' in aba, (
        "o seletor de reseter não está na aba Personagem da interface web")
    assert '<input id="ed-reset-nick"' not in html, "voltou a ser texto livre"
    assert 'id="ed-hh-reset"' not in html, (
        "a aba da HH voltou a ter seletor próprio")

    bc = html[html.index('id="aba-bc"'):html.index('id="aba-hh"')]
    assert "ed-reset-nick" not in bc, "a aba da BC voltou a ter o seletor"


def test_a_WEB_grava_o_nick_no_nivel_da_CONTA():
    js = (RAIZ / "web/main.js").read_text(encoding="utf-8")
    assert 'reset_nick: $("#ed-reset-nick").value.trim()' in js
    assert 'reset_nick: ($("#ed-hh-reset")' not in js


def test_a_PONTE_expoe_e_grava_no_nivel_da_CONTA():
    py = (RAIZ / "blazesbot/web_app.py").read_text(encoding="utf-8")
    assert '"reset_nick": st.reset_nick' in py, "a ponte não expõe o campo"
    assert "st.bc.reset_nick" not in py
    assert "st.hh.reset_nick" not in py


def test_o_dist_foi_reconstruido():
    """O app abre `dist/`, e o `.bat` não faz build. Ver `CLAUDE.md`."""
    dist = (RAIZ / "dist/index.html").read_text(encoding="utf-8")
    assert 'id="ed-reset-nick"' in dist
    assert 'id="ed-hh-reset"' not in dist, (
        "o `dist/` está mais velho que o `web/`: rode `npm run build`")


# ===========================================================================
# O TOTAL DE CLIQUES DA VENDA -- mesma promoção, mesmo risco
# ===========================================================================
#
# 09/09/2026: *"a 'quantidade de cliques' que hoje está na configuração de BC,
# ela deve ir para a aba do personagem, para valer para todas as caves"*.
#
# O número não descreve a cave -- descreve quanta bolsa este personagem tem
# para esvaziar. Ver `docs/decisoes/venda.md`, "O total de cliques".


def test_o_total_de_cliques_mora_no_PERSONAGEM():
    from blazesbot.config import BCVendor, HHVendor

    assert "sell_clicks" in AccountSettings.__dataclass_fields__
    for classe in (BCVendor, HHVendor):
        assert "sell_clicks" not in classe.__dataclass_fields__, (
            f"{classe.__name__} voltou a ter total de cliques próprio")
        # O TETO DE PASSADAS continua de cave: ele é do trajeto, não da bolsa.
        assert "max_sell_passes" in classe.__dataclass_fields__


def test_config_antigo_do_BC_migra_os_cliques():
    st = _settings({"bc": {"vendor": {"sell_clicks": 72}}})
    assert st.sell_clicks == 72


def test_config_antigo_da_HH_migra_os_cliques():
    st = _settings({"hh": {"vendor": {"sell_clicks": 48}}})
    assert st.sell_clicks == 48


def test_com_os_DOIS_divergindo_o_BC_ganha():
    """Na conta do usuário eles divergiam de verdade: BC 72, HH 24."""
    st = _settings({"bc": {"vendor": {"sell_clicks": 72}},
                    "hh": {"vendor": {"sell_clicks": 24}}})
    assert st.sell_clicks == 72


def test_o_campo_NOVO_ganha_do_legado():
    st = _settings({"sell_clicks": 96,
                    "bc": {"vendor": {"sell_clicks": 72}}})
    assert st.sell_clicks == 96


def test_o_derivado_RECEBE_o_total_em_vez_de_le_lo():
    """Propriedade que fosse buscar em `AccountSettings` faria a configuração
    da cave depender da conta -- o contrário da direção da árvore."""
    from blazesbot.config import BCVendor

    v = BCVendor()
    assert not hasattr(v, "passadas_necessarias"), (
        "a propriedade antiga voltou, e ela lê um campo que não existe mais")
    assert v.passadas_para(72) == 3, v.passadas_para(72)
    assert v.passadas_para(24) == 1
    assert v.passadas_para(0) >= 1, "zero cliques não pode virar zero passadas"


def test_a_venda_le_o_total_do_PERSONAGEM():
    from blazesbot.bot.vendedor import JanelaDeVenda

    fonte = inspect.getsource(JanelaDeVenda.sell_from_slot)
    assert "ctx.settings.sell_clicks" in fonte
    assert "cfg.sell_clicks" not in fonte


def test_a_interface_moveu_o_seletor_de_cliques_para_o_PERSONAGEM():
    html = (RAIZ / "web/index.html").read_text(encoding="utf-8")
    pessoa = html[html.index('id="aba-personagem"'):html.index('id="aba-teclas"')]
    assert 'id="ed-cliques-venda"' in pessoa
    bc_html = html[html.index('id="aba-bc"'):html.index('id="aba-hh"')]
    assert "ed-cliques-venda" not in bc_html

    js = (RAIZ / "web/main.js").read_text(encoding="utf-8")
    assert 'sell_clicks: Number($("#ed-cliques-venda").value || 24)' in js
    py = (RAIZ / "blazesbot/web_app.py").read_text(encoding="utf-8")
    assert '"sell_clicks": st.sell_clicks' in py
    assert "st.bc.vendor.sell_clicks" not in py

    dist = (RAIZ / "dist/index.html").read_text(encoding="utf-8")
    i_pessoa = dist.index('id="aba-personagem"')
    i_teclas = dist.index('id="aba-teclas"')
    assert 'id="ed-cliques-venda"' in dist[i_pessoa:i_teclas], (
        "o `dist/` está mais velho que o `web/`: rode `npm run build`")
