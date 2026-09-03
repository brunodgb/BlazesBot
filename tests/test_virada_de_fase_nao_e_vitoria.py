"""A virada de fase do boss NÃO pode virar vitória.

=============================================================================
O DEFEITO, RELATADO E MEDIDO
=============================================================================

O usuário viu na tela: *"eu vi acontecer visualmente isso, de entender que foi
para a segunda fase e ele tentar usar o auto pick, daí abriu o inventário e foi
para o Skull Herald para sair da cave, só não saiu pq eu desativei o bot e
impedi."*

O log de 19/08/2026, conta `creubo`, mostra o caminho inteiro:

    16:38:39  Em combate (boss) depois de 0.0s esperando
    16:39:01  A flag de combate baixou em boss (22s de luta, 98 golpes).
              Confirmando por 2.5s antes de encerrar.
    16:39:03  Fora de combate confirmado: 2.5s contínuos com a flag baixa
    16:39:03  Sai de combate no boss -- considerando o Blaze Skull Marshal
              derrotado
    16:39:04  package_courage ... -> SAIR -> Skull Herald

E o `fase_do_boss_por_combate` listava esse caso como *"flag baixando com o boss
vivo e o personagem vivo -- NÃO FOI OBSERVADO"*. Agora foi.

=============================================================================
O MECANISMO
=============================================================================

O golpe PARAVA no instante em que a flag baixava (`if not (falso_desde and
ja_entrou)`), e quem engaja a fase seguinte é o GOLPE -- *"a fase 2 pega o alvo
sozinha assim que ataca"*. Parado, ninguém reengaja: a flag fica baixa os 2,5 s e
a saída confirma com o boss de pé.

**A REGRA DA VITÓRIA NÃO MUDOU**, e é ordem do usuário: *"o boss derrotado só deve
ser considerado quando sai de batalha."* Nada de confirmar morte por imagem ou por
ponteiro aqui. O que mudou é só o bot deixar de ficar passivo enquanto confirma.

=============================================================================
OS TESTES QUE CARREGAM O PESO
=============================================================================

**`test_DEFEITO_a_virada_de_fase_nao_declara_vitoria`** -- reproduz o log: flag
baixa por 2,5 s e volta. Com o golpe parado, vira vitória; com ele insistindo, a
luta segue.

**`test_nos_guardas_o_golpe_PARA_na_hora`** -- o outro lado. Parar de bater foi
correção de um defeito real (bater depois da luta convida o mob seguinte), e ela
continua valendo onde há mob seguinte.
"""
from types import SimpleNamespace

import pytest

from blazesbot.bot import combate as motor_de_combate
from blazesbot.bot.bc import combat
from blazesbot.bot.bc.combat import CombatEngine


class ClienteDeLuta:
    """Relógio determinístico, e uma flag de combate que REAGE AO GOLPE.

    ==================================================================
    A PRIMEIRA VERSÃO DESTE DUBLÊ NÃO PODIA FALHAR NO DEFEITO
    ==================================================================

    Ela roteirizava a flag por TEMPO ("baixa aos 22 s, volta aos 24 s"),
    independente do que o bot fizesse -- e com isso o caminho ANTIGO passava: a
    flag voltava sozinha antes dos 2,5 s de confirmação, sem golpe nenhum.

    Só que é justamente essa independência que não existe no jogo. Quem reengaja
    a fase seguinte é o GOLPE (*"a fase 2 pega o alvo sozinha assim que ataca"*).
    Um dublê em que a flag volta sozinha modela um mundo onde o defeito não
    existe, e um teste que não pode falhar no defeito que nomeia é pior que teste
    nenhum.

    Então aqui a flag baixa em `queda` e **só volta se um golpe sair depois
    disso**. `reengaja_ao_golpe=False` é o boss MORTO: nada reage a golpe.
    """

    def __init__(self, *, reengaja_ao_golpe, queda=22.0, morte=50.0, teto=60.0):
        self.agora = 10_000.0
        self.queda = queda
        self.morte = morte
        self.reengaja_ao_golpe = reengaja_ao_golpe
        self.golpe_apos_a_queda = None
        self.golpes: list[float] = []
        # OS CAMPOS SÃO OS REAIS (`attack_skills`, `aoe_skill`, ...). O dublê é
        # que acompanha a produção, nunca o contrário: um `getattr` com default
        # aqui esconderia uma dependência de verdade.
        self.settings = SimpleNamespace(
            bc=SimpleNamespace(attack_delay=0.3, max_fight_seconds=teto,
                               aoe_until_mana_pct=30),
            use_aoe=False,
            keys=SimpleNamespace(next_target="TAB", attack_skills=["1"],
                                 aoe_skill="", break_soul="",
                                 sit="X", hp_potion="9", battle_hp_potion="",
                                 heal_skill="", super_skill=""),
            potions=SimpleNamespace(battle_hp_pct=15, max_heal_seconds=120),
        )
        # A CAVE QUE ESTÁ RODANDO. Os motores compartilhados leem número
        # de cave por aqui desde 03/09/2026 (`ctx.cave`), em vez de
        # `settings.bc` direto -- era o que fazia a HH rodar com os
        # números do BC. Aqui aponta para o `bc` deste dublê, que é a
        # cave que estes testes exercitam.
        self.cave = self.settings.bc
        self.log = SimpleNamespace(info=lambda *a, **k: None,
                                   debug=lambda *a, **k: None,
                                   warning=lambda *a, **k: None,
                                   error=lambda *a, **k: None)
        self.account_login = "teste"

    # -- o que o motor usa -------------------------------------------------

    @property
    def decorrido(self):
        return self.agora - 10_000.0

    def flag(self):
        t = self.decorrido
        if t < self.queda:
            return True
        if self.reengaja_ao_golpe and self.golpe_apos_a_queda is not None:
            # Reengajou por ter sido atacado, e agora morre de vez em `morte`.
            return t < self.morte
        return False

    def press(self, tecla, hold=0.1):
        if tecla != "TAB":
            self.golpes.append(round(self.decorrido, 2))
            if self.decorrido >= self.queda and self.golpe_apos_a_queda is None:
                self.golpe_apos_a_queda = self.decorrido
        return True

    def tick(self, s=0.2):
        self.agora += s

    def snapshot(self):
        return SimpleNamespace(dead=False, hp_pct=100.0, mp_pct=100.0,
                               position=(0, 0), location="Secret Cemetery",
                               max_hp=1000)

    def raise_if_stopped(self):
        pass


def _motor(monkeypatch, cliente):
    monkeypatch.setattr(motor_de_combate.time, "time", lambda: cliente.agora)
    motor = CombatEngine.__new__(CombatEngine)
    motor.ctx = cliente
    motor._skill_index = 0
    motor._na_segunda_fase_do_boss = False
    motor._struct_do_alvo = None
    motor._ultimo_hp_de_memoria = None
    motor._ultima_leitura_do_alvo = None
    motor._logou_aguardando_saida_combate = False
    monkeypatch.setattr(CombatEngine, "_ler_flag_de_combate",
                        lambda self: cliente.flag())
    monkeypatch.setattr(CombatEngine, "maintain",
                        lambda self, state, em_luta=False: None)
    return motor


def _lutar(monkeypatch, *, insistir, reengaja_ao_golpe, teto=60.0):
    cliente = ClienteDeLuta(reengaja_ao_golpe=reengaja_ao_golpe, teto=teto)
    motor = _motor(monkeypatch, cliente)
    fim = motor.atacar_ate_sair_de_combate(
        "boss", usar_aoe=False, limite=teto,
        atacar_na_confirmacao=insistir)
    return cliente, fim


# ---------------------------------------------------------------------------
# 1. O DEFEITO RELATADO
# ---------------------------------------------------------------------------

def test_DEFEITO_a_virada_de_fase_nao_declara_vitoria(monkeypatch):
    """Com o golpe insistindo, a flag voltando aos 24 s continua a luta.

    O boss só é dado por morto quando SAI DE BATALHA -- e neste roteiro ele não
    saiu: voltou. A luta tem que seguir até a saída de verdade (50 s).
    """
    cliente, fim = _lutar(monkeypatch, insistir=True,
                          reengaja_ao_golpe=True)

    assert fim.segundos > 30.0, (
        f"a luta terminou em {fim.segundos:.1f}s -- declarou vitória na virada "
        f"de fase, que é o defeito de 19/08/2026"
    )
    assert any(g >= 22.0 for g in cliente.golpes), (
        "nenhum golpe saiu depois de a flag baixar; sem golpe a fase seguinte "
        "não reengaja"
    )
    assert cliente.golpe_apos_a_queda is not None


def test_o_golpe_PARADO_e_o_que_produzia_o_defeito(monkeypatch):
    """O outro lado da mesma moeda, para o teste ter dente de verdade.

    Sem insistir, o MESMO roteiro termina em ~24,5 s: a confirmação de 2,5 s se
    completa antes de a flag voltar, e a virada de fase é declarada vitória.
    """
    cliente, fim = _lutar(monkeypatch, insistir=False,
                          reengaja_ao_golpe=True)

    assert fim.saiu_de_combate is True, "o caminho antigo declarava VITÓRIA"
    assert fim.segundos < 30.0, (
        f"o caminho antigo encerrava na confirmação de "
        f"{motor_de_combate.CONFIRMACAO_DE_SAIDA_DE_COMBATE}s, e levou {fim.segundos:.1f}s"
    )
    assert not any(g > 22.2 for g in cliente.golpes), (
        "o caminho antigo fica PASSIVO com a flag baixa -- e é essa passividade "
        "que impede o reengajamento"
    )


def test_a_MORTE_DE_VERDADE_continua_encerrando(monkeypatch):
    """Insistir no golpe não pode fazer o boss morto nunca terminar.

    Morto, nada reage: a flag fica baixa, os 2,5 s correm e a vitória sai igual.
    É o que garante que o conserto não troca um defeito por outro.
    """
    _cliente, fim = _lutar(monkeypatch, insistir=True,
                           reengaja_ao_golpe=False)

    assert fim.saiu_de_combate is True
    assert fim.segundos < 30.0, (
        f"levou {fim.segundos:.1f}s para aceitar a morte de verdade"
    )


def test_a_regra_da_vitoria_NAO_MUDOU():
    """"O boss derrotado só deve ser considerado quando sai de batalha."

    Nada de imagem nem de ponteiro decidindo vitória. Este teste FIXA o conjunto
    de vitórias que o laço conhece, para que acrescentar uma quarta apareça aqui:

      * `saiu de combate`                -- a única do BOSS;
      * `callback pos-tab encerrou fase` -- guardas, pelo callback pós-TAB;
      * `acabaram os ...`                -- guardas, pelo portão de NOME.

    As duas últimas dependem de `tabs_ao_morrer` / `pos_tab_callback`, que o boss
    não passa -- então nenhuma delas é alcançável na luta do boss.
    """
    import ast
    import inspect
    import textwrap

    arvore = ast.parse(textwrap.dedent(
        inspect.getsource(CombatEngine.atacar_ate_sair_de_combate)))

    motivos = set()
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Call)
                and getattr(no.func, "id", "") == "FimDeCombate" and no.args):
            continue
        if not (isinstance(no.args[0], ast.Constant)
                and no.args[0].value is True):
            continue
        segundo = no.args[1] if len(no.args) > 1 else None
        if isinstance(segundo, ast.Constant):
            motivos.add(segundo.value)
        elif isinstance(segundo, ast.JoinedStr):
            # f-string: guarda só o pedaço literal do começo.
            pedaco = next((v.value for v in segundo.values
                           if isinstance(v, ast.Constant)), "?")
            motivos.add(pedaco.strip())
        else:
            motivos.add("?")

    assert motivos == {"saiu de combate", "callback pos-tab encerrou fase",
                       "acabaram os"}, (
        f"o conjunto de vitórias do laço mudou: {sorted(motivos)}"
    )


# ---------------------------------------------------------------------------
# 2. OS GUARDAS NÃO MUDAM
# ---------------------------------------------------------------------------

def test_nos_guardas_o_golpe_PARA_na_hora(monkeypatch):
    """Parar de bater foi correção de um defeito REAL: *"o bot batendo por
    segundos depois de a luta acabar -- que é como se convida o mob seguinte."*

    Isso vale onde HÁ mob seguinte. Na sala do boss não há, e depois dele o bot
    vai embora -- é a única razão pela qual o boss pode insistir.

    O default do parâmetro é o que garante isso: quem não pede, não insiste.
    """
    import inspect
    padrao = inspect.signature(
        CombatEngine.atacar_ate_sair_de_combate
    ).parameters["atacar_na_confirmacao"].default

    assert padrao is False, "insistir no golpe passou a ser o padrão de TODOS"

    cliente, _fim = _lutar(monkeypatch, insistir=False,
                           reengaja_ao_golpe=True)
    assert not any(g > 22.2 for g in cliente.golpes)


def test_so_o_BOSS_pede_para_insistir():
    """Lido no AST: `atacar_na_confirmacao=True` sai de UM lugar só."""
    import ast
    import inspect

    fonte = inspect.getsource(combat)
    arvore = ast.parse(fonte)
    pedidos = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        for kw in no.keywords:
            if (kw.arg == "atacar_na_confirmacao"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True):
                pedidos.append(getattr(no.func, "attr", "?"))

    assert pedidos == ["atacar_ate_sair_de_combate"], (
        f"mais de um chamador pede para insistir no golpe: {pedidos}"
    )
    # E ele é o do boss: a mesma chamada passa `registrar_troca_de_fase`.
    for no in ast.walk(arvore):
        if (isinstance(no, ast.Call)
                and any(kw.arg == "atacar_na_confirmacao" for kw in no.keywords)):
            nomes = {kw.arg for kw in no.keywords}
            assert "registrar_troca_de_fase" in nomes, (
                "quem insiste no golpe não é a chamada do boss"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
