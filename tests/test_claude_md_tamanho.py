"""O `CLAUDE.md` é o NÚCLEO DE OPERAÇÕES — e quem o mantém assim é a GOVERNANÇA.

=========================================================================
O TETO É A REDE DE SEGURANÇA. A REGRA DE CONTEÚDO É O QUE ORGANIZA.
=========================================================================

O `CLAUDE.md` é lido inteiro no começo de cada sessão, então tudo que está nele
compete por atenção com tudo mais que está nele. Ele já chegou a 117 KB, e o que
aconteceu foi o previsível -- deixou de ser lido.

O teto de 35 000 caracteres existe desde 25/08/2026 e **funcionou como alarme e
falhou como organização**. Um limite quantitativo sem critério qualitativo é
otimizado pela via errada: quem precisa caber comprime o que já está lá em vez de
perguntar se aquilo pertence ali. Três sessões seguidas de 26-27/08/2026 gastaram
tempo escolhendo qual parágrafo espremer, com o arquivo parado em ~34,9k -- menos
legível a cada rodada, e do mesmo tamanho.

Em 27/08/2026 o usuário fixou a REGRA DE GOVERNANÇA (escrita no topo do próprio
`CLAUDE.md`): ali só entram configuração de skill, diretriz arquitetural global e
regra técnica crítica de atenção constante. Regra de ÁREA, documentação, guia de
uso e ata de decisão saíram para `docs/`. O arquivo caiu para ~13k **sem perder
uma linha** -- o conteúdo foi movido verbatim para `docs/INVARIANTES.md` e
`docs/decisoes/README.md`.

    configuração de skill, arquitetura global,
    regra crítica de atenção constante         -> CLAUDE.md
    regra de área ("não pode ser violado")     -> docs/INVARIANTES.md
    especificação e medição                    -> docs/REGRAS.md
    porquê medido                              -> docs/decisoes/<area>.md

=========================================================================
POR QUE O TETO CONTINUA EM 35k, E NÃO NO TAMANHO DE HOJE
=========================================================================

Decisão do usuário em 27/08/2026: *"o teto deve ser ainda de 35 mil caracteres,
mas com essas novas regras, de só escrever o necessário lá para tudo continuar
funcionando e melhorando"*.

E o raciocínio se sustenta: **quem organiza o arquivo agora é a governança, não o
teto.** Apertar o teto para perto do tamanho atual traria de volta exatamente o
problema que a separação resolveu -- o arquivo voltaria a viver encostado no
limite, e a próxima diretriz arquitetural legítima (um padrão obrigatório de
Python, de HTML, de estrutura) chegaria disputando espaço com as que já estão
aqui. Diretriz global é justamente o que ESTE arquivo existe para carregar; ela
não pode ser barrada por falta de folga.

Então o teto volta a ser o que sempre deveria ter sido: a **rede de segurança**
para o caso de a governança ser ignorada, e não a força que dá forma ao arquivo.
Quem dá a forma é `test_o_claude_md_nao_guarda_regra_de_AREA` -- esse sim reprova
por CATEGORIA, que é o critério certo.

Estourou os 35k? **A resposta certa quase nunca é subir o teto.** Com a
governança valendo, chegar perto disso significa que entrou aqui algo cujo
destino é `docs/` -- mova conteúdo, não comprima texto.
"""
import re
from pathlib import Path

MAXIMO = 35_000

# A partir daqui é aviso, não reprovação: dá tempo de mover detalhe antes de a
# suíte fechar a porta no meio de outra tarefa.
CONFORTAVEL = 33_000

RAIZ = Path(__file__).resolve().parent.parent


def _claude() -> str:
    return (RAIZ / "CLAUDE.md").read_text(encoding="utf-8")


def test_o_claude_md_cabe_no_teto():
    texto = _claude()
    assert len(texto) <= MAXIMO, (
        f"CLAUDE.md está com {len(texto)} caracteres, acima do teto de "
        f"{MAXIMO}. NÃO suba o teto: mova regra de ÁREA para "
        f"`docs/INVARIANTES.md`, especificação para `docs/REGRAS.md` e o porquê "
        f"medido para `docs/decisoes/`. Ver a seção 'Governança deste arquivo' "
        f"no topo do próprio CLAUDE.md."
    )


def test_o_claude_md_avisa_antes_de_encostar_no_teto():
    """Aviso, não reprovação -- para o teto não fechar a porta no meio de uma
    tarefa que só queria documentar uma linha."""
    import warnings

    tamanho = len(_claude())
    if tamanho > CONFORTAVEL:
        warnings.warn(
            f"CLAUDE.md com {tamanho} caracteres, encostando no teto de "
            f"{MAXIMO}. Com a governança valendo, isso quase sempre significa "
            f"que entrou aqui algo cujo destino é `docs/`.",
            stacklevel=1)
    assert True


def test_a_regra_de_governanca_esta_ESCRITA_no_proprio_arquivo():
    """A regra tem que viver onde ela é aplicada.

    Foi exigência explícita do usuário em 27/08/2026: *"escreva essa regra de
    organização dentro do próprio CLAUDE.md (…) para que o sistema saiba, nas
    próximas interações, o que é permitido adicionar nele e o que deve ser
    enviado para fora"*.

    E é ela, não o teto, que impede a reincidência. Um teto sozinho só diz QUANTO
    cabe; quem lê continua sem saber O QUE cabe, e a resposta natural a "está
    cheio" vira comprimir o texto em vez de mover o conteúdo -- que é exatamente
    o que aconteceu nas três sessões anteriores à separação.
    """
    texto = _claude()
    assert re.search(r"(?im)^##\s+Governança deste arquivo", texto), (
        "a seção 'Governança deste arquivo' sumiu do CLAUDE.md; sem ela o teto "
        "vira um número sem critério")

    for destino in ("docs/INVARIANTES.md", "docs/REGRAS.md",
                    "docs/decisoes/", "docs/SKILLS.md"):
        assert destino in texto, (
            f"a governança deixou de apontar o destino `{destino}`; regra sem "
            "destino é regra perdida")


def test_o_claude_md_nao_guarda_regra_de_AREA():
    """A trava que REALMENTE dá forma ao arquivo -- o teto é só a rede embaixo.

    Reprovar por CATEGORIA é o critério certo: um `CLAUDE.md` de 20k só com
    diretriz arquitetural está saudável, e um de 15k cheio de regra de combate
    está doente. O tamanho não distingue os dois; este teste distingue.

    É também o que impede a reincidência de "só desta vez escrevo aqui" -- foi
    assim que o arquivo chegou a 117 KB. O destino é `docs/INVARIANTES.md`, com
    o link daqui.
    """
    cabecalhos = set(re.findall(r"(?m)^#{2,3}\s+(.+)$", _claude()))
    proibidos = ("Combate", "Navegação", "Venda", "Pet", "Cliques e entrada",
                 "Ferramentas TEMPOR", "Deletar itens", "O laço do APP",
                 "Reset de time", "A TELA")
    intrusos = [c for c in cabecalhos
                if any(p.lower() in c.lower() for p in proibidos)]
    assert not intrusos, (
        f"regra de ÁREA voltou para o CLAUDE.md: {intrusos}. O destino é "
        "`docs/INVARIANTES.md` — mova VERBATIM e deixe aqui só o link.")
