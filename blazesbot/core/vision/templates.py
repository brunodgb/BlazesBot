"""
Templates .bmp/.png, casamentos e realce de UI.

Aqui mora o que o bot RECONHECE: botões, ícones, listas com seleção. Recebe
o BGR devolvido por `captura.py` e devolve onde o elemento está -- ou um
score de similaridade quando a decisão é melhor tomar lá fora.

A cor da seleção de linha de servidor (HIGHLIGHT_BGR) é daqui -- é o mesmo
problema de "achar o que está marcado", só que em vez de template match é
uma estatística de cor por linha.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from blazesbot.core.vision.captura import capture_window

DEFAULT_THRESHOLD = 0.87

# Cor da linha selecionada na lista de servidores (azul do realce).
# Medida em print real: RGB aproximado (51, 68, 153).
HIGHLIGHT_BGR = (153, 68, 51)


# ===========================================================================
# AS SUBPASTAS DE CATEGORIA
# ===========================================================================
#
# Os templates da raiz de `data/templates` estão agrupados por FUNÇÃO. Quem
# chama continua pedindo pelo NOME (`load("state_queue.png")`) e não sabe em
# que pasta o arquivo está -- a categoria é para o humano que abre o diretório,
# não para o código.
#
# POR QUE NÃO É BUSCA RECURSIVA. Debaixo de `data/templates` existem quatro
# pastas que NÃO podem entrar na busca:
#
#   `entrada/`     outra `TemplateLibrary`, com a caixa da entrada da cave
#   `deletar/`     208 PNG do usuário, carregados por `glob` (`bot/deletador`)
#   `deletar_hh/`  o mesmo, para a HH
#   `aprendidos/`  recortes gravados em tempo de execução (`LearnedCrops`)
#
# E a colisão não é hipótese: `boss_2_fase.png`, `dialogo_seta_baixo.png`,
# `link_enter_hh.png` e `link_west_suburb.png` existem na raiz **e** em
# `entrada/`, com conteúdo diferente. Uma varredura recursiva acharia o errado
# metade das vezes, e erraria CALADA -- template errado não levanta exceção,
# ele só não casa.
#
# Lista explícita, então. Pasta nova de categoria entra aqui, e
# `tests/test_templates_por_categoria.py` reprova se um nome ficar em duas.
SUBPASTAS_DE_CATEGORIA = (
    "estado", "link", "botao", "janela", "npc", "combate", "item",
)


class TemplateLibrary:
    """Carrega e cacheia templates .bmp/.png de uma pasta."""

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)
        self._cache: dict[str, np.ndarray] = {}

    def caminho_de(self, name: str) -> Path | None:
        """Onde está o template `name`. `None` = não achei em lugar nenhum.

        Procura na raiz primeiro e nas subpastas de categoria depois. É o único
        ponto que sabe que a categoria existe -- por isso mover um PNG de
        categoria não toca em nenhum chamador.
        """
        direto = self.folder / name
        if direto.exists():
            return direto
        for sub in SUBPASTAS_DE_CATEGORIA:
            candidato = self.folder / sub / name
            if candidato.exists():
                return candidato
        return None

    def load(self, name: str) -> np.ndarray | None:
        if name in self._cache:
            return self._cache[name]
        path = self.caminho_de(name)
        if path is None:
            return None
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            self._cache[name] = img
        return img

    def load_color(self, name: str) -> np.ndarray | None:
        """O mesmo template, mas em COR (BGR), com cache próprio.

        =================================================================
        QUANDO USAR COR E QUANDO USAR CINZA
        =================================================================

        Cinza é o padrão e serve para o que este bot mais procura: janelas,
        botões, texto, estados de tela. São elementos grandes, de forma única, e
        a cor deles não distingue nada.

        COR é para ÍCONE DE ITEM, e a diferença é medida, não estética. Um ícone
        de item tem 40x36 px e a bolsa está cheia de ícones de MESMA FORMA em
        cores diferentes -- poções, pergaminhos, livros. Em cinza esses viram o
        mesmo desenho:

            mesma forma, matiz +60  -> cinza 0.982   cor 0.863
            mesma forma, matiz +90  -> cinza 0.976   cor 0.804
            mesma forma, matiz +120 -> cinza 0.986   cor 0.863

        Com o limiar de 0.87, TODOS passam em cinza. Nenhum passa em cor.

        E o item verdadeiro sobrevive à cor com folga: degradado por recompressão
        JPEG, ruído e variação de brilho, ele fica entre 0.983 e 0.999. Ou seja,
        existe um vão limpo entre 0.87 e 0.98 para escolher o limiar.
        """
        chave = f"__cor__{name}"
        if chave in self._cache:
            return self._cache[chave]
        path = self.caminho_de(name)
        if path is None:
            return None
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is not None:
            self._cache[chave] = img
        return img


def crop(
    frame: np.ndarray | None,
    region: tuple[int, int, int, int],
) -> np.ndarray | None:
    """Recorta (x, y, largura, altura) do quadro. None se não couber."""
    if frame is None:
        return None
    x, y, w, h = region
    if x < 0 or y < 0 or w <= 0 or h <= 0:
        return None
    if y + h > frame.shape[0] or x + w > frame.shape[1]:
        return None
    return frame[y:y + h, x:x + w]


def regiao_mudou(
    antes: np.ndarray | None,
    depois: np.ndarray | None,
    region: tuple[int, int, int, int],
    minimo: float = 12.0,
) -> bool:
    """Alguma coisa APARECEU (ou sumiu) nesta região entre os dois quadros?

    Responde "o submenu abriu?" sem template: o menu de contexto do jogo não tem
    recorte em disco, e um submenu que aparece sobre a cena 3D muda a região
    inteira. Compara-se a média absoluta da diferença -- ruído de animação da
    cena fica bem abaixo de `minimo`, uma caixa opaca aparecendo fica muito
    acima.

    `False` quando falta qualquer um dos quadros: sem os dois não há comparação,
    e "não sei" nunca autoriza um clique.
    """
    a = crop(antes, region)
    b = crop(depois, region)
    if a is None or b is None or a.size == 0 or a.shape != b.shape:
        return False
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean()) >= minimo


def altura_da_mudanca(
    antes: np.ndarray | None,
    depois: np.ndarray | None,
    x: int,
    y: int,
    largura: int,
    altura_max: int,
    minimo: float = 12.0,
) -> int:
    """Quantas linhas SEGUIDAS mudaram, descendo a partir de (x, y).

    É a régua de uma caixa opaca que apareceu -- serve para saber QUANTOS itens
    um menu de contexto trouxe sem ter recorte dos itens em disco.

    SEGUIDAS é o que dá robustez: a varredura para na PRIMEIRA linha que não
    mudou, então a cena se mexendo mais abaixo não estica a medida. Ela também
    para cedo se uma linha do menu empatar com o fundo -- a medida erra para
    MENOS, nunca para mais, e quem chama tem de tratar "curto" como o caso menos
    arriscado.
    """
    for h in range(altura_max):
        if not regiao_mudou(antes, depois, (x, y + h, largura, 1), minimo):
            return h
    return altura_max


def region_is_uniform(
    frame: np.ndarray | None,
    region: tuple[int, int, int, int],
    max_std: float = 8.0,
) -> bool:
    """True se a região é lisa, ou seja, não tem texto nem ícone.

    Usado para responder "esta linha da lista está vazia?" sem precisar ler
    texto: fundo de painel é praticamente uniforme, e qualquer letra escrita
    sobre ele levanta o desvio padrão muito acima do limite.
    """
    pedaco = crop(frame, region)
    if pedaco is None or pedaco.size == 0:
        return False
    return float(pedaco.std()) < max_std


class LearnedCrops:
    """Recortes que o bot aprende durante a operação.

    POR QUE ISTO EXISTE

    Duas decisões dependem de LER texto da tela: qual nick está na primeira
    linha da Block list, e qual nick enviou um convite de time. O jogo não expõe
    esses textos na memória, e o projeto não tem OCR -- e colocar um seria
    trocar um problema pequeno por uma dependência grande.

    A saída é comparar pixels: no momento em que o bot SABE o que está escrito
    numa região (porque foi ele que acabou de digitar, ou porque o convite tinha
    acabado de ser enviado por uma conta dele), ele guarda o recorte daquela
    região em disco. Da próxima vez, reconhecer é comparar. A fonte, o fundo e a
    posição são sempre os mesmos, então o recorte casa com score altíssimo para
    o MESMO texto e falha para qualquer outro -- que é exatamente a distinção
    necessária.

    Os arquivos ficam separados dos templates de fábrica: são derivados da
    máquina de quem usa, e apagá-los só faz o bot reaprender.
    """

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)
        self._cache: dict[str, np.ndarray] = {}

    @staticmethod
    def _sanitize(chave: str) -> str:
        limpo = "".join(c if c.isalnum() or c in "-_" else "_" for c in chave)
        return limpo.lower() or "sem_nome"

    def path_for(self, chave: str) -> Path:
        return self.folder / f"{self._sanitize(chave)}.png"

    def load(self, chave: str) -> np.ndarray | None:
        nome = self._sanitize(chave)
        if nome in self._cache:
            return self._cache[nome]
        caminho = self.path_for(chave)
        if not caminho.exists():
            return None
        img = cv2.imread(str(caminho), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            self._cache[nome] = img
        return img

    def save(
        self,
        chave: str,
        frame: np.ndarray | None,
        region: tuple[int, int, int, int],
    ) -> bool:
        """Guarda o recorte de uma região. Recusa região lisa.

        Recusar região lisa é o que impede aprender "nada": se a captura veio
        vazia ou a janela já tinha fechado, o recorte seria fundo puro e passaria
        a casar com qualquer outro fundo puro -- transformando a verificação num
        sim para tudo.
        """
        pedaco = crop(frame, region)
        if pedaco is None or pedaco.size == 0:
            return False
        cinza = cv2.cvtColor(pedaco, cv2.COLOR_BGR2GRAY) if pedaco.ndim == 3 else pedaco
        if float(cinza.std()) < 8.0:
            return False
        self.folder.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(self.path_for(chave)), cinza)
        self._cache[self._sanitize(chave)] = cinza
        return True

    def forget(self, chave: str) -> None:
        self._cache.pop(self._sanitize(chave), None)
        try:
            self.path_for(chave).unlink(missing_ok=True)
        except Exception:
            pass

    def score(
        self,
        chave: str,
        frame: np.ndarray | None,
        region: tuple[int, int, int, int],
        slack: int = 4,
    ) -> float | None:
        """Semelhança entre o recorte guardado e a tela agora, de 0 a 1.

        Devolve None se não há recorte guardado ou não foi possível comparar --
        que é diferente de "não parece", e quem chama trata os dois casos de
        formas diferentes. A folga de alguns pixels absorve o desalinhamento
        normal entre a coordenada calculada e a captura real.
        """
        guardado = self.load(chave)
        if guardado is None or frame is None:
            return None
        x, y, w, h = region
        busca = (max(0, x - slack), max(0, y - slack), w + 2 * slack, h + 2 * slack)
        area = crop(frame, busca)
        if area is None or area.size == 0:
            return None
        cinza = cv2.cvtColor(area, cv2.COLOR_BGR2GRAY) if area.ndim == 3 else area
        if (cinza.shape[0] < guardado.shape[0]
                or cinza.shape[1] < guardado.shape[1]):
            return None
        resultado = cv2.matchTemplate(cinza, guardado, cv2.TM_CCOEFF_NORMED)
        return float(cv2.minMaxLoc(resultado)[1])


def find_template(
    frame: np.ndarray,
    template: np.ndarray,
    threshold: float = DEFAULT_THRESHOLD,
    region: tuple[int, int, int, int] | None = None,
) -> tuple[int, int] | None:
    """Procura o template no quadro. Devolve o CENTRO do match ou None.

    `region` = (x, y, w, h) restringe a busca -- sempre use quando souber
    onde o elemento fica; é mais rápido e reduz falso positivo.
    """
    if frame is None or template is None:
        return None

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    off_x, off_y = 0, 0
    if region:
        rx, ry, rw, rh = region
        gray = gray[ry:ry + rh, rx:rx + rw]
        off_x, off_y = rx, ry

    if gray.shape[0] < template.shape[0] or gray.shape[1] < template.shape[1]:
        return None

    result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < threshold:
        return None

    th, tw = template.shape[:2]
    return (off_x + max_loc[0] + tw // 2, off_y + max_loc[1] + th // 2)


def find_all_templates(
    frame: np.ndarray,
    template: np.ndarray,
    threshold: float = DEFAULT_THRESHOLD,
    region: tuple[int, int, int, int] | None = None,
    colorido: bool = False,
    placar: list[float] | None = None,
) -> list[tuple[int, int]]:
    """Todos os CENTROS dos matches do template, não só o melhor.

    Diferente do `find_template`, que devolve o pico único: aqui queremos CADA
    ocorrência do item na tela (ex.: vários `package_courage` na bolsa, um em
    cada célula da grade do inventário).

    O `cv2.matchTemplate` produz um "planalto" de valores altos ao redor de CADA
    item real (o pico exato e os vizinhos quase iguais), então não basta
    `np.where(>= threshold)`: um único item geraria vários centros. A supressão
    de não-máximos resolve: coleta todos os pontos acima do limiar, ordena do
    mais forte para o mais fraco e só aceita um ponto se não estiver dentro do
    retângulo do template de um já aceito. Assim cada item contribui com UM
    centro (o de correlação máxima).

    Devolve lista vazia quando não há match acima do limiar -- que é diferente
    de "captura falhou" (quem chama distingue pelo `frame`).

    `placar`, se dado, recebe o MAIOR valor de correlação visto -- de graça,
    porque o `matchTemplate` já roda aqui e esse número era simplesmente
    descartado. É o que permite a quem chama distinguir "não tem esse item na
    tela" (0,30) de "tem, mas o modelo não bate bem o bastante" (0,85 contra
    limiar 0,92) sem pagar uma segunda varredura. Ver `deletador.deletar_lixo`.

    `colorido=True` compara os TRÊS CANAIS em vez da luminância. É o modo certo
    para ÍCONE DE ITEM: em cinza, dois itens de mesma forma e cores diferentes
    marcam 0.98 um contra o outro e viram falso positivo garantido. Ver
    `TemplateLibrary.load_color`, que tem os números medidos -- e lembre de
    carregar o template com `load_color`, porque o de `load` vem em cinza e não
    casa com um quadro de três canais.
    """
    if frame is None or template is None:
        return []

    cena = frame if colorido else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    off_x, off_y = 0, 0
    if region:
        rx, ry, rw, rh = region
        cena = cena[ry:ry + rh, rx:rx + rw]
        off_x, off_y = rx, ry

    if cena.shape[0] < template.shape[0] or cena.shape[1] < template.shape[1]:
        return []
    if colorido and cena.ndim != template.ndim:
        # Template em cinza com quadro em cor (ou o contrário) faz o
        # `matchTemplate` levantar. Devolver vazio aqui viraria "não tem item",
        # que é uma resposta errada; quem chama precisa saber que errou a carga.
        raise ValueError(
            "find_all_templates(colorido=True) exige quadro e template em cor; "
            f"recebi quadro com {cena.ndim} dim e template com {template.ndim}. "
            "Use TemplateLibrary.load_color()."
        )

    result = cv2.matchTemplate(cena, template, cv2.TM_CCOEFF_NORMED)
    if placar is not None and result.size:
        placar.append(float(result.max()))
    th, tw = template.shape[:2]

    # (valor, x, y) para todos os pontos acima do limiar, do mais forte ao mais
    # fraco -- assim o pico de cada item é aceito antes dos seus vizinhos.
    ys, xs = np.where(result >= threshold)
    if ys.size == 0:
        return []
    candidatos = sorted(
        (float(result[y, x]), int(x), int(y)) for y, x in zip(ys, xs)
    )
    candidatos.reverse()

    aceitos: list[tuple[int, int]] = []
    for _valor, x, y in candidatos:
        # Centro do match, no quadro original (não no recorte).
        centro = (off_x + x + tw // 2, off_y + y + th // 2)
        if any(
            abs(centro[0] - ax) < tw and abs(centro[1] - ay) < th
            for ax, ay in aceitos
        ):
            continue  # dentro do retângulo de um item já aceito
        aceitos.append(centro)
        if len(aceitos) >= 64:  # proteção contra tela cheia de ruído
            break
    return aceitos


def highlight_ratio(
    frame: np.ndarray,
    y: int,
    x_from: int = 280,
    x_to: int = 680,
    tolerance: int = 45,
) -> float:
    """Fração de pixels da linha `y` que têm a cor do realce de seleção."""
    h, w = frame.shape[:2]
    if not (0 <= y < h):
        return 0.0
    x_to = min(x_to, w)
    if x_to <= x_from:
        return 0.0
    strip = frame[y, x_from:x_to].astype(int)
    target = np.array(HIGHLIGHT_BGR, dtype=int)
    return float((np.abs(strip - target) <= tolerance).all(axis=1).mean())


def find_highlighted_row(
    frame: np.ndarray | None,
    first_row_y: int,
    row_height: int,
    row_count: int,
    slack: int = 14,
    min_ratio: float = 0.35,
    center_x: int | None = None,
    half_width: int = 210,
) -> int | None:
    """Descobre QUAL linha da lista está com o realce de seleção.

    Devolve o índice (0 = primeira linha) ou None se nenhuma estiver realçada.

    Procurar onde o realce ESTÁ, em vez de perguntar "a linha N está
    realçada?", torna a verificação tolerante a alguns pixels de desalinhamento
    entre a coordenada medida e a captura real -- que foi o motivo de a
    verificação anterior falhar mesmo com o servidor corretamente selecionado.
    Como bônus, dá para dizer no log qual servidor ficou selecionado por engano.
    """
    if frame is None or row_count <= 0:
        return None

    # A faixa horizontal varrida acompanha a janela, em vez de ser fixa. Com
    # valores fixos de 1024x768, em 1632x918 a varredura caía fora da lista e a
    # verificação nunca achava o realce -- o bot clicava três vezes e seguia
    # sem confirmar.
    if center_x is None:
        center_x = frame.shape[1] // 2
    x_from = max(0, center_x - half_width)
    x_to = min(frame.shape[1], center_x + half_width)

    y_min = max(0, first_row_y - slack)
    y_max = min(frame.shape[0] - 1, first_row_y + (row_count - 1) * row_height + slack)

    # Coleta TODAS as linhas realçadas e usa o CENTRO da faixa. Usar o pico
    # (argmax) era instável: a faixa tem várias linhas com a mesma proporção e
    # o pico caía na borda, deslocando o índice calculado.
    marcadas = [y for y in range(y_min, y_max + 1)
                if highlight_ratio(frame, y, x_from, x_to) >= min_ratio]
    if not marcadas:
        return None

    centro = (marcadas[0] + marcadas[-1]) / 2.0
    index = int(round((centro - first_row_y) / row_height))
    if 0 <= index < row_count:
        return index
    return None


def template_present(
    hwnd: int,
    template: np.ndarray,
    threshold: float = DEFAULT_THRESHOLD,
    region: tuple[int, int, int, int] | None = None,
) -> bool:
    frame = capture_window(hwnd)
    if frame is None:
        return False
    return find_template(frame, template, threshold, region) is not None


def melhor_casamento(quadro, template, *, colorido: bool = False) -> float | None:
    """O MAIOR valor de correlação do template no quadro. `None` = não deu.

    =======================================================================
    ISTO SÓ MEDE. NÃO DECIDE NADA.
    =======================================================================

    Existe para o caso mais frustrante da busca por imagem: o modelo está na
    pasta, o item está na bolsa, e o bot apaga zero. Sem o número, esse estado
    é indistinguível de "não tem lixo na bolsa" -- e as três causas possíveis
    pedem correções OPOSTAS:

      * **0,85 com limiar 0,92** -> o modelo É daquele item, mas a captura
        difere um pouco (fundo do slot, badge de quantidade, item selecionado).
        Ou se afrouxa o limiar, COM medição, ou se refaz o PNG;
      * **0,40** -> não é aquele item. O limiar está certo e o modelo, errado;
      * **nenhuma medida** -> o item não está em NENHUMA região varrida, e o
        problema é de GEOMETRIA: bolsa extra fechada, painel arrastado, aba
        errada. Afrouxar o limiar aqui não muda nada.

    Ninguém chama isto para decidir se apaga -- quem apaga é
    `find_all_templates`, com o limiar. Este é o instrumento, e instrumento não
    vota.
    """
    if quadro is None or template is None:
        return None
    cena = quadro if colorido else cv2.cvtColor(quadro, cv2.COLOR_BGR2GRAY)
    if (cena.shape[0] < template.shape[0]
            or cena.shape[1] < template.shape[1]):
        return None
    if colorido and cena.ndim != template.ndim:
        return None
    resultado = cv2.matchTemplate(cena, template, cv2.TM_CCOEFF_NORMED)
    return float(resultado.max())
