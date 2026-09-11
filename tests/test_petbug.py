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
                 clique_falha=False, minimizada=False):
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
        self.mortes = 0
        self.restauracoes = 0
        self.minimizada = minimizada

    def achar_janela(self, _pedaco):
        return JANELA if self._aberta else None

    def matar_o_programa(self):
        """Mata o que estiver aberto -- ver `NOVA_INSTANCIA_SEMPRE`."""
        mortos = 1 if self._aberta else 0
        self.mortes += mortos
        self._aberta = False
        return mortos

    def restaurar_janela(self, _janela):
        """`True` = estava minimizada. O dublê nasce restaurada."""
        self.restauracoes += 1
        estava = self.minimizada
        self.minimizada = False
        return estava

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

def test_MATA_o_que_esta_aberto_antes_de_abrir_de_novo(tmp_path):
    """A regra virou o contrário em 07/09/2026, e o usuário tem o campo a favor.

    ANTES: *"caso esteja aberto, não reabra; use o que tiver aberto"* -- e o
    motivo era bom: dois processos do patcher mexendo nos mesmos clientes é a
    receita para um desfazer o do outro.

    AGORA: *"sempre que precisar dele mata o que está sendo executado e executa
    novamente, pois tem vezes que se já está aberto não funciona"*. O motivo
    antigo NÃO é violado -- mata-se ANTES de abrir, então em nenhum instante
    existem dois.

    E há uma razão de engenharia que o log de 07/09 escancarou: a confirmação
    lê o log do programa, que aceita o texto que já estava lá. Com a janela
    reusada, um "patch applied" de uma hora atrás confirma um clique que não
    fez nada. Log limpo é o que torna a prova honesta.
    """
    (tmp_path / "BlazesBot - PetBug.exe").write_bytes(b"")
    j = JanelasFalsas(aberta=True)
    resultado = _aplicar(j, raiz=tmp_path)

    assert j.mortes == 1, "não matou a instância aberta"
    assert j.lancamentos, "matou e não abriu de novo"
    assert resultado.aplicou is True
    assert resultado.lancou_o_programa is True


def test_com_o_interruptor_DESLIGADO_reusa_a_janela(monkeypatch):
    """O caminho antigo não foi apagado -- ver `NOVA_INSTANCIA_SEMPRE`."""
    monkeypatch.setattr(petbug, "NOVA_INSTANCIA_SEMPRE", False)
    j = JanelasFalsas(aberta=True)
    resultado = _aplicar(j)

    assert j.mortes == 0 and j.lancamentos == []
    assert resultado.aplicou is True
    assert resultado.lancou_o_programa is False


def test_a_janela_MINIMIZADA_e_restaurada_antes_do_clique():
    """Relato do usuário: já aberto às vezes não funciona, "deve estar minimizado".

    Restaurar é barato e cobre o caso em que o programa ignora o `BM_CLICK` por
    não ter sido pintado. SEM roubar o foco -- ver `restaurar_janela`.
    """
    j = JanelasFalsas(aberta=True, minimizada=True)
    _aplicar(j)
    assert j.restauracoes >= 1


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


# ===========================================================================
# REAPLICAR PELA ENTRADA DA CAVE -- 07/09/2026
# ===========================================================================

def _ui_service():
    """Um `UIService` cru: só o que a reaplicação toca."""
    from blazesbot.bot.bc import ui_service as mod_ui
    ui = mod_ui.UIService.__new__(mod_ui.UIService)
    ui.ctx = SimpleNamespace(log=_log())
    ui._falhas_rapidas = 0
    return ui, mod_ui


def test_falha_mecanica_em_serie_REAPLICA_o_petbug(monkeypatch):
    """*"Se não usa ele, fica outros players na frente e isso faz ele não
    conseguir clicar no NPC de entrar na cave"* — usuário, 07/09/2026.

    O log daquela madrugada: 13.449 falhas em 4 h, com o patch aplicado uma
    única vez, 9 h antes, num cliente que nem existia mais.
    """
    ui, mod_ui = _ui_service()
    aplicacoes = []
    monkeypatch.setattr(mod_ui.petbug, "aplicar_patch",
                        lambda **kw: aplicacoes.append(1))

    for _ in range(mod_ui.FALHAS_MECANICAS_PARA_REAPLICAR_O_PETBUG - 1):
        ui.registrar_falha_de_entrada()
    assert aplicacoes == [], "reaplicou cedo demais"

    ui.registrar_falha_de_entrada()
    assert len(aplicacoes) == 1


def test_a_reaplicacao_TEM_CADENCIA(monkeypatch):
    """Conta presa não pode matar e reabrir um programa de terceiro sem parar."""
    ui, mod_ui = _ui_service()
    aplicacoes = []
    monkeypatch.setattr(mod_ui.petbug, "aplicar_patch",
                        lambda **kw: aplicacoes.append(1))

    for _ in range(mod_ui.FALHAS_MECANICAS_PARA_REAPLICAR_O_PETBUG * 5):
        ui.registrar_falha_de_entrada()
    assert len(aplicacoes) == 1


def test_o_PETBUG_que_explode_nao_derruba_a_entrada(monkeypatch):
    """Programa de terceiro não pode custar a disputa da cave."""
    ui, mod_ui = _ui_service()

    def explode(**kw):
        raise RuntimeError("o patcher sumiu")

    monkeypatch.setattr(mod_ui.petbug, "aplicar_patch", explode)
    for _ in range(mod_ui.FALHAS_MECANICAS_PARA_REAPLICAR_O_PETBUG):
        ui.registrar_falha_de_entrada()


# ===========================================================================
# A METADE DO F12 -- conferivel por MEMORIA desde 10/09/2026
# ===========================================================================
#
# O patcher nativo se anuncia como "Pet Bug Fix & F12 Hide". A primeira metade
# (os seis NOPs) sempre foi conferivel em memoria. A segunda nao era: o
# conferidor mandava PARAR O BOT e apertar a tecla a mao, porque com o F12
# preso nao ha pet na tela -- patcheado ou nao.
#
# A auditoria de 10/09/2026 rodou o patcher nativo nos seis clientes com o
# antes-e-depois de toda pagina de 4 KB, e provou de passagem que ele NAO faz
# nada alem dos dois sitios: zero mudanca de protecao, zero modulo novo, zero
# thread nova, zero regiao executavel nova.

def _memoria_f12(a, b, ligado=True):
    """Duble com as duas bandeiras do F12."""
    from blazesbot.core import memory as mem_mod
    m = mem_mod.Memory.__new__(mem_mod.Memory)
    valores = {mem_mod.ADDR_F12_PRESO: a,
               mem_mod.ADDR_F12_PRESO_SEGUNDA: b}
    m.read_int = lambda e: valores.get(e)
    return m


def test_os_enderecos_do_f12_sao_os_medidos():
    from blazesbot.core import memory as mem_mod
    assert mem_mod.ADDR_F12_PRESO == 0x0115CB88
    assert mem_mod.ADDR_F12_PRESO_SEGUNDA == 0x011636BC
    assert mem_mod.USAR_BANDEIRA_DO_F12 is True


def test_f12_preso_e_solto():
    assert _memoria_f12(1, 1).esconder_jogadores_ativo() is True
    assert _memoria_f12(0, 0).esconder_jogadores_ativo() is False


def test_as_DUAS_bandeiras_DISCORDANDO_devolve_None():
    """Sao duas de proposito: nao se sabe qual e "a" bandeira, entao a
    redundancia vira o controle. Discordancia e "nao sei", nao um booleano com
    cara de certeza."""
    assert _memoria_f12(1, 0).esconder_jogadores_ativo() is None
    assert _memoria_f12(0, 1).esconder_jogadores_ativo() is None


def test_valor_NUNCA_VISTO_devolve_None():
    """So 0 e 1 foram observados em 3 rodadas de solta/prende nos seis
    clientes. Qualquer outra coisa nao vira booleano calado."""
    for nunca_visto in (2, -1, 903, None):
        assert _memoria_f12(nunca_visto, nunca_visto
                            ).esconder_jogadores_ativo() is None


def test_ilegivel_devolve_None():
    assert _memoria_f12(None, 1).esconder_jogadores_ativo() is None
    assert _memoria_f12(1, None).esconder_jogadores_ativo() is None


def test_desligado_devolve_None_e_nao_False(monkeypatch):
    from blazesbot.core import memory as mem_mod
    monkeypatch.setattr(mem_mod, "USAR_BANDEIRA_DO_F12", False)
    assert _memoria_f12(1, 1).esconder_jogadores_ativo() is None


def test_o_F12_NAO_mexe_no_array_de_entidades():
    """Medido: 37 entradas com a tecla presa e 37 solta. Ele tira da CENA, nao
    do jogo -- e e por isso que a leitura de alvo funciona com a tecla presa.
    Se alguem escrever que o F12 esvazia o array, este teste aponta a medicao."""
    import inspect

    from blazesbot.core import memory as mem_mod
    fonte = inspect.getsource(mem_mod)
    assert "array de entidades NAO muda" in fonte


def test_o_conferidor_checa_as_DUAS_metades():
    """Ele nao pode voltar a mandar olhar a tela: com o bot rodando o visual
    nao responde, porque o F12 esconde os pets patcheado ou nao."""
    import inspect

    from blazesbot.tools import conferir_petbug
    fonte = inspect.getsource(conferir_petbug)
    assert "esconder_jogadores_ativo" in fonte
    assert "F12 preso" in fonte
