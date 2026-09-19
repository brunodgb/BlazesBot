"""A janela Editar: exclusividade das funções, tooltip e altura das abas.

Refatoração pedida em 06/09/2026, com o council consultado antes de escrever
código. O que estes testes travam, e o defeito real de cada um:

1. **AS TRÊS FUNÇÕES SÃO MUTUAMENTE EXCLUSIVAS.** Eram três escritas
   independentes, e a exclusividade era uma PRECEDÊNCIA IMPLÍCITA no laço do
   supervisor -- com BC e APP marcados rodava o APP e o BC ficava "ligado e
   ignorado", com a tela mostrando dois selos acesos para uma conta que fazia
   uma coisa só.
2. **O TOOLTIP SOMAVA A POSIÇÃO DA JANELA NA TELA** a coordenadas de viewport,
   num elemento `position: fixed` -- ele era criado, preenchido e mostrado FORA
   da área visível. Não era falta de binding: os ouvintes sempre estiveram
   certos.
3. **ALTURA POR NÚMERO MÁGICO.** O painel tinha `max-height: calc(90vh - 160px)`,
   um chute da soma de cabeçalho + abas + rodapé (medido: ~153px).

Ver `docs/decisoes/interface.md`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from blazesbot.config import Account, BotConfig

RAIZ = Path(__file__).resolve().parents[1]
JS = (RAIZ / "web" / "main.js").read_text(encoding="utf-8")
CSS = (RAIZ / "web" / "style.css").read_text(encoding="utf-8")
HTML = (RAIZ / "web" / "index.html").read_text(encoding="utf-8")
PONTE = (RAIZ / "blazesbot" / "web_app.py").read_text(encoding="utf-8")
GUI = (RAIZ / "blazesbot" / "gui" / "main_window.py").read_text(encoding="utf-8")


def _sem_comentarios(texto: str, marca: str) -> str:
    """O texto sem as linhas de comentário.

    Os comentários deste projeto CITAM o defeito que consertaram -- e é o
    comentário que impede alguém de reintroduzi-lo sem saber por quê. Buscar a
    citação no arquivo inteiro reprovaria justamente a documentação.
    """
    return "\n".join(l for l in texto.splitlines()
                     if not l.lstrip().startswith(marca))


def _conta(login: str, bc: bool = False, hh: bool = False,
           app: bool = False) -> Account:
    c = Account(login=login, bc_farm=bc, hh_farm=hh)
    c.settings.app.enabled = app
    return c


# -- 1. uma função por conta ------------------------------------------------

def test_ligar_uma_funcao_DESLIGA_as_outras():
    cfg = BotConfig()
    cfg.accounts = [_conta("x", bc=True)]
    c = cfg.accounts[0]
    for pedida, esperado in (("hh", "hh"), ("app", "app"),
                             ("bc", "bc"), ("", "")):
        assert cfg.definir_funcao_da_conta(c, pedida) == esperado
        ligadas = [n for n, v in (("bc", c.bc_farm), ("hh", c.hh_farm),
                                  ("app", c.settings.app.enabled)) if v]
        assert ligadas == ([esperado] if esperado else []), (pedida, ligadas)


def test_config_ANTIGO_com_duas_marcadas_sobe_corrigido():
    """Duas marcadas é configuração INVÁLIDA a partir de 06/09/2026, não algo
    para o laço resolver em silêncio a cada ciclo.

    O critério é a precedência LEGADA (app > hh > bc) -- a que o supervisor já
    praticava, para o bot continuar fazendo exatamente o que fazia.
    """
    cfg = BotConfig.from_dict({"accounts": [
        {"login": "a", "bc_farm": True, "hh_farm": True},
        {"login": "b", "bc_farm": True, "settings": {"app": {"enabled": True}}},
    ]})
    assert cfg.funcao_ativa_da_conta(cfg.accounts[0]) == "hh"
    assert cfg.funcao_ativa_da_conta(cfg.accounts[1]) == "app"
    for c in cfg.accounts:
        ligadas = sum((c.bc_farm, c.hh_farm, c.settings.app.enabled))
        assert ligadas == 1, c.login


def test_funcao_desconhecida_e_RECUSADA():
    """Erro de digitação na ponte não pode desligar as três em silêncio."""
    cfg = BotConfig()
    cfg.accounts = [_conta("x", bc=True)]
    try:
        cfg.definir_funcao_da_conta(cfg.accounts[0], "farm")
    except ValueError:
        pass
    else:
        raise AssertionError("aceitou função inexistente")
    assert cfg.accounts[0].bc_farm, "recusou e ainda desligou o que estava certo"


def test_a_escrita_tem_UM_ponto_so():
    """Três `alternar_*` independentes eram exatamente o que deixava duas
    ligadas: em duas chamadas ("desliga BC", "liga HH") existe um instante com
    as duas, e o supervisor lê os campos a cada volta."""
    for antigo in ("def alternar_farm", "def alternar_hh", "def alternar_app"):
        assert antigo not in PONTE, f"{antigo} voltou"
    assert "def definir_funcao" in PONTE
    assert "definir_funcao_da_conta" in PONTE
    # E a GUI usa o MESMO ponto de escrita.
    assert "_trocar_funcao" in GUI
    assert "definir_funcao_da_conta" in GUI
    for antigo in ("def _toggle_farm", "def _toggle_hh", "def _toggle_app"):
        assert antigo not in GUI, f"{antigo} voltou"


def test_o_controle_da_tela_e_RADIO():
    """Caixa comunica semântica falsa -- sugere que a combinação é válida."""
    assert 'cx.type = "radio"' in JS
    assert "cx.name = `funcao-${c.uid}`" in JS, (
        "sem `name` por conta, os grupos de rádio se misturam entre linhas")
    # Clicar no que já está ligado desliga: "nenhuma função" é estado válido.
    assert 'definirFuncao(tr.dataset.uid, "")' in JS


def test_o_espelho_ao_vivo_tambem_e_exclusivo():
    """Ele corrigia BC e HH de forma independente, e com rádio isso
    reintroduzia a função antiga a cada poll de 1,5 s -- medido na tela."""
    bloco = JS.split("function marcarNoAr(est)")[1].split("\n}")[0]
    assert "const ativa = c.funcao" in bloco
    assert "cx.dataset.acao === ativa" in bloco


def test_a_troca_com_o_bot_rodando_AVISA_o_custo():
    """Trocar no meio de uma run da cave perde aquela run (teleporte gasto,
    boss vivo). Bloquear seria tirar uma função que o usuário usa; avisar deixa
    a decisão com ele."""
    assert "volta em andamento é perdida" in " ".join(PONTE.split())
    assert "volta em andamento é" in " ".join(GUI.split())


# -- 2. o tooltip -----------------------------------------------------------

def test_o_tooltip_NAO_soma_a_posicao_da_janela():
    """ESTE era o defeito: `getBoundingClientRect()` já é relativo ao viewport, e
    o balão é `position: fixed`. Somar `screenX`/`screenY` o jogava para fora da
    área visível -- ele existia, preenchido e visível, em lugar nenhum."""
    bloco = JS.split("function mostrarAjuda(icone)")[1].split("\nfunction ")[0]
    codigo = _sem_comentarios(bloco, "//")
    for proibido in ("window.screenX", "window.screenY",
                     "window.screenLeft", "window.screenTop"):
        assert proibido not in codigo, f"{proibido} voltou ao posicionamento"
    # Grampeia nas quatro bordas: a janela é travada em 1200x800 e o campo da
    # borda é caso real, não hipótese.
    assert "const grampo = (v, min, max)" in bloco
    assert "window.innerWidth" in bloco and "window.innerHeight" in bloco


def test_o_tooltip_nao_pisca_e_fecha_limpo():
    """Sem atraso no fechar, atravessar dois ícones vizinhos apaga e reacende o
    balão a cada pixel."""
    assert "clearTimeout(esconderAjuda._t)" in JS
    assert "esconderAjuda._t = setTimeout" in JS
    # Movimento DENTRO do próprio ícone não é saída.
    assert "!icone.contains(e.relatedTarget)" in JS


def test_o_tooltip_responde_ao_TECLADO():
    """Só no mouse, a ajuda não existe para quem navega por Tab."""
    assert 'document.addEventListener("focusin"' in JS
    depois = JS[JS.index("function esconderAjuda()"):]
    assert "mostrarAjuda(icone)" in depois.split("captura de tecla")[0]


# -- 3. altura e layout -----------------------------------------------------

def test_a_altura_do_painel_NAO_e_numero_magico():
    """Era `calc(90vh - 160px)`, e 160 era um chute da soma de cabeçalho + abas
    + rodapé (medido: ~153px). Número mágico que mente assim que qualquer uma
    das três barras muda de altura. O flex resolve sozinho."""
    declaracoes = [l for l in CSS.splitlines() if "max-height:" in l]
    assert not any("calc(" in l for l in declaracoes), declaracoes
    bloco = CSS.split(".painel-aba {")[1].split("}")[0]
    assert "flex: 1;" in bloco
    assert "min-height: 0;" in bloco, (
        "sem isto o `overflow-y: auto` falha dentro de flex")


def test_a_tecla_tem_O_MESMO_FORMATO_dos_outros_campos():
    """Rótulo EM CIMA, como as cinco abas inteiras. A primeira tentativa pôs
    rótulo e campo lado a lado para cortar altura -- cortava (410px contra
    469px) e ainda assim causava estranheza, porque era a única aba do modal com
    outro formato. A altura volta pela COLUNA: 118px são 7 colunas em vez de 4.
    Medido: 528px de conteúdo num painel de 565px, sem rolar."""
    bloco = CSS.split(".grade-teclas {")[1].split("}")[0]
    assert "minmax(118px" in bloco
    assert ".grade-teclas .campo {" not in CSS, (
        "o campo de tecla usa o `.campo` padrão -- é esse o ponto")
    rotulo = CSS.split(".grade-teclas .campo > .rotulo,")[1].split("}")[0]
    assert "truncate" in rotulo and "whitespace-nowrap" in rotulo
    assert "font: inherit" not in CSS.split(".grade-teclas")[1][:600], (
        "o rótulo da tecla usa a tipografia dos outros campos")


def test_cabecalho_e_rodape_do_modal_ficam_FIXOS():
    """Salvar e Cancelar têm de estar acessíveis em qualquer aba."""
    modal = HTML.split('id="modal-editor"')[1]
    modal = modal.split("Modal de confirma")[0]
    assert modal.count("shrink-0") >= 3, (
        "cabeçalho, abas e rodapé precisam de shrink-0")
    inicio = modal.index("btn-cancelar-modal")
    assert "shrink-0" in modal[max(0, inicio - 400):inicio]


def test_o_placeholder_de_tecla_e_CURTO():
    """"não usar tecla" truncava para "NÃO USAR TE..." no campo estreito -- uma
    frase onde cabe um símbolo, e truncada não informava nada."""
    assert 'placeholder="não usar tecla"' not in HTML
    assert 'placeholder="(sem atalho padrão)"' not in HTML
    assert HTML.count('placeholder="—"') >= 28, (
        "os campos de tecla usam o travessão, com o `title` explicando")


def test_o_ICONE_DE_AJUDA_nao_gasta_uma_linha():
    """`.campo` é `flex-col`: com o "?" como terceiro filho ele caía ABAIXO do
    input -- uma linha inteira por campo (medido: a aba HH transbordava 22px e
    passou a ter 78px de folga) e um símbolo solto, longe do rótulo."""
    bloco = CSS.split(".campo > .ajuda {")[1].split("}")[0]
    assert "absolute" in bloco
    assert ".campo:has(> .ajuda)" in CSS, "sem `relative` o âncora é o modal"


def test_o_ROTULO_tem_UMA_tipografia_no_modal_INTEIRO():
    """`font: inherit` no `.rotulo` deixava campo com ajuda ("Grupo") em
    tipografia diferente de LOGIN/SENHA, lado a lado na mesma grade. Depois de
    a grade de teclas voltar ao rótulo em cima, não sobrou nenhum lugar onde a
    exceção se justifique."""
    assert "font: inherit" not in CSS.split(".campo>.rotulo {")[1].split("}")[0]
    for solto in ('<label class="campo">HP alvo (%)',
                  '<label class="campo">AoE até mana (%)'):
        assert solto not in HTML, f"rótulo solto voltou: {solto}"


def test_o_ROTULO_DA_TECLA_e_um_elemento_de_verdade():
    """Era NÓ DE TEXTO SOLTO -- e nó de texto não é selecionável em CSS: o
    rótulo da tecla não recebia estilo nenhum, e a grade não tinha como alinhar
    nem truncar. Embrulhado em `.rotulo`, ele é o mesmo rótulo dos outros
    campos."""
    soltos = re.findall(
        r'<label class="campo[^"]*">[^<\s][^<]*?<input class="captura', HTML)
    assert not soltos, soltos


def test_clicar_na_funcao_LIGADA_desliga():
    """"Nenhuma função" é estado válido: a conta sobe, loga, reloga e não faz
    mais nada. Rádio nativo não desmarca sozinho, e no rádio já marcado o
    `change` também não dispara -- sem tratamento próprio não havia como voltar
    a esse estado pela tabela.

    QUEM DESLIGA É O `click`, NÃO O `mousedown` -- e isto é o conserto de
    08/09/2026, depois de o defeito VOLTAR na mão do usuário. Desligar no
    mousedown era uma corrida perdida: `preventDefault()` ali não impede o
    `<label>` de ativar o rádio no click seguinte. A sequência medida na trilha
    de eventos era

        mousedown (desliga) -> click no span -> click no rádio -> change (RELIGA)

    e só não religava quando `carregarContas()` respondia rápido o bastante para
    recriar a linha antes do click. Passou no teste de tela e falhou em uso real
    -- por isso o teste agora olha O EVENTO, não só a existência do tratamento.

    O clique tem de ser resolvido A PARTIR DO SELO: o rádio é escondido
    (`position: absolute; opacity: 0`) e quem recebe o clique é o `<span>` ao
    lado dele, DENTRO do mesmo `<label>` -- procurar `.selo-caixa` a partir do
    alvo não achava nada, porque são IRMÃOS, não ancestral.
    """
    # `#corpo-contas` tem MAIS DE UM listener de click (o outro seleciona a
    # linha), então o bloco se acha pelo que ele faz, não pela ordem.
    corpo = next(
        b.split("\n});")[0]
        for b in JS.split('$("#corpo-contas").addEventListener("click"')[1:]
        if "jaLigado" in b.split("\n});")[0])
    assert 'closest(".selo")' in corpo
    assert "e.preventDefault()" in corpo, (
        "sem `preventDefault` no CLICK, o label religa o rádio")
    assert 'definirFuncao(tr.dataset.uid, "")' in corpo

    # O mousedown continua existindo, mas SÓ para anotar: no click o rádio já
    # pode ter mudado de estado e não daria mais para saber se estava ligado.
    md = JS.split('$("#corpo-contas").addEventListener("mousedown"')[1]
    md = md.split("\n});")[0]
    assert "dataset.jaLigado" in md
    assert "definirFuncao" not in md, (
        "desligar no mousedown é a corrida que trouxe o defeito de volta")
    assert "jaLigado" in corpo, "o click precisa do que o mousedown anotou"

    # A GUI tem o mesmo estado: desmarcar a caixa manda `""`.
    assert 'pedida = qual if caixas[qual].isChecked() else ""' in GUI


def test_a_dica_das_funcoes_diz_a_REGRA():
    """A dica ensinava "Marcada junto com BC, roda a HH" -- a combinação que
    deixou de existir. Três selos não deixam adivinhar nem que a escolha é
    exclusiva, nem que clicar na ligada desliga.

    A Web passou a ler a dica do dicionário de i18n (`dica_troca_funcao_1`);
    a GUI PyQt6 continua com o texto literal -- ver `docs/SKILLS.md`, seção
    "i18n", sobre a GUI ainda não ter sido convertida."""
    assert "Marcada junto com BC" not in GUI
    assert "Uma função por conta" in GUI

    assert "Marcada junto com BC" not in JS
    assert 't("dica_troca_funcao_1")' in JS
    traducoes = json.loads(
        (RAIZ / "blazesbot" / "locales" / "traducoes.json").read_text(encoding="utf-8"))
    assert traducoes["dica_troca_funcao_1"]["pt-br"] == \
        "Uma função por conta: marcar esta desliga a outra."


def test_a_lista_do_time_NAO_remonta_a_regra():
    """A tela decidia o motivo a partir de três campos soltos (`farmando_bc`,
    `farmando_hh`, `lider_de_outro`) -- dois lugares decidindo a mesma coisa, e
    no dia de uma quarta função só um deles saberia dela. O backend manda o
    motivo pronto e a lista já filtrada."""
    codigo = _sem_comentarios(JS, "//")
    for antigo in ("farmando_bc", "farmando_hh", "lider_de_outro"):
        assert antigo not in codigo, f"{antigo} voltou para a tela"
    assert "contas_do_time_ocultas" in JS and "contas_do_time_ocultas" in PONTE
    assert "def _candidatas_do_time" in PONTE
    # Quem está no time e ficou inelegível NÃO é travado: é assim que dá para
    # tirar. Travar e desmarcar era o que apagava o login ao salvar.
    bloco = JS.split("function montarListaDoTime(")[1].split("\nfunction ")[0]
    assert "cx.disabled = true" not in bloco
    assert "cx.checked = false" not in bloco


def test_a_confirmacao_fica_POR_CIMA_de_qualquer_outra_camada():
    """Empate de `z-index` é decidido pela ordem no HTML — e isso é silencioso.

    MEDIDO em 19/09/2026: `#modal-confirmar` e `#modal-lixo` tinham os dois
    `z-index: 100` da `.modal-mascara`. A janela dos itens entrou depois no
    `index.html`, então a pergunta "descartar as alterações?" aparecia ATRÁS
    dela — invisível, e sem como ser respondida. O Cancelar da janela virava um
    beco sem saída.

    A confirmação BLOQUEIA: ela existe para ser respondida antes de qualquer
    outra coisa, então tem de estar acima de toda camada declarada no arquivo.
    """
    import re

    bloco = CSS.split("#modal-confirmar {")[1].split("}")[0]
    da_confirmacao = int(re.search(r"z-index:\s*(\d+)", bloco).group(1))
    todos = [int(n) for n in re.findall(r"z-index:\s*(\d+)", CSS)]

    assert da_confirmacao == max(todos), (
        f"a confirmação está em {da_confirmacao} e existe camada em "
        f"{max(todos)} — ela pode ficar atrás e travar quem a abriu")
    assert todos.count(da_confirmacao) == 1, (
        "outra camada empatou com a confirmação; no empate quem vence é quem "
        "vem depois no HTML, que é exatamente o defeito de 19/09/2026")


def test_a_busca_dos_itens_casa_TERMO_A_TERMO():
    """"robe 68" tem de achar "Robe Wizz lvl68" -- e são seis, um por classe.

    MEDIDO em 19/09/2026: a busca comparava a FRASE inteira, então quem
    digitava "robe 68" via "Nenhum item com esse filtro" e concluía que os
    itens não existiam. A classe vem no meio do rótulo, e quem busca não tem
    como saber disso.

    O nome do arquivo entra no alvo junto com o rótulo: ele saiu do cartão, mas
    continua sendo por onde o dicionário de rótulos é editado.
    """
    bloco = JS.split("function lixoVisiveis()")[1].split("\n}")[0]

    assert r"split(/\s+/)" in bloco, "a busca voltou a comparar a frase inteira"
    assert ".every(" in bloco, "algum termo deixou de ser obrigatório"
    assert "item.arquivo" in bloco, "a busca parou de olhar o nome do arquivo"


def test_lvl60_na_busca_traz_a_FAIXA_60_a_69():
    """Nenhum item se chama "lvl60": eles são lvl63, lvl65, lvl68.

    O nível destes modelos é dezena + unidade, com a DEZENA valendo o tier e a
    unidade valendo a peça (`Sin63` = tier 6, armguard). Por isso "todos os do
    60" é a busca natural do usuário -- e era impossível por texto.

    `lvl6` NÃO vira faixa de propósito: ele continua sendo busca de texto, que
    casa com "Belt lvl6" e com "lvl63". Adivinhar ali tiraria do usuário a
    busca exata que ele já tinha.
    """
    assert "function lixoCasaNaFaixa(" in JS
    bloco = JS.split("function lixoCasaNaFaixa(")[1].split("\n}")[0]

    assert r"/^lvl(\d*)0$/" in bloco, (
        "a forma da faixa mudou; `lvl0` (tier baixo) depende do `*`")
    assert "base + 9" in bloco, "a faixa deixou de ser a dezena inteira"
    assert "lixoCasaNaFaixa(alvo, termo)" in JS, (
        "a busca parou de consultar a faixa")
