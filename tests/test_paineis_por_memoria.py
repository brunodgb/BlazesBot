"""PAINEL DE UI POR MEMORIA -- e o contraexemplo que reduziu este patch.

=========================================================================
O QUE ENTROU, E O QUE FOI DERRUBADO PELO CAMPO
=========================================================================

O que entrou:

    `quest_aberto()`            -- discriminador validado
    `dialogo_de_ui_a_frente()`  -- SINAL DE UMA VIA

O que foi escrito, testado em bancada, e DERRUBADO na validacao em campo antes
de chegar aqui:

    "bandeira == 0 significa nada aberto, com CERTEZA"     -> FALSO
    "bandeira != 0 e segunda == 0 significa a BOLSA"       -> FALSO

O contraexemplo, medido em 02/09/2026 lendo os valores crus lado a lado com a
cadeia de bolsa ja validada (902 fechada / 903 aberta), em seis contas:

    bandeira | segunda | cadeia | vezes
    ---------+---------+--------+------
       != 0  |   != 0  |   902  |  12    painel aberto, bolsa fechada
       != 0  |   != 0  |   903  |  11    bolsa ABERTA, e `segunda` != 0
       == 0  |   != 0  |   903  |   7    bolsa aberta com a bandeira em ZERO
       == 0  |   == 0  |   902  |   6    nada aberto

A terceira linha derruba o "nao com certeza": a bolsa estava aberta e a bandeira
valia zero. A segunda derruba a regra da bolsa.

POR QUE O ERRO NAO FOI PARA PRODUCAO: a validacao em campo comparava a regra
nova com uma SEGUNDA FONTE independente, e contou a discordancia -- 105 de 240
leituras. Um leitor sozinho teria devolvido `False` com confianca, e ninguem
saberia.

=========================================================================
O QUE ESTE ARQUIVO TRAVA
=========================================================================

  * o interruptor fica LIGADO;
  * o `False` de `dialogo_de_ui_a_frente()` NAO pode voltar a ser tratado como
    prova de tela livre -- ha teste com o contraexemplo medido;
  * `modal_open()` NAO e reescrito pela bandeira (ela acende com a bolsa e com o
    quest log, que nao sao modais, e o watchdog conclui DC pela persistencia do
    modal);
  * "nao sei" continua sendo `None`, nunca `False`.
"""
from __future__ import annotations

import inspect

from blazesbot.core import memory as mem


def _memoria(bandeira=0, segunda=0, quest=0, ilegivel=()):
    m = mem.Memory.__new__(mem.Memory)
    valores = {
        mem.ADDR_PAINEL_ABERTO: bandeira,
        mem.ADDR_PAINEL_SEGUNDA_FENDA: segunda,
        mem.ADDR_QUEST_ABERTO: quest,
    }

    def ler(endereco):
        if endereco in ilegivel:
            return None
        return valores.get(endereco, 0)

    m.read_uint = ler
    m.read_int = ler
    return m


# ===========================================================================
# O INTERRUPTOR E OS ENDERECOS
# ===========================================================================

def test_o_interruptor_esta_ligado():
    assert mem.USAR_PAINEL_POR_MEMORIA is True


def test_os_enderecos_sao_os_medidos():
    assert mem.ADDR_QUEST_ABERTO == 0x012D0C78
    assert mem.ADDR_PAINEL_ABERTO == 0x012CE3D8
    assert mem.ADDR_PAINEL_SEGUNDA_FENDA == 0x012CE3E0


def test_a_bolsa_fechada_e_902_medido_em_campo():
    """O comentario herdado dizia "0 or 903". O 0 nunca apareceu; e 902."""
    assert mem.BAG_CLOSED_VALUE == 902
    assert mem.BAG_OPEN_VALUE == 903


def test_desligado_devolve_nao_sei_e_nao_False(monkeypatch):
    monkeypatch.setattr(mem, "USAR_PAINEL_POR_MEMORIA", False)
    m = _memoria(bandeira=0x10000000, quest=1)
    assert m.quest_aberto() is None
    assert m.dialogo_de_ui_a_frente() is None


# ===========================================================================
# O DISCRIMINADOR DO QUEST
# ===========================================================================

def test_quest_aberto():
    m = _memoria(bandeira=0x060E70F0, quest=1)
    assert m.quest_aberto() is True


def test_quest_fechado_mesmo_com_outro_painel_aberto():
    """O `0` com outro painel aberto e o que faz dele discriminador: em 3 de 3
    rodadas ficou em 0 para Item, Skill, Attribute, Guild e System."""
    m = _memoria(bandeira=0x112147B0, segunda=0x11214000, quest=0)
    assert m.quest_aberto() is False


def test_quest_ilegivel_e_None():
    m = _memoria(ilegivel={mem.ADDR_QUEST_ABERTO})
    assert m.quest_aberto() is None


# ===========================================================================
# A BANDEIRA E DE UMA VIA -- o contraexemplo travado
# ===========================================================================

def test_ponteiro_significa_dialogo_a_frente():
    m = _memoria(bandeira=0x10DDEE60)
    assert m.dialogo_de_ui_a_frente() is True


def test_zero_NAO_prova_tela_livre():
    """O caso medido 7 vezes: bandeira em ZERO com a bolsa ABERTA.

    O metodo pode devolver `False`, mas o contrato dito no docstring e que esse
    `False` nao conclui nada. Este teste existe para que a afirmacao derrubada
    nao volte disfarcada de melhoria.
    """
    m = _memoria(bandeira=0, segunda=0x0610AE88)
    assert m.dialogo_de_ui_a_frente() is False
    fonte = inspect.getsource(mem.Memory.dialogo_de_ui_a_frente)
    assert "UMA VIA" in fonte
    assert "NAO PROVA" in fonte or "NÃO PROVA" in fonte


def test_nao_existe_leitor_que_afirme_tela_livre():
    """Os nomes que a versao derrubada usava nao podem reaparecer."""
    for proibido in ("nada_aberto_na_ui", "bolsa_aberta_pela_bandeira",
                     "estado_da_ui"):
        assert not hasattr(mem.Memory, proibido), (
            "%s voltou -- ele afirmava 'nada aberto com certeza' ou "
            "classificava a bolsa por `segunda == 0`, e as duas coisas foram "
            "refutadas em campo" % proibido)


def test_bandeira_ilegivel_e_None():
    m = _memoria(ilegivel={mem.ADDR_PAINEL_ABERTO})
    assert m.dialogo_de_ui_a_frente() is None


# ===========================================================================
# A TRAVA MAIS IMPORTANTE: isto NAO substitui `modal_open`
# ===========================================================================

def test_modal_open_continua_lendo_ADDR_MODAL():
    """A bandeira acende com a bolsa e com o quest log, que NAO sao modais. O
    watchdog conclui DC pela PERSISTENCIA do modal; trocar um pelo outro faria
    ele ver "modal" a cada abertura de bolsa."""
    fonte = inspect.getsource(mem.Memory.modal_open)
    assert "ADDR_MODAL" in fonte
    assert "ADDR_PAINEL_ABERTO" not in fonte


def test_os_leitores_antigos_seguem_independentes():
    """Se um deles passasse a ler a bandeira, as duas fontes viravam uma -- e a
    discordancia, que foi o que pegou o erro deste patch, deixaria de existir."""
    for metodo in (mem.Memory.modal_open, mem.Memory.dialog_open,
                   mem.Memory.loot_window_open, mem.Memory.system_menu_open,
                   mem.Memory.bag_open):
        fonte = inspect.getsource(metodo)
        assert "ADDR_PAINEL_ABERTO" not in fonte
        assert "ADDR_QUEST_ABERTO" not in fonte


# ===========================================================================
# O DIAGNOSTICO EXPOE OS VALORES CRUS
# ===========================================================================

def test_o_probe_expoe_os_campos_e_os_valores_crus():
    """Booleano nao basta num sinal de uma via: quem investigar precisa dos
    numeros, e das duas fontes da bolsa lado a lado."""
    fonte = inspect.getsource(mem.Memory.probe)
    for chave in ("quest aberto", "dialogo de UI a frente", "bandeira (cru)",
                  "2a fenda (cru)", "bolsa (cru: 902 fechada, 903 aberta)"):
        assert chave in fonte, "o probe deixou de expor %r" % chave
