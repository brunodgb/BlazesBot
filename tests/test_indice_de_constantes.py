"""O índice das constantes não pode ficar velho, e a doc não pode mentir.

=============================================================================
O DEFEITO QUE ESTES TESTES TRAVAM
=============================================================================

O projeto decide comportamento por CONSTANTE no topo do módulo, e documenta o
valor dela em prosa -- no `CLAUDE.md` e em `docs/decisoes/`. Isso funciona
enquanto os dois andam juntos, e apodrece em silêncio quando não andam.

E não andaram: o `CLAUDE.md` afirma, em maiúsculas, *"O MOUSE SHIELD É
OBRIGATÓRIO (`USAR_MOUSE_SHIELD = True`)"*, e o código está em `False`. Quem lê
a documentação para decidir alguma coisa decide sobre um bot que não existe.

Dois dentes, contra dois modos de apodrecer:

  1. `test_o_indice_esta_atualizado` -- `docs/INTERRUPTORES.md` é GERADO; se o
     código mudar e o arquivo não for regenerado, reprova.
  2. `test_a_documentacao_nao_contradiz_o_codigo` -- todo `NOME = valor` citado
     entre crases no `CLAUDE.md` ou em `docs/decisoes/` tem que bater com o
     valor no código.

O segundo é o que importa. Ele não impede a divergência de acontecer; impede
que ela SOBREVIVA a uma corrida de testes -- que é a única coisa que funciona,
porque ninguém relê 117 KB de documentação procurando número errado.
"""
import re
from pathlib import Path

import pytest

from blazesbot.core.indice_de_constantes import (
    ARQUIVO_DO_INDICE,
    extrair,
    gerar_markdown,
)

# `NOME = valor` entre crases, que é como este projeto cita constante em prosa.
CITACAO = re.compile(r"`([A-Z][A-Z0-9_]{3,})\s*=\s*([^`]{1,40})`")


def _documentos() -> list[Path]:
    """Os documentos que descrevem o bot de HOJE -- e só eles.

    `CLAUDE.md` e `docs/INVARIANTES.md` guardam A REGRA: os dois descrevem o bot
    que existe agora, e a regra de manutenção diz *"não deixe descrever um
    comportamento que o código já não tem"*. Divergência ali é defeito.

    O `INVARIANTES.md` ENTROU AQUI EM 27/08/2026, junto com a separação que tirou
    as regras de área do `CLAUDE.md`. Sem esta linha, a mudança de organização
    teria desligado a rede de segurança em silêncio: a maior parte das citações
    `NOME = valor` mudou de arquivo, e um teste que varre só o `CLAUDE.md`
    passaria a proteger quase nada -- continuando verde, que é o pior jeito de
    uma proteção morrer.

    `docs/decisoes/` continua de FORA, e a exclusão é deliberada. Ele guarda O
    PORQUÊ MEDIDO -- *"a alternativa que foi tentada e reprovou"*. Valor antigo
    ali é o conteúdo, não o erro: `stuttering-mouse.md` cita
    `MODO_DE_CLIQUE = "sendmessage_rapido"` porque foi o padrão anterior, e
    apagar isso apagaria a medição que justifica o padrão atual.

    Um teste que reprovasse por causa dessas citações forçaria a reescrita da
    história para ficar verde -- exatamente o contrário do que os arquivos de
    decisão existem para fazer.
    """
    # SEM `if is_file()`: documento que muda de lugar tem que REPROVAR, não sair
    # da conferência calado -- ver `test_os_documentos_conferidos_existem`.
    return list(DOCUMENTOS_CONFERIDOS)


DOCUMENTOS_CONFERIDOS = (Path("CLAUDE.md"), Path("docs/INVARIANTES.md"))

# QUANTAS CITAÇÕES `NOME = valor` DE INTERRUPTOR A CONFERÊNCIA ACHA HOJE
# (25/09/2026). É catraca, como a da espera cega: a rede que encolhe até zero
# continua VERDE -- "nenhuma divergência" porque não sobrou o que examinar -- e
# é assim que uma reorganização de documentos a desliga sem sinal nenhum.
# Tirou uma citação de propósito? Baixe o número NESTE arquivo, no mesmo commit.
PISO_DE_CITACOES_CONFERIDAS = 2


def _normalizar(texto: str) -> str:
    """Compara VALOR, não grafia.

    A prosa é em português e escreve `0,9`; o código escreve `0.9`. As aspas
    variam entre simples e duplas. Nada disso é divergência -- fazer o teste
    reprovar por causa de vírgula decimal o transformaria em ruído, e teste
    ruidoso é desligado.
    """
    texto = texto.strip().strip("`").strip()
    texto = texto.replace('"', "").replace("'", "")
    if re.fullmatch(r"-?\d+,\d+", texto):
        texto = texto.replace(",", ".")
    try:
        return repr(float(texto))
    except ValueError:
        return texto.lower()


# ---------------------------------------------------------------------------
# 1. O índice não pode ficar velho
# ---------------------------------------------------------------------------

def test_o_indice_existe():
    assert ARQUIVO_DO_INDICE.is_file(), (
        f"{ARQUIVO_DO_INDICE} não existe. Gere com "
        "`python -m blazesbot.core.indice_de_constantes`"
    )


def test_o_indice_esta_atualizado():
    esperado = gerar_markdown()
    atual = ARQUIVO_DO_INDICE.read_text(encoding="utf-8")
    assert atual == esperado, (
        f"{ARQUIVO_DO_INDICE} está desatualizado. Regenere com "
        "`./.venv/Scripts/python.exe -m blazesbot.core.indice_de_constantes`"
    )


def test_todo_interruptor_conhecido_esta_no_indice():
    """Os interruptores são o motivo de o índice existir. Se um sumir da
    extração, o índice deixa de cobrir justamente o que ele foi feito para
    cobrir -- e não teria como alguém notar."""
    nomes = {c.nome for c in extrair() if c.e_interruptor}
    # `USAR_PRAZO_DO_PORTAO` e `FONTE_DA_MORTE_DO_ALVO` SAÍRAM desta lista em
    # 25/08/2026, junto com o `VigiaDoAlvo` e o consenso que eles governavam. O
    # veredito de morte passou a ser: barra da tela no offset medido, e o
    # `EnemyDead.png` confirmando abaixo de 10%. Interruptor que não governa
    # nada não é interruptor -- é comentário com cara de configuração.
    for esperado in ("MODO_DE_CLIQUE", "MODO_DE_TECLA", "USAR_MOUSE_SHIELD",
                     "USAR_TAB_NOS_GUARDAS", "CONFERIR_SLOT_VAZIO",
                     "USAR_OFFSET_FIXO_DA_BARRA", "USAR_PORTAO_DE_NOME"):
        assert esperado in nomes, f"{esperado} sumiu do índice"


def test_o_indice_diz_quem_le_cada_constante():
    """"Onde ela vai impactar" é metade do valor do índice."""
    por_nome = {c.nome: c for c in extrair()}
    assert por_nome["MODO_DE_CLIQUE"].leitores, (
        "MODO_DE_CLIQUE é lido por outros arquivos e o índice não achou nenhum"
    )


def test_endereco_de_memoria_fica_de_fora():
    """`ADDR_*`/`OFF_*`/`CHAIN_*` são medição do binário, não ajuste -- e são
    dezenas. Deixá-las entrar afogaria as constantes que alguém realmente muda."""
    nomes = {c.nome for c in extrair()}
    assert not any(n.startswith(("ADDR_", "OFF_", "CHAIN_")) for n in nomes)


def test_constante_de_protocolo_fica_de_fora():
    nomes = {c.nome for c in extrair()}
    assert "WM_KEYDOWN" not in nomes
    assert "MK_LBUTTON" not in nomes


# ---------------------------------------------------------------------------
# 2. A documentação não pode contradizer o código
# ---------------------------------------------------------------------------

def test_a_documentacao_nao_contradiz_o_codigo():
    """Todo `NOME = valor` citado em prosa tem que bater com o código.

    Só confere INTERRUPTOR (bool e modo). Os números medidos são citados na
    prosa com contexto histórico -- *"o 15 ms reprovou, virou 80"* --, e exigir
    que toda menção histórica bata com o valor de hoje apagaria justamente a
    história que `docs/decisoes/` existe para guardar.
    """
    # Nome definido em MAIS DE UM arquivo não pode ser conferido: não há como
    # saber de qual a prosa está falando. `ATIVADO` existe em `deletador.py` e
    # em `diagnostico_do_link.py` com valores diferentes, e a primeira versão
    # deste teste acusou o `deletador.md` de mentir comparando com o valor do
    # OUTRO arquivo. Acusação errada gasta mais confiança do que a checagem
    # devolve.
    por_nome: dict[str, list] = {}
    for constante in extrair():
        if constante.e_interruptor:
            por_nome.setdefault(constante.nome, []).append(constante)
    interruptores = {nome: lista[0]
                     for nome, lista in por_nome.items() if len(lista) == 1}

    divergencias: list[str] = []
    conferidas = 0

    for documento in _documentos():
        texto = documento.read_text(encoding="utf-8")
        for nome, citado in CITACAO.findall(texto):
            constante = interruptores.get(nome)
            if constante is None:
                continue
            conferidas += 1
            if _normalizar(citado) != _normalizar(repr(constante.valor)):
                divergencias.append(
                    f"  {documento}: diz `{nome} = {citado.strip()}`, "
                    f"mas {constante.arquivo}:{constante.linha} tem "
                    f"{constante.valor_formatado}"
                )

    assert not divergencias, (
        "A documentação afirma valores que o código não tem:\n"
        + "\n".join(sorted(set(divergencias)))
        + "\n\nCorrija o LADO ERRADO: se o código está certo, atualize a prosa; "
        "se a prosa está certa, o interruptor foi trocado sem querer."
    )
    assert conferidas >= PISO_DE_CITACOES_CONFERIDAS, (
        f"a conferência achou {conferidas} citação(ões) de interruptor, contra "
        f"{PISO_DE_CITACOES_CONFERIDAS} em 25/09/2026. Rede que encolhe continua "
        f"verde sem proteger nada: se a citação saiu de propósito, baixe "
        f"PISO_DE_CITACOES_CONFERIDAS neste arquivo, no mesmo commit.")


def test_os_documentos_conferidos_existem():
    """Documento que muda de lugar REPROVA -- não sai da conferência calado.

    Foi exatamente o modo de falha que o `INVARIANTES.md` quase causou em
    27/08/2026: a lista de caminhos é literal, e um arquivo renomeado sairia da
    varredura sem nenhum sinal.
    """
    faltam = [str(d) for d in DOCUMENTOS_CONFERIDOS if not d.is_file()]
    assert not faltam, (
        f"sumiram da conferência: {faltam}. Se mudaram de lugar, atualize "
        f"DOCUMENTOS_CONFERIDOS -- sem isso as citações deles param de ser "
        f"conferidas sem aviso.")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
