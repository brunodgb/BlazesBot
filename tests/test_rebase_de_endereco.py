"""O seletor de endereço nunca pode ficar PIOR que o endereço de hoje.

=============================================================================
O QUE ESTÁ SOB TESTE
=============================================================================

Três leituras de memória documentadas como quebradas neste cliente
(`team_size`, `modal_open`, `surroundings_first`) nascem de endereço herdado do
GhostBot, que é da versão 6139. O jogo está na 6400, e o segmento de dados
andou +0x60 -- já medido e corrigido em `PLAYER_BASE_RVA` e `ADDR_UI_ROOT`, e
não nos vizinhos.

`SeletorDeEndereco` mede os dois e escolhe. A regra inteira cabe numa linha:

    troca SÓ quando o candidato responde E o atual não.

Tudo o mais mantém o atual. O teste que carrega o peso é o do EMPATE
(`test_empate_nao_troca`): quando os dois parecem plausíveis, a tentação é
"o novo deve ser o certo" -- e é aí que se troca um endereço que funciona por
um que só por acaso lê um número na faixa esperada. Ler lixo com sucesso é pior
que não ler, e é o modo de falha mais caro que existe aqui.

O segundo teste com peso é o do INCONCLUSIVO (`test_inconclusivo_nao_e_guardado`):
o painel de arredores só produz texto quando está ABERTO, então perguntar com
ele fechado não prova nada. Cravar a resposta ali seria decidir no vazio, e a
resposta ficaria decidida para sempre.

Lógica pura -- nenhum teste aqui abre processo, lê memória ou precisa do jogo.
"""
import pytest

from blazesbot.core.rebase import (
    DESLOCAMENTO_6139_PARA_6400,
    SeletorDeEndereco,
    candidato_rebaseado,
)

ATUAL = 0x012CE2DC          # ADDR_SURROUNDINGS, o valor da versão 6139
CANDIDATO = 0x012CE33C      # o mesmo, +0x60


class _Leitor:
    """Devolve um valor por endereço, e CONTA quantas leituras aconteceram."""

    def __init__(self, valores: dict[int, object]) -> None:
        self.valores = valores
        self.chamadas: list[int] = []

    def __call__(self, endereco: int) -> object:
        self.chamadas.append(endereco)
        return self.valores.get(endereco)


def _e_dicionario(valor: object) -> bool:
    return isinstance(valor, dict)


# ---------------------------------------------------------------------------
# A aritmética
# ---------------------------------------------------------------------------

def test_o_deslocamento_e_o_medido_entre_as_versoes():
    """0x60 não é escolha: é a diferença medida em DOIS endereços independentes.

    `PLAYER_BASE_RVA` 0x00D450EC -> 0x00D4514C e `ADDR_UI_ROOT` 0x012CE2E0 ->
    0x012CE340. Mudar este número sem uma terceira medição desfaz as duas.
    """
    assert DESLOCAMENTO_6139_PARA_6400 == 0x60


def test_candidato_dos_arredores_cai_um_dword_abaixo_da_raiz_de_ui():
    """A evidência mais forte de que o +0x60 vale para este endereço.

    `ADDR_UI_ROOT` da 6400 é 0x012CE340. O candidato dos arredores é
    0x012CE33C = raiz - 4: nas DUAS versões este campo fica um DWORD abaixo da
    raiz de UI. Se essa relação quebrar, a hipótese perde o principal apoio.
    """
    assert candidato_rebaseado(ATUAL) == CANDIDATO
    assert CANDIDATO == 0x012CE340 - 4


# ---------------------------------------------------------------------------
# As quatro saídas da decisão
# ---------------------------------------------------------------------------

def test_troca_quando_so_o_candidato_responde():
    ler = _Leitor({CANDIDATO: {"nome": "Rich", "coords": (158, -494)}})
    seletor = SeletorDeEndereco()

    escolhido = seletor.escolher("surroundings", ATUAL, ler, _e_dicionario)

    assert escolhido == CANDIDATO
    decisao = seletor.decisoes()["surroundings"]
    assert decisao.trocou is True
    assert "candidato" in decisao.motivo


def test_mantem_quando_so_o_atual_responde():
    ler = _Leitor({ATUAL: {"nome": "Rich", "coords": (158, -494)}})
    seletor = SeletorDeEndereco()

    escolhido = seletor.escolher("surroundings", ATUAL, ler, _e_dicionario)

    assert escolhido == ATUAL
    assert seletor.decisoes()["surroundings"].trocou is False


def test_empate_nao_troca():
    """DOIS plausíveis = a plausibilidade não distingue. Trocar aí é apostar.

    É o teste que segura a mão: um endereço errado que por acaso lê um valor na
    faixa esperada passaria batido, e o defeito só apareceria em produção como
    "o bot acha que está em time e não está".
    """
    ler = _Leitor({ATUAL: {"nome": "A"}, CANDIDATO: {"nome": "B"}})
    seletor = SeletorDeEndereco()

    escolhido = seletor.escolher("surroundings", ATUAL, ler, _e_dicionario)

    assert escolhido == ATUAL, "empate trocou de endereço -- isso é apostar"
    assert "AMBOS" in seletor.decisoes()["surroundings"].motivo


def test_inconclusivo_devolve_o_atual():
    ler = _Leitor({})
    seletor = SeletorDeEndereco()

    assert seletor.escolher("surroundings", ATUAL, ler, _e_dicionario) == ATUAL


# ---------------------------------------------------------------------------
# Quando a decisão é guardada, e quando NÃO é
# ---------------------------------------------------------------------------

def test_decide_uma_vez_e_nao_mede_de_novo():
    """O binário não muda no meio da sessão; remedir é syscall à toa."""
    ler = _Leitor({CANDIDATO: {"nome": "Rich"}})
    seletor = SeletorDeEndereco()

    seletor.escolher("surroundings", ATUAL, ler, _e_dicionario)
    assert len(ler.chamadas) == 2, "a primeira chamada mede os dois endereços"

    for _ in range(50):
        assert seletor.escolher("surroundings", ATUAL, ler, _e_dicionario) == CANDIDATO
    assert len(ler.chamadas) == 2, (
        "as chamadas seguintes tinham que só consultar o que foi decidido"
    )


def test_inconclusivo_nao_e_guardado():
    """Sem painel aberto não há texto: isso é "ainda não sei", não "não tem".

    Guardar aqui congelaria a resposta errada para sempre -- e o painel de
    arredores fica fechado a maior parte do tempo, então esse seria o caso
    COMUM na primeira leitura.
    """
    valores: dict[int, object] = {}
    ler = _Leitor(valores)
    seletor = SeletorDeEndereco()

    assert seletor.escolher("surroundings", ATUAL, ler, _e_dicionario) == ATUAL
    assert not seletor.ja_decidiu("surroundings")

    # o painel abre, e agora o candidato responde
    valores[CANDIDATO] = {"nome": "Rich", "coords": (158, -494)}
    assert seletor.escolher("surroundings", ATUAL, ler, _e_dicionario) == CANDIDATO
    assert seletor.ja_decidiu("surroundings")


def test_empate_e_guardado():
    """Empate É uma decisão ("mantém o atual"), então não se repergunta."""
    ler = _Leitor({ATUAL: 1, CANDIDATO: 0})
    seletor = SeletorDeEndereco()

    seletor.escolher("modal", ATUAL, ler, lambda v: isinstance(v, int) and 0 <= v <= 1)
    assert seletor.ja_decidiu("modal")
    antes = len(ler.chamadas)
    seletor.escolher("modal", ATUAL, ler, lambda v: isinstance(v, int) and 0 <= v <= 1)
    assert len(ler.chamadas) == antes


def test_rotulos_sao_independentes():
    ler = _Leitor({CANDIDATO: {"a": 1}, ATUAL + 0x1000: "x"})
    seletor = SeletorDeEndereco()

    seletor.escolher("surroundings", ATUAL, ler, _e_dicionario)
    assert seletor.ja_decidiu("surroundings")
    assert not seletor.ja_decidiu("team_size")


# ---------------------------------------------------------------------------
# Nada aqui pode derrubar uma leitura de memória
# ---------------------------------------------------------------------------

def test_leitor_que_levanta_nao_derruba():
    def ler(endereco: int) -> object:
        if endereco == ATUAL:
            raise RuntimeError("processo morreu no meio")
        return {"nome": "Rich"}

    seletor = SeletorDeEndereco()
    assert seletor.escolher("surroundings", ATUAL, ler, _e_dicionario) == CANDIDATO


def test_validador_que_levanta_nao_derruba():
    def plausivel(valor: object) -> bool:
        raise ValueError("validador mal escrito")

    seletor = SeletorDeEndereco()
    ler = _Leitor({ATUAL: 1, CANDIDATO: 1})
    assert seletor.escolher("modal", ATUAL, ler, plausivel) == ATUAL


def test_registrador_que_levanta_nao_derruba():
    def registrar(_mensagem: str) -> None:
        raise OSError("disco cheio")

    seletor = SeletorDeEndereco(registrar=registrar)
    ler = _Leitor({CANDIDATO: {"nome": "Rich"}})
    assert seletor.escolher("surroundings", ATUAL, ler, _e_dicionario) == CANDIDATO


def test_none_nunca_e_plausivel():
    """`None` é o retorno de "não deu para ler". Um validador tolerante demais
    (`lambda v: True`) não pode transformar isso em resposta."""
    seletor = SeletorDeEndereco()
    ler = _Leitor({})
    assert seletor.escolher("qualquer", ATUAL, ler, lambda v: True) == ATUAL
    assert not seletor.ja_decidiu("qualquer")


# ---------------------------------------------------------------------------
# O log
# ---------------------------------------------------------------------------

def test_registra_a_decisao_uma_vez_e_nao_a_cada_leitura():
    linhas: list[str] = []
    ler = _Leitor({CANDIDATO: {"nome": "Rich"}})
    seletor = SeletorDeEndereco(registrar=linhas.append)

    for _ in range(20):
        seletor.escolher("surroundings", ATUAL, ler, _e_dicionario)

    assert len(linhas) == 1, f"log repetido {len(linhas)}x: deixa de ser lido"
    assert "surroundings" in linhas[0]
    assert "0x012ce33c" in linhas[0].lower()


def test_inconclusivo_repetido_nao_repete_o_log():
    """O inconclusivo repergunta a cada chamada, por desenho -- mas não pode
    encher o log com a mesma linha a cada leitura."""
    linhas: list[str] = []
    ler = _Leitor({})
    seletor = SeletorDeEndereco(registrar=linhas.append)

    for _ in range(20):
        seletor.escolher("surroundings", ATUAL, ler, _e_dicionario)

    assert len(linhas) == 1, f"log repetido {len(linhas)}x"
    assert "nenhum dos dois" in linhas[0]


def test_o_log_mostra_os_dois_valores_lidos():
    """Sem os dois valores, a linha não responde "por que ele trocou?"."""
    linhas: list[str] = []
    ler = _Leitor({ATUAL: None, CANDIDATO: 3})
    seletor = SeletorDeEndereco(registrar=linhas.append)

    seletor.escolher("team_size", ATUAL, ler,
                     lambda v: isinstance(v, int) and 0 <= v <= 5)

    assert "None" in linhas[0] and "3" in linhas[0]


# ---------------------------------------------------------------------------
# Candidato explícito
# ---------------------------------------------------------------------------

def test_candidato_explicito_sobrepoe_o_calculado():
    outro = 0x0BADF00D
    ler = _Leitor({outro: {"nome": "Rich"}})
    seletor = SeletorDeEndereco()

    escolhido = seletor.escolher("surroundings", ATUAL, ler, _e_dicionario,
                                 candidato=outro)

    assert escolhido == outro


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
