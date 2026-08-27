"""O Rich só existe em Stone City — e o bot precisa CHEGAR lá antes de procurar.

=========================================================================
O DEFEITO, RELATADO EM 18/08/2026
=========================================================================

*"o filtro por Rich e a ida até ele só deve acontecer em Stone City. Se tiver em
outra localização não irá funcionar, vai apenas ficar andando em um loop."*

Duas causas, e as duas estão cobertas aqui.

1. O RETORNO NÃO ERA CONFERIDO NEM REPETIDO. `voltar_para_a_cidade` confirmava o
   teleporte pelo SALTO DE POSIÇÃO -- que prova que algo aconteceu, não que o
   destino é Stone City -- e o chamador IGNORAVA o retorno
   (`self.voltar_para_a_cidade()` sem `if`).

2. `travel_to_vendor` NÃO TINHA PORTÃO DE LOCAL. Fora da cidade ela abria o
   painel de arredores, o filtro por "Rich" não achava nada, e o personagem
   ficava andando. E isso era pago 10 vezes, uma por ciclo de venda.
"""
from __future__ import annotations

import inspect

import pytest

from blazesbot.bot.bc import routine as mod_routine
from blazesbot.bot.bc import vendor as v


class _Log:
    def __init__(self): self.linhas = []
    def info(self, m, *a): self.linhas.append(("info", m % a if a else m))
    def warning(self, m, *a): self.linhas.append(("warning", m % a if a else m))
    def error(self, m, *a): self.linhas.append(("error", m % a if a else m))
    def debug(self, *a, **k): ...


def _servico(monkeypatch, roteiro, token="F1", pedra="F2"):
    """Um `VendorService` com o mundo dublado. `roteiro` diz onde o personagem
    está depois de cada tecla apertada."""
    servico = v.VendorService.__new__(v.VendorService)
    servico._guild_token_usado_em = 0.0
    servico._pedras_gastas = 0
    apertadas: list[str] = []
    estado = {"n": 0}

    class Memoria:
        @staticmethod
        def position(): return roteiro(estado["n"])[0]
        @staticmethod
        def location(): return roteiro(estado["n"])[1]

    class Keys:
        guild_token = token
        stone_charm = pedra

    class Ctx:
        log = _Log()
        account_login = "simulacao"
        memory = Memoria()
        settings = type("S", (), {"keys": Keys()})()

        def raise_if_stopped(self): ...
        def tick(self, s): ...

        def press(self, tecla, *a, **k):
            apertadas.append(tecla)
            estado["n"] += 1

    servico.ctx = Ctx()
    servico.nav = type("N", (), {
        "ensure_dismounted": staticmethod(lambda **k: True)})()
    monkeypatch.setattr(v.diario, "registrar_evento",
                        lambda *a, **k: None, raising=False)
    return servico, apertadas


# posições: Stone City é (158,-494); a cave é (423,53)
NA_CAVE = ((423, 53), "Bewitcher Cave")
EM_STONE = ((158, -494), "Stone City")


def test_chega_no_primeiro_token_e_nao_gasta_pedra(monkeypatch):
    """O caminho feliz: um Token resolve e a pedra nem é tocada."""
    servico, apertadas = _servico(
        monkeypatch, lambda n: EM_STONE if n >= 1 else NA_CAVE)
    assert servico.voltar_para_a_cidade() is True
    assert apertadas == ["F1"]
    assert servico._pedras_gastas == 0


def test_ja_estando_em_Stone_City_nao_gasta_nada(monkeypatch):
    """Conferir ANTES de apertar evita gastar item para ir aonde já se está."""
    servico, apertadas = _servico(monkeypatch, lambda n: EM_STONE)
    assert servico.voltar_para_a_cidade() is True
    assert apertadas == []


def test_o_token_e_tentado_10x_antes_da_pedra(monkeypatch):
    """Números do usuário: 10 Tokens, depois 3 pedras.

    O Token vem primeiro e é tentado muito porque NÃO GASTA ITEM. A recarga
    interna do bot não barra a tentativa — decisão do usuário, "às vezes pode ter
    ocorrido uma falha na contagem".
    """
    servico, apertadas = _servico(monkeypatch, lambda n: NA_CAVE)
    assert servico.voltar_para_a_cidade() is False
    assert apertadas.count("F1") == v.TENTATIVAS_DO_TOKEN
    assert apertadas.count("F2") == v.TENTATIVAS_DA_PEDRA
    assert apertadas[:v.TENTATIVAS_DO_TOKEN] == ["F1"] * v.TENTATIVAS_DO_TOKEN


def test_tecla_nao_configurada_e_PULADA(monkeypatch):
    """Pedido explícito: sem a tecla, o bloco dela é ignorado inteiro."""
    servico, apertadas = _servico(monkeypatch, lambda n: NA_CAVE, token="")
    servico.voltar_para_a_cidade()
    assert apertadas == ["F2"] * v.TENTATIVAS_DA_PEDRA

    servico, apertadas = _servico(monkeypatch, lambda n: NA_CAVE, pedra="")
    servico.voltar_para_a_cidade()
    assert apertadas == ["F1"] * v.TENTATIVAS_DO_TOKEN


def test_sem_nenhuma_tecla_recusa_sem_apertar(monkeypatch):
    servico, apertadas = _servico(monkeypatch, lambda n: NA_CAVE,
                                 token="", pedra="")
    assert servico.voltar_para_a_cidade() is False
    assert apertadas == []


def test_a_pedra_falhando_avisa_TECLA_ERRADA(monkeypatch):
    """A pedra não tem recarga e é garantida — falhar com ela é DIAGNÓSTICO.

    Palavra do usuário: o máximo que pode acontecer é a tecla estar configurada
    errada. Repetir em silêncio esconderia um erro de configuração dele.
    """
    servico, _ = _servico(monkeypatch, lambda n: NA_CAVE)
    servico.voltar_para_a_cidade()
    erros = " ".join(m for nivel, m in servico.ctx.log.linhas
                     if nivel == "error")
    assert "TECLA" in erros.upper(), erros
    assert "pedra" in erros.lower()


# =====================================================================
# O portão em travel_to_vendor
# =====================================================================

def test_travel_to_vendor_RECUSA_fora_de_Stone_City():
    """Ler o fonte, e não simular: o que importa é que o portão exista ANTES do
    painel de arredores. Simular a caminhada inteira testaria a navegação, que
    não é o que este defeito é."""
    fonte = inspect.getsource(v.VendorService.travel_to_vendor)
    i_portao = fonte.find("esta_em_stone_city")
    i_painel = fonte.find("travel_via_surroundings")
    assert i_portao != -1, "o portão de local desapareceu de travel_to_vendor"
    assert i_portao < i_painel, (
        "o portão está DEPOIS do painel de arredores — o personagem já teria "
        "começado a andar em laço antes de alguém conferir onde está")


def test_run_maintenance_CONFERE_o_retorno():
    """Antes era `self.voltar_para_a_cidade()` sem `if`: qualquer salto contava
    como chegada, e os 10 ciclos viravam 10 voltas de laço."""
    fonte = inspect.getsource(v.VendorService.run_maintenance)
    assert "if not self.voltar_para_a_cidade()" in fonte, (
        "o retorno da ida à cidade voltou a ser ignorado")


# =====================================================================
# As 3 rodadas, com uma run de BC entre elas
# =====================================================================

def test_a_run_extra_NAO_conta_para_o_gatilho_de_venda():
    """O ponto mais fácil de implementar errado.

    `_runs_na_ultima_venda` NÃO pode ser atualizado quando a venda falha: se
    fosse, o bot voltaria a farmar as 8 runs configuradas antes de tentar
    vender de novo. Pedido do usuário: a run extra conta para as RODADAS, não
    para as 8.
    """
    fonte = inspect.getsource(mod_routine.BossRushRoutine._do_manutencao)
    antes, _, depois = fonte.partition("self._rodadas_de_venda_falhas += 1")
    assert depois, "o contador de rodadas desapareceu"
    assert "_runs_na_ultima_venda" not in depois, (
        "o gatilho de venda é reiniciado no caminho de FALHA — o bot vai farmar "
        "as runs configuradas de novo em vez de tentar vender na sequência")


def test_a_venda_bem_sucedida_ZERA_as_rodadas():
    fonte = inspect.getsource(mod_routine.BossRushRoutine._do_manutencao)
    ok, _, resto = fonte.partition("if ok:")
    assert "_rodadas_de_venda_falhas = 0" in resto.split("# ====")[0], (
        "as rodadas não zeram na venda bem-sucedida; duas falhas separadas por "
        "horas de farm somariam e desligariam a conta sem motivo")


def test_esgotadas_as_rodadas_DESLIGA_o_bc_da_conta():
    """Decisão do usuário: "caso não chegue a vender os itens, o bot deve parar
    de funcionar, deve ser desligado"."""
    fonte = inspect.getsource(mod_routine.BossRushRoutine._do_manutencao)
    assert "bc_farm = False" in fonte
    assert "config.save()" in fonte, (
        "desligar sem salvar deixa o checkbox marcado no próximo início")
    assert mod_routine.RODADAS_DE_VENDA_ANTES_DE_DESLIGAR == 3


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
