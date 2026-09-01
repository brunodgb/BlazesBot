"""A LINHA 0 DA MACRO: o TAB, nas DUAS interfaces.

Pedido do usuário em 26/08/2026:

    *"Como a macro 0, mas sem poder editar o botão e não pode colocar em outro
     lugar, sempre será a primeira, e o tempo sim será editável; aquele 1
     segundo após o tab será isso."*

POR QUE ELA NÃO É UM `AppStep`
==============================

Como linha de verdade ela obrigaria `passos_ativos`, `uma_volta` e a régua do
inalcançável (que conta LINHAS da macro) a conhecer uma exceção que não bate em
ninguém. A tela DESENHA como linha 0; o executor lê um número de outro lugar.

É por isso que o teste mais importante deste arquivo é o que confere que ela
**fica fora da lista de passos** nas duas telas: se ela vazar para lá, o bot
passa a mandar a tecla de alvo no meio da rotação — que é exatamente o defeito
que a virada de 25/08/2026 tirou do caminho.
"""
from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


def _ler(caminho: str) -> str:
    return (RAIZ / caminho).read_text(encoding="utf-8")


# -- a web ----------------------------------------------------------------

def test_web_desenha_a_linha_0_com_a_tecla_do_next_target():
    """Espelho, e não um "TAB" escrito na tela: quem trocou a tecla veria a
    tela mentir sobre o que o bot aperta."""
    js = _ler("web/main.js")

    assert 'trTab.className = "linha-do-tab"' in js
    assert "keys.next_target" in js
    assert 'tdNT.textContent = "0"' in js


def test_web_deixa_a_tecla_da_linha_0_DESABILITADA():
    js = _ler("web/main.js")
    assert "inpKT.readOnly = true; inpKT.disabled = true;" in js


def test_web_NAO_manda_a_linha_0_como_passo_da_macro():
    """O teste que importa. A linha 0 não tem a classe `app-linha`, e é isso
    que a mantém fora de `steps` e fora da prévia."""
    js = _ler("web/main.js")

    assert js.count('$$("#corpo-app tr")') == 0, (
        "algum seletor pega TODAS as linhas e vai levar o TAB junto")
    assert js.count('$$("#corpo-app tr.app-linha")') == 2, (
        "os passos e a prévia precisam selecionar só as linhas da macro")


def test_web_transporta_o_tempo_da_linha_0_nos_dois_sentidos():
    js = _ler("web/main.js")
    ponte = _ler("blazesbot/web_app.py")

    assert "ed-app-espera-tab" in js
    assert "espera_depois_do_tab_ms" in js
    assert '"espera_depois_do_tab_ms": st.app.espera_depois_do_tab_ms' in ponte
    assert "st.app.espera_depois_do_tab_ms = max(" in ponte


# -- a GUI ----------------------------------------------------------------

def test_gui_desenha_a_linha_0_e_a_deixa_somente_leitura():
    gui = _ler("blazesbot/gui/account_dialog.py")

    assert "self.app_tecla_do_tab" in gui
    assert "self.app_tecla_do_tab.setReadOnly(True)" in gui
    assert "st.keys.next_target" in gui


def test_gui_carrega_e_grava_o_tempo_da_linha_0():
    gui = _ler("blazesbot/gui/account_dialog.py")

    assert "self.sp_app_espera_tab.setValue(st.app.espera_depois_do_tab_ms)" in gui
    assert "st.app.espera_depois_do_tab_ms = self.sp_app_espera_tab.value()" in gui


def test_gui_NAO_poe_a_linha_0_em_app_linhas():
    """`app_linhas` é o que vira `steps`. A linha 0 tem widgets próprios."""
    gui = _ler("blazesbot/gui/account_dialog.py")

    assert "self.app_linhas.append((tecla, espera))" in gui
    assert "self.app_linhas.append((self.app_tecla_do_tab" not in gui


# -- o piso, nas duas ------------------------------------------------------

@pytest.mark.parametrize("arquivo, trecho", [
    ("blazesbot/gui/account_dialog.py",
     "espera.setRange(MINIMO_DE_ESPERA_DO_APP_MS, 10000)"),
    ("blazesbot/gui/account_dialog.py",
     "self.sp_app_espera_tab.setRange(MINIMO_DE_ESPERA_DO_APP_MS, 10000)"),
    # O piso saiu da espera da macro e virou o piso de QUALQUER delay
    # (26/08/2026), então agora ele mora numa constante que os dois lados citam.
    ("web/main.js", "const MINIMO_DELAY_MS = 100;"),
    ("web/main.js", "const MINIMO_ESPERA_APP = MINIMO_DELAY_MS;"),
    ("blazesbot/config.py", "MINIMO_DELAY_MS = 100"),
    ("blazesbot/config.py", "MINIMO_DE_ESPERA_DO_APP_MS = MINIMO_DELAY_MS"),
    ("blazesbot/web_app.py", "MINIMO_DE_ESPERA_DO_APP_MS,"),
])
def test_o_piso_de_100ms_esta_nas_duas_telas(arquivo: str, trecho: str):
    """*"O mínimo vai ser 100ms em todos os campos do APP."*

    E a ponte reaplica o piso: "a tela impõe" não é garantia, é boa vontade.
    """
    assert trecho in _ler(arquivo)


# -- o piso valendo para TODO campo de tempo, não só os do APP -------------

def test_todo_campo_de_tempo_da_web_tem_piso_de_100ms():
    """*"tudo que for delay ou intervalo de tempo padroniza em MS e minimo
    100 ms"* (26/08/2026).

    Trava o `min` dos campos de tempo do `index.html`. A conversão para segundos
    (o que o `config.json` guarda) é conferida em
    `test_o_tempo_vai_e_volta_sem_perda`.
    """
    html = _ler("web/index.html")

    for campo in ("in-delay-lancamento", "ed-ataque-delay"):
        assert f'id="{campo}" type="number" min="100"' in html, campo
        # E o rótulo tem de dizer ms, senão o usuário digita segundos.
        assert "(ms)" in html


def test_o_tempo_vai_e_volta_sem_perda():
    """A tela fala ms, o arquivo guarda segundos: a ida e a volta têm de fechar.

    Se não fecharem, abrir e salvar a tela sem tocar em nada MUDA a configuração
    -- e o intervalo de ataque é a parte mais medida do projeto.
    """
    from blazesbot.config import (
        MINIMO_DELAY_MS,
        ms_para_segundos,
        segundos_para_ms,
    )

    for segundos in (0.1, 0.3, 0.5, 5.0, 8.0, 12.0, 30.0):
        assert ms_para_segundos(segundos_para_ms(segundos)) == segundos

    # Valor inválido no arquivo sobe para o piso, não vira zero.
    for invalido in (0, 0.0, None, -1):
        assert segundos_para_ms(invalido) == MINIMO_DELAY_MS
        assert ms_para_segundos(invalido) == MINIMO_DELAY_MS / 1000


def test_as_vinte_linhas_valem_nas_duas():
    """*"Pode colocar de 1..20 agora, para padronizar em 20 linhas no total."*"""
    from blazesbot.config import PASSOS_DO_APP

    assert PASSOS_DO_APP == 20
    # A web lê o número da ponte (`constantes.passos_app`); o fallback do JS
    # não pode ficar preso no valor antigo.
    assert "constantes.passos_app : 20" in _ler("web/main.js")
    assert '"passos_app": PASSOS_DO_APP' in _ler("blazesbot/web_app.py")


def test_o_dist_foi_recompilado():
    """`web/*` só chega ao usuário depois de `npm run build`. Editar o fonte e
    esquecer o build é uma tela que não muda e um bug que não existe."""
    assets = sorted((RAIZ / "dist" / "assets").glob("index-*.js"))
    assert assets, "dist/assets sem bundle"
    bundle = max(assets, key=lambda p: p.stat().st_mtime).read_text(
        encoding="utf-8")
    assert "linha-do-tab" in bundle, "o `dist` está velho — rode `npm run build`"


# ===========================================================================
# O ALVO DO APP VEM PELO MESMO CAMINHO DO BC — 26/08/2026
# ===========================================================================
#
# *"Sobre o HP do target, está sendo analisado como fazemos no Gun Witch? Pois
# lá funciona perfeitamente a análise do HP, nome, level e todas as informações
# do mob."*
#
# NÃO ESTAVA. O BC lê pelo `TargetHybrid`, que chama `Memory.alvo_atual()`
# direto. O APP passava a mesma leitura pelo `_ler` do supervisor, e o `_ler`
# tem um portão: `critical_ok()` — que exige `hp()`, `max_hp()` E `position()`
# DO PERSONAGEM. Nenhuma das três tem relação com o alvo.

def test_o_APP_le_o_alvo_pelo_TargetHybrid():
    sup = _ler("blazesbot/bot/supervisor.py")

    assert "from ..core.target_hybrid import TargetHybrid" in sup
    assert "alvo_hibrido = TargetHybrid(logger=log)" in sup
    assert "alvo_hibrido.entidade_do_alvo(self.pid)" in sup
    assert "alvo_hibrido.id_do_alvo(self.pid)" in sup


def test_a_leitura_do_ALVO_nao_passa_mais_pelo_portao_do_PERSONAGEM():
    """`position()` é uma cadeia de ponteiros que falha de vez em quando. Uma
    leitura ruim da POSIÇÃO vetava a leitura do ALVO, e o executor recebia
    `None` — o mesmo `None` de "a entidade sumiu do array"."""
    sup = _ler("blazesbot/bot/supervisor.py")
    inicio = sup.index("def _rodar_modo_app")
    fim = sup.index("def run(self)", inicio)
    trecho = sup[inicio:fim]

    assert "_ler(memoria_do_pet.alvo_atual)" not in trecho
    assert "_ler(memoria_do_pet.id_do_alvo)" not in trecho
    # O portão continua valendo para o que ele foi feito: o ESTADO DO
    # PERSONAGEM -- as leituras que de fato dependem de `hp`, `max_hp` e
    # `position` estarem sãs.
    for leitura in ("vida_pct", "is_sitting"):
        assert f"_ler(memoria_do_pet.{leitura})" in trecho, leitura

    # A FLAG DE COMBATE SAIU DO PORTÃO TAMBÉM, e pela MESMA razão do alvo:
    # `in_battle` é um byte direto no struct do jogador, e uma leitura ruim da
    # POSIÇÃO não tem por que vetá-la. Quem veta devolve `None`, e `None` é
    # indistinguível de "não estou em batalha" para quem consome -- foi assim
    # que a régua do inalcançável começou a errar.
    assert "_ler(memoria_do_pet.in_battle)" not in trecho, (
        "in_battle voltou para o portão do PERSONAGEM")
    assert "_ler_simples(memoria_do_pet.in_battle)" in trecho


def test_o_handle_do_hibrido_e_FECHADO_na_saida():
    """Ele abre o próprio handle (mesmo arranjo do BC). Sem o `finally`, uma
    exceção deixaria um handle por sessão de modo APP — e o modo APP é
    reiniciado a cada volta do laço de vida."""
    sup = _ler("blazesbot/bot/supervisor.py")
    assert "alvo_hibrido.fechar()" in sup


def test_o_hibrido_REABRE_o_processo_quando_o_PID_muda():
    """Relogin troca o PID, e um handle guardado vira leitura de processo
    morto, em silêncio. O `Memory` do pet, aberto uma vez em
    `_rodar_modo_app`, não tem isso — o híbrido tem."""
    import inspect

    from blazesbot.core.target_hybrid import TargetHybrid

    fonte = inspect.getsource(TargetHybrid._processo)
    assert "self._pid_aberto == pid" in fonte
    assert "self.fechar()" in fonte
