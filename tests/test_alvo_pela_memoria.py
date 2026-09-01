"""O ALVO VEM DA MEMÓRIA. A TELA É RESERVA.

Virada de 25/08/2026, e a medição que a autorizou é o log do `18-CASAR-ALVO`
numa luta inteira. Nos poucos ciclos em que memória e tela discordaram, **a
errada era a tela**:

    'Gun Witch' nv50           hp=6/100  (6.0%)   barra=23.1%   <- atraso
    'Blaze Skull Marshal' fase 2  hp=75/100 (75%)  barra=50.0%  <- barra amarela

A barra desenhada tem uma coleção de modos de falha que um inteiro vindo da
struct não tem -- e todos erravam CALADOS:

  * piso de 0,7% com o mob morto (bordas diluindo a média por área);
  * a amarela sobreposta à vermelha na fase 2 do boss;
  * o `EnemyDead.png` com falso positivo medido (0,955-0,971 com o mob VIVO);
  * a régua devolvendo float confiante enquanto media outra coisa.

O que este arquivo trava é que a memória vem PRIMEIRO, que ela não paga
captura, e que a tela continua inteira como reserva.
"""
from types import SimpleNamespace

from blazesbot.bot.bc.combat import CombatEngine
from blazesbot.core import target_hybrid as th


def _entidade(hp, maximo=100, nome="Gun Witch", nivel=50, ident=0x01832BD5):
    return {"obj": 0x2E9A99B0, "id": ident, "nome": nome, "nivel": nivel,
            "hp": hp, "max_hp": maximo, "pct": hp / maximo, "pos": (103, -404)}


def _motor(entidade):
    motor = CombatEngine.__new__(CombatEngine)
    motor.linhas: list[str] = []

    def anotar(f, *a):
        motor.linhas.append(f % a if a else f)

    motor.ctx = SimpleNamespace(
        pid=1, hwnd=2,
        templates=SimpleNamespace(load=lambda _n: "modelo"),
        log=SimpleNamespace(info=anotar, debug=lambda *a, **k: None,
                            warning=lambda *a, **k: None,
                            error=lambda *a, **k: None),
    )
    vigia = th.TargetHybrid(logger=motor.ctx.log)
    vigia.entidade_do_alvo = lambda _pid: entidade
    vigia.id_do_alvo = lambda _pid: None if entidade is None else entidade["id"]
    motor._target_hybrid = vigia
    motor._na_segunda_fase_do_boss = False
    motor._ultimo_alvo_morto_id = None
    motor._ultima_leitura_do_alvo = None
    motor._ultimo_escore_do_marcador = None
    motor._melhor_escore_do_marcador = None
    return motor


# ===========================================================================
# A LEITURA
# ===========================================================================

def test_a_memoria_responde_e_a_tela_NEM_E_CAPTURADA(monkeypatch):
    """O ganho maior não é velocidade: é que a captura era a ORIGEM de todos os
    erros calados desta área."""
    capturas = []
    monkeypatch.setattr(th.vision, "capture_window",
                        lambda hwnd: capturas.append(hwnd))

    vigia = th.TargetHybrid()
    vigia.entidade_do_alvo = lambda _pid: _entidade(hp=42)

    info = vigia.ler(pid=1, hwnd=2)

    assert capturas == [], "capturou a tela com a memória tendo respondido"
    assert info.pela_memoria is True
    assert info.fonte == "memoria"
    assert info.hp_pct == 0.42
    assert info.nome == "Gun Witch"


def test_sem_entidade_a_TELA_continua_inteira(monkeypatch):
    """Medido: no instante em que um alvo novo é selecionado, a entidade pode
    demorar um ciclo a entrar no array (1 leitura em ~45 numa luta de boss).

    Cair para "não sei" ali gastaria uma volta do laço à toa.
    """
    capturas = []
    monkeypatch.setattr(th.vision, "capture_window",
                        lambda hwnd: capturas.append(hwnd) or "quadro")
    monkeypatch.setattr(th.vision, "frame_is_blank", lambda _q: False)
    monkeypatch.setattr(th.vision, "ler_barra_do_alvo", lambda _q: None)

    vigia = th.TargetHybrid()
    vigia.entidade_do_alvo = lambda _pid: None
    vigia.id_do_alvo = lambda _pid: 0x01144C5D

    info = vigia.ler(pid=1, hwnd=2)

    assert capturas == [2], "não caiu para a tela quando a memória falhou"
    assert info.pela_memoria is False
    assert info.fonte == "tela"


def test_o_marcador_NAO_e_consultado_quando_a_memoria_responde():
    """`hp == 0` é exato. Perguntar a um template com falso positivo medido
    (0,955-0,971 com o mob VIVO) só poderia piorar uma resposta certa."""
    from blazesbot.core.target_hybrid import AlvoInfo

    info = AlvoInfo(target_id=1, mudou=False, barra=None, quadro=None,
                    timestamp=0.0, entidade=_entidade(hp=0))
    assert info.vale_olhar_o_marcador is False


# ===========================================================================
# A MORTE
# ===========================================================================

def test_hp_maior_que_zero_e_VIVO():
    motor = _motor(_entidade(hp=8))
    assert motor._alvo_morreu() is False
    assert motor._ultima_leitura_do_alvo.fonte == "memoria"
    assert "8/100" in motor._ultima_leitura_do_alvo.motivo


def test_hp_zero_e_MORTE():
    motor = _motor(_entidade(hp=0))
    assert motor._alvo_morreu() is True
    assert motor._ultima_leitura_do_alvo.fonte == "memoria"
    assert any("MORREU" in linha for linha in motor.linhas)


def test_a_mesma_morte_NAO_sai_duas_vezes():
    """O cadáver fica selecionável por 7 a 13 s (medido). Sem a trava, ele
    gastaria um TAB por leitura enquanto estivesse ali.

    A trava é por IDENTIDADE, não por tempo -- e agora a identidade é o id da
    entidade, que é exatamente o que ela sempre quis ser.
    """
    motor = _motor(_entidade(hp=0))
    assert motor._alvo_morreu() is True
    assert motor._alvo_morreu() is False
    assert motor._alvo_morreu() is False
    mortes = [linha for linha in motor.linhas if "MORREU" in linha]
    assert len(mortes) == 1, mortes


def test_alvo_novo_com_hp_zero_conta_de_novo():
    """A trava é por id: cadáver antigo não pode calar a morte do PRÓXIMO."""
    motor = _motor(_entidade(hp=0, ident=0xAAA))
    assert motor._alvo_morreu() is True

    outro = _entidade(hp=0, ident=0xBBB, nome="Rose Snake")
    motor._target_hybrid.entidade_do_alvo = lambda _pid: outro
    motor._target_hybrid.id_do_alvo = lambda _pid: outro["id"]
    assert motor._alvo_morreu() is True


def test_a_fase_1_do_boss_NAO_zera_e_isso_e_medido():
    """A fase 1 para em `hp=1` e some, nascendo a fase 2 como ENTIDADE NOVA --
    id novo, endereço novo, e nível 50 -> 51:

        [06:51:36] id=0x01144c5d obj=0x2e9856a0 'Blaze Skull Marshal' nv50 hp=1/100
        [06:51:38] id=0x01144c5d obj=0x2e9856a0 'Blaze Skull Marshal' nv50 hp=1/100
        [06:51:40] id=0x01e129c3 obj=0x2e995618 'Blaze Skull Marshal' nv51 hp=75/100

    Não é um caso a tratar aqui, e este teste existe para dizer isso: o boss
    NUNCA foi dado por morto por HP. A regra do projeto -- *"boss só é dado por
    morto quando SAI DE BATALHA"* -- já cobria, e agora tem o porquê medido.

    O que NÃO pode acontecer é `hp=1` virar morte: se virasse, o bot daria TAB
    no meio da virada de fase e largaria o boss.
    """
    motor = _motor(_entidade(hp=1, nome="Blaze Skull Marshal", ident=0x01144C5D))
    assert motor._alvo_morreu() is False
    assert not [linha for linha in motor.linhas if "MORREU" in linha]


def test_a_fase_2_le_o_HP_REAL_e_nao_o_da_barra_amarela():
    """A tela lia 50,0% com o boss em 75/100 -- a amarela sobreposta à vermelha.

    É a divergência que mais justifica esta virada: na fase 2 a tela erra por
    dezenas de pontos percentuais, e erra calada.
    """
    from blazesbot.core.target_hybrid import AlvoInfo
    from blazesbot.core.vision import LeituraDaBarra

    barra = LeituraDaBarra(vermelho=0.0, amarelo=0.50, vazio=0.5, colunas=134,
                           primeiro_x=466, ultimo_x=600, fonte="offset fixo")
    info = AlvoInfo(target_id=0x01E129C3, mudou=False, barra=barra, quadro=None,
                    timestamp=0.0,
                    entidade=_entidade(hp=75, nome="Blaze Skull Marshal",
                                       nivel=51, ident=0x01E129C3))
    assert info.hp_pct == 0.75, "a barra amarela ganhou da memória"


# ===========================================================================
# O NOME
# ===========================================================================

def test_o_nome_do_alvo_voltou():
    """`_nomes_do_alvo` foi escrito VAZIO, como o lugar da resposta, com a
    previsão de que *"quem descobrir uma fonte de nome muda só este método"*.

    Foi exatamente o que aconteceu.
    """
    motor = _motor(_entidade(hp=50, nome="Cemetery Guard"))
    assert motor._nomes_do_alvo() == ["Cemetery Guard"]
    assert motor._veredito_do_alvo("Cemetery Guard") == "bate"
    assert motor._veredito_do_alvo("Gun Witch") == "acabaram"


def test_sem_entidade_o_veredito_e_ILEGIVEL_e_isso_e_NAO_SEI():
    """"Não sei" nunca autoriza parar de bater: perder a luta por uma leitura
    que falhou é pior do que bater no alvo errado por um ciclo."""
    motor = _motor(None)
    assert motor._nomes_do_alvo() == []
    assert motor._veredito_do_alvo("Gun Witch") == "ilegivel"


def test_o_portao_de_nome_esta_LIGADO():
    """Ele foi aposentado por falta de fonte de nome -- 14/14 lutas gritando
    `ilegivel` sem decidir nada. A fonte apareceu."""
    from blazesbot.bot.bc import combat

    assert combat.USAR_PORTAO_DE_NOME is True


# ===========================================================================
# O LOG
# ===========================================================================

def test_o_log_mostra_nome_e_HP_exato():
    """Pedido do usuário: *"quero poder ir vendo a cada alteração, por exemplo:
    100% 86% 52% 20% 0%"*. Com a memória, vem nome e `hp/max` junto -- `8/100`
    diz mais do que `8.0%`, e o nome responde "estou batendo no quê?"."""
    vigia = th.TargetHybrid()
    info = th.AlvoInfo(target_id=7, mudou=False, barra=None, quadro=None,
                       timestamp=0.0, entidade=_entidade(hp=86))

    linha = vigia.linha_do_log(info, anterior=1.0, segunda_fase=False)

    assert "Gun Witch" in linha
    assert "86.0%" in linha
    assert "(86/100, nv50)" in linha
    assert "-14%" in linha


def test_o_valor_mostrado_NAO_zera_quando_a_barra_e_None():
    """DEFEITO QUE ESTE TESTE TRAVA: com a virada para memória, `info.barra` é
    `None` no caminho normal. A versão anterior devolvia `0.0` nesse caso -- o
    log mostraria 0% para todo alvo VIVO, e o `registrar` acharia que a vida
    despencava a cada leitura."""
    info = th.AlvoInfo(target_id=7, mudou=False, barra=None, quadro=None,
                       timestamp=0.0, entidade=_entidade(hp=86))

    assert th.TargetHybrid._valor_mostrado(info, segunda_fase=False) == 0.86
    assert th.TargetHybrid._valor_mostrado(info, segunda_fase=True) == 0.86


def test_na_fase_2_a_memoria_dispensa_a_conta_das_DUAS_barras():
    """`total_do_boss` existe porque a TELA desenha a amarela por cima da
    vermelha e nenhuma sozinha é a vida do boss. A struct não tem esse
    problema: ela leu 75/100 enquanto a barra lia 50,0%."""
    info = th.AlvoInfo(target_id=8, mudou=False, barra=None, quadro=None,
                       timestamp=0.0,
                       entidade=_entidade(hp=75, nome="Blaze Skull Marshal",
                                          nivel=51))

    assert th.TargetHybrid._valor_mostrado(info, segunda_fase=True) == 0.75



# ===========================================================================
# QUANTOS CAMINHOS DÃO TAB
# ===========================================================================

def test_existem_exatamente_DOIS_lugares_que_apertam_a_tecla_de_alvo():
    """Um TAB novo em qualquer outro lugar é um TAB que ninguém sabe explicar.

    Os dois de hoje, e a diferença entre eles importa para ler o log:

      1. `_trocar_de_alvo` -- o gesto "aperta o TAB e espera o jogo redesenhar",
         usado por quem troca de alvo **por MORTE**: o laço da luta
         (`atacar_ate_sair_de_combate`, atrás de `_alvo_morreu`) e o
         destravamento (`limpar_o_combate`, atrás da pausa de 3 s);
      2. `_fase_boss` -- **para ADQUIRIR o boss** que não engajou em
         `SEGUNDOS_ANTES_DO_TAB_NO_BOSS`. Este NÃO é morte de ninguém, e é o
         único do bot que não é.
    """
    import ast
    from pathlib import Path

    caminho = (Path(__file__).resolve().parent.parent
               / "blazesbot" / "bot" / "bc" / "combat.py")
    fonte = ast.parse(caminho.read_text(encoding="utf-8"))

    linhas = [n.lineno for n in ast.walk(fonte)
              if isinstance(n, ast.Attribute) and n.attr == "next_target"]

    assert len(linhas) == 2, (
        f"o número de TABs mudou: {len(linhas)} em {linhas}. Todo TAB novo "
        f"precisa dizer no log se é morte ou aquisição.")


def test_o_TAB_por_morte_so_sai_com_morreu_True():
    """O laço da luta só troca de alvo dentro de `if morreu:`.

    A tecla saiu daqui e foi para `_trocar_de_alvo` (um lugar só para o gesto),
    então quem o teste procura agora é a CHAMADA. A pergunta que ele trava é a
    mesma de sempre: o laço da luta não pode trocar de alvo com o mob vivo.
    """
    import ast
    import inspect
    import textwrap

    from blazesbot.bot.bc.combat import CombatEngine

    fonte = textwrap.dedent(
        inspect.getsource(CombatEngine.atacar_ate_sair_de_combate))
    arvore = ast.parse(fonte)

    def _trocas(no_raiz):
        return [n.lineno for n in ast.walk(no_raiz)
                if isinstance(n, ast.Attribute) and n.attr in
                ("next_target", "_trocar_de_alvo")]

    dentro_de_morreu = []
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.If) and isinstance(no.test, ast.Name)
                and no.test.id == "morreu"):
            continue
        dentro_de_morreu += _trocas(no)

    todos = _trocas(arvore)

    assert todos, "o TAB por morte sumiu do laço da luta"
    assert dentro_de_morreu == todos, (
        "há troca de alvo no laço da luta FORA do `if morreu:` -- ela sairia "
        "com o mob vivo")


def test_so_a_memoria_declara_morte_esta_LIGADO():
    from blazesbot.bot.bc import combat

    assert combat.SO_A_MEMORIA_DECLARA_MORTE is True


# ===========================================================================
# `is_sitting` É TRI-ESTADO -- conserto de 26/08/2026
# ===========================================================================
#
# Ela devolvia `bool` puro: falha de leitura virava `False`, ou seja "está de
# pé". O contrato tri-estado estava documentado com todo cuidado no CONSUMIDOR
# (`bot/app/cura.py`), mas a FONTE nunca o cumpriu -- e nenhum teste pegou,
# porque os testes do consumidor injetam a leitura por `lambda`.
#
# A lição: contrato tri-estado documentado no consumidor é expectativa. A prova
# mora na fonte.

def _memoria_com_byte(valor):
    """Um `Memory` sem processo: só o suficiente para `is_sitting`."""
    from blazesbot.core.memory import Memory

    m = Memory.__new__(Memory)
    m._player_field = lambda offset: 0x1000
    m.read_byte = lambda addr: valor
    return m


def test_sentado_de_verdade():
    from blazesbot.core.memory import SIT_VALUE

    assert _memoria_com_byte(SIT_VALUE).is_sitting() is True


def test_de_pe_de_verdade():
    from blazesbot.core.memory import SIT_VALUE

    assert _memoria_com_byte(SIT_VALUE + 1).is_sitting() is False


def test_leitura_que_FALHOU_devolve_NAO_SEI_e_nao_de_pe():
    """MEDIDO no log de 25/08/2026: 4 avisos de "acabaram as poções" na MESMA
    sessão em que houve 3 curas bem-sucedidas com 2 poções cada. As poções
    existiam; a leitura é que dizia `False` sem saber."""
    assert _memoria_com_byte(None).is_sitting() is None


def test_sem_endereco_do_campo_tambem_e_NAO_SEI():
    from blazesbot.core.memory import Memory

    m = Memory.__new__(Memory)
    m._player_field = lambda offset: None
    assert m.is_sitting() is None


def test_os_consumidores_do_BC_NAO_mudam_de_comportamento():
    """Os quatro usos no BC são booleanos (`not estado.sitting`,
    `estado.sitting and k.sit`), e `None` é falso exatamente como `False` era.
    O ganho é só para quem sabe perguntar a diferença."""
    assert not _memoria_com_byte(None).is_sitting()
    assert not _memoria_com_byte(0).is_sitting()


def test_pet_active_tambem_e_TRI_ESTADO():
    """MESMA classe de defeito que `is_sitting`, consertada no mesmo dia.

    O executor do APP usa esta resposta para decidir se aperta a tecla de
    invocar, e já documentava as três: *"tratar `None` como `False` faria a
    macro apertar a tecla do pet em toda volta num cliente que não lê memória
    -- que é justamente o cliente para o qual este módulo foi feito"*. Em
    várias classes a tecla é INTERRUPTOR, então o toque a mais desinvoca o pet
    que acabou de vir.
    """
    from blazesbot.core.memory import Memory

    def _mem(valor, addr=0x1000):
        m = Memory.__new__(Memory)
        m._player_field = lambda offset: addr
        m.read_byte = lambda a: valor
        return m

    assert _mem(1).pet_active() is True
    assert _mem(0).pet_active() is False
    assert _mem(None).pet_active() is None
    assert _mem(None, addr=None).pet_active() is None
    # Os consumidores do BC usam em contexto booleano: nada muda para eles.
    assert not _mem(None).pet_active()
