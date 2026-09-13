"""NUNCA A PÉ DENTRO DA CAVE, e todo o desmonte num lugar só.

As quatro regras que este arquivo segura foram combinadas com o usuário em
25/08/2026:

1. **A montaria insiste.** Lê o ponteiro, espera até 3 s, não montou clica de
   novo. Sem teto para desistir -- *"nunca deve seguir a pé dentro da cave; ir
   até o last boss depende de ter a montaria e estar usando ela"*.
2. **Fora da cave só desmonta se o pet estiver inativo.** Cura, buff e comida
   deixam de tirar a montaria em Stone City.
3. **O preparo de entrada faz tudo o que exige estar a pé**, na ordem cura →
   buffs → pet → comida → montar.
4. **Os cronômetros da run começam na montaria**, não na entrada.

E a quinta, do pet: **a grade da comida é FIXA**. Atrasar uma refeição não
empurra as seguintes, e a grade sobrevive a reinício -- senão o número de
refeições do dia cai e o pet some por fome.
"""
import time
from types import SimpleNamespace

import pytest

from blazesbot.bot import combate as motor_de_combate
from blazesbot.bot import navegacao as navigation
from blazesbot.bot.bc import mapa_bc
from blazesbot.bot.bc.combat import CombatEngine
from blazesbot.bot.hh import mapa_hh
from blazesbot.bot.hh.combate import CombateHH
from blazesbot.core.pet import PetFeeder

# ===========================================================================
# 1. A MONTARIA INSISTE
# ===========================================================================

class _NavFalso:
    """O portão de verdade, com `ensure_mounted` sob controle do teste.

    O DIAGNÓSTICO É O DE VERDADE (`_diagnosticar_o_portao`, emprestado da classe
    real): ele é parte do contrato do portão desde 01/09/2026 e um falso que o
    substituísse por um `pass` deixaria de exercitar justamente a decisão nova
    -- "não monto porque estou EM BATALHA" e "cadáver não monta".
    """

    def __init__(self, montar_na_tentativa: int, log) -> None:
        self.tentativas = 0
        self._alvo = montar_na_tentativa
        # ESTES TESTES SÃO SOBRE INSISTIR: o portão só insiste quando o trajeto
        # exige montaria, que é o padrão da BC. O `False` tem testes próprios
        # em `test_morte_no_app` (a volta ao ponto do APP, que vai a pé).
        self._exigir_montaria = True
        # FORA da cave por padrão: "East of Simen Mountain" é região conhecida
        # do mapa-múndi, e é isso que libera a desistência dos 20 toques.
        self.location_name = lambda: "East of Simen Mountain"
        self._avisou_a_pe = False
        # Sem destravamento ligado: estes testes são sobre INSISTIR, e a ligação
        # com o combate tem os seus próprios (`test_destravamento_do_combate`).
        self.destravar_o_combate = None
        # O PASSO DE DESTRAVE também é o de verdade (06/09/2026): fora de
        # combate, passados 10 s, o portão anda 6 unidades porque o jogo cancela
        # a montaria sozinho. Estes testes têm `in_battle` = False, então ele
        # ENTRA — e é isso que se quer, senão o dublê deixaria de exercitar o
        # ramo que mais roda. O clique é o único ponto substituído: aqui ele
        # apenas registra, para o teste poder contar os passos.
        self._ultimo_passo_de_destrave = 0.0
        self._direcao_do_passo_de_destrave = 0
        self.passos = []
        self.position = lambda: (1, 2)
        self._clicar_offset_e_verificar = (
            lambda centro, raio, dx, dy: self.passos.append((raio, dx, dy)) or True)
        self.ctx = SimpleNamespace(
            log=log,
            raise_if_stopped=lambda: None,
            account_login="teste",
            snapshot=lambda: SimpleNamespace(dead=False),
            settings=SimpleNamespace(keys=SimpleNamespace(mount="F1")),
            memory=SimpleNamespace(is_mounted=lambda: False,
                                   in_battle=lambda: False,
                                   position=lambda: (1, 2),
                                   location=lambda: "Cave"),
        )

    _diagnosticar_o_portao = navigation.Navigator._diagnosticar_o_portao
    _passo_para_destravar_a_montaria = (
        navigation.Navigator._passo_para_destravar_a_montaria)
    # O DISCRIMINADOR DA CAVE também é o de verdade: ele é parte da decisão
    # nova (desistir só FORA da cave), e um falso o esvaziaria de sentido.
    _dentro_da_cave = navigation.Navigator._dentro_da_cave

    def ensure_mounted(self, timeout=0.0):
        self.tentativas += 1
        return self.tentativas >= self._alvo


def _portao(montar_na_tentativa, linhas):
    log = SimpleNamespace(
        info=lambda f, *a: linhas.append(("INFO", f % a if a else f)),
        debug=lambda *a, **k: None,
        warning=lambda f, *a: linhas.append(("WARNING", f % a if a else f)),
        error=lambda f, *a: linhas.append(("ERROR", f % a if a else f)),
    )
    nav = _NavFalso(montar_na_tentativa, log)
    nav.garantir_montaria_para_andar = (
        navigation.Navigator.garantir_montaria_para_andar.__get__(nav))
    nav._sem_tecla_de_montaria = lambda _motivo: False
    return nav, linhas


def test_o_portao_insiste_ate_montar(monkeypatch):
    """A montaria sobe em 1 a 3 s; o portão não pode desistir antes disso."""
    monkeypatch.setattr(navigation.hotbar, "garantir_pagina_1",
                        lambda *a, **k: None)
    nav, linhas = _portao(montar_na_tentativa=4, linhas=[])

    assert nav.garantir_montaria_para_andar("atravessar a cave") is True
    assert nav.tentativas == 4


def test_o_portao_insiste_MUITO_antes_de_desistir(monkeypatch):
    """O DENTE da regra: insistir é o caminho normal, não a exceção.

    ATÉ 06/09/2026 ELE NÃO DESISTIA NUNCA, e isso tinha um motivo medido -- a
    pé não se chega no boss, e a run se perde mais tarde, depois de gastar a
    travessia inteira.

    O que mudou: uma conta SEM MONTARIA ficou 33 minutos e 315 tentativas
    parada, sem andar um passo, porque a tecla estava configurada (era o padrão)
    e o portão concluía que bastava insistir. Decisão do usuário no mesmo dia:
    *"caso tentou mais de 20 vezes ativar a montaria e não foi, vai a pé
    mesmo"*. Parado é pior que devagar.

    Este teste trava a PRIMEIRA metade: dentro do limite, ele insiste e monta.
    A segunda metade -- desistir no vigésimo -- é o teste seguinte.
    """
    monkeypatch.setattr(navigation.hotbar, "garantir_pagina_1",
                        lambda *a, **k: None)
    monkeypatch.setattr(navigation.diario, "registrar_evento",
                        lambda *a, **k: None)
    nav, linhas = _portao(montar_na_tentativa=8, linhas=[])

    assert nav.garantir_montaria_para_andar("ir até os guardas") is True
    assert nav.tentativas == 8
    gritos = [t for nivel, t in linhas if nivel == "ERROR"]
    assert gritos, "insistiu muito e não gritou nenhuma vez"
    assert "não chega no boss" in gritos[0].lower() or "boss" in gritos[0]


def test_o_portao_DESISTE_e_vai_a_pe_no_limite(monkeypatch):
    """A segunda metade: 20 tentativas sem montar e ele segue a pé.

    Medido em campo em 06/09/2026: a conta líder do time ficou 2015 s presa
    tentando montar para voltar ao ponto depois de reviver. 315 tentativas, zero
    passos, o time inteiro parado atrás dela.
    """
    monkeypatch.setattr(navigation.hotbar, "garantir_pagina_1",
                        lambda *a, **k: None)
    monkeypatch.setattr(navigation.diario, "registrar_evento",
                        lambda *a, **k: None)
    nav, linhas = _portao(montar_na_tentativa=10_000, linhas=[])

    assert nav.garantir_montaria_para_andar("atravessar o mapa") is False
    assert nav.tentativas == navigation.CICLOS_ANTES_DE_IR_A_PE
    gritos = [t for nivel, t in linhas if nivel == "ERROR"]
    assert any("VOU A PÉ" in t for t in gritos), gritos


def test_DENTRO_DA_CAVE_ele_nao_desiste_nunca(monkeypatch):
    """A regra nova é para FORA da cave. Decisão do usuário em 06/09/2026:
    *"mas isso é dentro da cave, APP não é cave e nunca será cave"*.

    Lá dentro "a pé" já foi medido como run perdida com atraso -- o personagem
    não chega no boss, e a travessia inteira se gasta para falhar no fim.
    """
    monkeypatch.setattr(navigation.hotbar, "garantir_pagina_1",
                        lambda *a, **k: None)
    monkeypatch.setattr(navigation.diario, "registrar_evento",
                        lambda *a, **k: None)
    nav, linhas = _portao(montar_na_tentativa=25, linhas=[])
    # Instância NÃO é região do mapa-múndi -- é assim que ele sabe.
    nav.location_name = lambda: "Bewitcher Cave"

    assert nav.garantir_montaria_para_andar("atravessar a cave") is True
    assert nav.tentativas == 25, ("desistiu dentro da cave; a pé não se chega "
                                  "no boss")


def test_sem_saber_ONDE_esta_ele_mantem_o_comportamento_antigo(monkeypatch):
    """Sem leitura, insistir -- estrear a regra nova às cegas seria trocar um
    defeito conhecido por um desconhecido."""
    monkeypatch.setattr(navigation.hotbar, "garantir_pagina_1",
                        lambda *a, **k: None)
    monkeypatch.setattr(navigation.diario, "registrar_evento",
                        lambda *a, **k: None)
    nav, linhas = _portao(montar_na_tentativa=25, linhas=[])
    nav.location_name = lambda: None

    assert nav.garantir_montaria_para_andar("atravessar o mapa") is True
    assert nav.tentativas == 25


def test_o_limite_de_desistencia_e_MUITO_maior_que_o_do_grito():
    """O grito é aviso; a desistência é decisão. Se os dois se encostassem, o
    bot passaria a andar a pé no primeiro soluço da montaria."""
    assert (navigation.CICLOS_ANTES_DE_IR_A_PE
            >= 3 * navigation.CICLOS_ANTES_DE_GRITAR)

def test_o_grito_so_comeca_depois_do_limite(monkeypatch):
    """Insistir calado é o certo no caso comum (1 a 3 s)."""
    monkeypatch.setattr(navigation.hotbar, "garantir_pagina_1",
                        lambda *a, **k: None)
    nav, linhas = _portao(montar_na_tentativa=2, linhas=[])

    nav.garantir_montaria_para_andar("atravessar a cave")

    assert not [t for nivel, t in linhas if nivel == "ERROR"]


def test_sem_tecla_configurada_desiste():
    """O único caso em que o portão devolve False: não há o que acionar."""
    nav, _ = _portao(montar_na_tentativa=1, linhas=[])
    nav._sem_tecla_de_montaria = lambda _motivo: True

    assert nav.garantir_montaria_para_andar("qualquer coisa") is False
    assert nav.tentativas == 0


def test_o_intervalo_entre_toques_cabe_na_subida_da_montaria():
    """MEDIÇÃO do usuário: montar leva de 1 a 3 s.

    A tecla é interruptor: um segundo toque DENTRO da subida desmonta quem
    estava montando. Com 1,50 s (o valor antigo) o toque caía no meio da
    montaria mais lenta, e o sintoma era indistinguível de "a montaria não
    funciona".
    """
    assert navigation.INTERVALO_REMONTAR >= 3.0


# ===========================================================================
# 2. FORA DA CAVE, SÓ DESMONTA SE O PET ESTIVER INATIVO
# ===========================================================================

def _motor(montado=True, pet_ativo=True, fora_da_cave=True, linhas=None):
    linhas = linhas if linhas is not None else []
    motor = CombatEngine.__new__(CombatEngine)
    motor.ctx = SimpleNamespace(
        account_login="teste",
        log=SimpleNamespace(
            info=lambda f, *a: linhas.append(f % a if a else f),
            debug=lambda *a, **k: None,
            warning=lambda f, *a: linhas.append(f % a if a else f)),
        memory=SimpleNamespace(
            is_mounted=lambda: montado,
            pet_active=lambda: pet_ativo,
            position=lambda: (1000, -500) if fora_da_cave else (200, 40),
            location=lambda: "Stone City" if fora_da_cave else "Cave"),
    )
    motor.linhas = linhas
    motor.desmontou = False

    def desmontar(*a, **k):
        motor.desmontou = True
        return True

    motor.nav = SimpleNamespace(ensure_dismounted=desmontar)
    return motor


def test_fora_da_cave_com_pet_ativo_NAO_desmonta(monkeypatch):
    """O sintoma relatado: em Stone City, indo ao vendedor e à Fay, o bot descia
    da montaria no meio do caminho."""
    monkeypatch.setattr(mapa_bc, "posicao_esta_fora_da_cave",
                        lambda _pos: True)
    motor = _motor(pet_ativo=True)

    assert motor._preparar_para_agir("alimentar o pet") is False
    assert motor.desmontou is False


def test_fora_da_cave_com_pet_INATIVO_desmonta(monkeypatch):
    """A exceção certa: entrar sem pet obriga a invocar lá dentro, parado no
    trem de mobs."""
    monkeypatch.setattr(mapa_bc, "posicao_esta_fora_da_cave",
                        lambda _pos: True)
    motor = _motor(pet_ativo=False)

    assert motor._preparar_para_agir("invocar o pet") is True
    assert motor.desmontou is True


def test_DENTRO_da_cave_desmonta_normalmente(monkeypatch):
    """A regra é só para fora. Dentro, curar exige estar a pé."""
    monkeypatch.setattr(mapa_bc, "posicao_esta_fora_da_cave",
                        lambda _pos: False)
    motor = _motor(pet_ativo=True)

    assert motor._preparar_para_agir("curar depois de entrar") is True
    assert motor.desmontou is True


def test_sem_saber_onde_esta_a_acao_PASSA(monkeypatch):
    """"Não sei" não bloqueia: não curar dentro da cave mata o personagem, e um
    desmonte a mais fora dela custa segundos."""
    monkeypatch.setattr(mapa_bc, "posicao_esta_fora_da_cave",
                        lambda _pos: False)          # é o que ela devolve sem leitura
    motor = _motor(pet_ativo=True)

    assert motor._preparar_para_agir("curar") is True


def test_o_interruptor_devolve_o_comportamento_antigo(monkeypatch):
    monkeypatch.setattr(motor_de_combate, "DESMONTAR_FORA_DA_CAVE_SO_SEM_PET", False)
    monkeypatch.setattr(mapa_bc, "posicao_esta_fora_da_cave",
                        lambda _pos: True)
    motor = _motor(pet_ativo=True)

    assert motor._preparar_para_agir("alimentar o pet") is True
    assert motor.desmontou is True


# ===========================================================================
# 2b. E A HH TAMBÉM SABE ONDE FICA A CAVE DELA -- 13/09/2026
# ===========================================================================
#
# Tudo acima exercita o motor da BC. A HH usava o motor CRU, cujo
# `_esta_fora_da_cave` responde `False` ("não sei") de propósito, porque cada
# cave responde com a caixa dela. Resultado: na HH o veto perguntava, ouvia
# "não sei", e deixava passar TODO desmonte de fora da cave.
#
# Relato do usuário: *"ao lado de fora da cave HH tem vezes que está saindo da
# montaria, mas no geral não deve sair, eu tenho notado principalmente depois de
# vender os itens"*.


def _motor_hh(pet_ativo=True, pos=mapa_hh.PONTO_DA_ENTRADA):
    motor = _motor(pet_ativo=pet_ativo)
    motor.__class__ = CombateHH
    motor.ctx.memory.position = lambda: pos
    return motor


def test_a_HH_fora_da_cave_com_pet_ativo_NAO_desmonta():
    """O caso do usuário: na porta, logo depois de vender."""
    motor = _motor_hh(pet_ativo=True, pos=mapa_hh.PONTO_DA_ENTRADA)

    assert motor._preparar_para_agir("alimentar o pet") is False
    assert motor.desmontou is False


def test_a_HH_no_ponto_da_VENDA_tambem_esta_fora():
    """É de lá que o usuário viu o desmonte acontecer."""
    motor = _motor_hh(pet_ativo=True, pos=mapa_hh.PONTO_DA_VENDA)

    assert motor._preparar_para_agir("recuperar vida e mana") is False
    assert motor.desmontou is False


def test_a_HH_DENTRO_da_cave_desmonta_normalmente():
    """A regra é só para fora. Dentro, buff e cura exigem estar a pé -- e o
    ponto de saída fica dentro, com X e Y positivos."""
    motor = _motor_hh(pet_ativo=True, pos=mapa_hh.PONTO_DA_SAIDA)

    assert motor._preparar_para_agir("aplicar buffs") is True
    assert motor.desmontou is True


def test_a_HH_sem_leitura_de_posicao_DEIXA_PASSAR():
    """"Não sei" não bloqueia: um buff que não sai dentro da cave custa a run,
    e um desmonte a mais fora dela custa segundos."""
    motor = _motor_hh(pet_ativo=True, pos=None)

    assert motor._preparar_para_agir("curar depois de entrar") is True
    assert motor.desmontou is True


def test_o_motor_CRU_continua_respondendo_nao_sei():
    """É o padrão, e ele tem que continuar valendo para quem não respondeu.

    Trocá-lo por um palpite faria toda cave futura herdar a caixa errada em
    silêncio -- que é exatamente como a HH passou a ter este defeito.
    """
    motor = _motor(pet_ativo=True)
    assert motor_de_combate.CombatEngine._esta_fora_da_cave(motor) is False


# ===========================================================================
# 3. A GRADE DA COMIDA É FIXA
# ===========================================================================

def test_a_grade_nao_escorrega_com_atraso(monkeypatch):
    """O caso do usuário: intervalo 50 min, venceu às 10:00, alimentou 10:12.

    Ancorado na REFEIÇÃO a próxima seria 11:02 (escorregou 12 min). Ancorado no
    VENCIMENTO ela é 10:50 -- a grade não se move, e o número de refeições do
    dia se mantém.
    """
    agora = [1000.0]
    monkeypatch.setattr(time, "time", lambda: agora[0])
    feeder = PetFeeder(vence_em=1000.0)          # vence AGORA

    agora[0] = 1000.0 + 12 * 60                  # alimentou 12 min atrasado
    assert feeder.deve_alimentar(50) is True
    feeder.registrar_alimentacao(50)

    assert feeder.vence_em == pytest.approx(1000.0 + 50 * 60)


def test_atraso_maior_que_um_intervalo_NAO_vira_fila(monkeypatch):
    """Bot parado uma hora não pode voltar dando três refeições seguidas: a
    barra tem teto e o excedente é ração jogada fora."""
    agora = [1000.0]
    monkeypatch.setattr(time, "time", lambda: agora[0])
    feeder = PetFeeder(vence_em=1000.0)

    agora[0] = 1000.0 + 3 * 50 * 60              # três intervalos depois
    feeder.registrar_alimentacao(50)

    assert feeder.vence_em == pytest.approx(agora[0] + 50 * 60)
    assert feeder.deve_alimentar(50) is False, "acumulou refeição em dívida"


def test_a_grade_sobrevive_a_reinicio(monkeypatch):
    """Sem persistência, a grade nasce de novo a cada restart e o dia perde
    refeições -- justamente nas sessões em que o bot é reiniciado."""
    agora = [5000.0]
    monkeypatch.setattr(time, "time", lambda: agora[0])
    guardado = PetFeeder(vence_em=9000.0).vence_em

    depois_do_restart = PetFeeder(vence_em=guardado)
    assert depois_do_restart.deve_alimentar(50) is False
    agora[0] = 9001.0
    assert depois_do_restart.deve_alimentar(50) is True


def test_sem_grade_o_relogio_comeca_sem_alimentar(monkeypatch):
    """`feed_on_start=False` (padrão): inicia o cronômetro sem gastar ração."""
    agora = [100.0]
    monkeypatch.setattr(time, "time", lambda: agora[0])
    feeder = PetFeeder()

    assert feeder.deve_alimentar(50) is False
    assert feeder.vence_em == pytest.approx(100.0 + 50 * 60)


def test_feed_on_start_alimenta_na_primeira(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 100.0)
    assert PetFeeder().deve_alimentar(50, force=True) is True


def test_o_campo_da_grade_atravessa_o_config(tmp_path):
    """Campo novo em `AccountSettings` PRECISA sobreviver à ida e volta do disco
    -- regra do `CLAUDE.md`, e sem isso a grade some no primeiro save.

    E é justamente esta grade que não pode sumir: perdê-la é o pet perder
    refeições do dia e desaparecer por fome no meio de uma run.
    """
    from blazesbot.config import Account, BotConfig

    caminho = tmp_path / "config.json"
    cfg = BotConfig()
    cfg.accounts.append(Account(login="teste"))
    cfg.accounts[0].settings.pet.proxima_comida_em = 12345.0
    cfg.save(caminho)

    voltou = BotConfig.load(caminho).accounts[0]
    assert voltou.settings.pet.proxima_comida_em == pytest.approx(12345.0)


# ===========================================================================
# 4. OS CRONÔMETROS COMEÇAM NA MONTARIA, NÃO NA ENTRADA
# ===========================================================================

def _arvore(metodo):
    import ast
    import inspect
    import textwrap
    return ast.parse(textwrap.dedent(inspect.getsource(metodo))).body[0]


def _chamadas(metodo):
    """As chamadas do método, NA ORDEM DO CÓDIGO.

    `ast.walk` percorre em largura, então uma chamada dentro de um `if` aparece
    depois de tudo que está no corpo principal -- e a ordem do preparo é
    justamente o que se quer travar. Ordenar por linha devolve a ordem real.
    """
    import ast
    nos = [no for no in ast.walk(_arvore(metodo))
           if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)]
    nos.sort(key=lambda no: (no.lineno, no.col_offset))
    return [no.func.attr for no in nos]


def test_a_contagem_da_run_comeca_no_preparo_de_entrada():
    """Ordem do usuário: contar a partir de quando o preparo termina e ele monta
    para andar -- não de quando entrou."""
    from blazesbot.bot.bc.routine import BossRushRoutine

    assert "begin_run" in _chamadas(BossRushRoutine._do_curar)


def test_a_contagem_NAO_comeca_mais_ao_confirmar_a_entrada():
    """O DENTE: se o `begin_run` voltar para a entrada, o tempo do preparo entra
    na conta de novo e as estatísticas medem outra coisa."""
    from blazesbot.bot.bc.routine import BossRushRoutine

    assert "begin_run" not in _chamadas(BossRushRoutine._do_entrar)


def test_a_ordem_do_preparo_de_entrada():
    """cura -> buffs -> pet -> comida -> montar -> contar.

    A ordem não é gosto: buff em personagem que vai morrer é buff desperdiçado,
    e a comida por último é o que faz a grade dela começar a valer daqui.
    """
    from blazesbot.bot.bc.routine import BossRushRoutine

    passos = _chamadas(BossRushRoutine._do_curar)
    esperados = ["curar_ao_entrar", "apply_buffs", "ensure_pet", "feed_pet",
                 "garantir_montaria_para_andar", "begin_run"]
    posicoes = [passos.index(p) for p in esperados]
    assert posicoes == sorted(posicoes), (
        f"o preparo de entrada saiu de ordem: {passos}")


def test_o_preparo_de_saida_nao_alimenta_mais_o_pet():
    """A comida saiu de `ATE_A_ENTRADA`: alimentar exige desmontar, e fora da
    cave só se desmonta por pet inativo."""
    from blazesbot.bot.bc.routine import BossRushRoutine

    assert "feed_pet" not in _chamadas(BossRushRoutine._do_ate_a_entrada)


# ===========================================================================
# 5. O AUTO-PATH DO SURROUNDINGS É CONFIRMADO POR COORDENADA
# ===========================================================================

class _CtxDeCaminhada:
    def __init__(self, posicoes):
        self._posicoes = list(posicoes)
        self.log = SimpleNamespace(info=lambda *a, **k: None,
                                   debug=lambda *a, **k: None,
                                   warning=lambda *a, **k: None)

    def raise_if_stopped(self):
        pass

    def tick(self, _s):
        pass

    @property
    def memory(self):
        pos = self._posicoes.pop(0) if self._posicoes else self._ultima
        self._ultima = pos
        return SimpleNamespace(position=lambda: pos)


def _espera(posicoes, destino):
    from blazesbot.bot.bc.ui_service import UIService

    servico = UIService.__new__(UIService)
    servico.ctx = _CtxDeCaminhada(posicoes)
    return UIService._esperar_chegar(servico, destino, time.time() + 5.0)


def test_chegar_perto_do_destino_encerra_a_espera():
    """O ATALHO: perto do destino não se espera o fim do trajeto."""
    chegou, motivo, _dist = _espera([(0, 0), (50, 0), (95, 0), (99, 0)], (100, 0))
    assert chegou is True
    assert "perto do destino" in motivo


def test_parar_de_andar_TAMBEM_encerra_e_isso_e_o_que_manda():
    """O critério que sempre funcionou, e o único que não depende de as duas
    coordenadas estarem na mesma escala.

    Ele existe porque `Memory.position()` divide a leitura por 20 e o `[x,y]` do
    painel vem do texto da UI -- e ninguém provou que os dois vivem no mesmo
    espaço.
    """
    chegou, motivo, _dist = _espera(
        [(0, 0), (30, 0), (30, 0), (30, 0), (30, 0)], (100, 0))
    assert chegou is True, "parou longe e a espera não encerrou"
    assert "parei de andar" in motivo


def test_o_DENTE_parar_longe_NAO_reabre_o_painel():
    """O defeito de produção, travado.

    Ligado, isso fez as aberturas do Surroundings virarem constantes na ida à
    Fay, com o bot em loop andando para o lugar errado. Se este teste passar a
    falhar, alguém religou a confirmação sem a medição que a autoriza.
    """
    from blazesbot.bot import ui_do_jogo

    assert ui_do_jogo.CONFIRMAR_CHEGADA_POR_COORDENADA is False


def test_a_distancia_volta_para_o_LOG_mesmo_sem_decidir():
    """A coordenada continua sendo lida -- é ela que vai dizer, ao longo de
    algumas runs, se os dois espaços são o mesmo."""
    _chegou, _motivo, distancia = _espera(
        [(0, 0), (30, 0), (30, 0), (30, 0), (30, 0)], (100, 0))
    assert distancia == pytest.approx(70.0, abs=1.0)


def test_sem_coordenada_a_espera_ainda_funciona():
    """Nem todo chamador tem coordenada, e a ausência dela não pode travar."""
    chegou, motivo, distancia = _espera(
        [(0, 0), (5, 0), (5, 0), (5, 0), (5, 0)], None)
    assert chegou is True and distancia is None
    assert "parei de andar" in motivo


def test_o_auto_path_clica_UMA_vez_por_chamada():
    """O clique é caro: clique esquerdo fora do painel é ANDAR, e cada clique a
    mais é uma chance de o personagem sair para o lugar errado."""
    from blazesbot.bot.bc.ui_service import UIService

    assert _chamadas(UIService.ir_para_resultado).count("click") == 1


# ===========================================================================
# 6. A FAY: ENCOSTA NO PONTO ANTES DE CLICAR
# ===========================================================================
#
# Defeito medido em 25/08/2026, com print: o bot parava onde o auto-path
# largasse (`Stone City [180,-516]`, uns 2 passos antes) e clicava no ponto
# genérico de NPC -- que dali pegava o **White Eagle** no caminho. O diálogo não
# abria, a rotina concluía "não estou em Stone City" e gastava o item de
# retorno: desmontava, usava (já estava na cidade), remontava.

def _servico_da_fay(posicoes, linhas=None):
    from blazesbot.bot.bc.ui_service import UIService

    linhas = linhas if linhas is not None else []
    servico = UIService.__new__(UIService)
    servico.idas = []
    seq = list(posicoes)

    def posicao():
        return seq.pop(0) if len(seq) > 1 else seq[0]

    servico.ctx = SimpleNamespace(
        raise_if_stopped=lambda: None,
        memory=SimpleNamespace(position=posicao),
        log=SimpleNamespace(
            info=lambda f, *a: linhas.append(f % a if a else f),
            debug=lambda *a, **k: None,
            warning=lambda f, *a: linhas.append(f % a if a else f)),
    )

    def goto(alvo, **k):
        servico.idas.append(alvo)
        return True

    servico.nav = SimpleNamespace(goto=goto)
    return servico, linhas


def test_ja_no_ponto_da_fay_nao_anda_mais():
    from blazesbot.bot.bc import mapa_bc

    servico, _ = _servico_da_fay([mapa_bc.POSICAO_DA_FAY])
    assert servico._encostar_na_fay() is True
    assert servico.idas == [], "andou estando no ponto"


def test_perto_mas_fora_do_ponto_ANDA_antes_de_clicar():
    """A posição do print: (180,-516), uns 2 passos do ponto (178,-518)."""
    from blazesbot.bot.bc import mapa_bc

    servico, _ = _servico_da_fay([(180, -516), mapa_bc.POSICAO_DA_FAY])
    assert servico._encostar_na_fay() is True
    assert servico.idas == [mapa_bc.POSICAO_DA_FAY]


def test_a_celula_vizinha_do_usuario_PASSA():
    """O usuário falou em (178,-517) e a constante diz (178,-518). Uma unidade
    que ninguém remediu -- a precisão aceita as duas até a medição nova."""
    servico, _ = _servico_da_fay([(178, -517)])
    assert servico._encostar_na_fay() is True
    assert servico.idas == []


def test_o_DENTE_nao_clica_de_fora_do_ponto():
    """Se não conseguir encostar, NÃO clica: dali o clique pega outro alvo e o
    personagem anda, piorando a tentativa seguinte."""
    servico, linhas = _servico_da_fay([(240, -560)])
    assert servico._encostar_na_fay() is False
    assert any("NÃO" in linha and "fora do ponto" in linha for linha in linhas)


def test_sem_leitura_de_posicao_segue_em_vez_de_travar():
    """Recusar sem leitura travaria a viagem num laço sem saída -- mesmo
    tratamento que `_no_ponto_do_vendedor` já dá."""
    servico, _ = _servico_da_fay([None])
    assert servico._encostar_na_fay() is True


def test_a_viagem_encosta_ANTES_de_falar_com_o_npc():
    """A ordem é o ponto: encostar depois de clicar não conserta nada.

    A sequência subiu para `UIDoJogo` em 01/09/2026 e agora protege as DUAS
    caves: a HH percorre exatamente estes passos com outros nomes.
    """
    from blazesbot.bot.ui_do_jogo import UIDoJogo

    passos = _chamadas(UIDoJogo._viajar_pelo_transporte)
    assert passos.index("encostar_no_ponto") < passos.index("falar_com_npc")


def test_em_Stone_City_a_falha_NAO_gasta_item_de_retorno():
    """O desperdício medido: desmontar, usar o item para ir aonde já está, e
    remontar. A posição responde o que a falha do clique não responde."""
    from blazesbot.bot.bc.routine import BossRushRoutine

    fonte = _fonte(BossRushRoutine._do_ate_a_entrada)
    assert "esta_em_stone_city" in fonte
    i_cidade = fonte.index("esta_em_stone_city")
    i_item = fonte.index("voltar_para_a_cidade")
    assert i_cidade < i_item, (
        "o item de retorno é usado antes de conferir se já está na cidade")


def _fonte(metodo):
    import inspect
    import textwrap
    return textwrap.dedent(inspect.getsource(metodo))


# ===========================================================================
# 7. A CÂMERA: ESCREVE E CONFERE
# ===========================================================================
#
# `apply_camera` escreve zoom/rotação/ângulo desde sempre, depois de todo View
# Reset -- e NUNCA foi verificado. `ADDR_CAMERA` é herança da versão 6139 e não
# está na lista do rebase, que já precisou de +0x60 para outros estáticos do
# mesmo banco. O sintoma relatado encaixa: o View Reset resolve esquerda/direita
# (é o botão do jogo) e cima/baixo não se ajusta nunca.

def _contexto_de_camera(poses, alvo=None):
    """`poses` é o que a struct devolve a cada leitura de `camera_pose`."""
    from blazesbot.bot.context import BotContext
    from blazesbot.core import memory as mod

    alvo = alvo or mod.POSE_DA_CAMERA
    ctx = BotContext.__new__(BotContext)
    ctx.escritas = []
    ctx.linhas = []
    seq = list(poses)

    def certo(pedido=None):
        atual = seq.pop(0) if len(seq) > 1 else seq[0]
        if atual is None:
            return None
        return all(abs(a - b) <= mod.TOLERANCIA_DA_POSE
                   for a, b in zip(atual, pedido or alvo, strict=True))

    ctx.config = SimpleNamespace()
    ctx.memory = SimpleNamespace(
        set_camera=lambda z, r, a: ctx.escritas.append((z, r, a)),
        camera_na_pose_certa=certo,
        camera_pose=lambda: seq[0] if seq else None)
    ctx.log = SimpleNamespace(
        info=lambda f, *a: ctx.linhas.append(("INFO", f % a if a else f)),
        warning=lambda f, *a: ctx.linhas.append(("WARNING", f % a if a else f)),
        debug=lambda *a, **k: None)
    return ctx


def test_camera_certa_de_primeira_escreve_uma_vez():
    from blazesbot.bot.context import BotContext
    from blazesbot.core.memory import POSE_DA_CAMERA

    ctx = _contexto_de_camera([POSE_DA_CAMERA])
    BotContext.apply_camera(ctx)

    assert ctx.escritas == [POSE_DA_CAMERA]
    assert not [t for n, t in ctx.linhas if n == "WARNING"]


def test_camera_torta_insiste_e_para_quando_acerta():
    from blazesbot.bot.context import BotContext
    from blazesbot.core.memory import POSE_DA_CAMERA

    torta = (POSE_DA_CAMERA[0], POSE_DA_CAMERA[1], POSE_DA_CAMERA[2] + 15.0)
    ctx = _contexto_de_camera([torta, POSE_DA_CAMERA])
    BotContext.apply_camera(ctx)

    assert len(ctx.escritas) == 2
    assert not [t for n, t in ctx.linhas if n == "WARNING"]


def test_camera_que_nao_obedece_vira_AVISO_e_a_run_segue():
    """Travar a run pela câmera troca um incômodo por uma parada."""
    from blazesbot.bot.context import TENTATIVAS_DE_AJUSTE_DA_CAMERA, BotContext
    from blazesbot.core.memory import POSE_DA_CAMERA

    torta = (POSE_DA_CAMERA[0], POSE_DA_CAMERA[1], POSE_DA_CAMERA[2] + 15.0)
    ctx = _contexto_de_camera([torta])
    BotContext.apply_camera(ctx)

    assert len(ctx.escritas) == TENTATIVAS_DE_AJUSTE_DA_CAMERA
    assert [t for n, t in ctx.linhas if n == "WARNING"]


def test_nao_sei_NAO_e_esta_errada():
    """"Não sei" não é "está errada": insistir às cegas mexeria na câmera de
    quem estava certo."""
    from blazesbot.bot.context import BotContext

    ctx = _contexto_de_camera([None])
    BotContext.apply_camera(ctx)

    assert len(ctx.escritas) == 1
    assert not [t for n, t in ctx.linhas if n == "WARNING"]


def test_a_conferencia_confere_contra_a_pose_pedida():
    """`camera_na_pose_certa(alvo)` recebe o alvo em vez de reler a constante.

    Não é indireção à toa: é o que deixa o DIAGNÓSTICO e qualquer experimento
    conferirem uma pose candidata sem mexer em `POSE_DA_CAMERA`. Sem o
    parâmetro, testar uma pose nova exigiria editar o módulo -- e aí não dá
    para comparar duas.
    """
    from blazesbot.core import memory as mod

    class _Falsa:
        def camera_pose(self):
            return (250.0, 0.0, 35.0)

    falsa = _Falsa()
    assert mod.Memory.camera_na_pose_certa(falsa, (250.0, 0.0, 35.0)) is True
    assert mod.Memory.camera_na_pose_certa(falsa, (300.0, 0.0, 40.0)) is False
    assert mod.Memory.camera_na_pose_certa(falsa) is False

def test_a_pose_mora_SO_no_py():
    """`POSE_DA_CAMERA` é o único lugar. Não há chave em `config.json`, não há
    campo em `BotConfig`, não há nada para sincronizar.

    A pose já passou pelos dois e deu o problema clássico de valor duplicado: o
    `config.json` salvo trazia `[380.0, 0.0, 40.0]` e GANHAVA do padrão, então
    corrigir o código não chegava em quem já tinha config gravado.

    ESTE TESTE NÃO CRAVA O VALOR, de propósito. A pose existe para ser ajustada
    sem depender de ninguém -- travar a tupla transformaria cada experimento do
    usuário em suíte vermelha. O que se trava é a LIGAÇÃO.
    """
    import json
    import math
    from pathlib import Path

    from blazesbot.config import BotConfig
    from blazesbot.core.memory import POSE_DA_CAMERA

    zoom, rotacao, angulo = POSE_DA_CAMERA
    assert all(isinstance(v, float) and math.isfinite(v)
               for v in POSE_DA_CAMERA)
    assert zoom > 0.0, "zoom 0 ou negativo põe a câmera dentro do personagem"

    assert not hasattr(BotConfig(), "camera")

    caminho = Path(__file__).resolve().parent.parent / "data" / "config.json"
    if caminho.exists():
        salvo = json.loads(caminho.read_text(encoding="utf-8"))
        assert "camera" not in salvo, (
            "data/config.json ainda traz `camera`. Um valor em dois lugares "
            "diverge -- e foi assim que o zoom 380 sobreviveu.")

def test_a_escrita_vai_para_o_endereco_VIVO():
    """`ADDR_CAMERA` resolve NULO na 6400 -- toda escrita de câmera caiu nele
    desde o transplante do GhostBot. Ele sobrevive só como referência do
    diagnóstico."""
    from blazesbot.core import memory as mod

    class _Falsa:
        def __init__(self):
            self.bases = []

        def resolve(self, base, offsets):
            self.bases.append(base)
            return None

    falsa = _Falsa()
    mod.Memory.set_camera(falsa, 300.0, 0.0, 40.0)
    assert set(falsa.bases) == {mod.ADDR_CAMERA_VIVA}
    assert mod.ADDR_CAMERA not in falsa.bases


def test_a_pose_le_os_tres_campos_da_struct():
    """`camera_pose` devolve (zoom, rotacao, angulo) -- nesta ordem."""
    from blazesbot.core import memory as mod

    class _Falsa:
        def resolve(self, base, offsets):
            return 0x1000 + offsets[0]

        def read_float(self, endereco):
            return {0x1000 + 0x64: 300.0,
                    0x1000 + 0x5C: 0.0,
                    0x1000 + 0x60: 40.0}.get(endereco)

    assert mod.Memory.camera_pose(_Falsa()) == (300.0, 0.0, 40.0)


def test_o_termometro_e_SO_LEITURA():
    """Escrever nele não funciona -- medição do usuário no Cheat Engine: *"não
    aceita, ele volta para o valor anterior e não muda nada na tela"*.

    O termômetro NÃO é mais a régua do bot: ele responde a dois eixos (ângulo e
    zoom) e pode depender do lugar. Ficou como instrumento de DIAGNÓSTICO, que
    é o papel em que ele foi bom -- foi vendo este número reagir a uma escrita
    que o `ADDR_CAMERA_VIVA` ficou provado."""
    import ast
    import inspect
    import textwrap

    from blazesbot.core.memory import Memory

    fonte = textwrap.dedent(inspect.getsource(Memory.camera_angulo))
    escritas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "write_float" not in escritas
    assert "read_float" in escritas


# ===========================================================================
# A PROVA DA CÂMERA ESPERA O JOGO DESENHAR
# ===========================================================================
#
# A primeira versão desta prova escrevia na struct e relia o termômetro na
# instrução seguinte -- antes de o jogo ter desenhado um quadro sequer. Ela
# concluiu "não é a câmera" para um candidato que tinha ACEITADO a escrita, e
# essa conclusão errada quase mandou o projeto automatizar as telas de Gráficos
# do jogo, que é o caminho caro e feio.
#
# Era o relógio, não o endereço.


class _MemoriaFalsa:
    """Um `Memory` de mentira: guarda floats e simula o jogo por cima."""

    def __init__(self, valor, termometro, desenha_em=0, o_jogo_desfaz=False):
        self.valores = {0x1000: valor}
        self.termometro = termometro
        self.desenha_em = desenha_em      # quantas leituras até o quadro sair
        self.o_jogo_desfaz = o_jogo_desfaz
        self.original = valor
        self.leituras = 0
        self.escritas = []

    def read_float(self, endereco):
        return self.valores.get(endereco)

    def write_float(self, endereco, valor):
        self.escritas.append((endereco, valor))
        self.valores[endereco] = valor
        return True

    def _esperar_o_termometro(self, antes):
        """A espera REAL, sob teste -- é ela que o bug antigo não fazia."""
        from blazesbot.core.memory import Memory

        return Memory._esperar_o_termometro(self, antes)

    def camera_angulo(self):
        self.leituras += 1
        if self.leituras > self.desenha_em and self.escritas:
            # O "quadro" saiu: o jogo reagiu à escrita.
            if self.o_jogo_desfaz:
                self.valores[0x1000] = self.original
            else:
                self.termometro += 10.0
        return self.termometro


def _provar(memoria):
    from blazesbot.core.memory import Memory

    return Memory._provar_campo_da_camera(memoria, "angulo", 0x1000,
                                          memoria.original)


def test_a_prova_espera_o_jogo_desenhar(monkeypatch):
    """O termômetro só mexe alguns quadros depois. Concluir na hora é o bug."""
    from blazesbot.core import memory as mod

    monkeypatch.setattr(mod, "PASSO_DA_PROVA_DA_CAMERA", 0.001)
    monkeypatch.setattr(mod, "TETO_DA_PROVA_DA_CAMERA", 1.0)

    memoria = _MemoriaFalsa(valor=41.6, termometro=1220.0, desenha_em=3)
    prova = _provar(memoria)

    assert prova["moveu_o_termometro"] is True
    assert prova["situacao"] == "ESCREVE E MOVE A CÂMERA"


def test_a_prova_desiste_no_teto_quando_o_termometro_nao_mexe(monkeypatch):
    """Teto é aviso, não gasto: sem movimento, ele É a resposta."""
    from blazesbot.core import memory as mod

    monkeypatch.setattr(mod, "PASSO_DA_PROVA_DA_CAMERA", 0.001)
    monkeypatch.setattr(mod, "TETO_DA_PROVA_DA_CAMERA", 0.05)

    memoria = _MemoriaFalsa(valor=41.6, termometro=1220.0, desenha_em=10**9)
    prova = _provar(memoria)

    assert prova["moveu_o_termometro"] is False
    assert prova["a_escrita_ficou"] is True
    assert "termômetro não mexeu" in prova["situacao"]


def test_a_prova_separa_campo_derivado_de_campo_de_entrada(monkeypatch):
    """Campo DERIVADO é desfeito pelo jogo; campo de ENTRADA fica onde foi posto.

    É a mesma assinatura que o usuário viu no Cheat Engine ao tentar escrever no
    próprio termômetro: *"não aceita, ele volta para o valor anterior"*.
    """
    from blazesbot.core import memory as mod

    monkeypatch.setattr(mod, "PASSO_DA_PROVA_DA_CAMERA", 0.001)
    monkeypatch.setattr(mod, "TETO_DA_PROVA_DA_CAMERA", 0.05)

    derivado = _MemoriaFalsa(valor=41.6, termometro=1220.0, desenha_em=1,
                             o_jogo_desfaz=True)
    assert _provar(derivado)["o_jogo_manteve"] is False

    entrada = _MemoriaFalsa(valor=41.6, termometro=1220.0, desenha_em=10**9)
    assert _provar(entrada)["o_jogo_manteve"] is True


def test_a_prova_sempre_restaura_o_valor_original(monkeypatch):
    """Diagnóstico não pode deixar a câmera torta atrás de si."""
    from blazesbot.core import memory as mod

    monkeypatch.setattr(mod, "PASSO_DA_PROVA_DA_CAMERA", 0.001)
    monkeypatch.setattr(mod, "TETO_DA_PROVA_DA_CAMERA", 0.05)

    memoria = _MemoriaFalsa(valor=41.6, termometro=1220.0, desenha_em=1)
    _provar(memoria)

    assert memoria.escritas[-1] == (0x1000, 41.6)
    assert memoria.valores[0x1000] == 41.6


def test_a_prova_roda_nos_TRES_campos():
    """Provar só o ângulo respondia por um eixo e calava sobre os outros dois."""
    import ast
    import inspect
    import textwrap

    from blazesbot.core.memory import Memory

    fonte = textwrap.dedent(inspect.getsource(Memory.diagnostico_da_camera))
    campos = {n.value for n in ast.walk(ast.parse(fonte))
              if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert {"rotacao", "angulo", "zoom"} <= campos


def test_o_leitor_de_camera_NUNCA_escreve():
    """`17-LER-CAMERA` existe para capturar a pose boa sem mexer no jogo."""
    import ast
    import inspect

    from blazesbot.tools import ler_camera

    fonte = ast.parse(inspect.getsource(ler_camera))
    chamadas = {n.func.attr for n in ast.walk(fonte)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "write_float" not in chamadas
    assert "set_camera" not in chamadas
    assert "read_float" in chamadas


def test_a_camera_viva_e_o_endereco_rebaseado():
    """O `+0x60` da câmera é o MESMO deslocamento medido no `TARGET_ID`.

    GhostBot (6139) `0x0115CB20` -> BlazesBot (6400) `0x0115CB80`. Não é chute
    por endereço: é o banco de estáticos inteiro que andou na virada.
    """
    from blazesbot.core.memory import ADDR_CAMERA, ADDR_CAMERA_VIVA
    from blazesbot.core.target_hybrid import TARGET_ID_ADDR

    assert ADDR_CAMERA_VIVA - ADDR_CAMERA == 0x60
    assert TARGET_ID_ADDR - 0x0115CB20 == 0x60


def test_a_pose_em_uso_aparece_no_log_uma_vez_por_sessao():
    """Testar uma pose nova sem ver qual pegou é palpite -- e foi esse buraco
    que deixou o zoom 380 sobreviver anos escrevendo num endereço morto."""
    from blazesbot.bot.context import BotContext
    from blazesbot.core.memory import POSE_DA_CAMERA

    ctx = _contexto_de_camera([POSE_DA_CAMERA])
    BotContext.apply_camera(ctx)
    BotContext.apply_camera(ctx)

    linhas = [t for n, t in ctx.linhas if n == "INFO" and "pose alvo" in t]
    assert len(linhas) == 1, ctx.linhas
    assert f"zoom={POSE_DA_CAMERA[0]}" in linhas[0]
    assert "POSE_DA_CAMERA" in linhas[0]
