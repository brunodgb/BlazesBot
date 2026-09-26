"""Quality gates do BlazesBot, em Python.

================================================================
POR QUE ESTE ARQUIVO EXISTE
================================================================

O toolkit `soumatheusgomes/vibe-coding-toolkit` traz três regras de ESLint
(teto de linhas por arquivo, proibição de `console` direto, e proibição da
camada de apresentação importar o cliente do banco) que são uma forma
compacta de dizer três princípios que valem para qualquer projeto:

  1. Um arquivo que cresce demais sem ser quebrado vira o lugar onde
     ninguém entra para mexer — e a próxima vez que precisar de mexer,
     o problema já é gigante. O teto de linhas é a pressão constante
     para que a quebra aconteça EM TEMPO DE ESCREVER, não em refactor
     heroico dois anos depois.

  2. `print()` em código de aplicação é o anti-log: o desenvolvedor
     depura localmente, deixa o print no código, o bot roda por horas
     em produção, e ninguém sabe o que apareceu no stdout do servidor
     nem tem como correlacionar com `logs/dev/blazes-dev.jsonl`.

  3. A camada de UI importar o cliente do banco é o acoplamento que
     parece inofensivo no dia e só cobra o preço meses depois, quando
     mexer num canto quebra o outro. A contraparte Python deste
     princípio já é `tests/test_ecossistemas.py` (bc/app/hh não se
     importam; core não conhece bot; bot não conhece ecossistema —
     exceto o supervisor, que ESCOLHE qual roda).

Este arquivo é a porta 1 e 2. A porta 3 já está coberta em
`test_ecossistemas.py` e não é duplicada.

================================================================
POR QUE WARN E NÃO ERROR (regra do passo 6 do toolkit)
================================================================

A regra do toolkit é clara: gate que nasce vermelho em cima de código
que já existia é ruído que alguém desliga na primeira sexta-feira.
Por isso cada teste nasce em `pytest.warns` (avisa, não reprova) e só
vira `assert` quando a contagem anotada chega a zero. A lista
baseline fica na docstring de cada teste, e a migração termina
quando a contagem zera e o teste passa a reprovar de verdade.

================================================================
MEDIÇÃO (05/09/2026) — POR QUE O TETO É 800, E NÃO 350
================================================================

O 350 do toolkit foi importado e reprovou 45 dos 90 `.py`. Duas
medições mostraram que o número não serve para ESTE projeto:

  1. A MEDIANA do projeto é 410 linhas. Um teto ABAIXO da mediana
     não sinaliza exceção — descreve o projeto inteiro. Gate que
     reprova a mediana não é gate: é ruído com 45 itens de fila,
     e fila que parece infinita convida a partir arquivo na marreta.

  2. Só 40% das linhas daqui são código executável:

         código ....... 22.475  (40%)
         docstring .... 13.136  (23%)
         comentário ... 11.907  (21%)
         em branco .....  7.621  (13%)

     O 350 do toolkit foi calibrado para TypeScript/JSX, muito mais
     denso. Aqui, 350 linhas cruas equivalem a ~142 linhas de código
     real — um teto 2,5x mais apertado do que o toolkit pretendia.
     Pior: 44% do arquivo é docstring e comentário, que é exatamente
     o que o `CLAUDE.md` EXIGE ("porquê medido", "documentação de
     transição no mesmo passo"). Um teto de linhas cruas em 350
     pune a documentação que outra regra do projeto manda escrever.

800 linhas cruas ≈ 325 linhas de código real — o ponto de pressão que
o toolkit de fato queria ("abaixo de ~200 vira briga, acima de ~500
para de pressionar", em linhas de CÓDIGO). Fica acima do p75 (664),
então reprova o outlier e não a mediana. E é o número que
`~/.claude/rules/ecc/code-review.md` já mandava ("Files are cohesive
(<800 lines)") antes do 350 vindo de fora atropelá-lo calado.

Teto de 800: 19 arquivos acima (era 45 com 350) — lista ordenada em
`docs/decisoes/eslint-portado-para-python.md`.

`print()` em local proibido: 4 ocorrências — ver mesmo doc.
"""
import re
import warnings
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent / "blazesbot"

# 800 linhas CRUAS ~= 325 linhas de código real neste projeto (só 40% das
# linhas daqui são código; 44% é docstring e comentário). É o ponto de
# pressão que o toolkit queria, medido para esta base — e não o 350 dele,
# que fica abaixo da mediana de 410 e reprovaria metade do projeto.
# O porquê completo está na docstring do módulo, seção MEDIÇÃO (05/09/2026).
TETO_DE_LINHAS = 800

# Quanto um HERDADO pode crescer sobre o tamanho que tinha em 05/09/2026
# antes de reprovar. Medido pelo efeito, nao escolhido no ar: a versao
# anterior desta catraca proibia QUALQUER crescimento, e no primeiro dia
# reprovou tres alteracoes de funcionalidade legitimas (combate.py +47L,
# hh/mapa_hh.py +58L, hh/routine.py +37L). A saida que ela sugeria --
# "coloque o codigo novo em outro modulo" -- e exatamente a fragmentacao
# que o GATE 3 abaixo existe para impedir: dois gates brigando.
#
# 10% deixa passar a alteracao normal e pega o arquivo em FUGA. Em
# combate.py (3735) a folga e de 373 linhas; um arquivo que consome isso
# nao esta recebendo uma funcionalidade, esta virando outro problema.
MARGEM_DO_HERDADO = 1.10

# Onde `print()` É legítimo. São a porta de saída de scripts ad-hoc e de
# diagnósticos que rodam UMA vez por invocação humana, não dentro do bot
# rodando. Tudo o mais é aplicação e deveria ir para `logging`.
#
# - `tools/` é a fronteira dos scripts CLI de aferição (vigiar, ler_camera,
#   find_base). É diagnóstico, não produção.
# - `core/calibracao.py`, `core/indice_de_constantes.py`,
#   `core/indice_de_tempos.py` rodam como `python -m blazesbot.core.X` —
#   mesma natureza de tools.
# - `bot/instrumentar_clique.py` e `bot/teste_do_cursor.py` são entradas
#   CLI do bot (ver `18-AFERIR-ALVO-ALIADO.bat`); têm `if __name__ ==
#   "__main__":` no fim e rodam uma vez por aferição.
EXCECOES_DE_PRINT = frozenset({
    "blazesbot/tools/find_base.py",
    "blazesbot/tools/ler_camera.py",
    "blazesbot/tools/vigiar_combate.py",
    "blazesbot/tools/vigiar_local.py",
    "blazesbot/tools/medir_a_rolha.py",
    "blazesbot/tools/medir_a_volta_do_pet.py",
    "blazesbot/tools/portao_de_commit.py",
    "blazesbot/tools/relatorio_da_rota_hh.py",
    "blazesbot/core/calibracao.py",
    "blazesbot/core/indice_de_constantes.py",
    "blazesbot/core/indice_de_tempos.py",
    "blazesbot/bot/instrumentar_clique.py",
    "blazesbot/bot/teste_do_cursor.py",
})


def _todos_os_python(raiz: Path) -> list[Path]:
    """Todos os `.py` da árvore, ordenados, exceto `__pycache__`."""
    return sorted(p for p in raiz.rglob("*.py")
                  if "__pycache__" not in p.parts)


# ===========================================================================
# GATE 1 — TETO DE 800 LINHAS POR ARQUIVO (CATRACA)
# ===========================================================================

# Os 19 arquivos que JÁ estavam acima do teto em 05/09/2026, com o tamanho
# que tinham naquele dia. A catraca usa este número como limite individual:
# o herdado pode ficar como está ou encolher, NUNCA crescer.
#
# Tirar um daqui é permanente: se o arquivo voltar a passar de 800 depois de
# sair da lista, ele é tratado como arquivo novo e REPROVA.
#
# 15 destes 19 são "uma classe gorda" (59-92% do arquivo é UMA classe) e
# estão marcados COESO: não têm costura de responsabilidade em nível de
# arquivo, e a regra do prompt 09 do toolkit para esse caso é "say so, leave
# it alone". Dividi-los não é refatoração, é redesenho da classe em objetos
# colaboradores — decisão própria, com medição própria. A tentativa de
# 04-05/09 provou o custo de ignorar isso (ver `git show
# refatoracao-350-descartada`). Ver a triagem completa em
# `docs/decisoes/eslint-portado-para-python.md`.
# QUANDO A LINHA DE BASE PODE SUBIR -- e é raro
#
# A catraca não tem escapatória de propósito: herdado encolhe ou fica. Só que
# DOIS destes arquivos são o ÚNICO lugar possível de uma classe inteira de
# alteração -- um campo novo de configuração precisa de uma linha no dataclass
# (`config.py`), uma no dicionário que a ponte manda para a tela e outra na que
# ela lê de volta (`web_app.py`). Não existe "outro módulo" para uma linha dentro de um
# literal, e quebrar `config.py` para acrescentar uma tecla seria pior desenho
# do que a linha.
#
# Então a regra fica: subir a base é ATO DELIBERADO, no mesmo commit que a
# provoca, com o motivo escrito ao lado do número. Subir por comodidade -- para
# caber lógica nova, comentário longo, método novo -- não vale: aí o certo
# continua sendo outro módulo. Toda subida aqui tem data e motivo.
HERDADOS = {
    # COESO — uma classe gorda, sem costura de arquivo
    "blazesbot/bot/combate.py": 3735,                    # CombatEngine, 52 métodos (74%)
    # SUBIU DE 2939 PARA 3326 EM 07/09/2026, e a margem foi consumida por
    # SOBREVIVÊNCIA, não por funcionalidade nova: o socorro em batalha, o
    # desfecho do teclado mudo e o reflexo contra a ociosidade sob ataque. Os
    # três nasceram de mortes e de horas paradas medidas em log
    # (`docs/decisoes/madrugada-07-09-2026.md`), e cada um empurrou o que dava
    # para o `core/` -- `teclado_mudo`, `vizinhanca.contar_pelo_injetado`,
    # `vigia_da_vida`. O que sobrou aqui é ação, e ação depende de `self`.
    #
    # A LINHA DE BASE SOBE UMA VEZ E FICA CARA: a próxima adição volta a
    # reprovar em +10%. O caminho para o 3327 não é subir de novo -- é o GATE 3,
    # e o corte natural é a família de AQUISIÇÃO DE ALVO (`_adquirir_alvo`,
    # `_preciso_de_alvo`, `_conseguir_o_tab`, `_garantir_alvo`,
    # `_tenho_alvo_vivo`, `_alvo_aceitavel`), que é uma responsabilidade
    # inteira e tem casa pronta em `core/target_hybrid.py`.
    "blazesbot/bot/app/executor.py": 3326,               # ExecutorDeMacro, 47 métodos (74%)
    # SUBIU DE 2755 PARA 3043 EM 15/09/2026, e a margem já estava ZERADA: o
    # arquivo marcava 3030 linhas, que é o limite EXATO. Treze linhas de sinal
    # de vida do time do APP estouraram.
    #
    # ESTE É O ÚLTIMO AUMENTO. O corte está identificado e tem precedente
    # pronto: `_rodar_modo_app` é uma montagem de closures do mesmo tipo que já
    # saiu daqui uma vez -- `bot/fada_montagem.py` nasceu exatamente assim,
    # empurrado por esta catraca. A próxima linha que alguém quiser acrescentar
    # paga essa extração, não outro número aqui.
    "blazesbot/bot/supervisor.py": 3043,                 # AccountSupervisor, 41 métodos (85%)
    "blazesbot/bot/bc/routine.py": 2596,                 # BossRushRoutine, 37 métodos (84%)
    "blazesbot/core/memory.py": 2498,                    # Memory, 82 métodos (74%)
    "blazesbot/bot/navegacao.py": 2164,                  # Navigator, 32 métodos (80%)
    "blazesbot/bot/ui_do_jogo.py": 1929,                 # UIDoJogo, 34 métodos (70%)
    "blazesbot/bot/hh/routine.py": 1511,                 # HHRoutine, 34 métodos (86%)
    # SUBIU DE 1451 PARA 1603 EM 18/09/2026 (a folga era de DUAS linhas).
    # Seis linhas: o campo `desativados` nos dois sentidos da ponte, para
    # o APP e para a HH.
    #
    # ESTE ARQUIVO CRESCE POR CONSTRUÇÃO -- ele é a fachada entre o
    # JavaScript e o Python, e toda tela nova passa por aqui. A regra que
    # o mantém honesto não é o tamanho, é `test_a_ponte_web_expoe_tudo`:
    # `Api` só delega, nunca implementa. Lógica de tela nova vai para
    # módulo próprio, e só a delegação entra aqui.
    "blazesbot/web_app.py": 1603,                        # _App, 45 métodos (63%)
    #  +2 em 04/09: ida e volta da tecla `revive_skill` na ponte
    "blazesbot/bot/login.py": 1134,                      # LoginSequence, 26 métodos (84%)
    # SUBIU DE 1111 PARA 1233 EM 16/09/2026, e a folga que sobrava era de TRÊS
    # linhas. O que entrou foi `passar_o_mouse` -- o hover sintético, primitiva
    # nova e sem substituto: submenu de menu de contexto NÃO abre com clique.
    #
    # É O SEGUNDO ARQUIVO NESTA SEMANA a encostar em 100% da margem (o outro é
    # `bot/supervisor.py`). Os dois são do caminho quente e nenhum para de
    # crescer sozinho -- o GATE 3 deixou de ser recomendação e virou tarefa.
    "blazesbot/core/inputs.py": 1233,
    # SUBIU DE 972 PARA 1080 EM 16/09/2026. A margem antiga acabou em duas
    # entregas do mesmo dia: a régua que mede o menu de contexto do convite
    # (perto do convidado ele vem com 12 itens, não 7) e o aviso da recusa sem
    # prova de caixa -- sem ele o seguidor recusava o convite CALADO, e o time
    # do APP não se formava sem deixar uma linha no log.
    #
    # O CORTE ESTÁ IDENTIFICADO: `InviteAcceptor` não é `TeamService`. Um
    # convida e o outro aceita; eles só se encontram pelo mural. São ~200 linhas
    # com casa pronta (`bot/aceitador.py`), do mesmo tipo que já saiu de
    # `supervisor.py` para `bot/fada_montagem.py`.
    "blazesbot/bot/team.py": 1080,                        # TeamService, 18 métodos (59%)
    "blazesbot/bot/vendedor.py": 935,                    # JanelaDeVenda, 19 métodos (65%)
    # COM COSTURA — muitas funções top-level; dividir é possível quando valer
    # SUBIU DE 1942 PARA 2165 EM 18/09/2026, com a folga JÁ ZERADA (2136 de
    # um teto de 2136). O que entrou foi o campo `desativados` -- os itens
    # que cada conta não apaga -- nos dois blocos de configuração.
    #
    # POR QUE NÃO FOI PAGO COM EXTRAÇÃO: tentei, e o próprio portão recusa.
    # `test_um_contexto_uma_porta` proíbe `config.py` + `config_*.py` como
    # irmãos e exige PACOTE com fachada -- e o pacote obriga a carvar o
    # `BotConfig` (753 linhas: carga, gravação e as migrações de versão).
    # Partir a persistência da configuração inteira do bot como efeito
    # colateral de uma tela é risco maior do que este portão protege.
    #
    # O CORTE CONTINUA SENDO ESSE, e agora com o nome dele: `BotConfig`
    # vira `blazesbot/config/` com fachada no `__init__.py`.
    "blazesbot/config.py": 2165,                         # 15 classes + 10 funções top-level
    #  +7 em 04/09: campo `revive_skill` no `KeyBinds` e o resumo dele
    "blazesbot/core/calibracao.py": 1105,                # 24 funções top-level (diagnóstico)
    "blazesbot/bot/bc/amostragem_de_cliques.py": 852,    # 12 funções top-level (diagnóstico)
    "blazesbot/bot/hh/mapa_hh.py": 834,                  # 0 classes, 16 funções top-level
}


@pytest.mark.parametrize("arquivo", _todos_os_python(RAIZ),
                         ids=lambda p: str(p.relative_to(RAIZ)))
def test_max_linhas_por_arquivo(arquivo):
    """Teto de 800 linhas por arquivo — como CATRACA, não como lista de tarefas.

    O gate NÃO existe para pagar a dívida dos 19 herdados. Existe para
    impedir o 20º de nascer. Por isso ele tem três comportamentos:

      * arquivo dentro do teto ................... passa;
      * arquivo NOVO acima do teto ............... REPROVA (assert);
      * herdado que passou a MARGEM de 10% ....... REPROVA (assert);
      * herdado, mesmo tamanho ou menor .......... avisa (`warn`).

    A diferença para o gate anterior é que agora ele tem dentes nos dois
    lados que importam: nada grande NASCE, e nada grande CRESCE. A fila
    só pode encolher. Um herdado que baixar de 800 deve ser removido do
    `HERDADOS` no mesmo commit — o teste diz isso na mensagem.

    Por que a dívida herdada não tem prazo: 15 dos 19 são "uma classe
    gorda", e a regra do prompt 09 do toolkit para arquivo sem costura
    de responsabilidade é "say so, leave it alone, and move to the next
    file". Arquivo grande e COESO é aceitável; arquivo grande e
    incoerente não é. Ver `docs/decisoes/eslint-portado-para-python.md`.
    """
    caminho = arquivo.relative_to(RAIZ.parent)
    # `__init__.py` puro-reexport tem zero linhas de lógica. Contar ele
    # como arquivo só porque existe é a armadilha que o prompt 08 avisa.
    texto = arquivo.read_text(encoding="utf-8")
    if caminho.name == "__init__.py" and not texto.strip():
        return
    chave = caminho.as_posix()
    n = len(texto.splitlines())
    limite_herdado = HERDADOS.get(chave)

    if n <= TETO_DE_LINHAS:
        # Encolheu para dentro do teto: a entrada em `HERDADOS` tem que sair
        # NESTE commit, senão o arquivo poderia voltar a crescer até o
        # limite antigo sem a catraca reclamar.
        assert limite_herdado is None, (
            f"{chave} baixou para {n} linhas e está dentro do teto "
            f"({TETO_DE_LINHAS}): REMOVA a entrada de `HERDADOS` neste "
            f"mesmo commit. Sair da lista é permanente — se o arquivo "
            f"voltar a passar do teto, ele reprova como arquivo novo."
        )
        return

    assert limite_herdado is not None, (
        f"{chave}: {n} linhas, acima do teto de {TETO_DE_LINHAS}. "
        f"Este arquivo NÃO está em `HERDADOS` — ou é novo, ou saiu da "
        f"lista e voltou a crescer. A catraca existe para impedir "
        f"exatamente isso. "
        f"Quebre-o por RESPONSABILIDADE (não por contagem de linhas) "
        f"antes de commitar. Se não houver costura, o arquivo não devia "
        f"ter chegado a este tamanho de uma vez: reveja o desenho. "
        f"Ver docs/decisoes/eslint-portado-para-python.md."
    )
    teto_individual = int(limite_herdado * MARGEM_DO_HERDADO)
    assert n <= teto_individual, (
        f"{chave}: {n} linhas — passou a margem. Tinha {limite_herdado} "
        f"em 05/09/2026, e o limite com {int((MARGEM_DO_HERDADO - 1) * 100)}% "
        f"de folga é {teto_individual} (+{n - teto_individual} além). "
        f"Crescimento normal de funcionalidade cabe na margem; consumir "
        f"ela inteira significa que este arquivo virou outro problema. "
        f"Divida-o em pacote de contexto (ver GATE 3: de 2 a 7 módulos, "
        f"120 a 800 linhas cada) antes de continuar crescendo."
    )

    with pytest.warns(UserWarning, match=re.escape(
            f"{caminho}: {n} linhas (teto {TETO_DE_LINHAS})")):
        warnings.warn(
            f"{caminho}: {n} linhas (teto {TETO_DE_LINHAS}). "
            f"Herdado de 05/09/2026, sem prazo (margem até "
            f"{teto_individual}). "
            f"Ver docs/decisoes/eslint-portado-para-python.md.",
            stacklevel=1,
        )


# ===========================================================================
# GATE 2 — `print()` SÓ EM SCRIPTS DE DIAGNÓSTICO
# ===========================================================================

def test_print_so_em_scripts_de_diagnostico():
    """`print()` em código de aplicação é o anti-log: sai no stdout do
    servidor, não tem `id_run`/`conta`/`fase`, e ninguém consegue
    correlacionar com `logs/dev/blazes-dev.jsonl`.

    A porta de saída de diagnóstico (scripts CLI, geradores) está em
    `EXCECOES_DE_PRINT`. Toda adição nova ali é decisão consciente,
    documentada na docstring acima do frozenset.

    A diferença para o T201 do ruff: o T201 é puramente sintático
    ("tem print, viola"). Este teste sabe o que é aplicação e o que
    é diagnóstico, e isola só o que importa.
    """
    # Regex só no nível de módulo. `print` dentro de string é `repr`,
    # e o nome da função `_salvar_print` de `core/quedas.py` também
    # não conta — começa com `_`. A regex exige `print(` no início
    # da linha OU após um caractere que não seja letra/`_`/dígito
    # (defensivo contra `repr(x.print)` hipotético).
    call = re.compile(r"(?<![\w.])print\(")
    violacoes: list[str] = []
    for arquivo in _todos_os_python(RAIZ):
        caminho = arquivo.relative_to(RAIZ.parent)
        caminho_str = str(caminho).replace("\\", "/")
        if caminho_str in EXCECOES_DE_PRINT:
            continue
        for n_linha, linha in enumerate(
                arquivo.read_text(encoding="utf-8").splitlines(), start=1):
            if call.search(linha):
                violacoes.append(f"{caminho_str}:{n_linha}: {linha.strip()}")
    if violacoes:
        lista = "\n  ".join(violacoes)
        with pytest.warns(UserWarning, match=re.escape(
                f"{len(violacoes)} `print()` em local proibido")):
            warnings.warn(
                f"{len(violacoes)} `print()` em local proibido. "
                f"Adicione o caminho a `EXCECOES_DE_PRINT` (decisão "
                f"documentada) ou troque por `logging`: \n  {lista}",
                stacklevel=1,
            )


# ===========================================================================
# GATE 3 — COESÃO DE CONTEXTO (o outro lado do teto de linhas)
# ===========================================================================
#
# POR QUE ESTE GATE EXISTE
# ------------------------
# O teto de 800 linhas resolve METADE do problema: impede o arquivo
# gigante. Sozinho, ele empurra para o defeito oposto — um contexto picado
# em 20 pedaços, que custa MAIS para navegar do que o arquivo grande
# custava. "Onde está a lógica da fada?" não pode ter como resposta "abre
# esses seis arquivos".
#
# Diretriz do usuário (05/09/2026), palavra por palavra:
#
#   "quando é referente a combate é importante que esteja agrupado, ou se
#    é referente a fada é bom que esteja em um lugar só, para eu como
#    desenvolvedor não precisar caçar em 500 arquivos diferentes"
#
# A FAIXA SAUDÁVEL DE UM CONTEXTO
# -------------------------------
# Um contexto tem UMA PORTA: ou um arquivo `X.py`, ou um pacote `X/` com
# fachada. E o pacote tem forma MEDIDA — a do `core/vision/`, que é o
# único split deste projeto que deu certo:
#
#     core/vision/   5 módulos, 1647 linhas, de 132 a 448, mediana 340
#
# Daí a faixa: 2 a 7 módulos, cada um entre 120 e 800 linhas. Nem
# monolito, nem picadinho. A faixa comporta a fila inteira: o maior
# arquivo do projeto (combate.py, 3735L) cabe em 5-6 módulos de ~650L.
#
# POR QUE `error` E NÃO `warn`
# ---------------------------
# Medido em 05/09/2026: ZERO violações. A fragmentação ainda não
# aconteceu, e essa é a única condição em que o passo 6 do toolkit permite
# `error` de saída. Instalar agora é de graça; instalar depois de 20
# fragmentos seria outra fila de dívida.

# Pastas que agrupam contextos DIFERENTES (namespaces) e por isso não
# respondem pela faixa: ninguém espera que `core/` seja um só assunto.
# Todo pacote que NÃO estiver aqui é PACOTE DE CONTEXTO — nasceu de
# dividir um assunto, e a faixa vale para ele.
NAMESPACES = frozenset({
    "blazesbot",
    "blazesbot/bot",
    "blazesbot/core",
    "blazesbot/tools",
    "blazesbot/bot/bc",
    "blazesbot/bot/app",
    "blazesbot/bot/hh",
})

PISO_DE_MODULO = 120
MIN_MODULOS_POR_CONTEXTO = 2
MAX_MODULOS_POR_CONTEXTO = 7

# Módulos que PODEM ser pequenos dentro de um pacote de contexto: são
# declaração, não lógica. Um arquivo só de constantes com 40 linhas não é
# fragmento — é o lugar certo das constantes.
MODULO_PEQUENO_LEGITIMO = ("_constantes", "_protocolo", "_tipos", "_estado")

# `X.py` com satélites `X_*.py` ao lado é um pacote fingindo não ser um
# pacote: para responder sobre o assunto é preciso abrir todos, e nenhum
# deles é a porta. Estes 5 são de antes da regra e avisam; grupo NOVO
# reprova.
PORTAS_DUPLAS_HERDADAS = frozenset({
    "blazesbot/bot/fada",          # fada.py + fada_montagem.py + fada_reviver.py
    "blazesbot/bot/login",         # login.py + login_states.py
    "blazesbot/bot/mural",         # mural.py + mural_da_morte.py
    "blazesbot/bot/app/afericao",  # afericao.py + afericao_do_aliado.py
    "blazesbot/core/janelas",      # janelas.py + janelas_abertas.py
})


def _pacotes_de_contexto() -> list[Path]:
    """Pastas que representam UM assunto — as que respondem pela faixa."""
    return sorted(
        d for d in RAIZ.rglob("*")
        if d.is_dir() and "__pycache__" not in d.parts
        and (d / "__init__.py").exists()
        and d.relative_to(RAIZ.parent).as_posix() not in NAMESPACES
    )


def _modulos(pacote: Path) -> list[Path]:
    return sorted(p for p in pacote.glob("*.py") if p.name != "__init__.py")


def _ids_de_pacote(d):
    return "-" if d is None else str(d.relative_to(RAIZ))


@pytest.mark.parametrize("pacote", _pacotes_de_contexto() or [None],
                         ids=_ids_de_pacote)
def test_pacote_de_contexto_nao_e_picadinho(pacote):
    """Pacote de contexto tem de 2 a 7 módulos — nem monolito, nem picadinho.

    Um pacote com 1 módulo não era para ser pacote: o arquivo bastava, e o
    pacote só acrescenta uma pasta para atravessar. Um pacote com mais de
    7 deixou de ser navegável — a pergunta "onde está X?" voltou a custar
    caro, que é exatamente o que o teto de linhas queria evitar.

    ESCAPE: contexto que honestamente precisa de mais de 7 pedaços não
    vira 12 irmãos — vira SUBPACOTES com nome de domínio
    (`combate/alvo/`, `combate/rotacao/`). Aí cada nível continua
    respondendo à pergunta num relance.
    """
    if pacote is None:
        pytest.skip("nenhum pacote de contexto ainda")
    mods = _modulos(pacote)
    nome = pacote.relative_to(RAIZ.parent).as_posix()
    assert len(mods) >= MIN_MODULOS_POR_CONTEXTO, (
        f"{nome}/ tem {len(mods)} módulo(s), abaixo de "
        f"{MIN_MODULOS_POR_CONTEXTO}. Pacote com um módulo só não se "
        f"justifica: o arquivo único bastava."
    )
    assert len(mods) <= MAX_MODULOS_POR_CONTEXTO, (
        f"{nome}/ tem {len(mods)} módulos, acima de "
        f"{MAX_MODULOS_POR_CONTEXTO}. O contexto foi PICADO, não dividido "
        f"— e a pergunta 'onde está X?' voltou a custar caro. Junte os "
        f"que respondem à mesma pergunta, ou crie subpacotes com nome de "
        f"domínio em vez de mais irmãos."
    )


@pytest.mark.parametrize("pacote", _pacotes_de_contexto() or [None],
                         ids=_ids_de_pacote)
def test_modulo_de_contexto_tem_massa(pacote):
    """Módulo dentro de pacote de contexto tem pelo menos 120 linhas.

    Abaixo disso quase nunca é uma responsabilidade: é pedaço de outra,
    separado por contagem de linhas em vez de por assunto. O custo de
    abrir um arquivo é FIXO e não depende do tamanho dele — dez arquivos
    de 60 linhas cobram dez aberturas para entregar o que um de 600
    entregaria em uma.

    ISENTOS: `_constantes`, `_protocolo`, `_tipos`, `_estado` — são
    declaração, não lógica, e o lugar certo delas é arquivo próprio por
    menor que seja.
    """
    if pacote is None:
        pytest.skip("nenhum pacote de contexto ainda")
    for m in _modulos(pacote):
        if any(k in m.name for k in MODULO_PEQUENO_LEGITIMO):
            continue
        n = len(m.read_text(encoding="utf-8").splitlines())
        assert n >= PISO_DE_MODULO, (
            f"{m.relative_to(RAIZ.parent).as_posix()}: {n} linhas, abaixo "
            f"do piso de {PISO_DE_MODULO}. Módulo pequeno demais é "
            f"fragmento, não responsabilidade. Funda com o irmão que "
            f"responde à mesma pergunta — ou, se for mesmo só declaração, "
            f"nomeie como tal ({', '.join(MODULO_PEQUENO_LEGITIMO)})."
        )


def test_um_contexto_uma_porta():
    """`X.py` com satélites `X_*.py` ao lado deveria ser o pacote `X/`.

    É o padrão que a diretriz de 05/09/2026 nomeia. Hoje, responder "onde
    está a lógica da fada?" custa abrir `fada.py`, `fada_montagem.py` e
    `fada_reviver.py` — três arquivos, nenhum deles a porta. Um pacote
    `fada/` com fachada responde num lugar só, SEM juntar tudo num arquivo
    gigante: é o meio-termo entre os dois defeitos.

    Os 5 grupos de antes da regra avisam; grupo NOVO reprova.
    """
    from collections import defaultdict
    achados = []
    for d in sorted({p.parent for p in _todos_os_python(RAIZ)}):
        por_prefixo = defaultdict(list)
        for p in sorted(d.glob("*.py")):
            if p.name == "__init__.py":
                continue
            por_prefixo[p.stem.split("_")[0]].append(p)
        for pref, membros in sorted(por_prefixo.items()):
            if (d / f"{pref}.py").exists() and len(membros) >= 2:
                achados.append(((d / pref).relative_to(RAIZ.parent).as_posix(),
                                [m.name for m in membros]))

    novos = [(k, v) for k, v in achados if k not in PORTAS_DUPLAS_HERDADAS]
    assert not novos, (
        "Contexto novo espalhado em irmãos `X.py` + `X_*.py`: "
        + "; ".join(f"{k} -> {v}" for k, v in novos)
        + ". Faça um pacote com o nome do contexto e uma fachada no "
        "`__init__.py`. Vale a faixa do GATE 3: de 2 a 7 módulos, cada um "
        "com 120 a 800 linhas."
    )

    for k, v in achados:
        with pytest.warns(UserWarning, match=re.escape(k)):
            warnings.warn(
                f"{k}: contexto espalhado em {len(v)} irmãos "
                f"({', '.join(v)}). Herdado de 05/09/2026, sem prazo — "
                f"vira pacote quando alguém mexer nele de qualquer forma.",
                stacklevel=1,
            )
