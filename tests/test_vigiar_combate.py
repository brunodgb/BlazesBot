"""O `9-VIGIAR-COMBATE` NÃO REIMPLEMENTA A LEITURA QUE ELE DIAGNOSTICA.

Pedido do usuário em 26/08/2026: *"cria um .bat que acompanha em tempo real a
batalha e USA A FUNÇÃO DE TARGET DO `target_hybrid`"*.

A versão ANTIGA desta ferramenta foi apagada justamente por ter a própria
leitura de alvo por ponteiro. Ferramenta de diagnóstico que reimplementa o que
deveria estar diagnosticando não mostra o bot: mostra a cópia — e a cópia pode
estar certa enquanto o bot está errado, que é o pior resultado possível.

Por isso os testes daqui são quase todos sobre PROCEDÊNCIA: de onde vem cada
número que aparece na tela.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from blazesbot.tools import vigiar_combate as mod

RAIZ = Path(__file__).resolve().parent.parent


def _chamadas(funcao) -> set[str]:
    fonte = inspect.getsource(funcao)
    return {n.func.attr for n in ast.walk(ast.parse(fonte))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}


# -- procedência -----------------------------------------------------------

def test_o_alvo_vem_do_TargetHybrid_e_nao_de_uma_copia():
    chamadas = _chamadas(mod.run_vigiar_combate)

    assert "ler" in chamadas, "não chama `TargetHybrid.ler`"
    assert "linha_do_log" in chamadas, (
        "monta a própria linha em vez de usar a do bot")


def test_a_linha_e_a_MESMA_que_o_BC_escreve():
    """Se ela fosse montada aqui, o formato divergiria no primeiro conserto de
    um dos dois lados — e ninguém perceberia."""
    from blazesbot.core.target_hybrid import TargetHybrid

    assert "hibrido.linha_do_log(" in inspect.getsource(mod.run_vigiar_combate)
    assert hasattr(TargetHybrid, "linha_do_log")


def test_o_veredito_de_morte_vem_da_peca_COMPARTILHADA():
    fonte = inspect.getsource(mod)
    assert "from ..core.target_hybrid import (" in fonte
    assert "MorteDoAlvo," in fonte
    assert "TargetHybrid," in fonte
    assert "morte.veredito(" in fonte
    assert "morte.contar(" in fonte


def test_a_lista_de_PIDs_vem_do_watchdog():
    """`client_pids` já existia. Varrer `psutil` de novo aqui seria a mesma
    definição de "cliente do jogo" escrita em dois lugares."""
    fonte = inspect.getsource(mod)
    assert "from ..bot.watchdog import client_pids" in fonte
    assert "psutil" not in fonte


def test_o_titulo_da_janela_vem_da_peca_PROMOVIDA():
    """Era uma função aninhada no `main.py`; subiu para `core/janelas.py`
    quando esta ferramenta passou a precisar dela."""
    fonte = inspect.getsource(mod)
    assert "from ..core.janelas import titulo_do_pid" in fonte
    assert "EnumWindows" not in fonte, "recopiou a varredura de janelas"


def test_o_main_usa_a_MESMA_peca_promovida():
    principal = (RAIZ / "main.py").read_text(encoding="utf-8")

    assert "from blazesbot.core.janelas import" in principal
    assert "def cb(handle, _extra):" not in principal, (
        "a cópia antiga da varredura continua no main.py")
    assert "EnumWindows" not in principal, (
        "sobrou varredura de janela no main.py — a promoção ficou pela metade")


# -- o que ela NÃO faz -----------------------------------------------------

def test_ela_SO_LE_e_nunca_escreve_no_jogo():
    """Módulo FOLHA de diagnóstico. Escrever aqui é o tipo de coisa que ninguém
    revisa depois."""
    fonte = inspect.getsource(mod)
    for proibido in ("write_", "set_camera", "PostMessage", "SendMessage",
                     "Input(", "click"):
        assert proibido not in fonte, proibido


def test_ela_NAO_captura_a_tela():
    """`com_tela=False`: a reserva pela barra desenhada é do BC e exige
    captura. Aqui a pergunta é o que a MEMÓRIA responde."""
    assert "com_tela=False" in inspect.getsource(mod.run_vigiar_combate)


def test_nada_do_bot_importa_esta_ferramenta():
    """Módulo FOLHA, como as outras ferramentas temporárias.

    A conferência é por AST e não por texto: `core/diario.py` cita o caminho
    antigo desta ferramenta num docstring histórico, e uma busca por texto
    reprovaria uma MENÇÃO como se fosse um IMPORT. Um teste que confunde
    comentário com dependência ensina a apagar comentário.
    """
    for caminho in (RAIZ / "blazesbot").rglob("*.py"):
        if caminho.name == "vigiar_combate.py":
            continue
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom):
                alvo = f"{no.module or ''}." + ".".join(
                    a.name for a in no.names)
            elif isinstance(no, ast.Import):
                alvo = ".".join(a.name for a in no.names)
            else:
                continue
            assert "vigiar_combate" not in alvo, (
                f"{caminho} importa uma ferramenta temporária")


# -- a escolha do cliente --------------------------------------------------

def test_UM_cliente_so_nao_pergunta_nada(monkeypatch):
    monkeypatch.setattr(mod, "client_pids", lambda: {4242})
    monkeypatch.setattr(mod, "_rotulo", lambda pid: "Fulano (Talisman)")

    def nao_pergunte(*a, **k):
        raise AssertionError("perguntou com um cliente só")

    monkeypatch.setattr("builtins.input", nao_pergunte)
    assert mod._escolher_pid() == 4242


def test_VARIOS_clientes_sao_listados_por_NUMERO(monkeypatch, capsys):
    """*"Liste eles que tenha o mesmo nome, só para eu escolher o número."*

    Todos se chamam `client.exe`, então o nome não separa nada — quem separa é
    o nick e o título da janela.
    """
    monkeypatch.setattr(mod, "client_pids", lambda: {300, 100, 200})
    monkeypatch.setattr(mod, "_rotulo", lambda pid: f"nick{pid}")
    monkeypatch.setattr("builtins.input", lambda *a: "2")

    escolhido = mod._escolher_pid()

    saida = capsys.readouterr().out
    assert "[1]" in saida and "[2]" in saida and "[3]" in saida
    assert "nick100" in saida
    # ORDENADO: a lista tem que ser estável entre uma rodada e a seguinte,
    # senão o número que a pessoa acabou de ler muda de dono.
    assert escolhido == 200


def test_numero_INVALIDO_pergunta_de_novo(monkeypatch, capsys):
    monkeypatch.setattr(mod, "client_pids", lambda: {100, 200})
    monkeypatch.setattr(mod, "_rotulo", lambda pid: "x")
    respostas = iter(["9", "abc", "1"])
    monkeypatch.setattr("builtins.input", lambda *a: next(respostas))

    assert mod._escolher_pid() == 100
    assert "Não entendi" in capsys.readouterr().out


def test_ENTER_desiste_sem_explodir(monkeypatch):
    monkeypatch.setattr(mod, "client_pids", lambda: {100, 200})
    monkeypatch.setattr(mod, "_rotulo", lambda pid: "x")
    monkeypatch.setattr("builtins.input", lambda *a: "")
    assert mod._escolher_pid() is None


def test_SEM_cliente_aberto_avisa_o_que_fazer(monkeypatch, capsys):
    monkeypatch.setattr(mod, "client_pids", lambda: set())
    assert mod._escolher_pid() is None
    assert "ENTRE COM UM PERSONAGEM" in capsys.readouterr().out


# -- o estado do personagem ------------------------------------------------

@pytest.mark.parametrize("vida, batalha, esperado", [
    (88.0, True, "vida 88%  EM BATALHA"),
    (12.0, False, "vida 12%  fora de batalha"),
    (None, None, "vida ?  batalha: ?"),
])
def test_o_personagem_diz_NAO_SEI_em_vez_de_zero(vida, batalha, esperado):
    """`?` e não `0%`: quem lê a tela precisa distinguir "morrendo" de "não
    consegui ler" — é a mesma regra que atravessa o bot inteiro."""
    memoria = SimpleNamespace(vida_pct=lambda: vida, in_battle=lambda: batalha)
    assert esperado in mod._estado_do_personagem(memoria)


def test_leitura_que_EXPLODE_nao_derruba_a_ferramenta():
    def explode():
        raise RuntimeError("boom")

    memoria = SimpleNamespace(vida_pct=explode, in_battle=explode)
    assert "sem leitura" in mod._estado_do_personagem(memoria)
    assert "sem leitura" in mod._estado_do_personagem(None)


# -- o .bat ----------------------------------------------------------------

def test_o_bat_existe_e_chama_a_opcao_certa():
    bat = (RAIZ / "9-VIGIAR-COMBATE.bat").read_text(encoding="utf-8",
                                                    errors="replace")
    assert "--watch-combat" in bat
    assert "RunAs" in bat, "sem elevação, a leitura de memória falha"
    assert "1-INSTALAR.bat" in bat, "não diz o que fazer sem ambiente"


# ===========================================================================
# O ID QUE RESPONDE E A ENTIDADE QUE NÃO APARECE — 26/08/2026
# ===========================================================================
#
# *"Eu vejo que o value do 0115CB80 altera, mas não acha o target no array —
# mas em algum lugar da memória do jogo ele está, pq o mob existe, a chave
# existe."*

def test_os_SLOTS_DE_SELECAO_caem_dentro_da_janela_varrida():
    """A ARITMÉTICA QUE LEVANTOU A SUSPEITA.

    Os sete "slots de seleção visual" descobertos em 21/08/2026 estão TODOS
    dentro dos `LIMITE_DE_ENTIDADES * 4` bytes que `_procurar_entidade` varre.

    Isso é evidência de que a região varrida não é uma "array de entidades", e
    sim um pedaço estático que contém ponteiros para entidades RECENTEMENTE
    SELECIONADAS — o que explicaria o log: os mobs que aparecem inteiros são os
    engajados, e o TAB ciclando produz quase só ausências.
    """
    from blazesbot.core.memory import ADDR_ENTITY_SCAN_BASE, LIMITE_DE_ENTIDADES

    fim = ADDR_ENTITY_SCAN_BASE + LIMITE_DE_ENTIDADES * 4
    slots = (0x0107C714, 0x0107C79C, 0x0107C8FC, 0x0107C71C,
             0x0107C948, 0x0107C758, 0x0107C998)

    for slot in slots:
        assert ADDR_ENTITY_SCAN_BASE <= slot < fim, hex(slot)


def test_a_investigacao_diz_QUANDO_o_id_nao_existe_em_lugar_nenhum():
    from blazesbot.core import target_hybrid as th

    memoria = SimpleNamespace(
        pm=SimpleNamespace(pattern_scan_all=lambda *a, **k: []))
    linhas = th.investigar_alvo_perdido(memoria, 230967247)

    assert any("NÃO APARECE" in t for t in linhas)
    # O HEX importa: quem confere isso está com o Cheat Engine aberto, e lá o
    # número decimal não serve para nada.
    assert any("0x0DC447CF" in t for t in linhas)


def test_o_LIXO_MEDIDO_no_jogo_e_reprovado():
    """A MEDIÇÃO DE 26/08/2026 derrubou a primeira versão do filtro.

    Com o jogo na frente, a investigação aprovou dois endereços como se fossem
    entidades:

        0x1095C228  ?  nv32  hp=1/390876288
        0x2F28A424  ?  nv2   hp=0/1030909696

    `hp <= max_hp` sozinho não filtra nada: com `max_hp` gigante a relação é
    trivialmente verdadeira. E o mesmo endereço reaparecia para ids DIFERENTES,
    que é a assinatura de falso positivo.
    """
    from blazesbot.core.entidades import parece_entidade
    from blazesbot.core.memory import OFF_HP as OFF_HP_DA_ENTIDADE
    from blazesbot.core.memory import OFF_LEVEL, OFF_MAX_HP

    for obj, hp, maximo, nivel in ((0x1095C228, 1, 390876288, 32),
                                   (0x2F28A424, 0, 1030909696, 2)):
        campos = {obj + OFF_HP_DA_ENTIDADE: hp, obj + OFF_MAX_HP: maximo}
        memoria = SimpleNamespace(
            read_int=lambda a, c=campos: c.get(a),
            read_byte=lambda a, n=nivel, o=obj: n if a == o + OFF_LEVEL else 0,
            _nome_da_entidade=lambda o: None)
        assert parece_entidade(memoria, obj) is None, hex(obj)


def test_a_entidade_de_VERDADE_continua_passando():
    """O filtro não pode matar a regra: `Rose Snake 100/100 nv61` é o gabarito
    que a mesma medição produziu, e ele tem que passar."""
    from blazesbot.core.entidades import parece_entidade
    from blazesbot.core.memory import OFF_HP as OFF_HP_DA_ENTIDADE
    from blazesbot.core.memory import OFF_LEVEL, OFF_MAX_HP

    obj = 0x2F35A450
    campos = {obj + OFF_HP_DA_ENTIDADE: 100, obj + OFF_MAX_HP: 100}
    memoria = SimpleNamespace(
        read_int=lambda a: campos.get(a),
        read_byte=lambda a: 61 if a == obj + OFF_LEVEL else 0,
        _nome_da_entidade=lambda o: "Rose Snake")

    achado = parece_entidade(memoria, obj)
    assert achado is not None
    assert achado["nome"] == "Rose Snake" and achado["nivel"] == 61


def test_o_NOME_ilegivel_NAO_reprova_a_entidade():
    """Estado REAL medido em 26/08/2026: `#245506802  100/100, nv61` — entidade
    legítima, nome ilegível. Exigir nome esconderia justamente esse caso."""
    from blazesbot.core.entidades import parece_entidade
    from blazesbot.core.memory import OFF_HP as OFF_HP_DA_ENTIDADE
    from blazesbot.core.memory import OFF_LEVEL, OFF_MAX_HP

    obj = 0x2F35A450
    campos = {obj + OFF_HP_DA_ENTIDADE: 100, obj + OFF_MAX_HP: 100}
    memoria = SimpleNamespace(
        read_int=lambda a: campos.get(a),
        read_byte=lambda a: 61 if a == obj + OFF_LEVEL else 0,
        _nome_da_entidade=lambda o: None)

    assert parece_entidade(memoria, obj) is not None


def test_o_vigia_SEPARA_entidade_ok_de_nome_ilegivel():
    """Os dois saíam com a mesma cara (`#id`), e pedem consertos opostos."""
    fonte = inspect.getsource(mod.run_vigiar_combate)
    assert 'info.entidade["nome"]' in fonte
    assert "NOME ilegível" in fonte


def test_o_ruido_do_pymem_e_calado_NA_FERRAMENTA():
    """`Process N is being debugged` a cada handle aberto punha uma linha de
    ruído entre cada linha da lista de clientes."""
    fonte = inspect.getsource(mod)
    assert 'logging.getLogger("pymem").setLevel(logging.WARNING)' in fonte
    # SÓ o logger do pymem: em `dev` esse DEBUG vai para o JSONL e lá ele não
    # atrapalha. Calar o raiz apagaria o log da sessão inteira.
    assert "getLogger()" not in fonte


def test_a_investigacao_ACHA_a_entidade_e_diz_que_ela_esta_FORA_da_janela():
    """O resultado que separa "a entidade não existe" de "estamos procurando no
    lugar errado" — e as duas pedem consertos opostos."""
    from blazesbot.core import target_hybrid as th
    from blazesbot.core.memory import OFF_ENTITY_ID, OFF_LEVEL, OFF_MAX_HP
    from blazesbot.core.memory import OFF_HP as OFF_HP_DA_ENTIDADE

    obj = 0x2F35A450
    campos = {obj + OFF_HP_DA_ENTIDADE: 63, obj + OFF_MAX_HP: 100}

    memoria = SimpleNamespace(
        pm=SimpleNamespace(
            pattern_scan_all=lambda *a, **k: [obj + OFF_ENTITY_ID]),
        read_int=lambda a: campos.get(a),
        read_uint=lambda a: 0,          # a janela varrida não aponta para ele
        read_byte=lambda a: 61 if a == obj + OFF_LEVEL else 0,
        _nome_da_entidade=lambda o: "Rose Snake",
    )

    linhas = th.investigar_alvo_perdido(memoria, 20187649)

    assert any("Rose Snake" in t and "nv61" in t for t in linhas), linhas
    assert any("NÃO está na janela varrida" in t for t in linhas), linhas
    assert any("o lugar onde procuramos" in t for t in linhas), linhas


def test_a_investigacao_roda_UMA_VEZ_por_id():
    """Ela varre o processo inteiro e custa segundos; repetir a cada leitura
    transformaria o vigia num travamento."""
    fonte = inspect.getsource(mod.run_vigiar_combate)

    assert "investigados: set[int] = set()" in fonte
    assert "info.target_id not in investigados" in fonte
    assert "investigados.add(info.target_id)" in fonte


def test_a_investigacao_NAO_roda_no_caminho_do_bot():
    """`investigar_alvo_perdido` varre a memória do processo. No laço do bot
    isso seria um congelamento por mob."""

    for pasta in ("blazesbot/bot", "blazesbot/core"):
        for caminho in (RAIZ / pasta).rglob("*.py"):
            if caminho.name in ("target_hybrid.py", "entidades.py"):
                continue          # onde ela mora, e a peça que ela cita
            fonte = caminho.read_text(encoding="utf-8")
            assert "investigar_alvo_perdido" not in fonte, caminho


def test_a_linha_diz_DE_QUAL_ID_veio_quando_o_alvo_troca():
    """A pergunta que o log de 26/08/2026 não respondia.

    Um id órfão que vira mob legível tem duas explicações OPOSTAS: era o mob
    novo chegando atrasado (o certo é esperar) ou era o cadáver e o bot trocou
    (o certo é dar TAB de novo). Sem o id na linha, os dois aparecem como
    "alvo novo".
    """
    fonte = inspect.getsource(mod.run_vigiar_combate)

    assert "anterior_id" in fonte
    assert "info.target_id} ← era {anterior_id}" in fonte
