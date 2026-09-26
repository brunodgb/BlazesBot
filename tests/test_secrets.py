"""A senha nunca vai para o disco em texto puro."""
import pytest

from blazesbot.core import secrets


def test_sem_dpapi_a_cifra_RECUSA_em_vez_de_devolver_o_texto(monkeypatch):
    """Devolvia o texto puro, e a senha ia para o `config.json` em claro."""
    monkeypatch.setattr(secrets, "_HAS_DPAPI", False)
    with pytest.raises(RuntimeError):
        secrets.encrypt("senha")


def test_senha_vazia_continua_vazia_mesmo_sem_dpapi(monkeypatch):
    monkeypatch.setattr(secrets, "_HAS_DPAPI", False)
    assert secrets.encrypt("") == ""


def test_texto_puro_legado_ainda_e_lido():
    assert secrets.decrypt("antiga") == "antiga"


def test_a_cifra_recusada_chega_na_tela_como_erro():
    """Sem isto o erro sumia no `chamar()` do JS, e a tela dizia "senha
    gravada" com a senha antiga valendo (achado da revisão de segurança)."""
    from pathlib import Path

    from blazesbot.web_app import Api

    class _App:
        def definir_senha(self, _uid, _nova):
            raise RuntimeError("sem DPAPI")

    assert Api(_App()).definir_senha("u", "x") == {"ok": False, "erro": "sem DPAPI"}

    fonte = (Path(__file__).resolve().parent.parent / "web" / "main.js").read_text(
        encoding="utf-8")
    trecho = fonte.split('chamar("definir_senha", uid')[1][:300]
    assert trecho.index("r.ok === false") < trecho.index('t("msg_senha_gravada")')
    # E no editor da conta: senha recusada não segue para o `salvar_personagem`.
    editor = fonte.split('chamar("definir_senha", contaUidEditando')[1][:600]
    assert editor.index("rs.ok === false") < editor.index("salvar_personagem")


@pytest.mark.skipif(not secrets.dpapi_available(), reason="sem DPAPI")
def test_ida_e_volta_com_dpapi():
    cifrada = secrets.encrypt("s3nh@")
    assert secrets.is_encrypted(cifrada)
    assert "s3nh@" not in cifrada
    assert secrets.decrypt(cifrada) == "s3nh@"
