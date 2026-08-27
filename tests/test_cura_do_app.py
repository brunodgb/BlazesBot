"""O PERSONAGEM DO APP NÃO MORRE: ele se cura no ponto seguro.

Combinado com o usuário em 25/08/2026. A frase que resume: *"a ideia é garantir
que o personagem não morra, e sim se cure em um lugar seguro, que é onde o
usuário decidiu que seria o ponto inicial"*.

O que este arquivo trava é o que foi COMBINADO, não o que o código faz -- cada
teste cita a decisão que ele segura.
"""
from types import SimpleNamespace

import pytest

from blazesbot.bot.app import cura as mod


class _Jogo:
    """Um jogo de mentira: vida, batalha, alvo e posição sob controle."""

    def __init__(self, vida=100.0, em_batalha=False, alvo=None, distancia=0.0,
                 sentado=False, cura_por_pocao=40.0, tem_base=True,
                 tem_pocoes=True):
        self.vida = vida
        self.batalha = em_batalha
        self.alvo = alvo
        self.distancia = distancia
        self.sentado = sentado
        self.cura_por_pocao = cura_por_pocao
        self.tem_base = tem_base
        # BOLSA VAZIA: a tecla sai, o jogo ignora, e o personagem
        # NÃO senta -- é assim que o bot descobre que acabaram.
        self.tem_pocoes = tem_pocoes
        self.teclas: list[str] = []
        self.cliques_no_minimapa = 0
        self.linhas: list[tuple[str, str]] = []

    # -- o que a cura enxerga --
    def vida_pct(self):
        return self.vida

    def em_batalha(self):
        return self.batalha

    def alvo_atual(self):
        return self.alvo

    def distancia_da_base(self):
        return self.distancia

    def esta_sentado(self):
        return self.sentado

    def voltar_para_base(self):
        if not self.tem_base:
            return False
        self.cliques_no_minimapa += 1
        self.distancia = 0.0
        return True

    def apertar(self, tecla):
        self.teclas.append(tecla)
        if tecla == "9":
            # BEBER PÕE O PERSONAGEM SENTADO -- medição do usuário, e é o
            # observável que prova que a poção saiu. Sem poção na bolsa, a
            # tecla não faz nada: nem vida, nem sentar.
            if not self.tem_pocoes:
                return
            self.vida = min(100.0, self.vida + self.cura_por_pocao)
            self.sentado = True
        if tecla == "X":
            self.sentado = not self.sentado

    @property
    def log(self):
        anotar = self.linhas.append
        return SimpleNamespace(
            info=lambda f, *a: anotar(("INFO", f % a if a else f)),
            warning=lambda f, *a: anotar(("WARNING", f % a if a else f)),
            debug=lambda *a, **k: None)


def _cura(jogo, pocao="9", sentar="X"):
    return mod.CuraDoApp(
        log=jogo.log,
        vida_pct=jogo.vida_pct,
        em_batalha=jogo.em_batalha,
        alvo_atual=jogo.alvo_atual,
        distancia_da_base=jogo.distancia_da_base,
        voltar_para_base=jogo.voltar_para_base,
        apertar=jogo.apertar,
        esta_sentado=jogo.esta_sentado,
        tecla_de_pocao=lambda: pocao,
        tecla_de_sentar=lambda: sentar,
    )


@pytest.fixture(autouse=True)
def _relogio(monkeypatch):
    """RELÓGIO FALSO, e não `sleep` neutralizado.

    Neutralizar o `sleep` não faz o tempo passar: os laços deste módulo saem por
    `time.time() >= fim`, então eles girariam em vazio pelos 15 s da poção e
    pelos 30 s sentado, de verdade. Aqui cada `sleep` ADIANTA o relógio, e os
    tetos resolvem em algumas centenas de voltas.
    """
    agora = [1000.0]
    monkeypatch.setattr(mod.time, "time", lambda: agora[0])
    monkeypatch.setattr(mod.time, "sleep",
                        lambda segundos: agora.__setitem__(
                            0, agora[0] + max(float(segundos), 0.01)))


def _alvo(hp, maximo=100, nome="Gun Witch"):
    return {"id": 7, "nome": nome, "nivel": 50, "hp": hp, "max_hp": maximo}


# ===========================================================================
# O GATILHO
# ===========================================================================

def test_vida_cheia_nao_faz_nada():
    jogo = _Jogo(vida=100.0)
    assert _cura(jogo).cuidar() is False
    assert jogo.teclas == []


def test_o_gatilho_e_30_por_cento():
    """O usuário SUBIU de 20 para 30 na revisão final: *"assim tem uma margem
    de erro maior e a probabilidade de morrer é menor"*.

    A margem existe porque entre o gatilho e a primeira poção há uma volta de
    macro para terminar, até 2 s de espera de batalha e até 5 s de caminhada.
    """
    assert mod.VIDA_PARA_CURAR == 30.0
    assert mod.VIDA_ALVO_DA_CURA == 90.0

    assert _cura(_Jogo(vida=30.1)).cuidar() is False
    assert _cura(_Jogo(vida=29.9)).cuidar() is True


def test_sem_leitura_de_vida_a_protecao_e_INERTE_e_avisa_uma_vez():
    """Não dá para proteger o que não se enxerga -- e fingir que protege é pior
    que dizer que não consegue."""
    jogo = _Jogo()
    jogo.vida_pct = lambda: None
    cura = _cura(jogo)

    assert cura.cuidar() is False
    assert cura.cuidar() is False

    avisos = [t for n, t in jogo.linhas if n == "WARNING"]
    assert len(avisos) == 1, avisos
    assert "inerte" in avisos[0]


# ===========================================================================
# SAIR DE BATALHA -- a poção de fora de batalha não funciona em combate
# ===========================================================================

def test_em_batalha_com_alvo_VIVO_nao_espera_o_relogio():
    """*"Caso não saia de batalha meio logo, é pq pode ter outro mob
    atacando."*

    O alvo com vida é a prova de que esperar a flag baixar é esperar por nada:
    tem mob vivo batendo, e o certo é rodar a macro para matá-lo. Sai NA HORA.
    """
    jogo = _Jogo(vida=20.0, em_batalha=True, alvo=_alvo(hp=60))

    assert _cura(jogo).cuidar() is False
    assert jogo.teclas == [], "curou em batalha"
    assert jogo.cliques_no_minimapa == 0, "andou em batalha"


def test_alvo_MORTO_e_flag_baixando_deixa_curar():
    """O mob morreu e o jogo baixou a flag: pode curar."""
    jogo = _Jogo(vida=20.0, em_batalha=False, alvo=_alvo(hp=0))

    assert _cura(jogo).cuidar() is True
    assert "9" in jogo.teclas


def test_preso_em_batalha_GRITA_depois_de_N_voltas():
    """O bot roda a macro para sempre -- decisão do usuário (*"não adianta
    continuar insistindo se não está curando"*). O que o código faz é AVISAR:
    é informação que só o usuário pode agir sobre.
    """
    jogo = _Jogo(vida=12.0, em_batalha=True, alvo=_alvo(hp=80))
    cura = _cura(jogo)

    for _ in range(mod.VOLTAS_PRESAS_PARA_AVISAR):
        assert cura.cuidar() is False

    avisos = [t for n, t in jogo.linhas if n == "WARNING"]
    assert avisos, "ficou preso em batalha e não avisou ninguém"
    assert "sem conseguir sair de batalha" in avisos[0].lower() or \
           "SEM conseguir sair" in avisos[0]


def test_o_log_traz_a_VIDA_EXATA_do_mob():
    """Pedido final do usuário: *"é importante trazer os dados do target para o
    APP, para que também saibamos a vida exata do mob que está sendo
    atacado"*."""
    jogo = _Jogo(vida=20.0, em_batalha=True, alvo=_alvo(hp=37, nome="Rose Snake"))
    _cura(jogo).cuidar()

    tudo = " | ".join(t for _n, t in jogo.linhas)
    assert "Rose Snake" in tudo
    assert "37/100" in tudo


# ===========================================================================
# VOLTAR AO PONTO INICIAL
# ===========================================================================

def test_volta_ao_ponto_antes_de_curar():
    jogo = _Jogo(vida=20.0, distancia=8.0)
    _cura(jogo).cuidar()

    assert jogo.cliques_no_minimapa == 1
    assert "9" in jogo.teclas


def test_sem_ponto_inicial_cura_no_lugar_MESMO():
    """Decisão do usuário: nunca deixar de curar por falta de ponto."""
    jogo = _Jogo(vida=20.0, tem_base=False)

    assert _cura(jogo).cuidar() is True
    assert jogo.teclas.count("9") >= 1
    assert jogo.cliques_no_minimapa == 0


def test_nao_chegou_no_teto_CURA_ONDE_ESTIVER(monkeypatch):
    """*"Em no máximo 5 segundos é para chegar no ponto inicial."* Estourado,
    cura onde estiver: melhor no lugar errado do que morrer esperando chegar no
    certo."""
    monkeypatch.setattr(mod, "SEGUNDOS_PARA_VOLTAR_AO_PONTO", 0.05)
    jogo = _Jogo(vida=20.0, distancia=40.0)
    jogo.voltar_para_base = lambda: True      # clica, mas não chega nunca

    assert _cura(jogo).cuidar() is True
    assert "9" in jogo.teclas
    assert any("não confirmei a chegada" in t.lower() for _n, t in jogo.linhas)


# ===========================================================================
# CURAR COM POÇÃO
# ===========================================================================

def test_bebe_ate_90_por_cento_e_para():
    """*"Sempre seja a vida atual o maior limitante; chegando nos 90% não
    precisa mais curar."*"""
    jogo = _Jogo(vida=20.0, cura_por_pocao=40.0)


    assert _cura(jogo).cuidar() is True

    assert jogo.teclas.count("9") == 2, jogo.teclas
    assert jogo.vida >= mod.VIDA_ALVO_DA_CURA


def test_uma_pocao_forte_resolve_com_UMA():
    """Quem comprou poção forte não paga os 15 s da segunda."""
    jogo = _Jogo(vida=25.0, cura_por_pocao=80.0)
    _cura(jogo).cuidar()
    assert jogo.teclas.count("9") == 1


def test_teto_de_5_pocoes_e_o_aviso_de_pocao_fraca():
    """*"Normalmente em no máximo 2 deve curar."* Chegar a 5 significa poção
    fraca demais para o dano que o personagem toma."""
    jogo = _Jogo(vida=20.0, cura_por_pocao=1.0)

    assert _cura(jogo).cuidar() is True

    assert jogo.teclas.count("9") == mod.MAXIMO_DE_POCOES
    avisos = [t for n, t in jogo.linhas if n == "WARNING"]
    assert any("fraca demais" in t for t in avisos), avisos


def test_o_contador_de_pocoes_ZERA_a_cada_ciclo():
    """*"Cada vez que entrou em batalha e precisou voltar para a macro, reseta
    a quantidade de poções usadas."* Cada volta ao ponto é um ciclo novo."""
    jogo = _Jogo(vida=20.0, cura_por_pocao=1.0)
    cura = _cura(jogo)

    cura.cuidar()
    assert jogo.teclas.count("9") == mod.MAXIMO_DE_POCOES

    jogo.teclas.clear()
    jogo.vida = 20.0
    cura.cuidar()
    assert jogo.teclas.count("9") == mod.MAXIMO_DE_POCOES, (
        "o teto não zerou entre um ciclo e o outro")


def test_entrar_em_batalha_no_meio_da_cura_VOLTA_PARA_A_MACRO():
    """*"Se entrar em batalha e a vida começar a cair, só começar a rotacionar
    a macro, pois não adianta continuar insistindo se não está curando, pois só
    vai fazer o personagem morrer para o mob."*"""
    jogo = _Jogo(vida=20.0, cura_por_pocao=1.0)
    original = jogo.apertar

    def apertar(tecla):
        original(tecla)
        jogo.batalha = True          # o mob chegou logo depois da 1ª poção

    jogo.apertar = apertar

    assert _cura(jogo).cuidar() is True
    assert jogo.teclas.count("9") == 1, "insistiu na poção com mob em cima"
    assert any("volto a rodar a macro" in t.lower() for _n, t in jogo.linhas)


# ===========================================================================
# SENTAR -- sem tecla de poção
# ===========================================================================

def test_sem_tecla_de_pocao_SENTA(monkeypatch):
    """*"O que pode fazer é voltar para o ponto inicial e sentar, ficar sentado
    por até 30 segundos."*"""
    monkeypatch.setattr(mod, "SEGUNDOS_SENTADO", 0.05)
    jogo = _Jogo(vida=20.0)

    assert _cura(jogo, pocao="").cuidar() is True

    assert jogo.teclas.count("X") == 2, "sentou e não levantou (ou nem sentou)"
    assert jogo.sentado is False


def test_sentado_LEVANTA_ao_bater_90():
    """*"Caso chegue a 90% pode voltar a macro."*"""
    jogo = _Jogo(vida=20.0)
    leituras = [20.0, 50.0, 95.0]

    def vida_pct():
        return leituras.pop(0) if len(leituras) > 1 else leituras[0]

    jogo.vida_pct = vida_pct

    _cura(jogo, pocao="").cuidar()
    assert jogo.sentado is False


def test_mob_chegou_com_o_personagem_SENTADO(monkeypatch):
    """*"O mob pode acabar vindo atacar e, se for o caso, deve começar a rodar
    a macro para poder matar o mob."* Sentado é o estado mais vulnerável do
    jogo -- levantar vem antes de qualquer outra coisa."""
    monkeypatch.setattr(mod, "SEGUNDOS_SENTADO", 5.0)
    jogo = _Jogo(vida=20.0)
    original = jogo.apertar

    def apertar(tecla):
        original(tecla)
        if tecla == "X" and jogo.sentado:
            jogo.batalha = True      # o mob veio assim que sentou

    jogo.apertar = apertar

    _cura(jogo, pocao="").cuidar()

    assert jogo.sentado is False, "ficou sentado com mob em cima"
    assert any("levanto" in t.lower() for _n, t in jogo.linhas)


def test_a_tecla_de_sentar_e_INTERRUPTOR_entao_o_estado_e_LIDO_ANTES(monkeypatch):
    """Apertá-la de pé senta; apertá-la sentado LEVANTA. Já sentado, não se
    aperta -- senão o bot levanta o personagem para "sentar"."""
    monkeypatch.setattr(mod, "SEGUNDOS_SENTADO", 0.05)
    jogo = _Jogo(vida=20.0, sentado=True)

    _cura(jogo, pocao="").cuidar()

    assert jogo.teclas.count("X") == 1, (
        "apertou a tecla de sentar com o personagem já sentado")
    assert jogo.sentado is False


def test_sem_pocao_e_sem_sentar_avisa_e_nao_inventa():
    jogo = _Jogo(vida=20.0)
    assert _cura(jogo, pocao="", sentar="").cuidar() is False
    assert any("não tenho como curar" in t.lower()
               for _n, t in jogo.linhas), jogo.linhas


# ===========================================================================
# ONDE OS NÚMEROS MORAM
# ===========================================================================

def test_os_numeros_do_APP_nao_vem_do_BC():
    """*"O ecossistema APP tem que ter suas próprias configurações, que não
    dependam do bot BC."* Todos num lugar só, para a mudança futura ser uma
    mudança só."""
    from blazesbot.config import PotionConfig

    assert mod.VIDA_PARA_CURAR != PotionConfig().hp_pct
    assert mod.VIDA_PARA_CURAR != PotionConfig().battle_hp_pct
    for nome in ("VIDA_PARA_CURAR", "VIDA_ALVO_DA_CURA", "SEGUNDOS_ENTRE_POCOES",
                 "MAXIMO_DE_POCOES", "SEGUNDOS_PARA_VOLTAR_AO_PONTO",
                 "SEGUNDOS_SENTADO", "SEGUNDOS_ESPERANDO_SAIR_DE_BATALHA"):
        assert hasattr(mod, nome), nome


def test_o_modulo_de_cura_NAO_importa_do_BC():
    """Ecossistema APP. `bc/` e `app/` nunca se importam."""
    import ast
    import inspect

    fonte = ast.parse(inspect.getsource(mod))
    importados = set()
    for no in ast.walk(fonte):
        if isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module)
        elif isinstance(no, ast.Import):
            importados |= {n.name for n in no.names}

    assert not [m for m in importados if "bc" in m.split(".")]


def test_nenhuma_espera_cega_no_modulo():
    """Regra do projeto: onde havia espera cega, agora se PERGUNTA.

    Todo `sleep` daqui é o PASSO de um laço que confere alguma coisa; nenhum é
    "dorme o intervalo inteiro e torce".
    """
    import ast
    import inspect

    fonte = ast.parse(inspect.getsource(mod))
    for no in ast.walk(fonte):
        if not (isinstance(no, ast.Call)
                and isinstance(no.func, ast.Attribute)
                and no.func.attr == "sleep"):
            continue
        arg = no.args[0]
        assert isinstance(arg, ast.Name) and arg.id == "PASSO_DA_PERGUNTA", (
            f"espera cega na linha {no.lineno}")


def test_a_cura_e_chamada_UMA_VEZ_por_volta_e_antes_do_lixo():
    """*"Ao terminar a macro você vai verificar a vida."* E antes da limpeza da
    bolsa: com 30% de vida, apagar lixo primeiro é tempo que ele não tem."""
    import ast
    import inspect
    import textwrap

    from blazesbot.bot.app.executor import ExecutorDeMacro

    fonte = textwrap.dedent(inspect.getsource(ExecutorDeMacro.rodar))
    arvore = ast.parse(fonte)

    linha_da_cura = [n.lineno for n in ast.walk(arvore)
                     if isinstance(n, ast.Attribute) and n.attr == "cuidar"]
    linha_do_lixo = [n.lineno for n in ast.walk(arvore)
                     if isinstance(n, ast.Attribute)
                     and n.attr == "_limpar_a_bolsa_se_for_a_hora"]

    assert len(linha_da_cura) == 1, "a cura é chamada mais de uma vez por volta"
    assert linha_da_cura[0] < linha_do_lixo[0], "o lixo vem antes da cura"


def test_a_cura_NAO_conta_como_volta():
    """Volta é rotação de macro. As cadências de limpeza e de shuffle foram
    pensadas em cima de trabalho de macro, não de tempo parado se curando."""
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(mod))
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Attribute):
            assert no.attr != "voltas", "a cura mexe no contador de voltas"


def test_a_volta_a_base_deixou_de_ser_espera_cega():
    """Era `time.sleep(2.0)` cego, e o método dizia ter devolvido o personagem
    sem nunca ter conferido."""
    import ast
    import inspect
    import textwrap

    from blazesbot.bot.app.executor import ExecutorDeMacro

    fonte = textwrap.dedent(
        inspect.getsource(ExecutorDeMacro._voltar_para_base))
    chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}

    assert "_esperar_chegar_na_base" in chamadas
    assert "sleep" not in chamadas


# ===========================================================================
# A POÇÃO ACABOU -- e o personagem descobre em UM SEGUNDO
# ===========================================================================

def test_pocao_que_NAO_senta_significa_que_ACABOU(monkeypatch):
    """*"Ela deve fazer [sentar] caso, ao usar poção, não entre no estado de
    sentado pela memória, pois provavelmente acabou as poções do usuário."*

    BEBER PÕE O PERSONAGEM SENTADO. Antes desta leitura, "a poção saiu?" era
    pergunta sem observável: o bot descobria pela vida, quinze segundos depois,
    e com a bolsa vazia repetia isso CINCO vezes -- apertando uma tecla que não
    fazia nada enquanto o personagem apanhava.
    """
    monkeypatch.setattr(mod, "SEGUNDOS_SENTADO", 0.05)
    jogo = _Jogo(vida=20.0, tem_pocoes=False)

    assert _cura(jogo).cuidar() is True

    assert jogo.teclas.count("9") == 1, (
        f"insistiu na poção que não existe: {jogo.teclas}")
    assert jogo.teclas.count("X") >= 1, "não sentou como alternativa"
    assert any("acabaram as poções" in t for _n, t in jogo.linhas), jogo.linhas


def test_pocao_que_SENTA_segue_bebendo():
    """O caminho normal não pode ser confundido com bolsa vazia."""
    jogo = _Jogo(vida=20.0, cura_por_pocao=40.0, tem_pocoes=True)

    assert _cura(jogo).cuidar() is True

    assert jogo.teclas.count("9") == 2
    assert jogo.vida >= mod.VIDA_ALVO_DA_CURA


def test_NAO_SEI_se_sentou_nao_conclui_que_acabou(monkeypatch):
    """Sem leitura do estado, concluir "acabaram as poções" trocaria a cura boa
    por sentar no chão. "Não sei" nunca pode virar veredito."""
    jogo = _Jogo(vida=20.0, cura_por_pocao=40.0)
    jogo.esta_sentado = lambda: None
    monkeypatch.setattr(mod, "SEGUNDOS_PARA_SENTAR_COM_A_POCAO", 0.05)

    _cura(jogo).cuidar()

    assert jogo.teclas.count("9") >= 2, "desistiu da poção por não conseguir ler"
    assert not any("acabaram as poções" in t for _n, t in jogo.linhas)


def test_a_bolsa_vazia_e_descoberta_em_UM_SEGUNDO_e_nao_em_quinze():
    """O teto da prova é a animação local do cliente, não uma ida ao servidor.

    Se ela fosse da ordem de `SEGUNDOS_ENTRE_POCOES`, descobrir a bolsa vazia
    custaria o mesmo que não descobrir.
    """
    assert mod.SEGUNDOS_PARA_SENTAR_COM_A_POCAO < mod.SEGUNDOS_ENTRE_POCOES / 5


def test_o_aviso_de_bolsa_vazia_NAO_repete_o_de_sem_tecla(monkeypatch):
    """Dois caminhos chegam a sentar, e o log tem que dizer qual foi."""
    monkeypatch.setattr(mod, "SEGUNDOS_SENTADO", 0.05)

    vazia = _Jogo(vida=20.0, tem_pocoes=False)
    _cura(vazia).cuidar()
    sem_tecla = _Jogo(vida=20.0)
    _cura(sem_tecla, pocao="").cuidar()

    texto_vazia = " ".join(t for _n, t in vazia.linhas)
    texto_sem = " ".join(t for _n, t in sem_tecla.linhas)

    assert "acabaram as poções" in texto_vazia
    assert "acabaram as poções" not in texto_sem
    assert "sem tecla de poção" in texto_sem
    assert "sem tecla de poção" not in texto_vazia


# ===========================================================================
# A CURA DEVOLVE O PERSONAGEM DE PÉ, E SÓ ANDA ANTES DE BEBER
# ===========================================================================

def test_depois_da_pocao_o_personagem_fica_DE_PE():
    """DEFEITO QUE ESTE TESTE TRAVA: beber senta o personagem, então a cura com
    poção devolvia o controle com ele NO CHÃO.

    Sentado, a macro inteira bate no chão: as teclas saem, o jogo ignora, e o
    bot conta voltas achando que está farmando. O caminho do "sentar" já
    levantava; o da poção não -- e ninguém tinha como saber.
    """
    jogo = _Jogo(vida=20.0, cura_por_pocao=40.0)

    _cura(jogo).cuidar()

    assert jogo.sentado is False, "a cura devolveu o personagem sentado"


def test_fica_DE_PE_tambem_quando_o_mob_chega_no_meio_da_cura():
    """Com o mob em cima, levantar vem ANTES de qualquer outra coisa."""
    jogo = _Jogo(vida=20.0, cura_por_pocao=1.0)
    original = jogo.apertar

    def apertar(tecla):
        original(tecla)
        if tecla == "9":
            jogo.batalha = True

    jogo.apertar = apertar

    _cura(jogo).cuidar()

    assert jogo.sentado is False, "voltou para a macro sentado, com mob em cima"


def test_fica_DE_PE_quando_as_5_pocoes_nao_bastaram():
    jogo = _Jogo(vida=20.0, cura_por_pocao=1.0)
    _cura(jogo).cuidar()
    assert jogo.sentado is False


def test_NAO_levanta_ENTRE_uma_pocao_e_a_outra():
    """A recuperação acontece com o personagem SENTADO. Levantar no meio
    cortaria justamente o efeito que se está esperando."""
    jogo = _Jogo(vida=20.0, cura_por_pocao=20.0)   # precisa de 4 poções

    _cura(jogo).cuidar()

    # Uma única tecla de sentar no fim -- não uma a cada poção.
    assert jogo.teclas.count("X") == 1, jogo.teclas
    assert jogo.teclas.index("X") == len(jogo.teclas) - 1, (
        f"levantou no meio da cura: {jogo.teclas}")


def test_NAO_anda_DEPOIS_de_beber():
    """*"Caso use a poção não pode andar depois, só deve andar antes de usar a
    poção."*

    Depois da poção o personagem está SENTADO, e um clique no minimapa o
    levanta e cancela a recuperação.
    """
    jogo = _Jogo(vida=20.0, distancia=8.0, cura_por_pocao=40.0)
    ordem: list[str] = []
    original_voltar, original_apertar = jogo.voltar_para_base, jogo.apertar

    def voltar():
        ordem.append("ANDOU")
        return original_voltar()

    def apertar(tecla):
        ordem.append(f"tecla {tecla}")
        original_apertar(tecla)

    jogo.voltar_para_base, jogo.apertar = voltar, apertar

    _cura(jogo).cuidar()

    assert ordem.count("ANDOU") == 1, f"andou mais de uma vez: {ordem}"
    assert ordem[0] == "ANDOU", f"bebeu antes de andar: {ordem}"
    assert "ANDOU" not in ordem[1:], f"andou depois de beber: {ordem}"


def test_nenhum_caminho_de_CURA_manda_andar():
    """A trava de desenho: `_voltar_ao_ponto` roda UMA vez, antes de `_curar`.
    Um `voltar_para_base` dentro de qualquer rotina de cura é andar depois de
    beber."""
    import ast
    import inspect
    import textwrap

    for nome in ("_curar", "_curar_com_pocao", "_curar_sentado", "_levantar"):
        fonte = textwrap.dedent(
            inspect.getsource(getattr(mod.CuraDoApp, nome)))
        chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)}
        assert "_voltar_para_base" not in chamadas, (
            f"`{nome}` manda andar -- depois de beber isso cancela a cura")


def test_a_batalha_e_conferida_MUITAS_vezes_durante_os_15_segundos():
    """O usuário pediu "de 1 em 1 segundo". O passo é 0,1 s -- dez vezes mais
    frequente, e cada volta custa uma leitura de memória de ~1 µs.

    Encurtar a reação ao mob é o ponto inteiro da cura.
    """
    assert mod.PASSO_DA_PERGUNTA <= 1.0
    perguntas = mod.SEGUNDOS_ENTRE_POCOES / mod.PASSO_DA_PERGUNTA
    assert perguntas >= 15, f"só {perguntas:.0f} conferências em 15 s"


# ===========================================================================
# O ESTADO DE SENTAR É TRI-ESTADO -- conserto de 26/08/2026
# ===========================================================================
#
# `Memory.is_sitting()` devolvia `bool` puro: falha de leitura virava `False`,
# ou seja "está de pé". O ramo `ilegivel` de `_a_pocao_saiu` era inalcançável, e
# toda leitura falha virava o veredito "acabaram as poções".
#
# MEDIDO no log de 25/08/2026: 4 avisos de bolsa vazia na MESMA sessão em que
# houve 3 curas bem-sucedidas com 2 poções cada. As poções existiam.

def test_a_SEGUNDA_pocao_nao_pode_usar_o_sentar_como_prova():
    """DA SEGUNDA POÇÃO EM DIANTE ELE JÁ ESTÁ SENTADO pela primeira.

    "Está sentado" deixa de provar qualquer coisa -- seria dar por boa uma
    tecla apertada contra a bolsa vazia. A pergunta perde o observável, e a
    resposta certa é "não sei", que segue bebendo.
    """
    jogo = _Jogo(vida=20.0, cura_por_pocao=5.0)
    cura = _cura(jogo)

    cura.cuidar()

    # Cinco poções: a bolsa nunca esvaziou, então nenhum aviso de bolsa vazia
    # pode ter saído por causa do "já estava sentado".
    assert jogo.teclas.count("9") == mod.MAXIMO_DE_POCOES
    assert not any("acabaram as po" in t for _n, t in jogo.linhas), jogo.linhas


def test_estado_ILEGIVEL_nao_conclui_bolsa_vazia():
    """`None` NÃO É "não saiu". Sem leitura de estado, concluir "acabaram as
    poções" trocaria a cura boa por sentar no chão."""
    jogo = _Jogo(vida=20.0, cura_por_pocao=5.0)
    jogo.esta_sentado = lambda: None
    cura = _cura(jogo)

    cura.cuidar()

    assert jogo.teclas.count("9") == mod.MAXIMO_DE_POCOES
    assert not any("acabaram as po" in t for _n, t in jogo.linhas), jogo.linhas


def test_LEVANTAR_com_o_estado_ilegivel_usa_o_que_o_BOT_FEZ():
    """Os dois erros custam o mesmo: apertar quem está de pé o SENTA; não
    apertar quem está sentado deixa a macro batendo no chão.

    Não se decide isso no palpite -- decide-se no que este objeto SABE ter
    feito. Se fomos nós que o sentamos, ele está sentado.
    """
    # SEM TECLA DE POÇÃO: o caminho é sentar direto. A tecla de sentar
    # funciona; o que está ilegível é a LEITURA do estado.
    jogo = _Jogo(vida=20.0)
    jogo.esta_sentado = lambda: None
    cura = _cura(jogo, pocao="")

    cura.cuidar()

    # Apertou para sentar e apertou de novo para levantar.
    assert jogo.teclas.count("X") == 2, jogo.teclas
    assert any("uso o que eu mesmo fiz" in t for _n, t in jogo.linhas)


def test_o_aviso_do_estado_ilegivel_sai_UMA_vez():
    """Uma sessão de APP roda por horas; uma linha por cura afogaria o log."""
    jogo = _Jogo(vida=20.0)
    jogo.esta_sentado = lambda: None
    cura = _cura(jogo, pocao="")

    for _ in range(3):
        jogo.vida = 20.0
        cura.cuidar()

    avisos = [t for _n, t in jogo.linhas if "uso o que eu mesmo fiz" in t]
    assert len(avisos) == 1, avisos


def test_a_pocao_que_realmente_NAO_SENTA_ainda_e_bolsa_vazia():
    """O mecanismo não pode morrer no conserto: com a leitura BOA e o
    personagem de pé depois da tecla, a bolsa está vazia."""
    jogo = _Jogo(vida=20.0, tem_pocoes=False)
    cura = _cura(jogo)

    cura.cuidar()

    assert jogo.teclas.count("9") == 1, "insistiu numa bolsa provadamente vazia"
    assert any("acabaram as po" in t for _n, t in jogo.linhas), jogo.linhas


def test_sentar_dura_30s_e_confere_a_batalha_o_tempo_todo():
    """Decisão do usuário em 26/08/2026: *"caso seja sentar será no máximo 30
    segundos e tbm precisa ficar verificando se entrou em batalha, que se for o
    caso pode começar a macro diretamente"*."""
    assert mod.SEGUNDOS_SENTADO == 30.0

    jogo = _Jogo(vida=20.0, tem_pocoes=False)
    perguntas = [0]
    original = jogo.em_batalha

    def contando():
        perguntas[0] += 1
        return original()

    jogo.em_batalha = contando
    _cura(jogo).cuidar()

    assert perguntas[0] > 20, (
        f"o sentar virou espera cega: {perguntas[0]} pergunta(s) em 30 s")
