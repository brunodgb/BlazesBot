"""O `docs/TEMPOS.md` ACOMPANHA O CÓDIGO, e o ponto de restauração sobrevive.

Pedido do usuário em 25/08/2026:

    *"gera um .md para documentar isso e sempre atualiza lá coisas referentes a
     tempo, fixos ou variáveis... até para se eu alterar algo manualmente e der
     errado, eu tenho o ponto original"*

O "sempre atualiza" não pode depender de alguém lembrar. Aqui ele é o teste
passar: mexeu num tempo e não regerou, a suíte reprova e diz o comando.
"""
import json
from pathlib import Path

from blazesbot.core.indice_de_tempos import (
    ARQUIVO_DOS_ORIGINAIS,
    Tempo,
    carregar_originais,
    extrair,
    gerar_markdown,
)

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "docs" / "TEMPOS.md"


def test_o_catalogo_esta_atualizado():
    atual = ARQUIVO.read_text(encoding="utf-8")
    assert atual == gerar_markdown(), (
        "docs/TEMPOS.md está desatualizado. Regenere com "
        "`./.venv/Scripts/python.exe -m blazesbot.core.indice_de_tempos`"
    )


def test_todo_tempo_do_projeto_esta_no_catalogo():
    """A cobertura é da EXTRAÇÃO, não de quem escreveu. Se a extração deixar de
    achar um tipo de espera, o catálogo mente sem ninguém perceber."""
    tempos = extrair()
    assert len(tempos) > 200, f"a extração encolheu para {len(tempos)}"

    arquivos = {t.arquivo for t in tempos}
    for esperado in ("blazesbot/bot/bc/vendor.py",
                     "blazesbot/bot/bc/ui_service.py",
                     "blazesbot/bot/ui_do_jogo.py",
                     "blazesbot/bot/navegacao.py",
                     "blazesbot/bot/app/cura.py"):
        assert esperado in arquivos, f"nenhum tempo achado em {esperado}"


def test_a_extracao_acha_ESPERA_LITERAL_e_nao_so_constante():
    """Metade das esperas do bot é literal no meio de uma função
    (`ctx.tick(0.5)`), e nenhum índice de CONSTANTES as enxerga.

    São justamente as que mais atrapalham quem quer acelerar o bot: espera cega
    escondida dentro de uma função não aparece em lugar nenhum.
    """
    literais = [t for t in extrair() if not t.nome]
    assert len(literais) > 30, f"só {len(literais)} literais -- a extração quebrou"
    assert all(t.funcao for t in literais), "literal sem função dona"


def test_a_natureza_separa_TETO_de_espera_CEGA():
    """`ESPERA_DO_TELEPORTE` tem cara de espera fixa e o comentário dele abre com
    *"TETO da espera do teleporte -- não é mais o tempo gasto, é o limite"*.

    Classificar só pelo nome marcaria como dívida de espera cega justamente uma
    das conversões que já foram feitas.
    """
    por_chave = {t.chave: t for t in extrair()}
    teleporte = por_chave["blazesbot/bot/bc/vendor.py::ESPERA_DO_TELEPORTE"]
    assert teleporte.natureza == "TETO"

    passo = por_chave["blazesbot/bot/bc/vendor.py::PASSO_DA_ESPERA_DO_TELEPORTE"]
    assert passo.natureza == "PASSO"

    sell = por_chave["blazesbot/bot/bc/vendor.py::ESPERA_ANTES_DO_SELL"]
    assert sell.natureza == "FIXO"


def test_a_chave_NAO_usa_a_linha():
    """A linha muda a cada edição. Se ela entrasse na identidade, todo ajuste de
    código apagaria o ponto de restauração de tudo abaixo dele."""
    t = Tempo(arquivo="a/b.py", linha=10, funcao="f", nome="ESPERA_X",
              valor=1.0, porque="")
    outro = Tempo(arquivo="a/b.py", linha=999, funcao="f", nome="ESPERA_X",
                  valor=2.0, porque="")
    assert t.chave == outro.chave


def test_o_ponto_de_restauracao_existe_e_cobre_o_que_esta_no_codigo():
    """`docs/tempos-originais.json` é o motivo de o catálogo existir."""
    assert (RAIZ / ARQUIVO_DOS_ORIGINAIS).exists(), (
        "o ponto de restauração sumiu -- rode "
        "`python -m blazesbot.core.indice_de_tempos`")

    originais = carregar_originais()
    assert originais, "o arquivo de originais está vazio"

    sem_referencia = [t.chave for t in extrair() if t.chave not in originais]
    # Tempo NOVO não tem original, e isso é correto -- ele aparece como *novo*
    # na tabela. O que não pode é a referência ter sumido para tudo.
    assert len(sem_referencia) < len(originais) / 2, (
        f"{len(sem_referencia)} tempos sem referência: o arquivo de originais "
        f"parece de outra versão do código")


def test_o_json_dos_originais_e_legivel_e_estavel():
    """Ele é para ser lido por gente, e comparado entre versões."""
    dados = json.loads(
        (RAIZ / ARQUIVO_DOS_ORIGINAIS).read_text(encoding="utf-8"))
    assert all(isinstance(v, int | float) for v in dados.values())
    chaves = list(dados)
    assert chaves == sorted(chaves), "as chaves não estão ordenadas"


def test_o_catalogo_avisa_o_que_MUDOU_do_original():
    """A coluna ORIGINAL com `⚠` é o ponto de restauração. Sem ela o arquivo
    seria só mais uma lista."""
    texto = ARQUIVO.read_text(encoding="utf-8")
    assert "| original |" in texto
    assert "ponto de restauração" in texto.lower()


def test_o_catalogo_diz_que_e_GERADO():
    """Editar à mão um arquivo gerado é trabalho que a próxima geração apaga."""
    texto = ARQUIVO.read_text(encoding="utf-8")
    assert "GERADO" in texto
    assert "blazesbot.core.indice_de_tempos" in texto
