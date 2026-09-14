"""A entrada da BC exige coordenada EXATA — e o painel de arredores erra por 6.

RELATO DO USUÁRIO, 14/09/2026: *"para chegar na entrada de BC é usado o
surroundings e normalmente ele entrega precisão, mas em raras exceções ele fica
um pouco fora da coordenada exata... acabou ficando parado sem conseguir entrar
por muito tempo, já que não acertava o clique direito"*.

MEDIDO no log: o painel pousou FORA do ponto **34 vezes** — de 4 a 12 unidades,
mediana **6** —, e em 2 delas as três tentativas se esgotaram sem corrigir. A
tolerância para o diálogo abrir é `TOLERANCIA_DO_NPC_DA_ENTRADA = 2`.

A correção ERA repetir o painel, com a justificativa de que ele *"comprovadamente
pousa no ponto certo"*. A medição derrubou isso: repetir o painel é repetir a
ferramenta que acabou de errar. Agora os últimos passos vão pelo MINIMAPA
(`encostar_no_ponto`), que é a mesma peça que o altar, a saída, a Fay e o
vendedor já usam — e a Fay tem o defeito IDÊNTICO documentado ("o painel caminha
até PERTO, ele aceita folga por construção").

O painel fica como reserva: ele ainda é a ferramenta certa quando o personagem
está longe de verdade.
"""
from types import SimpleNamespace

from blazesbot.bot.bc import ui_service


class _UI:
    """Só o que `garantir_coordenada_da_entrada` toca."""

    def __init__(self, posicoes, minimapa_funciona=True):
        self._posicoes = list(posicoes)
        self.ordem = []
        self._minimapa_funciona = minimapa_funciona
        self.ctx = SimpleNamespace(
            raise_if_stopped=lambda: None,
            memory=SimpleNamespace(position=self._position),
            settings=SimpleNamespace(
                route=SimpleNamespace(cave_entrance=(1395, -635))),
            log=SimpleNamespace(info=lambda *a, **k: None,
                                warning=lambda *a, **k: None,
                                debug=lambda *a, **k: None,
                                error=lambda *a, **k: None),
        )

    def _position(self):
        return self._posicoes.pop(0) if len(self._posicoes) > 1 else self._posicoes[0]

    def encostar_no_ponto(self, alvo, precisao, tentativas,
                          segundos_por_tentativa, o_que):
        self.ordem.append("minimapa")
        if self._minimapa_funciona:
            self._posicoes = [alvo]          # andou e chegou
        return self._minimapa_funciona

    def ir_ate_o_npc_da_cave(self):
        self.ordem.append("painel")
        return True

    def esquecer_entrada(self):
        # Esgotadas as tentativas, as coordenadas de clique aprendidas apontam
        # para o lugar errado. Só registra: o teste não exercita a redescoberta.
        self.ordem.append("esqueceu")

    garantir_coordenada_da_entrada = (
        ui_service.UIService.garantir_coordenada_da_entrada)


def test_ja_no_ponto_nao_anda_nada():
    ui = _UI([(1395, -635)])
    assert ui.garantir_coordenada_da_entrada() is True
    assert ui.ordem == []


def test_fora_do_ponto_corrige_PELO_MINIMAPA_e_nao_pelo_painel():
    """O caso medido: 6 unidades fora, que é a mediana das 34 falhas."""
    ui = _UI([(1389, -635)])

    assert ui.garantir_coordenada_da_entrada() is True
    assert ui.ordem == ["minimapa"], (
        "voltou a corrigir pelo painel, que é a ferramenta que acabou de errar")


def test_o_painel_e_a_RESERVA_quando_o_minimapa_nao_da_conta():
    """Longe de verdade o painel ainda é a ferramenta certa."""
    ui = _UI([(900, -400)], minimapa_funciona=False)

    ui.garantir_coordenada_da_entrada()
    assert ui.ordem[:2] == ["minimapa", "painel"]


def test_sem_leitura_de_posicao_deixa_seguir():
    """"Não sei" não bloqueia — recusar aqui travaria a run por falha de
    leitura, e quem decide então é o diálogo abrir ou não."""
    ui = _UI([None])
    assert ui.garantir_coordenada_da_entrada() is True
    assert ui.ordem == []


def test_a_precisao_exigida_e_a_MESMA_que_o_minimapa_recebe():
    """Um número lido por dois lados mora num lugar só. Dois valores — um para
    andar, outro para conferir — foi o defeito que travou a run no altar
    ("cheguei" de um lado, "não cheguei" do outro, sobre o mesmo instante)."""
    import ast
    import inspect
    import textwrap

    arvore = ast.parse(textwrap.dedent(inspect.getsource(
        ui_service.UIService.garantir_coordenada_da_entrada)))

    chamada = next(
        no for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
        and no.func.attr == "encostar_no_ponto")
    precisao = next(k.value for k in chamada.keywords if k.arg == "precisao")
    assert isinstance(precisao, ast.Name)
    assert precisao.id == "TOLERANCIA_DO_NPC_DA_ENTRADA"


def test_duas_tentativas_cobrem_o_pior_caso_medido():
    """Um clique de minimapa alcança ~17,6 unidades e a pior falha vista foi de
    12 — duas tentativas cobrem com folga."""
    assert ui_service.TENTATIVAS_DE_ENCOSTAR_NA_ENTRADA == 2
    assert ui_service.TOLERANCIA_DO_NPC_DA_ENTRADA == 2
