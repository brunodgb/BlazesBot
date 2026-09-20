"""A venda inteira, simulada, com o VÃO DE REARRANJO da grade.

=========================================================================
O QUE ESTA SIMULAÇÃO PROVA
=========================================================================

Medido na venda das 10:43 de 14/08/2026: a passada parou com **22 dos 66
cliques**, dizendo "acabaram os itens" com a grade CHEIA. A foto da própria
run (`logs/diagnostico-do-link/104345.082-...-t+750.png`) mostra 24 itens na
página 1/3 e o slot 4 -- o que o bot clicava -- com item.

A causa é a mecânica que o `sell_from_slot` descreve: ao tirar um item, os
seguintes SOBEM para preencher o buraco. Entre o item sair e o próximo descer,
o slot fica **de verdade vazio** por um instante. A `ESPERA_ENTRE_CLIQUES_DA_
VENDA` (0,1 s) foi encurtada de propósito para clicar mais rápido que isso --
então contar leituras seguidas NAQUELA cadência não separa "acabou" de "está
rearranjando": as três caem dentro do MESMO vão.

O relógio começa em 5.000,0 e não em zero: `0.0` é sentinela em vários pontos
do bot, e um relógio em zero torna "ainda não aconteceu" indistinguível de
"aconteceu no instante 0".
"""
import pytest

from blazesbot.bot import vendedor as janela_de_venda
from blazesbot.bot.bc import vendor as v

# LIDO NO IMPORT, antes da fixture que força o interruptor ligado. Perguntar a
# `v` depois da fixture provaria a fixture, não o código -- mesma lição do
# `FONTE_PADRAO_NO_CODIGO` em `test_combat_vigia_do_alvo.py`.
INTERRUPTOR_NO_CODIGO = janela_de_venda.CONFERIR_SLOT_VAZIO

# Quanto tempo a grade leva para trazer o item de baixo. Maior que a espera
# entre cliques (0,1 s) -- é essa desigualdade que cria o defeito.
#
# Precisa ser > 3 * ESPERA_ENTRE_CLIQUES_DA_VENDA (0,3 s): o DENTE faz 3 leituras
# coladas (0,1 + 0,1 + 0,1) e todas devem cair dentro do vão para reproduzir o
# defeito. 0,3 não basta por causa do `<`; 0,35 dá folga.
VAO_DE_REARRANJO = 0.35

# O slot 4 da janela localizada, o mesmo que o log de produção mostra.
PONTO_DO_SLOT = (554, 292)
BOTAO_VENDER = (474, 710)


@pytest.fixture(autouse=True)
def _com_a_conferencia_ligada(monkeypatch):
    """O interruptor está DESLIGADO em produção; os testes forçam LIGADO.

    Sem isto o caminho inteiro deixaria de ser exercitado e apodreceria
    desligado — e ligar de volta um dia seria ligar código não testado. O
    estado real do interruptor é conferido por
    `test_o_interruptor_esta_desligado`, que lê o valor do MÓDULO.
    """
    monkeypatch.setattr(janela_de_venda, "CONFERIR_SLOT_VAZIO", True)


class Relogio:
    def __init__(self) -> None:
        self.agora = 5_000.0

    def tick(self, segundos: float) -> None:
        self.agora += segundos


class GradeFalsa:
    """A grade da janela de venda: N itens, subindo com atraso a cada clique."""

    def __init__(self, relogio: Relogio, itens: int) -> None:
        self.relogio = relogio
        self.itens = itens
        self.cliques = 0
        self.vendidos = 0
        self._descido_em = relogio.agora

    def clicar(self) -> None:
        self.cliques += 1
        if self.itens > 0:
            self.itens -= 1
            self.vendidos += 1
            # O próximo item só aparece depois do vão.
            self._descido_em = self.relogio.agora + VAO_DE_REARRANJO

    def nota_de_vazio(self) -> float:
        """O CONTRASTE do miolo: BAIXO quando o slot está vazio na tela.

        Os números são os medidos nas fotos reais deste cliente -- vazio perto
        de 3, cheio perto de 60.
        """
        if self.itens <= 0:
            return 3.0
        rearranjando = self.relogio.agora < self._descido_em
        return 3.0 if rearranjando else 60.0


def _servico(monkeypatch, itens: int, cliques: int):
    """Um `VendorService` com o mundo dublado no nível do serviço."""
    relogio = Relogio()
    grade = GradeFalsa(relogio, itens)
    servico = v.VendorService.__new__(v.VendorService)

    class Log:
        def info(self, *a, **k): ...
        def debug(self, *a, **k): ...
        def warning(self, *a, **k): ...
        # `error` desde 20/09/2026: o Sell passou a gritar quando falha as três
        # tentativas (`_vender_a_lista`), e um dublê sem `error` esconderia
        # justamente o caminho novo.
        def error(self, *a, **k): ...

    class Vendor:
        # O TOTAL DE CLIQUES é do PERSONAGEM desde 09/09/2026; aqui fica só o
        # que continuou sendo da cave -- o slot inicial e o teto de passadas.
        sell_start_slot = 4

        @staticmethod
        def passadas_para(total):
            return max(1, -(-total // janela_de_venda.CLIQUES_POR_PASSADA))

    class Memoria:
        # A bolsa encolhe junto com a grade: é o que o serviço loga no fim, e
        # uma bolsa parada dispararia o registro de "ação sem efeito".
        @staticmethod
        def bag_count(): return 40 + grade.itens
        @staticmethod
        def position(): return (158, -494)
        @staticmethod
        def location(): return "Stone City"

    class Ctx:
        log = Log()
        account_login = "simulacao"
        settings = type("S", (), {"vendor": Vendor(),
                                  "sell_clicks": cliques})()
        memory = Memoria()

        def raise_if_stopped(self): ...
        def tick(self, s): relogio.tick(s)

        def click(self, ponto):
            # SÓ o clique no slot mexe na grade. O clique no botão Sell também
            # passa por aqui, e contá-lo como clique de slot mascararia a
            # contagem que os testes conferem.
            if ponto == PONTO_DO_SLOT:
                grade.clicar()

    servico.ctx = Ctx()
    monkeypatch.setattr(servico, "_open_npc", lambda: True, raising=False)
    monkeypatch.setattr(servico, "_quadro", lambda: object(), raising=False)
    monkeypatch.setattr(servico, "_dismiss_confirm", lambda: False,
                        raising=False)
    monkeypatch.setattr(servico, "_ponto_do_slot",
                        lambda: (PONTO_DO_SLOT, BOTAO_VENDER, "simulado"),
                        raising=False)
    monkeypatch.setattr(
        servico, "_nota_do_slot_vazio",
        lambda quadro, ponto: (grade.nota_de_vazio(), "miolo"),
        raising=False)
    return servico, grade


def test_o_rearranjo_nao_encerra_a_venda(monkeypatch):
    """O caso de produção: 66 cliques, grade cheia, vão a cada clique.

    Com a confirmação colada à cadência do clique a venda parava em 22. Com a
    confirmação ESPAÇADA ela vai até o fim.
    """
    servico, grade = _servico(monkeypatch, itens=66, cliques=66)
    servico.sell_from_slot()
    assert grade.vendidos == 66, (
        f"parou cedo: vendeu {grade.vendidos} de 66 -- o vão de rearranjo "
        f"voltou a ser lido como fim de itens")


def test_o_fim_de_verdade_encerra_a_venda(monkeypatch):
    """Acabando os itens antes dos cliques, a venda PARA -- é o pedido do usuário.

    Uma confirmação que nunca encerra seria tão defeituosa quanto uma que
    encerra cedo: os cliques restantes cairiam no nada.
    """
    servico, grade = _servico(monkeypatch, itens=10, cliques=66)
    servico.sell_from_slot()
    assert grade.vendidos == 10
    assert grade.cliques < 30, (
        f"não parou: {grade.cliques} cliques para 10 itens")


def test_a_confirmacao_e_espacada_e_nao_colada():
    """O número que separa confirmação de cadência de clique.

    Se a espera da confirmação encolher para perto da espera entre cliques, as
    leituras voltam a caber no mesmo vão de rearranjo e o defeito de produção
    volta -- sem nada no log parecendo diferente.
    """
    assert janela_de_venda.ESPERA_PARA_CONFIRMAR_VAZIO > janela_de_venda.ESPERA_ENTRE_CLIQUES_DA_VENDA * 4
    assert janela_de_venda.ESPERA_PARA_CONFIRMAR_VAZIO >= VAO_DE_REARRANJO


def test_confirmar_nao_clica(monkeypatch):
    """A confirmação relê, não vende.

    Se ela clicasse, cada dúvida custaria itens -- e no fim da venda clicaria
    contra a grade vazia, que é justamente o que se quer parar de fazer.
    """
    servico, grade = _servico(monkeypatch, itens=0, cliques=66)
    antes = grade.cliques
    assert servico._confirmar_slot_vazio(PONTO_DO_SLOT) is not None
    assert grade.cliques == antes


def test_volta_a_ter_item_desfaz_a_confirmacao(monkeypatch):
    """Uma leitura com item no meio da confirmação a derruba INTEIRA.

    Não é "a maioria venceu": item na grade é prova de que não acabou.
    """
    servico, grade = _servico(monkeypatch, itens=5, cliques=66)
    grade.clicar()                       # abre o vão
    assert servico._esta_vazio((grade.nota_de_vazio(), "miolo")), (
        "a simulação não abriu o vão de rearranjo")
    assert servico._confirmar_slot_vazio(PONTO_DO_SLOT) is None


# =====================================================================
# O INTERRUPTOR — desligado por decisão do usuário em 14/08/2026
# =====================================================================

def test_o_interruptor_esta_desligado():
    """A conferência está DESLIGADA em produção, e isso é escolha, não descuido.

    Pedido do usuário: "comenta por hora essa verificação de slot vazio e deixa
    clicar a quantidade total de vezes que o usuário configurou como estava
    antes". Se um dia religar, é aqui que a mudança aparece — de propósito.
    """
    assert INTERRUPTOR_NO_CODIGO is False


def test_DESLIGADA_clica_o_total_configurado(monkeypatch):
    """Desligada, a venda faz o que fazia antes de a conferência existir.

    Nem a grade vazia encerra: os 66 cliques configurados saem, em passadas de
    24, com o Sell de cada passada. É o comportamento antigo, inteiro.
    """
    monkeypatch.setattr(janela_de_venda, "CONFERIR_SLOT_VAZIO", False)
    servico, grade = _servico(monkeypatch, itens=2, cliques=66)
    servico.sell_from_slot()
    assert grade.cliques == 66, (
        f"deu {grade.cliques} cliques de 66 — algo ainda encerra a venda cedo")


def test_DESLIGADA_nao_paga_a_captura(monkeypatch):
    """Sem conferir, não se fotografa a tela por clique.

    É o ganho de velocidade que vem junto: a captura era o custo real da
    conferência. A caixa "It's precious item" continua conferida a cada clique
    — ela tem captura própria, e sem ela a passada inteira vende zero.
    """
    monkeypatch.setattr(janela_de_venda, "CONFERIR_SLOT_VAZIO", False)
    servico, _grade = _servico(monkeypatch, itens=9, cliques=66)
    olhadas = []
    monkeypatch.setattr(
        servico, "_nota_do_slot_vazio",
        lambda quadro, ponto: olhadas.append(ponto), raising=False)
    servico.sell_from_slot()
    assert olhadas == [], "conferiu o slot com o interruptor desligado"


# =====================================================================
# DENTE — reintroduz o defeito de produção e exige reprovação
# =====================================================================

def test_DENTE_contagem_colada_para_a_venda_cedo(monkeypatch):
    """Contando leituras na cadência do clique, a venda de 66 para em ~3.

    Este é o defeito medido em produção. Se um dia alguém "simplificar" a
    confirmação de volta para um contador de leituras seguidas, é este teste
    que denuncia -- ele passa SÓ enquanto o defeito é reproduzível, o que
    prova que a simulação tem o vão que importa.

    O defeito antigo contava 3 leituras coladas (LEITURAS_VAZIAS_PARA_PARAR=3).
    Com o valor atual 6, o contador colado faria 5 leituras (6-1) e ainda
    pararia cedo se não houvesse espaçamento.
    """
    servico, grade = _servico(monkeypatch, itens=66, cliques=66)

    # A versão antiga: conta leituras seguidas, sem espaçar nada.
    # O defeito original usava 3 leituras. Para reproduzir, usamos o valor
    # antigo (3) explicitamente em vez da constante atual (6).
    DEFEITO_ORIGINAL_LEITURAS = 3
    def contando_colado(alvo):
        leitura = None
        for _ in range(DEFEITO_ORIGINAL_LEITURAS - 1):
            servico.ctx.tick(janela_de_venda.ESPERA_ENTRE_CLIQUES_DA_VENDA)
            leitura = servico._nota_do_slot_vazio(servico._quadro(), alvo)
            if not servico._esta_vazio(leitura):
                return None
        return leitura

    monkeypatch.setattr(servico, "_confirmar_slot_vazio", contando_colado,
                        raising=False)
    servico.sell_from_slot()
    assert grade.vendidos < 10, (
        "o vão de rearranjo sumiu da simulação: sem ele os outros testes não "
        "provam nada")


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
