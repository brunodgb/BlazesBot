"""A tela de contas: coluna Função, estados da linha e alvos de clique.

Reformulação pedida em 28/08/2026: *"ele deve bater o olho e identificar
instantaneamente qual conta está rodando, em qual ecossistema (APP, BC, HH) e
quais são as divisões lógicas da interface"*.

O que estes testes travam, e o defeito real que cada um teve atrás:

1. **O `colspan` do cabeçalho de grupo tem de cobrir a tabela inteira.** Já saiu
   de sincronia uma vez: a coluna HH entrou e a constante ficou em 9 com 10
   colunas -- e `colspan` errado não avisa ninguém.
2. **UMA coluna Função, não três de caixa.** O que distinguia BC de HH de APP
   estava no `<th>`, fora da linha.
3. **A caixa nativa continua lá.** Trocar por `<button>` custaria reimplementar
   teclado e leitor de tela, e é onde esse tipo de reforma quebra acessibilidade
   sem ninguém notar.
4. **Os quatro estados da linha usam canais diferentes.** Eles coexistem.

Ver `docs/decisoes/interface.md`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
HTML = (RAIZ / "web" / "index.html").read_text(encoding="utf-8")
JS = (RAIZ / "web" / "main.js").read_text(encoding="utf-8")
CSS = (RAIZ / "web" / "style.css").read_text(encoding="utf-8")


def _colunas_do_thead() -> list[str]:
    """As colunas da tabela de contas, na ordem."""
    tabela = HTML.split('id="corpo-contas"')[0]
    cabecalho = tabela.rsplit("<thead>", 1)[1]
    return re.findall(r"<th[^>]*>(.*?)</th>", cabecalho, re.S)


# -- 1. o colspan não pode sair de sincronia de novo -----------------------

def test_o_colspan_do_grupo_cobre_a_tabela_inteira():
    """Já quebrou: a coluna HH entrou e a constante ficou para trás. Um
    `colspan` curto não dá erro -- só deixa o cabeçalho torto em silêncio."""
    declarado = int(
        re.search(r"const COLUNAS_DA_TABELA_DE_CONTAS = (\d+);", JS).group(1))
    assert declarado == len(_colunas_do_thead()), (
        f"a constante diz {declarado} e o thead tem "
        f"{len(_colunas_do_thead())} colunas")


def test_a_ordem_das_colunas_e_a_esperada():
    """A célula é montada por uma lista fixa; se o thead mudar de ordem sem ela,
    o dado aparece sob o rótulo errado -- e ninguém percebe olhando."""
    rotulos = [re.sub(r"<[^>]+>", "", c).strip() for c in _colunas_do_thead()]
    assert rotulos == ["", "Ativa", "Login", "Senha", "Run",
                       "Servidor", "Posição", "Função", "Editar"], rotulos
    assert ("[tdAlca, tdAtiva, tdLogin, tdSenha, tdRun, tdServ, tdPos, "
            "tdFuncao, tdEdit]") in JS


# -- 2. os três ecossistemas, numa coluna só -------------------------------

def test_os_tres_ecossistemas_estao_declarados_num_lugar_so():
    # Virou função (não const): os títulos dependem do idioma atual e precisam
    # ser recalculados a cada render -- ver `ecossistemas()` em web/main.js.
    assert "function ecossistemas() {" in JS
    for acao in ("bc", "hh", "app"):
        assert f'acao: "{acao}"' in JS, acao
    for campo in ("bc_farm", "hh_farm", "app_enabled"):
        assert f'campo: "{campo}"' in JS, campo


def test_o_selo_e_SO_A_SIGLA():
    """O pictograma saiu (06/09/2026): quem removia a ambiguidade entre BC e HH
    sempre foi a SIGLA -- dois pictogramas de caverna não se distinguem a 16px.
    Tirar o desenho devolveu ~18px por selo, que é o que faz esta coluna aguentar
    a quarta função sem espremer o resto da tabela."""
    for sigla in ("BC", "HH", "APP"):
        assert f'sigla: "{sigla}"' in JS, sigla
    assert ".selo-sigla" in CSS
    assert "icone:" not in JS, "o pictograma voltou; ele custa ~18px por selo"
    assert ".selo-icone" not in CSS


def test_o_selo_cabe_em_mais_funcoes():
    """O usuário avisou que virão mais funções. Um selo largo hoje é uma coluna
    espremida amanhã: `padding` lateral e altura ficam travados no compacto."""
    bloco = CSS.split("\n  .selo {")[1].split("}")[0]
    padding = re.search(r"padding: 0 (\d+)px", bloco)
    altura = re.search(r"height: (\d+)px", bloco)
    assert padding and int(padding.group(1)) <= 5, bloco
    assert altura and int(altura.group(1)) <= 22, bloco


def test_NAO_existem_mais_tres_colunas_de_caixa():
    rotulos = [re.sub(r"<[^>]+>", "", c).strip() for c in _colunas_do_thead()]
    for antigo in ("BC", "HH", "APP"):
        assert antigo not in rotulos, (
            f"'{antigo}' voltou a ser coluna; o rótulo tem de ficar DENTRO do "
            "controle, não no cabeçalho")


# -- 3. a caixa nativa continua lá, e alcançável ---------------------------

def test_o_selo_usa_CHECKBOX_NATIVO_escondido():
    """`display: none` tiraria a caixa da ordem de foco e mataria o teclado."""
    assert 'cx.type = "checkbox"' in JS
    bloco = CSS.split(".selo-caixa {")[1].split("}")[0]
    assert "position: absolute" in bloco
    assert "opacity: 0" in bloco
    assert "display: none" not in bloco, (
        "tiraria a caixa do Tab -- o selo deixaria de ser operável por teclado")
    # E o foco de teclado precisa aparecer, já que a caixa está invisível.
    assert ".selo:has(.selo-caixa:focus-visible)" in CSS


def test_o_alvo_de_clique_tem_pelo_menos_24px():
    """Eram 14x14 -- metade do mínimo da WCAG 2.5.8 -- e havia quatro por linha.
    Era o defeito mais objetivo da tela."""
    bloco = CSS.split(".alvo-caixa {")[1].split("}")[0]
    largura = int(re.search(r"width: (\d+)px", bloco).group(1))
    altura = int(re.search(r"height: (\d+)px", bloco).group(1))
    assert largura >= 24 and altura >= 24, (largura, altura)


# -- 4. quatro estados, quatro canais --------------------------------------

def test_os_estados_da_linha_usam_canais_DIFERENTES():
    """Eles coexistem: uma conta pode estar selecionada, ativa e rodando ao mesmo
    tempo. Se dois usarem o mesmo recurso visual, um esconde o outro."""
    # selecionada -> borda; inativa -> opacidade; no ar -> ponto próprio.
    assert "box-shadow: inset 3px 0 0 var(--accent)" in CSS   # selecionada
    assert ".tabela tbody tr.linha-inativa {" in CSS
    assert "opacity: 0.45" in CSS.split("tr.linha-inativa {")[1].split("}")[0]
    assert ".conta-ao-vivo::before" in CSS                    # no ar
    assert 'tr.classList.toggle("linha-no-ar"' in JS


def test_a_zebra_continua_PROIBIDA_na_tabela_de_contas():
    """A faixa alternada consumiria o FUNDO, que é o canal de "selecionada"."""
    assert "tabela tbody tr:nth-child" not in CSS


def test_o_indicador_de_no_ar_vem_do_estado_e_nao_do_disco():
    """`estado().contas` só traz conta EM EXECUÇÃO. O dado já chegava no
    navegador e era jogado fora -- a tabela só o usava para espelhar duas
    caixas."""
    assert "function marcarNoAr(est)" in JS
    assert '"uid": conta.garantir_uid() if conta else ""' in (
        RAIZ / "blazesbot" / "web_app.py").read_text(encoding="utf-8")


def test_a_contagem_de_RUNS_e_so_de_CAVE():
    """*"o APP nao deve aparecer a quantidade de runs pois nao faz sentido"* —
    usuário, 28/08/2026.

    O modo APP é macro de teclado: não existe "run" ali, e um número na coluna
    seria inventar uma medida que o ecossistema não tem. Conta parada mostra
    VAZIO e não zero -- zero diria "rodou e não fechou nenhuma", que é outra
    coisa.
    """
    bloco = JS.split("function marcarNoAr(est)")[1].split("\n}")[0]
    assert "const cave = !!c && (c.farm || c.farm_hh);" in bloco
    assert 'cel.textContent = cave ? String(runs) : "";' in bloco


def test_o_ponto_de_NO_AR_vale_para_qualquer_ecossistema():
    """"Está no ar" e "quantas runs fez" são perguntas diferentes: juntá-las
    deixava a conta de APP sem indicador nenhum. O ponto fica no login e não
    depende de cave; só a contagem depende."""
    bloco = JS.split("function marcarNoAr(est)")[1].split("\n}")[0]
    ponto = bloco.split('data-papel="ao-vivo"')[1].split(";")[0]
    assert "farm" not in ponto, "o ponto voltou a depender de cave"
    assert 'marca.classList.toggle("parada", !c)' in bloco
    # Classe PRÓPRIA: a `.escondida` global é `display: none !important` e faria
    # o slot sumir, deslocando o nome da conta 15px ao entrar no ar.
    assert '.conta-ao-vivo.parada {' in CSS
    assert "visibility: hidden" in CSS.split(".conta-ao-vivo.parada {")[1].split("}")[0]


def test_conta_ativa_sem_ecossistema_e_declarada():
    """Quatro das sete contas reais estão nesse estado: sobem, logam e não fazem
    mais nada. Antes tinham o mesmo peso visual de quem trabalha."""
    assert 'selos.classList.add("selos-so-login")' in JS
    assert 'content: "só login"' in CSS


def test_a_SEGUIDORA_de_time_NAO_e_chamada_de_so_login():
    """*"caso alguma conta de APP esteja ativa por causa do lider, é bom também
    mostrar visualmente que ela esta ativa e não o 'só login'"* — 06/09/2026.

    A seguidora roda a macro do líder e MESMO ASSIM tem as três caixas vazias:
    quem liga `AppConfig.enabled` é o líder, e o time dela própria é ignorado
    (`docs/INVARIANTES.md`, "Time do APP"). Chamar isso de "só login" era mentira.
    """
    assert '"lider_do_time": lideres.get(' in (
        RAIZ / "blazesbot" / "web_app.py").read_text(encoding="utf-8")
    assert "const lider = (c.lider_do_time" in JS
    assert "if (!algumLigado && lider) {" in JS
    assert "} else if (!algumLigado) {" in JS, (
        "'só login' tem de ficar no ELSE: com líder, a conta está trabalhando")
    assert ".selo-seguindo {" in CSS


def test_o_ponto_fica_VERMELHO_quando_a_conta_caiu():
    """*"o ponto verde, fica vermelho se a conta estiver offline? tipo a conta
    caiu, mas esta em relogin"* — 06/09/2026.

    O ponto era verde só por a conta estar na LISTA do resumo -- e a conta que
    caiu continua nela, por minutos, tentando religar. Ele dizia "no ar" com o
    personagem fora do jogo. Quem responde de verdade é `hwnd`: é ele que morre
    junto com a sessão.
    """
    sup = (RAIZ / "blazesbot" / "bot" / "supervisor.py").read_text(encoding="utf-8")
    assert '"conectada": _janela_viva(sup.hwnd),' in sup
    assert '"relogando": bool(not sup.hwnd' in sup

    bloco = JS.split("function marcarNoAr(est)")[1].split("\n}")[0]
    assert "const caida = !!c && !c.conectada;" in bloco
    assert 'marca.classList.toggle("caida", caida);' in bloco
    # A dica virou chave de i18n (`dica_reconectando`); o que este teste
    # protege continua o mesmo: a dica tem de dizer QUE relogin é.
    assert 't("dica_reconectando"' in bloco
    traducoes = json.loads(
        (RAIZ / "blazesbot" / "locales" / "traducoes.json").read_text(encoding="utf-8"))
    assert "relogin #" in traducoes["dica_reconectando"]["pt-br"], \
        "a dica tem de dizer QUE relogin é"

    # Cor NÃO pode ser o único sinal: daltonismo vermelho-verde é o mais comum.
    caida = CSS.split(".conta-ao-vivo.caida::before {")[1].split("}")[0]
    assert "var(--color-err)" in caida
    assert "animation-duration" in caida, (
        "sem um segundo canal, quem não distingue vermelho de verde não vê nada")


def test_o_ponto_tem_NOME_ACESSIVEL():
    """Achado da revisão: o estado era dito por COR e por `title`, e nenhum dos
    dois chega a um leitor de tela -- tooltip não é nome acessível."""
    bloco = JS.split("function marcarNoAr(est)")[1].split("\n}")[0]
    assert 'marca.setAttribute("aria-label", dica)' in bloco
    assert 'marca.setAttribute("aria-hidden"' in bloco, (
        "sem ponto, o elemento tem de sumir para o leitor em vez de virar ruído")
    assert 'aoVivo.setAttribute("role", "img")' in JS


def test_a_CADEIA_de_lideres_nao_produz_lider_falso():
    """Achado da revisão: com C liderando A e A liderando B, a consulta direta
    devolvia "A" para B -- mas a lista de A é IGNORADA enquanto ela é seguidora
    de C, então B não está em time nenhum e "segue A" seria mentira."""
    from blazesbot.config import Account, BotConfig

    def conta(login, segue=(), app=True):
        c = Account(login=login)
        c.settings.app.time_logins = list(segue)
        c.settings.app.enabled = app
        return c

    cfg = BotConfig()
    cfg.accounts = [conta("C", ["A"]), conta("A", ["B"]), conta("B")]
    mapa = cfg.lideres_do_time_do_app()
    assert mapa == {"a": "C"}, mapa


def test_lider_com_o_APP_DESLIGADO_nao_puxa_ninguem():
    """Pedido do usuário em 08/09/2026, olhando a tela: *"esse 'segue...' só
    deve aparecer se o líder estiver com o APP ativo (...) já que eu também
    posso ativar individualmente e posso estar com o APP inativo do líder"*.

    É a MESMA condição que o supervisor exige para convocar
    (`_SupervisorDaConta._lider_do_time`, item 2): com o modo APP do líder
    desmarcado ninguém é convocado, a seguidora fica só no login -- e era isso
    que a tabela contava errado. Montar o time é uma coisa; o time estar VALENDO
    é outra, e a lista guardada sozinha não distingue as duas.

    A lista NÃO é apagada quando o líder desliga (`docs/INVARIANTES.md`: "sair
    do time por `bc_farm` não apaga o login") -- o que muda é só o que a tela
    diz.
    """
    from blazesbot.config import Account, BotConfig

    def conta(login, segue=(), app=False):
        c = Account(login=login)
        c.settings.app.time_logins = list(segue)
        c.settings.app.enabled = app
        return c

    cfg = BotConfig()
    lider = conta("lider", ["seg"], app=True)
    cfg.accounts = [lider, conta("seg")]
    assert cfg.lideres_do_time_do_app() == {"seg": "lider"}

    lider.settings.app.enabled = False
    assert cfg.lideres_do_time_do_app() == {}, (
        "líder sem APP não convoca -- a seguidora é 'só login'")
    assert lider.settings.app.time_logins == ["seg"], (
        "desligar o APP não pode APAGAR o time montado")


def test_o_lider_e_resolvido_em_UMA_passada():
    """Era uma varredura por conta -- O(n²) a cada leitura da tabela."""
    fonte = (RAIZ / "blazesbot" / "web_app.py").read_text(encoding="utf-8")
    assert "lideres = self.config.lideres_do_time_do_app()" in fonte
    assert "self.config.lider_do_time_do_app(c.login)" not in fonte


def test_PARAR_o_bot_nao_e_o_mesmo_que_CAIR():
    """Achado da revisão: o Parar também mata a janela, e sem olhar o
    `stop_event` a tela pintava "Caiu — reconectando" em toda conta que já
    tivesse tentado logar. Encerrar de propósito não é queda."""
    sup = (RAIZ / "blazesbot" / "bot" / "supervisor.py").read_text(encoding="utf-8")
    assert "and not sup.stop_event.is_set()" in sup


def test_a_conexao_e_CONFERIDA_e_nao_so_o_handle_em_cache():
    """Achado da revisão: entre a janela morrer e o laço perceber, o handle fica
    em cache e a tela ficava VERDE com o personagem fora do jogo."""
    sup = (RAIZ / "blazesbot" / "bot" / "supervisor.py").read_text(encoding="utf-8")
    assert '"conectada": _janela_viva(sup.hwnd),' in sup
    assert "def _janela_viva(" in sup
    # E falhar a checagem não pode derrubar o resumo, que alimenta a tela toda.
    corpo = sup.split("def _janela_viva(")[1].split("\n\nclass ")[0]
    assert "except Exception:" in corpo


# -- 5. o que só apareceu medindo na tela ----------------------------------

def test_o_sticky_do_grupo_nao_usa_numero_magico():
    """Era `top: 27px` chutado enquanto o `<th>` media 27,5 -- meio pixel de
    fresta, e qualquer mudança de fonte ou zoom abriria mais."""
    assert "--altura-cabecalho-tabela:" in CSS
    assert "top: var(--altura-cabecalho-tabela);" in CSS
    assert "height: var(--altura-cabecalho-tabela);" in CSS
    assert "top: 27px" not in CSS


def test_o_pulso_do_ponto_verde_e_COMPOSITAVEL():
    """Era `box-shadow`, que repinta a cada quadro: com dezenas de contas no ar
    seriam dezenas de repaints contínuos."""
    corpo = CSS.split("@keyframes pulso-no-ar {")[1].split("}\n  }")[0]
    assert "box-shadow" not in corpo, "volta a repintar a cada quadro"
    assert "opacity" in corpo and "transform" in corpo


def test_as_cores_dos_selos_tem_variante_de_TEMA_CLARO():
    """Medido na tela: com valores fixos pensados para fundo escuro, o tema claro
    punha texto quase branco sobre fundo claro e a sigla sumia. O estado
    DESLIGADO caía para 3,28:1, abaixo de AA para 9,5px."""
    claro = CSS.split(':root[data-tema="claro"]')[1]
    for token in ("--selo-bc-texto", "--selo-hh-texto", "--selo-off-texto"):
        assert token in claro, f"{token} não tem variante de tema claro"
    # E nada de cor crua dentro das regras dos selos.
    for regra in (".selo-bc:has(.selo-caixa:checked) {",
                  ".selo-hh:has(.selo-caixa:checked) {"):
        bloco = CSS.split(regra)[1].split("}")[0]
        assert "#" not in bloco, f"cor crua em {regra}: {bloco}"


def test_as_colunas_de_largura_fixa_nao_truncam():
    """A coluna Função entrou e o navegador redistribuiu sozinho: "Center" virou
    "Cente", o servidor virou "Light in the Darkn" e o botão Editar quebrou em
    duas linhas. Dado truncado é dado que o usuário não confere."""
    for classe in ("col-ativa", "col-senha", "col-posicao",
                   "col-editar", "col-servidor"):
        assert f".tabela .{classe}" in CSS, classe
    assert "white-space: nowrap" in CSS.split(".bt-editar {")[1].split("}")[0]
