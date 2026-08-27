"""Configuração que o usuário edita tem que SOBREVIVER a fechar o bot.

Este arquivo nasceu de um defeito real: o "Limpar a bolsa a cada N voltas" era
GRAVADO certo no `config.json` e ignorado na LEITURA — `_app_from_dict`
reconstruía o `AppConfig` só com `enabled` e `steps`, e o resto caía no default
do dataclass. Na tela, o valor voltava para 10 toda vez que o bot abria.

O teste é de IDA E VOLTA porque é assim que o defeito aparece: gravar sozinho
funcionava, ler sozinho funcionava, e só a viagem completa mostrava a perda.
"""
import json

import pytest

from blazesbot.config import DEFAULT_CONFIG_PATH, Account, BotConfig


def _ida_e_volta(tmp_path, muda):
    """Aplica `muda` numa conta, grava, relê do disco e devolve a conta lida."""
    caminho = tmp_path / "config.json"
    cfg = BotConfig()
    cfg.accounts.append(Account(login="teste"))
    muda(cfg.accounts[0])
    cfg.save(caminho)
    return BotConfig.load(caminho).accounts[0]


def test_apagar_lixo_a_cada_sobrevive(tmp_path):
    """O defeito relatado: o valor voltava para 10 ao reabrir o bot."""
    conta = _ida_e_volta(tmp_path, lambda c: setattr(
        c.settings.app, "apagar_lixo_a_cada", 37))
    assert conta.settings.app.apagar_lixo_a_cada == 37


def test_zero_sobrevive_e_nao_vira_o_default(tmp_path):
    """`0` = nunca limpar, e é justamente o valor que um `or 10` descuidado
    transformaria de volta em 10."""
    conta = _ida_e_volta(tmp_path, lambda c: setattr(
        c.settings.app, "apagar_lixo_a_cada", 0))
    assert conta.settings.app.apagar_lixo_a_cada == 0


def test_arquivo_antigo_sem_o_campo_ganha_o_padrao(tmp_path):
    """Config gravada por uma versão anterior não pode quebrar a leitura."""
    caminho = tmp_path / "config.json"
    caminho.write_text(json.dumps({
        "accounts": [{"login": "velho",
                      "settings": {"app": {"enabled": True, "steps": []}}}],
    }), encoding="utf-8")
    conta = BotConfig.load(caminho).accounts[0]
    assert conta.settings.app.apagar_lixo_a_cada == 10
    assert conta.settings.app.enabled is True


def test_o_resto_do_APP_continua_indo_e_voltando(tmp_path):
    """Guarda contra uma correção que conserte um campo e quebre outro."""
    def muda(c):
        c.settings.app.enabled = True
        c.settings.app.apagar_lixo_a_cada = 5
        c.settings.app.steps[0].key = "F1"
        c.settings.app.steps[0].delay_ms = 1234

    conta = _ida_e_volta(tmp_path, muda)
    assert conta.settings.app.enabled is True
    assert conta.settings.app.apagar_lixo_a_cada == 5
    assert conta.settings.app.steps[0].key == "F1"
    assert conta.settings.app.steps[0].delay_ms == 1234


@pytest.mark.parametrize("campo, valor", [
    ("apagar_lixo_a_cada", 3),
    ("travar_posicao", False),
    ("shuffle_apos_n_voltas", 15),
    # A LINHA 0 da macro: o tempo depois do TAB (26/08/2026).
    ("espera_depois_do_tab_ms", 1500),
    # Campos internos (não expostos na UI, mas salvos no config.json)
    ("_base_pos_x", 123),
    ("_base_pos_y", 456),
])
def test_todo_campo_do_AppConfig_sobrevive(tmp_path, campo, valor):
    """LISTA VIVA: todo campo novo do `AppConfig` (fora `steps`) entra aqui.

    O dataclass sozinho não basta — `_app_from_dict` precisa ler o campo
    explicitamente, e é esse esquecimento que este teste pega.
    """
    conta = _ida_e_volta(tmp_path, lambda c: setattr(
        c.settings.app, campo, valor))
    assert getattr(conta.settings.app, campo) == valor


def test_a_lista_acima_cobre_o_AppConfig_inteiro():
    """Se alguém acrescentar um campo ao `AppConfig` e esquecer do teste, aqui
    reprova — que é o único jeito de a 'lista viva' continuar viva."""
    from dataclasses import fields

    from blazesbot.config import AppConfig

    cobertos = {"enabled", "steps", "apagar_lixo_a_cada", "travar_posicao",
                "shuffle_apos_n_voltas", "espera_depois_do_tab_ms",
                # Campos internos: salvos no config.json, não expostos na UI
                "_base_pos_x", "_base_pos_y"}
    faltando = {f.name for f in fields(AppConfig)} - cobertos
    assert not faltando, (
        f"campo(s) novo(s) no AppConfig sem teste de ida e volta: {faltando}")


def test_o_config_de_verdade_tem_o_campo():
    """Sanidade no arquivo real: o campo é gravado (o defeito era só na leitura)."""
    if not DEFAULT_CONFIG_PATH.is_file():
        pytest.skip("sem config.json neste ambiente")
    dados = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    for conta in dados.get("accounts", []):
        app = (conta.get("settings") or {}).get("app") or {}
        if app:
            assert "apagar_lixo_a_cada" in app, conta.get("login")


# ===========================================================================
# `AccountSettings`: a MESMA armadilha, um nível acima
# ===========================================================================
#
# `usar_catador` foi acrescentado ao `AccountSettings` e esquecido no
# `_settings_from_dict`. Resultado relatado pelo usuário: *"a flag está
# resetando para false sozinha"* -- gravava certo e voltava ao padrão a cada
# abertura do bot. É letra por letra o defeito que abre este arquivo.
#
# A "lista viva" do `AppConfig` acima funciona, mas depende de alguém lembrar de
# atualizá-la. Aqui a varredura é AUTOMÁTICA: percorre os campos escalares do
# dataclass, inventa um valor diferente do padrão para cada um e confere que ele
# sobreviveu à ida e volta. Campo novo entra coberto sem ninguém fazer nada --
# que é o único jeito de a cobertura não depender de memória.

def _valor_diferente(campo, atual):
    """Um valor válido e DIFERENTE do padrão, para o tipo do campo."""
    if campo.name == "mount_speed_pct":
        # Não é um int qualquer: tem que ser uma velocidade que existe.
        from blazesbot.config import MOUNT_SPEEDS
        return next(v for v in MOUNT_SPEEDS if v != atual)
    if isinstance(atual, bool):
        return not atual
    if isinstance(atual, int):
        return atual + 7
    if isinstance(atual, float):
        return atual + 1.5
    if isinstance(atual, str):
        return (atual or "") + "X"
    return None


def _campos_escalares(clazz):
    from dataclasses import fields
    padrao = clazz()
    for campo in fields(clazz):
        atual = getattr(padrao, campo.name)
        if isinstance(atual, (bool, int, float, str)):
            yield campo, atual


@pytest.mark.parametrize(
    "nome, valor",
    [(c.name, _valor_diferente(c, atual))
     for c, atual in _campos_escalares(__import__(
         "blazesbot.config", fromlist=["AccountSettings"]).AccountSettings)],
)
def test_todo_campo_escalar_do_AccountSettings_sobrevive(tmp_path, nome, valor):
    """Varredura AUTOMÁTICA -- campo novo entra coberto sozinho.

    Foi assim que `usar_catador` passou: ele estava no dataclass, era gravado no
    `config.json`, aparecia nas duas interfaces, e simplesmente não era lido de
    volta. Nenhum teste de comportamento pegaria isso, porque não há
    comportamento errado -- há um campo que não faz a viagem inteira.
    """
    conta = _ida_e_volta(tmp_path, lambda c: setattr(c.settings, nome, valor))

    assert getattr(conta.settings, nome) == valor, (
        f"{nome} não sobreviveu à ida e volta: gravou {valor!r} e leu "
        f"{getattr(conta.settings, nome)!r}. Falta ler o campo em "
        "`BotConfig._settings_from_dict`."
    )


def test_usar_catador_sobrevive_em_VARIAS_contas(tmp_path):
    """O usuário pediu explicitamente: "pode ser usado em várias contas".

    O campo é POR CONTA -- uma conta tem o pet com auto pick e outra não --,
    então marcar numa não pode marcar nem desmarcar as outras.
    """
    caminho = tmp_path / "config.json"
    cfg = BotConfig()
    for nome, liga in (("com_pet", False), ("sem_pet", True), ("outra", True)):
        conta = Account(login=nome)
        conta.settings.usar_catador = liga
        cfg.accounts.append(conta)
    cfg.save(caminho)

    lido = {c.login: c.settings.usar_catador
            for c in BotConfig.load(caminho).accounts}

    assert lido == {"com_pet": False, "sem_pet": True, "outra": True}, lido


# ===========================================================================
# O PISO DE 100 ms EM TODO CAMPO DE TEMPO DO APP — 26/08/2026
# ===========================================================================
#
# *"O mínimo vai ser 100ms em todos os campos do APP."*
#
# Zero deixava duas teclas saírem no mesmo instante, e o cliente engole a
# segunda — o mesmo defeito do botão "Sell" da venda, espalhado pela sequência.

def test_a_linha_da_macro_nasce_com_o_piso():
    from blazesbot.config import MINIMO_DE_ESPERA_DO_APP_MS, AppStep

    assert MINIMO_DE_ESPERA_DO_APP_MS == 100
    assert AppStep(key="1", delay_ms=0).delay_ms == 100
    assert AppStep(key="1", delay_ms=40).delay_ms == 100
    assert AppStep(key="1", delay_ms=900).delay_ms == 900


def test_o_piso_vale_para_o_ARQUIVO_salvo_por_versao_antiga(tmp_path):
    """O piso é aplicado na LEITURA, não só na tela: quem já tem `0 ms` gravado
    sobe corrigido em vez de continuar com o defeito."""
    caminho = tmp_path / "config.json"
    caminho.write_text(json.dumps({"accounts": [{
        "login": "velho",
        "settings": {"app": {"enabled": True, "espera_depois_do_tab_ms": 0,
                             "steps": [{"key": "1", "delay_ms": 0}]}},
    }]}), encoding="utf-8")

    app = BotConfig.load(caminho).accounts[0].settings.app
    assert app.steps[0].delay_ms == 100
    assert app.espera_depois_do_tab_ms == 100


def test_sao_VINTE_linhas_mais_a_linha_0():
    """*"Pode colocar de 1..20 agora, para padronizar em 20 linhas no total."*"""
    from blazesbot.config import PASSOS_DO_APP, AppConfig

    assert PASSOS_DO_APP == 20
    assert len(AppConfig().steps) == 20
