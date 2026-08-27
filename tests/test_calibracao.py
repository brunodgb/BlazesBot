"""O placar da calibração: a tela é o gabarito, a memória é a aluna.

=============================================================================
O QUE ESTE ARQUIVO PROTEGE
=============================================================================

A calibração existe para responder, sem ninguém olhando a tela, QUAL offset é o
ponteiro certo. Se o placar contar errado, a resposta vem errada -- e o que se faz
com a resposta é promover um ponteiro a DECIDIR MORTE, que gasta TAB.

Então os testes que carregam o peso são os que impedem o placar de aprender a
coisa errada:

**`test_gabaritar_exige_RUNS_distintas`** -- acertar 50 vezes na mesma sessão pode
ser sorte de heap. O episódio do `+0x60` é a prova de que endereço muda entre
versões, e a struct muda entre sessões.

**`test_amostra_em_vida_CHEIA_nao_e_discriminante`** -- no waypoint todo mundo está
com 100. O log de 19/08/2026 mostra `hp_memoria=100` constante por 38 s: um
candidato que leia qualquer coisa perto de 100 "acerta" ali sem provar nada.

**`test_o_PET_reprova_pela_ESCALA`** -- `hp_memoria=243` apareceu em produção, e
243/243 é a escala de jogador/pet. O número era plausível; a escala é o que
denuncia.

**`test_um_erro_TIRA_o_gabaritou`** -- promoção não é permanente. Um cliente novo
(o cenário do `+0x60`) invalida o que já passou, e um rótulo velho mentiria.
"""
import json

import pytest

from blazesbot.core import calibracao
from blazesbot.core.calibracao import Amostra, julgar_booleano, julgar_hp

ESCALA = 100


@pytest.fixture(autouse=True)
def _placar_limpo(tmp_path, monkeypatch):
    """Placar zerado e em pasta temporária.

    O estado é de MÓDULO (cinco contas no mesmo processo compartilham o placar),
    então sem zerar um teste contamina o seguinte -- e o sintoma seria uma cascata
    de falhas sem relação com o que cada um mede.
    """
    monkeypatch.setattr(calibracao, "ATIVADA", True)
    monkeypatch.setattr(calibracao, "CAMINHO_DO_PLACAR",
                        tmp_path / "calibracao.json")
    calibracao.zerar_para_teste()


def _amostra(acertou=True, discriminante=True, run="run1", candidato="0x808"):
    return Amostra(prova="alvo_hp", candidato=candidato, acertou=acertou,
                   discriminante=discriminante, id_run=run)


def _alimentar(n, *, acertou=True, discriminante=True, runs=1,
               candidato="0x808"):
    """`n` amostras espalhadas por `runs` runs distintas."""
    ultimo = None
    for i in range(n):
        ultimo = calibracao.registrar(_amostra(
            acertou=acertou, discriminante=discriminante,
            run=f"run{i % runs}", candidato=candidato))
    return ultimo


# ---------------------------------------------------------------------------
# 1. O JULGAMENTO DO HP
# ---------------------------------------------------------------------------

def test_acerto_dentro_da_tolerancia():
    """A barra é pixel contado e a memória é inteiro: divergir 1 ou 2 pontos é o
    normal, e reprovar por isso reprovaria o ponteiro CERTO."""
    a = julgar_hp(prova="alvo_hp", candidato="0x808", hp_lido=48,
                  max_hp_lido=100, hp_da_tela=0.50, escala_de_inimigo=ESCALA)

    assert a.acertou is True
    assert a.discriminante is True


def test_erro_fora_da_tolerancia():
    a = julgar_hp(prova="alvo_hp", candidato="0x808", hp_lido=90,
                  max_hp_lido=100, hp_da_tela=0.50, escala_de_inimigo=ESCALA)

    assert a.acertou is False


def test_o_PET_reprova_pela_ESCALA():
    """`hp_memoria=243` apareceu no log de 19/08/2026 -- é o PET.

    `memory.py` documenta que a escala 243/243 é de jogador/pet e que a validação
    de ENTIDADE não pega isso, porque o pet é uma entidade legítima. Quem pega é a
    escala, e é por isso que ela entra no julgamento.
    """
    a = julgar_hp(prova="alvo_hp", candidato="0x80c", hp_lido=243,
                  max_hp_lido=243, hp_da_tela=0.50, escala_de_inimigo=ESCALA)

    assert a.acertou is False
    assert "pet" in a.detalhe


def test_sem_gabarito_a_amostra_NAO_CONTA():
    """`acertou=None` não conta nem a favor nem contra -- mesma regra do veredito
    de morte, onde "não sei" nunca foi resposta.

    O que ela PASSOU a fazer, em 20/08/2026, é ser CONTADA em separado: sem isso
    um candidato que nunca responde ficava fora do placar para sempre e travava a
    escalada para a varredura. Ver `TENTATIVAS_SEM_LEITURA_PARA_DESISTIR`.
    """
    a = julgar_hp(prova="alvo_hp", candidato="0x808", hp_lido=50,
                  max_hp_lido=100, hp_da_tela=None, escala_de_inimigo=ESCALA)
    assert a.acertou is None

    v = calibracao.registrar(a)
    assert v.amostras == 0, "silêncio contou como amostra"
    assert v.acertos == 0
    assert v.sem_leitura == 1

    b = julgar_hp(prova="alvo_hp", candidato="0x808", hp_lido=None,
                  max_hp_lido=None, hp_da_tela=0.5, escala_de_inimigo=ESCALA)
    assert b.acertou is None


# ---------------------------------------------------------------------------
# 1b. `sem_resposta` -- o silêncio tem fim
# ---------------------------------------------------------------------------

def _calar(n, candidato="0x868"):
    """`n` tentativas que não produzem leitura nenhuma."""
    v = None
    for _ in range(n):
        v = calibracao.registrar(julgar_hp(
            prova="alvo_hp", candidato=candidato, hp_lido=None,
            max_hp_lido=None, hp_da_tela=0.5, escala_de_inimigo=ESCALA))
    return v


def test_quem_NUNCA_responde_e_encerrado():
    """O defeito medido em 20/08/2026: `VARREDURA 0 eventos`.

    `0x868` e `0x86c` nunca produziam leitura, então nunca entravam no placar,
    então nunca eram encerrados -- e `_lista_fechada_esgotou` esperava por eles
    para sempre. A varredura nunca começava, justamente para o ponteiro que mais
    precisa dela.
    """
    v = _calar(calibracao.TENTATIVAS_SEM_LEITURA_PARA_DESISTIR)

    assert v.situacao == "sem_resposta"
    assert calibracao.deve_amostrar("alvo_hp", "0x868") is False


def test_antes_do_limite_ainda_e_amostrado():
    _calar(calibracao.TENTATIVAS_SEM_LEITURA_PARA_DESISTIR - 1)
    assert calibracao.deve_amostrar("alvo_hp", "0x868") is True


def test_quem_JA_respondeu_nao_e_aposentado_pelo_silencio():
    """Candidato que já deu leitura e ficou mudo é leitura que falhou, não offset
    inexistente. Aposentá-lo perderia um candidato bom por um trecho ruim da run.
    """
    calibracao.registrar(julgar_hp(
        prova="alvo_hp", candidato="0x868", hp_lido=50, max_hp_lido=100,
        hp_da_tela=0.50, escala_de_inimigo=ESCALA))

    v = _calar(calibracao.TENTATIVAS_SEM_LEITURA_PARA_DESISTIR * 2)

    assert v.situacao != "sem_resposta"
    assert calibracao.deve_amostrar("alvo_hp", "0x868") is True


@pytest.mark.parametrize("fracao, esperado", [
    (1.00, False),   # vida cheia: qualquer leitura perto de 100 "acerta"
    (0.97, False),
    (0.90, True),
    (0.50, True),
    (0.10, True),
    (0.03, False),   # vida quase zero: idem, no outro extremo
    (0.00, False),
])
def test_amostra_em_vida_CHEIA_nao_e_discriminante(fracao, esperado):
    """A amostra que PROVA algo é a do meio da luta.

    No waypoint todo mundo está com 100 -- e o log de 19/08/2026 mostra
    `hp_memoria=100` constante por 38 s. Contar aquilo como evidência faria um
    ponteiro parado "gabaritar".
    """
    a = julgar_hp(prova="alvo_hp", candidato="0x808",
                  hp_lido=int(fracao * 100), max_hp_lido=100,
                  hp_da_tela=fracao, escala_de_inimigo=ESCALA)

    assert a.discriminante is esperado


# ---------------------------------------------------------------------------
# 2. O JULGAMENTO BOOLEANO (modal, janela de loot)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lido, na_tela, acertou", [
    (True, True, True), (False, False, True),
    (True, False, False), (False, True, False),
])
def test_booleano_compara_com_a_tela(lido, na_tela, acertou):
    a = julgar_booleano(prova="modal", candidato="0x012CE35C", lido=lido,
                        na_tela=na_tela)
    assert a.acertou is acertou


def test_booleano_e_SEMPRE_discriminante():
    """Ao contrário do HP, booleano não tem extremo em que qualquer leitura
    acerta: errar `False` quando é `True` informa tanto quanto o contrário."""
    a = julgar_booleano(prova="modal", candidato="x", lido=False, na_tela=False)
    assert a.discriminante is True


# ---------------------------------------------------------------------------
# 3. GABARITAR -- os três critérios, cada um sozinho
# ---------------------------------------------------------------------------

def test_gabaritar_exige_as_TRES_condicoes():
    v = _alimentar(calibracao.AMOSTRAS_PARA_GABARITAR,
                   runs=calibracao.RUNS_PARA_GABARITAR)

    assert v.situacao == "gabaritou"
    assert v.amostras >= calibracao.AMOSTRAS_PARA_GABARITAR
    assert v.runs >= calibracao.RUNS_PARA_GABARITAR


def test_gabaritar_exige_RUNS_distintas():
    """Acertar 50 vezes na MESMA sessão pode ser sorte de heap.

    O `+0x60` do `core/rebase.py` é a prova medida de que endereço muda entre
    versões do cliente -- e a struct muda entre sessões. "Acertou nesta sessão"
    não é "está certo".
    """
    v = _alimentar(calibracao.AMOSTRAS_PARA_GABARITAR * 2, runs=1)

    assert v.situacao == "aprendendo", (
        "gabaritou com uma run só -- o critério de runs distintas caiu"
    )


def test_gabaritar_exige_DISCRIMINANTES():
    """Mil amostras em vida cheia não provam nada. Ver o teste do discriminante."""
    v = _alimentar(calibracao.AMOSTRAS_PARA_GABARITAR * 2, discriminante=False,
                   runs=calibracao.RUNS_PARA_GABARITAR)

    assert v.situacao == "aprendendo"
    assert v.discriminantes_certas == 0


def test_gabaritar_exige_ZERO_erro():
    """Não é rigor por gosto: o que se faz com um ponteiro promovido é decidir
    morte, e morte gasta TAB. Um candidato que erra uma em cinquenta erraria uma
    vez por noite -- e essa run é indistinguível de uma normal no log."""
    _alimentar(calibracao.AMOSTRAS_PARA_GABARITAR,
               runs=calibracao.RUNS_PARA_GABARITAR)
    v = calibracao.registrar(_amostra(acertou=False, run="runX"))

    assert v.situacao == "aprendendo"


def test_um_erro_TIRA_o_gabaritou():
    """Promoção não é permanente.

    Um cliente novo (o cenário do `+0x60`) invalida o que já passou, e um rótulo
    velho mentiria justamente para quem confia no placar.
    """
    v = _alimentar(calibracao.AMOSTRAS_PARA_GABARITAR,
                   runs=calibracao.RUNS_PARA_GABARITAR)
    assert v.situacao == "gabaritou"

    v = calibracao.registrar(_amostra(acertou=False, run="run0"))

    assert v.situacao == "aprendendo", "o rótulo `gabaritou` sobreviveu a um erro"


# ---------------------------------------------------------------------------
# 4. REPROVAR -- e a economia que ele traz
# ---------------------------------------------------------------------------

def test_reprova_quem_erra_muito():
    v = _alimentar(calibracao.AMOSTRAS_PARA_REPROVAR, acertou=False, runs=5)

    assert v.situacao == "reprovado"


def test_reprovado_PARA_de_ser_amostrado():
    """A economia do caminho quente: hoje são quatro leituras de ponteiro por
    leitura de combate, e no fim da convergência será uma."""
    _alimentar(calibracao.AMOSTRAS_PARA_REPROVAR, acertou=False, runs=5)

    assert calibracao.deve_amostrar("alvo_hp", "0x808") is False
    assert calibracao.deve_amostrar("alvo_hp", "0x80c") is True, (
        "reprovar um candidato não pode calar os outros"
    )


def test_desligado_nao_amostra_nem_registra(monkeypatch):
    monkeypatch.setattr(calibracao, "ATIVADA", False)

    assert calibracao.deve_amostrar("alvo_hp", "0x808") is False
    assert calibracao.registrar(_amostra()) is None


# ---------------------------------------------------------------------------
# 5. PERSISTÊNCIA -- o arquivo tem que sobreviver às noites
# ---------------------------------------------------------------------------

def test_o_placar_vai_para_o_disco_e_volta(tmp_path, monkeypatch):
    _alimentar(10, runs=3)
    assert calibracao.salvar() is True

    bruto = json.loads(calibracao.CAMINHO_DO_PLACAR.read_text(encoding="utf-8"))
    assert bruto["candidatos"]["alvo_hp|0x808"]["amostras"] == 10

    # Um "processo novo": o estado de módulo some, o arquivo fica.
    calibracao.zerar_para_teste()
    monkeypatch.setattr(calibracao, "_CARREGADO", False)
    assert calibracao.deve_amostrar("alvo_hp", "0x808") is True
    assert calibracao.resumo()[0].amostras == 10, (
        "o placar não voltou do disco -- a evidência das noites anteriores "
        "estaria perdida"
    )


def test_a_gravacao_e_ATOMICA(tmp_path):
    """Cinco contas e uma queda no meio de um `write` deixariam JSON truncado --
    e a próxima leitura perderia TODA a evidência acumulada, que é exatamente o
    que este arquivo existe para não deixar acontecer."""
    _alimentar(5)
    calibracao.salvar()

    assert calibracao.CAMINHO_DO_PLACAR.is_file()
    assert not calibracao.CAMINHO_DO_PLACAR.with_suffix(".tmp").exists(), (
        "o temporário ficou para trás; o `replace` não aconteceu"
    )
    json.loads(calibracao.CAMINHO_DO_PLACAR.read_text(encoding="utf-8"))


def test_grava_sozinho_a_cada_N_amostras():
    """Nem a cada amostra (seria uma reescrita por leitura de combate, com cinco
    contas) nem só no fim da run (uma queda perderia a sessão inteira)."""
    _alimentar(calibracao.AMOSTRAS_ENTRE_GRAVACOES - 1, runs=3)
    assert not calibracao.CAMINHO_DO_PLACAR.exists()

    _alimentar(1, runs=3)
    assert calibracao.CAMINHO_DO_PLACAR.is_file()


def test_placar_corrompido_nao_derruba_nada(tmp_path, monkeypatch):
    calibracao.CAMINHO_DO_PLACAR.write_text("{isto nao e json", encoding="utf-8")
    calibracao.zerar_para_teste()
    monkeypatch.setattr(calibracao, "_CARREGADO", False)

    assert calibracao.deve_amostrar("alvo_hp", "0x808") is True
    assert calibracao.registrar(_amostra()) is not None


def test_a_mesma_run_nao_conta_duas_vezes():
    """Uma run que amostra em dois pontos (waypoint dos guardas e do boss) não
    pode valer como duas runs."""
    for _ in range(20):
        calibracao.registrar(_amostra(run="a-mesma-run"))

    assert calibracao.resumo()[0].runs == 1


def test_o_resumo_poe_quem_gabaritou_na_frente():
    _alimentar(calibracao.AMOSTRAS_PARA_GABARITAR,
               runs=calibracao.RUNS_PARA_GABARITAR, candidato="0x808")
    _alimentar(calibracao.AMOSTRAS_PARA_REPROVAR, acertou=False, runs=5,
               candidato="0x80c")

    ordem = [v.candidato for v in calibracao.resumo()]
    assert ordem[0] == "0x808" and ordem[-1] == "0x80c"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ---------------------------------------------------------------------------
# 6. A PENEIRA -- filtragem progressiva estilo Cheat Engine
# ---------------------------------------------------------------------------
#
# Pedido do usuário depois de a lista fechada esgotar (`0x808` com 96% de erro,
# `0x80c` com 100%): *"o próprio bot tentar usar o cheat engine e ir tentando
# filtrar por si só."*
#
# O que faz o CE funcionar não é a varredura, é a MUDANÇA do valor -- e é isso
# que os testes abaixo protegem.

from blazesbot.core.calibracao import Peneira  # noqa: E402


def test_a_primeira_passada_guarda_quem_casa():
    p = Peneira(prova="alvo_hp")

    restam = p.peneirar({0x100: 50, 0x200: 90, 0x300: 51}, esperado=50.0)

    assert restam == 2                      # 50 e 51 estão na tolerância
    assert p.sobreviventes == {0x100, 0x300}


def test_a_segunda_passada_INTERSECTA():
    """É o aperto do CE: quem casou antes E casa agora."""
    p = Peneira(prova="alvo_hp")
    p.peneirar({0x100: 50, 0x200: 90, 0x300: 51}, esperado=50.0)

    restam = p.peneirar({0x100: 30, 0x200: 30, 0x300: 99}, esperado=30.0)

    assert restam == 1
    assert p.sobreviventes == {0x100}


def test_passada_SEM_MUDANCA_e_recusada():
    """O teste que carrega o peso.

    Apertar duas vezes com a MESMA vida não elimina ninguém -- todo endereço que
    passou na primeira passa na segunda. Pior que inútil: daria impressão de
    convergência. `MUDANCA_MINIMA_PARA_FILTRAR` é a tradução do "the value has
    changed" do Cheat Engine.
    """
    p = Peneira(prova="alvo_hp")
    p.peneirar({0x100: 50, 0x200: 50}, esperado=50.0)

    assert p.peneirar({0x100: 50, 0x200: 50}, esperado=51.0) == -1, (
        "a peneira apertou sem a vida ter mudado"
    )
    assert p.passadas == 1, "a passada recusada não pode contar"


def test_promove_so_com_POUCOS_sobreviventes_e_VARIAS_passadas():
    p = Peneira(prova="alvo_hp")
    achados = {0x100: 50, 0x200: 50}

    p.peneirar(achados, esperado=50.0)
    assert not p.pronta, "uma passada só não basta"

    p.peneirar({0x100: 30, 0x200: 30}, esperado=30.0)
    p.peneirar({0x100: 80, 0x200: 80}, esperado=80.0)

    assert p.passadas == calibracao.PASSADAS_PARA_PROMOVER
    assert p.pronta


def test_MUITOS_sobreviventes_nao_promove():
    """Cem candidatos não são resposta -- são a varredura ainda no começo."""
    p = Peneira(prova="alvo_hp")
    muitos = {off: 50 for off in range(0x100, 0x100 + 4 * 100, 4)}
    for esperado in (50.0, 50.0 + 20, 50.0 - 20):
        p.peneirar({o: esperado for o in muitos}, esperado=esperado)

    assert p.passadas == 3
    assert not p.pronta
    assert len(p.sobreviventes) > calibracao.SOBREVIVENTES_PARA_PROMOVER


def test_esgotada_e_recomecar():
    """Interseção zerada não paralisa: pode ser que o alvo tenha trocado no meio,
    e recomeçar é melhor que travar."""
    p = Peneira(prova="alvo_hp")
    p.peneirar({0x100: 50}, esperado=50.0)
    p.peneirar({0x100: 99}, esperado=20.0)

    assert p.esgotada
    p.recomecar()
    assert p.sobreviventes is None and p.passadas == 0


# ---------------------------------------------------------------------------
# 7. O NOME DO ALVO -- a segunda testemunha, independente do número
# ---------------------------------------------------------------------------
#
# Um número pode coincidir por acaso: foi o `hp_memoria=100` em vida cheia que
# obrigou a inventar `discriminante`. Um nome não -- `Gun Witch` num campo
# aleatório não acontece.
#
# E o gabarito é de CENÁRIO, não de tela: no waypoint dos guardas o alvo se chama
# `Gun Witch`, no do boss `Blaze Skull Marshal`. Não custa captura.

from blazesbot.core.calibracao import julgar_texto  # noqa: E402


def test_nome_certo_acerta():
    a = julgar_texto(prova="alvo_nome", candidato="0x808", lido="Gun Witch",
                     esperado="Gun Witch")
    assert a.acertou is True
    assert a.discriminante is True


def test_nome_errado_erra():
    a = julgar_texto(prova="alvo_nome", candidato="0x80c",
                     lido="Cemetery Guard", esperado="Gun Witch")
    assert a.acertou is False
    assert "Cemetery Guard" in a.detalhe


@pytest.mark.parametrize("lido", ["Gun Witch ", "gun witch",
                                  "Gun Witch Lv50", " Gun Witch"])
def test_compara_por_CONTINENCIA_e_nao_por_igualdade(lido):
    """O cliente devolve o nome com sufixo de nível, espaço à direita e caixa
    variável. Exigir igualdade exata reprovaria a leitura CERTA por formatação --
    e o objetivo é achar o ponteiro, não conferir string."""
    assert julgar_texto(prova="alvo_nome", candidato="x", lido=lido,
                        esperado="Gun Witch").acertou is True


def test_nome_que_NAO_leu_nao_conta():
    """Nome vazio é falha de leitura, não nome errado. Contra o candidato seria
    injusto; a favor seria pior."""
    for vazio in (None, ""):
        a = julgar_texto(prova="alvo_nome", candidato="x", lido=vazio,
                         esperado="Gun Witch")
        assert a.acertou is None


# ---------------------------------------------------------------------------
# 8. REABRIR -- quando a LEITURA muda, o histórico mente
# ---------------------------------------------------------------------------
#
# Defeito medido em 20/08/2026: a reserva `0x80C` (o PET) saiu do
# `target_object`, e `alvo_hp|0x808` passou a significar outra coisa. Mas o placar
# já o tinha REPROVADO na leitura antiga -- e reprovado não volta a ser amostrado.
#
# Doze runs depois do conserto, `alvo_hp` estava com TODOS os candidatos
# encerrados e não havia como medir o conserto. O placar guardava a memória de um
# defeito já corrigido e bloqueava a evidência nova.

def test_reabrir_devolve_o_candidato_a_medicao():
    _alimentar(calibracao.AMOSTRAS_PARA_REPROVAR, acertou=False, runs=5)
    assert calibracao.deve_amostrar("alvo_hp", "0x808") is False

    assert calibracao.reabrir("alvo_hp") == 1
    assert calibracao.deve_amostrar("alvo_hp", "0x808") is True
    assert calibracao.resumo() == []


def test_reabrir_um_candidato_so():
    _alimentar(10, candidato="0x808")
    _alimentar(10, candidato="0x80c")

    assert calibracao.reabrir("alvo_hp", "0x808") == 1

    restantes = {v.candidato for v in calibracao.resumo()}
    assert restantes == {"0x80c"}


def test_reabrir_prova_que_nao_existe_nao_estoura():
    assert calibracao.reabrir("nao_existe") == 0


def test_reabrir_grava_no_disco():
    """Senão o reinício seguinte traria o histórico velho de volta."""
    _alimentar(10)
    calibracao.salvar()
    calibracao.reabrir("alvo_hp")

    bruto = json.loads(calibracao.CAMINHO_DO_PLACAR.read_text(encoding="utf-8"))
    assert bruto["candidatos"] == {}


# ---------------------------------------------------------------------------
# 9. TOLERÂNCIA POR PROVA -- gabarito por consequência tem ruído próprio
# ---------------------------------------------------------------------------

def _alimentar_prova(prova, n, erros, runs):
    v = None
    for i in range(n):
        v = calibracao.registrar(Amostra(
            prova=prova, candidato="x", acertou=i >= erros,
            discriminante=True, id_run=f"run{i % runs}"))
    return v


def test_prova_com_gabarito_EXATO_exige_zero_erro():
    """Barra desenhada, caixa na tela, botão na tela: errar ali é o ponteiro
    errando, e o que se faz com um ponteiro promovido é decidir morte."""
    v = _alimentar_prova("alvo_hp", calibracao.AMOSTRAS_PARA_GABARITAR + 1,
                         erros=1, runs=calibracao.RUNS_PARA_GABARITAR)
    assert v.situacao == "aprendendo"


def test_flag_combate_aceita_o_ruido_do_ORACULO():
    """Medido em 20/08/2026, 12 runs: **8 erros em 6.452 amostras = 0,12%**.

    O gabarito da flag é por CONSEQUÊNCIA ("barra acima de 20% ⇒ há luta"), e a
    barra pode estar desenhada no instante em que o combate acabou. Exigir zero
    dela é exigir perfeição do ORÁCULO, não do ponteiro -- e `0x854` é o que o bot
    usa para encerrar as fases, e funciona.
    """
    total = 1000
    v = _alimentar_prova("flag_combate", total, erros=2,
                         runs=calibracao.RUNS_PARA_GABARITAR)

    assert v.taxa_de_erro <= calibracao.TOLERANCIA_DE_ERRO_POR_PROVA[
        "flag_combate"]
    assert v.situacao == "gabaritou"


def test_a_tolerancia_NAO_salva_candidato_ruim():
    """Ela é folga para RUÍDO, não indulgência.

    1% é oito vezes o ruído medido (0,12%) e duas ordens de grandeza abaixo do que
    um candidato ruim produz -- os reprovados desta noite estavam em 40%, 61%, 96%
    e 100%.
    """
    # 10% de erro: acima da tolerância, então NÃO gabarita...
    v = _alimentar_prova("flag_combate", 1000, erros=100,
                         runs=calibracao.RUNS_PARA_GABARITAR)
    assert v.situacao == "aprendendo"

    # ...e acima de `TAXA_DE_ERRO_PARA_REPROVAR` ele é REPROVADO como qualquer
    # outro. A tolerância não mexe no reprovar, só no gabaritar.
    calibracao.reabrir("flag_combate")
    ruim = _alimentar_prova("flag_combate", 1000, erros=500,
                            runs=calibracao.RUNS_PARA_GABARITAR)
    assert ruim.situacao == "reprovado"


# ---------------------------------------------------------------------------
# 10. DOIS PROCESSOS NO MESMO ARQUIVO -- perda de atualização
# ---------------------------------------------------------------------------
#
# Defeito medido em 20/08/2026: eu reabri `alvo_hp` num processo separado, e o
# BOT -- que estava rodando com as entradas velhas em memória -- sobrescreveu a
# reabertura no flush seguinte. `salvar()` escrevia o `_PLACAR` INTEIRO, então o
# último a escrever vencia com a cópia dele.

def _simular_outro_processo(candidato="0x808", amostras=500):
    """Escreve no arquivo como se outro processo tivesse gravado."""
    dados = {"candidatos": {f"alvo_hp|{candidato}": {
        "prova": "alvo_hp", "candidato": candidato, "amostras": amostras,
        "acertos": amostras, "discriminantes": amostras,
        "discriminantes_certas": amostras, "runs": ["a", "b"],
        "situacao": "aprendendo", "sem_leitura": 0,
        "primeira_vez": "", "ultima_vez": "", "ultimo_erro": ""}}}
    calibracao.CAMINHO_DO_PLACAR.parent.mkdir(parents=True, exist_ok=True)
    calibracao.CAMINHO_DO_PLACAR.write_text(json.dumps(dados),
                                            encoding="utf-8")


def test_salvar_NAO_apaga_o_que_outro_processo_gravou():
    """O teste que carrega o peso: contador de amostra só CRESCE, então "mais
    amostras" é sempre "mais informado" -- e a mescla é monótona."""
    _alimentar(10)                       # este processo viu 10
    _simular_outro_processo(amostras=500)   # o outro viu 500

    calibracao.salvar()

    bruto = json.loads(calibracao.CAMINHO_DO_PLACAR.read_text(encoding="utf-8"))
    assert bruto["candidatos"]["alvo_hp|0x808"]["amostras"] == 500, (
        "a gravação deste processo apagou as 500 amostras do outro"
    )


def test_o_processo_com_MAIS_amostras_ganha():
    _simular_outro_processo(amostras=5)
    _alimentar(100, runs=3)              # este processo viu mais

    calibracao.salvar()

    bruto = json.loads(calibracao.CAMINHO_DO_PLACAR.read_text(encoding="utf-8"))
    assert bruto["candidatos"]["alvo_hp|0x808"]["amostras"] == 100


def test_reabrir_NAO_e_desfeito_pela_mescla():
    """`reabrir` põe a contagem em ZERO, e zero PERDE a mescla por definição.

    Se `reabrir` gravasse com mescla, ele ressuscitaria exatamente o que quer
    apagar -- e foi o que a primeira versão fez. Ele grava SEM mesclar.
    """
    _alimentar(10)
    calibracao.salvar()
    assert calibracao.CAMINHO_DO_PLACAR.is_file()

    calibracao.reabrir("alvo_hp")

    bruto = json.loads(calibracao.CAMINHO_DO_PLACAR.read_text(encoding="utf-8"))
    assert bruto["candidatos"] == {}, (
        "a mescla ressuscitou o candidato que a reabertura apagou"
    )
