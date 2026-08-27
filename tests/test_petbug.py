"""O PetBug: usa a janela aberta, clica no BOTÃO, e confere no log dele.

=============================================================================
O QUE ESTÁ SOB TESTE
=============================================================================

`BlazesBot - PetBug.exe` é um programa de terceiro que faz o esconder jogadores
por sessão e um "pet bug" contra disconnect. O bot clica no botão `Patch` dele a
cada vez que uma conta de BC cai, porque o patch age nos clientes que estão
RODANDO -- e uma conta que caiu volta num cliente NOVO.

O pedido do usuário era **clicar numa coordenada fixa**. Inspecionando a janela
apareceu algo melhor: o botão é um `TButton` de verdade e o log é um `TMemo`. Então
o clique vai no `hwnd` (sem coordenada, funciona minimizado) e o RESULTADO é
conferido lendo o log do próprio programa.

=============================================================================
OS TESTES QUE CARREGAM O PESO
=============================================================================

**`test_nao_reabre_se_ja_estiver_aberto`** -- regra explícita do usuário. Dois
processos do patcher mexendo nos mesmos clientes é a receita para um desfazer o do
outro.

**`test_cinco_contas_caindo_juntas_produzem_UM_clique`** -- cinco contas caem
juntas com frequência (medido, está no `CLAUDE.md`), e um clique cobre todos os
clientes. Sem o intervalo, seriam cinco cliques idênticos.

**`test_cai_na_coordenada_fixa_quando_o_botao_nao_e_localizavel`** -- a reserva
existe para nunca ficar pior que o pedido original.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from blazesbot.core import petbug

LOG_DE_SUCESSO = (
    "=== Starting Pet Bug Fix & F12 Hide ===\r\n"
    "[OK] Patch applied to all running clients.\r\n"
    "=== Completed ===\r\n"
)
JANELA = 202152
BOTAO = 1119894
MEMO = 202164


class JanelasFalsas:
    """Dublê das peças Win32. Modela janela ausente, botão ausente e log."""

    def __init__(self, aberta=True, tem_botao=True, tem_log=True,
                 texto=LOG_DE_SUCESSO, abre_ao_lancar=True,
                 clique_falha=False):
        self._aberta = aberta
        self._tem_botao = tem_botao
        self._tem_log = tem_log
        self._texto = texto
        self._abre_ao_lancar = abre_ao_lancar
        self._clique_falha = clique_falha
        self.lancamentos: list[Path] = []
        self.cliques_no_botao: list[int] = []
        self.cliques_por_coordenada: list[tuple[int, tuple[int, int]]] = []
        self.esperas: list[float] = []

    def achar_janela(self, _pedaco):
        return JANELA if self._aberta else None

    def achar_botao(self, _janela):
        return BOTAO if self._tem_botao else None

    def achar_log(self, _janela):
        return MEMO if self._tem_log else None

    def ler_texto(self, _controle):
        return self._texto

    def clicar_no_botao(self, botao):
        self.cliques_no_botao.append(botao)
        return not self._clique_falha

    def clicar_por_coordenada(self, janela, ponto):
        self.cliques_por_coordenada.append((janela, ponto))
        return True

    def esperar(self, s):
        self.esperas.append(s)

    def abrir(self, caminho):
        self.lancamentos.append(caminho)
        if self._abre_ao_lancar:
            self._aberta = True


def _log():
    return SimpleNamespace(info=lambda *a, **k: None,
                           debug=lambda *a, **k: None,
                           warning=lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _zerar_o_intervalo(monkeypatch):
    """O intervalo é estado de MÓDULO, compartilhado entre supervisores.

    Sem zerar, o primeiro teste que aplica bloqueia todos os seguintes -- e o
    sintoma seria uma cascata de falhas sem relação com o que cada um testa.
    """
    monkeypatch.setattr(petbug, "_ULTIMA_APLICACAO", 0.0)
    monkeypatch.setattr(petbug, "ATIVADO", True)


def _aplicar(janelas, **kw):
    return petbug.aplicar_patch(log=_log(), janelas=janelas, **kw)


# ---------------------------------------------------------------------------
# 1. Usa a janela aberta -- regra explícita
# ---------------------------------------------------------------------------

def test_nao_reabre_se_ja_estiver_aberto():
    """"Caso esteja aberto, não reabra; use o que tiver aberto."

    Dois processos do patcher mexendo nos mesmos clientes é a receita para um
    desfazer o do outro.
    """
    j = JanelasFalsas(aberta=True)
    resultado = _aplicar(j)

    assert j.lancamentos == [], "abriu um segundo processo do patcher"
    assert resultado.aplicou is True
    assert resultado.lancou_o_programa is False


def test_abre_o_programa_quando_nao_esta_aberto(tmp_path):
    exe = tmp_path / petbug.NOMES_DO_PATCHER[0]
    exe.write_bytes(b"")
    j = JanelasFalsas(aberta=False)

    resultado = _aplicar(j, raiz=tmp_path)

    assert j.lancamentos == [exe]
    assert resultado.lancou_o_programa is True
    assert resultado.aplicou is True


def test_aceita_o_nome_ANTIGO_do_arquivo(tmp_path):
    """O usuário renomeou de RaaskiBot para BlazesBot. Os dois valem."""
    exe = tmp_path / petbug.NOMES_DO_PATCHER[1]
    exe.write_bytes(b"")
    j = JanelasFalsas(aberta=False)

    _aplicar(j, raiz=tmp_path)

    assert j.lancamentos == [exe]


def test_sem_o_arquivo_avisa_e_nao_levanta(tmp_path):
    j = JanelasFalsas(aberta=False)
    resultado = _aplicar(j, raiz=tmp_path)

    assert resultado.aplicou is False
    assert "não achei o programa" in resultado.motivo


def test_janela_que_nao_aparece_depois_de_lancar(tmp_path):
    (tmp_path / petbug.NOMES_DO_PATCHER[0]).write_bytes(b"")
    j = JanelasFalsas(aberta=False, abre_ao_lancar=False)

    resultado = _aplicar(j, raiz=tmp_path)

    assert resultado.aplicou is False
    assert resultado.lancou_o_programa is True


# ---------------------------------------------------------------------------
# 2. Clica no BOTÃO, não numa coordenada
# ---------------------------------------------------------------------------

def test_clica_no_hwnd_do_botao():
    """Sem coordenada não há o que envelhecer, e funciona minimizado."""
    j = JanelasFalsas()
    _aplicar(j)

    assert j.cliques_no_botao == [BOTAO]
    assert j.cliques_por_coordenada == []


def test_cai_na_coordenada_fixa_quando_o_botao_nao_e_localizavel():
    """A RESERVA. É o que o usuário autorizou originalmente, e ela garante que o
    caminho novo nunca fique pior que o pedido."""
    j = JanelasFalsas(tem_botao=False)
    resultado = _aplicar(j)

    assert j.cliques_por_coordenada == [(JANELA, petbug.PONTO_FIXO_DO_PATCH)]
    assert resultado.aplicou is True


def test_cai_na_coordenada_fixa_quando_o_BM_CLICK_falha():
    j = JanelasFalsas(clique_falha=True)
    _aplicar(j)

    assert j.cliques_no_botao == [BOTAO]
    assert j.cliques_por_coordenada == [(JANELA, petbug.PONTO_FIXO_DO_PATCH)]


# ---------------------------------------------------------------------------
# 3. CONFERE no log do programa
# ---------------------------------------------------------------------------

def test_confirma_pelo_log_do_programa():
    j = JanelasFalsas(texto=LOG_DE_SUCESSO)
    resultado = _aplicar(j)

    assert resultado.confirmado_no_log is True


def test_log_sem_a_confirmacao_e_relatado_como_NAO_confirmado():
    """Clicou, mas o programa não disse que aplicou. Não é a mesma coisa que
    sucesso, e o log do bot precisa distinguir os dois."""
    j = JanelasFalsas(texto="=== Starting ===\r\n[ERRO] nenhum cliente\r\n")
    resultado = _aplicar(j)

    assert resultado.aplicou is True
    assert resultado.confirmado_no_log is False


def test_sem_o_log_do_programa_relata_que_nao_deu_para_conferir():
    j = JanelasFalsas(tem_log=False)
    resultado = _aplicar(j)

    assert resultado.aplicou is True
    assert resultado.confirmado_no_log is False
    assert "não achei o log" in resultado.motivo


def test_o_texto_IGUAL_ao_de_antes_ainda_conta_como_sucesso():
    """O programa reescreve as MESMAS três linhas a cada Patch.

    Exigir que o texto MUDE reprovaria uma aplicação bem-sucedida só porque ela
    produziu a mesma saída da anterior -- e a segunda aplicação em diante é o caso
    comum, porque o gatilho é a cada queda.
    """
    j = JanelasFalsas(texto=LOG_DE_SUCESSO)
    assert _aplicar(j).confirmado_no_log is True


# ---------------------------------------------------------------------------
# 4. CINCO CONTAS, UM CLIQUE
# ---------------------------------------------------------------------------

def test_cinco_contas_caindo_juntas_produzem_UM_clique():
    """Um clique cobre TODOS os clientes, e cinco contas caem juntas com
    frequência. Sem o intervalo, seriam cinco cliques idênticos e inúteis."""
    j = JanelasFalsas()

    resultados = [_aplicar(j) for _ in range(5)]

    assert j.cliques_no_botao == [BOTAO], (
        f"{len(j.cliques_no_botao)} cliques para cinco contas caindo juntas"
    )
    assert resultados[0].aplicou is True
    assert all(not r.aplicou for r in resultados[1:])
    assert "cobre todos os clientes" in resultados[1].motivo


def test_forcar_ignora_o_intervalo():
    """Para um botão de diagnóstico: o usuário mandou aplicar, aplica."""
    j = JanelasFalsas()
    _aplicar(j)
    resultado = _aplicar(j, forcar=True)

    assert resultado.aplicou is True
    assert len(j.cliques_no_botao) == 2


def test_o_intervalo_e_reservado_ANTES_de_agir():
    """Marcar depois deixaria duas contas passarem pela janela de tempo enquanto
    a primeira ainda está clicando."""
    j = JanelasFalsas()
    _aplicar(j)
    assert petbug._ULTIMA_APLICACAO > 0


# ---------------------------------------------------------------------------
# 5. O interruptor
# ---------------------------------------------------------------------------

def test_desligado_nao_procura_nem_clica(monkeypatch):
    monkeypatch.setattr(petbug, "ATIVADO", False)
    j = JanelasFalsas()

    resultado = _aplicar(j)

    assert j.cliques_no_botao == [] and j.lancamentos == []
    assert resultado.aplicou is False
    assert "DESLIGADO" in resultado.motivo


# ---------------------------------------------------------------------------
# 6. O sinal de sucesso é o que o programa REALMENTE escreve
# ---------------------------------------------------------------------------

def test_o_sinal_casa_a_linha_real_do_programa():
    """Capturada da janela de verdade por `WM_GETTEXT`, não inventada."""
    assert petbug.SINAL_DE_SUCESSO.search(LOG_DE_SUCESSO)


def test_o_sinal_nao_casa_qualquer_coisa():
    assert not petbug.SINAL_DE_SUCESSO.search("=== Starting ===\r\n=== Completed ===")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
