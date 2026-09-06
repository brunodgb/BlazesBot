"""Ordem das contas, identidade estável (`uid`) e o rótulo de grupo.

Pedido do usuário em 28/08/2026: reordenar as contas arrastando, agrupar
visualmente, e o bot lembrar a ordem depois de reiniciar.

Três regras que estes testes existem para travar, e todas as três já tinham
defeito real atrás:

1. **A ORDEM É A ORDEM DO ARRAY.** Não existe campo de ordem, e não pode existir:
   seriam duas fontes de verdade para a mesma coisa.
2. **A IDENTIDADE DA CONTA NA INTERFACE É O `uid`, NUNCA O ÍNDICE.** Era o
   índice, e com a tabela reordenável isso grava senha na conta errada.
3. **`Account.grupo` É RÓTULO VISUAL.** Nenhum caminho do bot pode ler dele:
   time do APP é `time_logins` (por login, no líder) e party do BC é
   `accept_team_invites`.

Ver `docs/decisoes/interface.md` e `docs/INVARIANTES.md`.
"""

from __future__ import annotations

import ast
import re
import struct
from pathlib import Path

import pytest

from blazesbot.config import (
    ICONE_DO_APP,
    LIMITE_DO_NOME_DO_GRUPO,
    Account,
    BotConfig,
)

RAIZ = Path(__file__).resolve().parents[1]


def _ler(rel: str) -> str:
    return (RAIZ / rel).read_text(encoding="utf-8")


def _cfg(*logins: str) -> BotConfig:
    cfg = BotConfig()
    cfg.accounts = [Account(login=x) for x in logins]
    for c in cfg.accounts:
        c.garantir_uid()
    return cfg


# -- 1. a ordem é o array, e sobrevive ao disco ----------------------------

def test_a_ordem_vai_e_volta_pelo_disco():
    """*"o bot lembrar a posição das contas após reiniciar"*."""
    cfg = _cfg("a", "b", "c", "d")
    uids = [c.uid for c in cfg.accounts]
    cfg.reordenar_contas([uids[2], uids[0], uids[3], uids[1]])

    volta = BotConfig.from_dict(cfg.to_dict())
    assert [c.login for c in volta.accounts] == ["c", "a", "d", "b"]
    assert [c.uid for c in volta.accounts] == [uids[2], uids[0], uids[3], uids[1]]


def test_NAO_existe_campo_de_ordem_em_Account():
    """Ordem num campo seria a SEGUNDA fonte de verdade, e a pergunta "se ele
    discordar do array, quem manda?" não tem resposta boa."""
    campos = set(Account().__dict__)
    for proibido in ("sort_order", "ordem", "index", "indice", "posicao_lista"):
        assert proibido not in campos, (
            f"'{proibido}' duplicaria a ordem que o array já guarda")


# -- 2. reordenar não pode perder conta ------------------------------------

def test_reordenar_nao_perde_conta():
    """Perder conta aqui é perder a senha cifrada dela, sem desfazer."""
    cfg = _cfg("a", "b", "c")
    uids = [c.uid for c in cfg.accounts]

    # Citando só uma: as outras vão para o fim, na ordem que tinham.
    cfg.reordenar_contas([uids[2]])
    assert [c.login for c in cfg.accounts] == ["c", "a", "b"]

    # Uid inexistente e uid repetido não podem descartar ninguém.
    cfg.reordenar_contas(["fantasma", uids[0], uids[0], ""])
    assert sorted(c.login for c in cfg.accounts) == ["a", "b", "c"]
    assert len(cfg.accounts) == 3


def test_reordenar_com_uid_REPETIDO_nao_perde_conta():
    """Achado da revisão do Codex: um índice por `uid` guardava só a ÚLTIMA das
    contas com uid repetido, e a primeira desaparecia do resultado.

    `config.json` é editado à mão (o usuário duplica conta copiando o bloco),
    então uid repetido é cenário real, não hipótese.
    """
    cfg = BotConfig()
    cfg.accounts = [Account(login="a", uid="X"), Account(login="b", uid="X"),
                    Account(login="c")]
    cfg.reordenar_contas(["X"])
    assert sorted(c.login for c in cfg.accounts) == ["a", "b", "c"]


def test_reordenar_devolve_se_MUDOU():
    """O retorno é o gatilho de gravação: gravar sem mudança é escrita à toa."""
    cfg = _cfg("a", "b")
    uids = [c.uid for c in cfg.accounts]
    assert cfg.reordenar_contas(uids) is False
    assert cfg.reordenar_contas([uids[1], uids[0]]) is True


# -- 3. o uid é estável, único e texto ------------------------------------

def test_uid_e_estavel_e_unico():
    cfg = _cfg("a", "b", "c")
    antes = [c.uid for c in cfg.accounts]
    for c in cfg.accounts:          # idempotente
        c.garantir_uid()
    assert [c.uid for c in cfg.accounts] == antes
    assert len(set(antes)) == 3


def test_uid_repetido_no_arquivo_e_desfeito_na_leitura():
    cfg = BotConfig.from_dict({"accounts": [
        {"login": "a", "uid": "MESMO"}, {"login": "b", "uid": "MESMO"}]})
    uids = [c.uid for c in cfg.accounts]
    assert len(set(uids)) == 2, "duas contas com o mesmo uid = escrita na errada"


@pytest.mark.parametrize("bruto", [123, None, "  ", "", 0])
def test_uid_sempre_vira_TEXTO(bruto: object):
    """Achado da revisão: `uid` numérico ficava `int` e as buscas comparam com
    texto -- a conta existia e nenhuma escrita a encontrava."""
    cfg = BotConfig.from_dict({"accounts": [{"login": "a", "uid": bruto}]})
    conta = cfg.accounts[0]
    assert isinstance(conta.uid, str) and conta.uid.strip()
    assert cfg.conta_por_uid(conta.uid) is conta


def test_a_TELA_nunca_recebe_uid_repetido():
    """Fecha o último caminho apontado na revisão: a leitura do arquivo desfaz
    uid repetido, mas conta criada em MEMÓRIA não passa por lá -- e a tela
    endereça por uid, então duas iguais são indistinguíveis para ela (arrastar a
    segunda moveria a primeira). `contas()` normaliza antes de responder."""
    from blazesbot.web_app import _App

    cfg = BotConfig()
    cfg.accounts = [Account(login="a", uid="X"), Account(login="b", uid="X"),
                    Account(login="c", uid="X")]
    app = _App.__new__(_App)
    app._cfg = cfg
    app.config = cfg

    uids = [linha["uid"] for linha in app.contas()]
    assert len(set(uids)) == 3, uids
    assert all(u.strip() for u in uids)
    # E cada uid entregue tem de achar a conta certa.
    for linha, conta in zip(app.contas(), cfg.accounts, strict=True):
        assert cfg.conta_por_uid(linha["uid"]) is conta


def test_garantir_uids_unicos_e_idempotente():
    """Chamado a cada leitura da tabela: não pode trocar uid de quem já tem um --
    trocar apontaria as escritas em voo para outra conta."""
    cfg = _cfg("a", "b", "c")
    antes = [c.uid for c in cfg.accounts]
    cfg.garantir_uids_unicos()
    cfg.garantir_uids_unicos()
    assert [c.uid for c in cfg.accounts] == antes


def test_conta_por_uid_e_reordenar_CONCORDAM():
    """Com uid repetido, as duas têm de apontar para a MESMA conta -- senão uma
    escrita acerta uma e o arraste opera na outra."""
    cfg = BotConfig()
    cfg.accounts = [Account(login="a", uid="X"), Account(login="b", uid="X")]
    achada = cfg.conta_por_uid("X")
    cfg.reordenar_contas(["X"])
    assert cfg.accounts[0] is achada


# -- 4. a interface não endereça conta por índice --------------------------

def test_a_ponte_web_NAO_endereca_conta_por_indice():
    """Era o índice, e a tabela reordenável quebra a premissa: com a ordem da
    tela diferente da do disco, `definir_senha` grava na conta errada."""
    fonte = _ler("blazesbot/web_app.py")
    vivas = [linha for linha in fonte.splitlines()
             if "indice" in linha
             and not linha.lstrip().startswith(("#", '"', "'"))]
    assert not vivas, vivas


def test_o_frontend_identifica_a_linha_por_uid():
    fonte = _ler("web/main.js")
    assert "tr.dataset.uid = c.uid;" in fonte
    assert 'closest("tr[data-uid]")' in fonte
    # O POLL DO ESTADO TAMBÉM, e é o que importa aqui: login é campo livre, e
    # dois iguais faziam a busca acertar a primeira linha, que podia ser de
    # outra conta. A forma mudou (a busca virou um índice por uid dentro de
    # `marcarNoAr`), a GARANTIA não: o casamento é por uid e uid sem valor é
    # descartado em vez de virar palpite pelo login.
    assert "function marcarNoAr(est)" in fonte
    casamento = fonte.split("function marcarNoAr(est)")[1].split("\n}")[0]
    assert "noAr.set(c.uid, c)" in casamento
    assert "noAr.get(tr.dataset.uid)" in casamento
    assert "if (c.uid)" in casamento, "uid vazio não pode virar chave"
    assert "c.login" not in casamento, (
        "o poll voltou a casar a linha pelo login")
    assert "dataset.id" not in fonte


# -- 5. GRUPO É RÓTULO: o bot não pode ler dele ---------------------------

def test_NENHUM_caminho_do_bot_le_o_grupo():
    """A regra que mantém `grupo` inofensivo.

    Se algum comportamento passar a depender dele, o rótulo deixa de ser
    "organização do usuário" e vira configuração escondida -- e arrastar uma
    conta na tabela mudaria o que o bot FAZ. Só a config, as duas interfaces e
    os testes podem tocá-lo.
    """
    permitidos = {
        Path("blazesbot/config.py"),
        Path("blazesbot/web_app.py"),
        Path("blazesbot/gui/main_window.py"),
        Path("blazesbot/gui/account_dialog.py"),
    }
    culpados = []
    for py in (RAIZ / "blazesbot").rglob("*.py"):
        rel = py.relative_to(RAIZ)
        if rel in permitidos:
            continue
        arvore = ast.parse(py.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Attribute) and no.attr == "grupo":
                culpados.append(f"{rel}:{no.lineno}")
    assert not culpados, (
        "o grupo é RÓTULO VISUAL; nenhum caminho do bot pode decidir por ele: "
        f"{culpados}")


def test_o_grupo_nao_se_confunde_com_time_nem_com_party():
    """As três coisas são ortogonais, e a documentação tem de dizer isso."""
    conf = _ler("blazesbot/config.py")
    assert "RÓTULO DE ORGANIZAÇÃO" in conf
    assert "NÃO É TIME" in conf
    # O time continua por LOGIN, no líder — imune a reordenação.
    assert "time_logins: list[str]" in conf


def test_o_nome_do_grupo_tem_teto_nas_duas_pontas():
    """O rótulo entra num cabeçalho que ocupa a tabela toda."""
    assert LIMITE_DO_NOME_DO_GRUPO == 40
    assert "[:LIMITE_DO_NOME_DO_GRUPO]" in _ler("blazesbot/web_app.py")
    assert f'maxlength="{LIMITE_DO_NOME_DO_GRUPO}"' in _ler("web/index.html")
    assert "setMaxLength(LIMITE_DO_NOME_DO_GRUPO)" in _ler(
        "blazesbot/gui/account_dialog.py")


def test_o_grupo_sobrevive_ao_disco():
    cfg = BotConfig()
    cfg.accounts = [Account(login="a", grupo="Farmadores")]
    volta = BotConfig.from_dict(cfg.to_dict())
    assert volta.accounts[0].grupo == "Farmadores"


# -- 6. o arraste, e o que ele não pode fazer -----------------------------

def test_o_arraste_grava_SEM_debounce_e_com_rollback():
    """Debounce é justamente o que perde a última alteração quando a janela
    fecha. E o rollback recarrega do BACKEND: reconstruir de memória sumia com
    conta que entrou no cache durante a chamada, e podia mostrar uma ordem que o
    disco não tem (achados da revisão)."""
    fonte = _ler("web/main.js")
    assert "setTimeout" not in fonte.split("function aoSoltarLinha")[1][:1500]
    assert "carregarContas();" in fonte.split("Não foi possível salvar a nova ordem")[1][:200]


def test_o_arraste_solta_a_captura_e_respeita_o_pointerId():
    """Estado de arraste vazado trava a tabela: sem soltar a captura, cancelar
    por Esc deixava o ponteiro preso na alça."""
    fonte = _ler("web/main.js")
    assert "releasePointerCapture" in fonte
    assert "e.pointerId !== arraste.pointerId" in fonte
    assert "if (arraste) return;" in fonte      # um arraste por vez


def test_a_GUI_reordena_por_BOTAO_e_nao_por_arraste():
    """A tabela da GUI tem SEIS `setCellWidget`, e o arraste interno do Qt move
    os itens mas NÃO os widgets de célula: a senha de uma conta ficaria na linha
    de outra. Botão mexe no modelo e repopula."""
    fonte = _ler("blazesbot/gui/main_window.py")
    assert "def _mover_conta" in fonte
    assert "InternalMove" not in fonte
    assert "setSectionsMovable" not in fonte


def test_a_GUI_tambem_edita_o_grupo():
    """Regra das duas interfaces: a funcionalidade existe nas duas."""
    fonte = _ler("blazesbot/gui/account_dialog.py")
    assert "self.in_grupo" in fonte
    assert "self.conta.grupo = " in fonte
    assert "self.in_grupo.setText(self.conta.grupo)" in fonte


# -- 7. o ícone existe de verdade -----------------------------------------

def test_o_icone_existe_e_e_um_ICO_valido():
    """`favicon.ico` era referenciado em dois lugares e NÃO EXISTIA -- o que
    aparecia no titlebar era o placeholder de imagem quebrada do WebView2."""
    assert ICONE_DO_APP.exists(), f"{ICONE_DO_APP} não existe"
    dados = ICONE_DO_APP.read_bytes()
    reservado, tipo, quantas = struct.unpack("<HHH", dados[:6])
    assert reservado == 0 and tipo == 1, "não é um ICO"
    assert quantas >= 4, "ICO precisa de várias resoluções para a taskbar"
    # 16px é o tamanho que a aba e a lista de tarefas pequena usam.
    tamanhos = {struct.unpack("<BBBBHHII", dados[6 + 16 * i:22 + 16 * i])[0] or 256
                for i in range(quantas)}
    assert 16 in tamanhos and 32 in tamanhos and 256 in tamanhos, tamanhos


def test_a_janela_e_a_GUI_usam_o_MESMO_arquivo_de_icone():
    """Duas cópias divergiriam na primeira troca de arte."""
    assert "ICONE_DO_APP" in _ler("blazesbot/gui/main_window.py")
    assert "ICONE_DO_APP" in _ler("blazesbot/web_app.py")
    assert "setWindowIcon" in _ler("blazesbot/gui/main_window.py")


def test_o_titlebar_NAO_referencia_imagem_quebrada():
    # Sem os comentários: o histórico do defeito CITA a tag antiga de propósito,
    # e é o comentário que impede alguém de reintroduzi-la sem saber por quê.
    html = re.sub(r"<!--.*?-->", "", _ler("web/index.html"), flags=re.S)
    assert '<img src="favicon.ico"' not in html, (
        "o ícone do titlebar é SVG inline; o .ico serve à aba e à taskbar")
    assert 'class="app-icon"' in html and "<svg" in html
