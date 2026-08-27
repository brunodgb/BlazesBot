"""
Visão computacional: captura da janela do cliente e template matching.

Usada apenas onde a memória não alcança -- basicamente elementos de UI que
não têm flag mapeada (fila de login, ícone de fase do boss, botões).

A captura usa PrintWindow com PW_RENDERFULLCONTENT, que funciona com janela
em background e, na maioria dos casos, minimizada. Se voltar quadro preto,
o cliente precisa estar visível (ver README).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import win32con
import win32gui
import win32ui

from blazesbot.core import coords as coords_mod

PW_RENDERFULLCONTENT = 0x00000002
DEFAULT_THRESHOLD = 0.87

# De quantos em quantos pixels o `frame_is_blank` amostra o quadro.
#
# NÃO É AJUSTE FINO -- é o que impede uma queda por memória. Ver o comentário
# dentro de `frame_is_blank` para o log da noite de 20/08/2026 e as medições:
# `frame.std()` sobre o quadro inteiro aloca 18 MB de float64 por chamada e custa
# 8-10 ms; amostrado de 8 em 8 são 0,36 MB e 0,13 ms, com o mesmo veredito.
PASSO_DA_AMOSTRAGEM_DO_QUADRO = 8


def frame_is_blank(frame: np.ndarray | None) -> bool:
    """True se o quadro está preto/uniforme, ou seja, inútil.

    ARMADILHA IMPORTANTE: PrintWindow retorna SUCESSO mesmo quando produz uma
    imagem totalmente preta -- o que acontece com frequência em clientes
    DirectX que não estão em primeiro plano. Confiar no código de retorno faz o
    bot achar que capturou quando não capturou. Por isso a verificação é feita
    no conteúdo, não no retorno da API.
    """
    if frame is None or frame.size == 0:
        return True
    # ==================================================================
    # A AMOSTRAGEM NÃO É OTIMIZAÇÃO PREMATURA -- É CONSERTO DE QUEDA
    # ==================================================================
    #
    # `frame.std()` sobre `uint8` aloca um temporário **float64 do tamanho do
    # quadro inteiro**: (768,1024,3) x 8 bytes = **18 MB por chamada**. Isso
    # derrubou o bot na noite de 20/08/2026, e o log guardou a frase exata:
    #
    #     Erro inesperado na sessão: Unable to allocate 18.0 MiB for an array
    #     with shape (768, 1024, 3) and data type float64
    #
    # Quatro ocorrências, seguidas de "OpenBLAS error: Memory allocation still
    # failed after 10 retries". Ficou visível quando a calibração multiplicou por
    # ~10 a frequência de captura: cinco contas x ~2 capturas/s x 18 MB é
    # **~180 MB/s de rotatividade em blocos grandes**, que fragmenta o heap até
    # não haver bloco contíguo.
    #
    # Amostrar de 8 em 8 pixels responde a MESMA pergunta -- "este quadro está
    # preto?" -- e foi medido em quadros reais:
    #
    #     quadro real 1     std completo 46,67   amostrado 45,41
    #     quadro real 2     std completo 53,42   amostrado 53,42
    #     quadro real 3     std completo 35,84   amostrado 36,21
    #     preto puro                     0,00              0,00
    #     quase uniforme                 0,00              0,01
    #
    # Os dois lados do limiar de 3,0 continuam do mesmo lado, com folga enorme.
    # E o ganho é duplo:
    #
    #     pico de alocação   18,94 MB  ->  0,36 MB   (52x menos)
    #     custo por chamada  8-10 ms   ->  0,13 ms   (65x mais rápido)
    #
    # Os 8-10 ms eram pagos a cada captura, em toda conta -- ou seja, este "teste
    # barato" custava mais que o casamento de template que ele protege.
    #
    # `PASSO_DA_AMOSTRAGEM_DO_QUADRO` fica ajustável porque é o único número aqui
    # que troca precisão por custo. 8 deixa ~12.000 pixels, ordens de grandeza
    # acima do necessário para distinguir preto de cena.
    return float(frame[::PASSO_DA_AMOSTRAGEM_DO_QUADRO,
                       ::PASSO_DA_AMOSTRAGEM_DO_QUADRO].std()) < 3.0


def client_offset(hwnd: int) -> tuple[int, int]:
    """Deslocamento da área de cliente dentro da janela.

    Em janela com barra de título e bordas, a área de cliente começa alguns
    pixels abaixo e à direita do canto da janela. Saber esse deslocamento é o
    que permite recortar exatamente a área de cliente de uma captura da janela
    inteira.
    """
    try:
        wl, wt, _wr, _wb = win32gui.GetWindowRect(hwnd)
        cl, ct = win32gui.ClientToScreen(hwnd, (0, 0))
        return max(0, cl - wl), max(0, ct - wt)
    except Exception:
        return 0, 0


# ---------------------------------------------------------------------------
# Pool de recursos GDI — alocados uma vez por janela, reutilizados em todas
# as capturas. Elimina o ciclo CreateDC/CreateBitmap/DeleteDC/ReleaseDC que
# acontecia a CADA frame capturado e que, sob carga (10+ capturas/s x N
# contas), saturava o subsistema GDI e travava a interface.
# ---------------------------------------------------------------------------

class GdiPool:
    """Recursos GDI pré-alocados para captura de uma janela, reutilizáveis."""

    def __init__(self, hwnd: int) -> None:
        self._hwnd = hwnd
        self._origem_dc: int | None = None
        self._src_dc: object | None = None          # PyCDC
        self._mem_dc: object | None = None          # PyCDC
        self._bitmap: object | None = None          # PyCBitmap
        self._old_bitmap: object | None = None      # bitmap original do mem_dc
        self._largura = 0
        self._altura = 0
        self._modo: str | None = None               # 'printwindow' | 'bitblt'

    # -- propriedades públicas (usadas por _capture_with_pool) ----------

    @property
    def mem_dc(self) -> object | None:
        return self._mem_dc

    @property
    def bitmap(self) -> object | None:
        return self._bitmap

    @property
    def src_dc(self) -> object | None:
        return self._src_dc

    # -- API ------------------------------------------------------------

    def ensure(self, largura: int, altura: int, modo: str) -> bool:
        """Garante recursos para o tamanho e modo. Recria se mudou."""
        if (self._largura == largura
                and self._altura == altura
                and self._modo == modo
                and self._bitmap is not None):
            return True
        self._release()
        try:
            if modo == 'printwindow':
                self._origem_dc = win32gui.GetWindowDC(self._hwnd)
            else:
                self._origem_dc = win32gui.GetDC(self._hwnd)
            self._src_dc = win32ui.CreateDCFromHandle(self._origem_dc)
            self._mem_dc = self._src_dc.CreateCompatibleDC()
            self._bitmap = win32ui.CreateBitmap()
            self._bitmap.CreateCompatibleBitmap(self._src_dc, largura, altura)
            self._old_bitmap = self._mem_dc.SelectObject(self._bitmap)
            self._largura = largura
            self._altura = altura
            self._modo = modo
            return True
        except Exception:
            self._release()
            return False

    def _release(self) -> None:
        """Restaura o bitmap original, destrói tudo, libera DC."""
        if self._mem_dc is not None and self._old_bitmap is not None:
            try:
                self._mem_dc.SelectObject(self._old_bitmap)
            except Exception:
                pass
        self._old_bitmap = None
        if self._bitmap is not None:
            try:
                win32gui.DeleteObject(self._bitmap.GetHandle())
            except Exception:
                pass
            self._bitmap = None
        if self._mem_dc is not None:
            try:
                self._mem_dc.DeleteDC()
            except Exception:
                pass
            self._mem_dc = None
        if self._src_dc is not None:
            try:
                self._src_dc.DeleteDC()
            except Exception:
                pass
            self._src_dc = None
        if self._origem_dc is not None:
            try:
                win32gui.ReleaseDC(self._hwnd, self._origem_dc)
            except Exception:
                pass
            self._origem_dc = None
        self._largura = 0
        self._altura = 0
        self._modo = None

    def close(self) -> None:
        """Libera todos os recursos. Seguro chamar mais de uma vez."""
        self._release()


# Pool global por hwnd. Um só supervisor acessa cada hwnd, então não precisa
# de lock. Se no futuro o mesmo hwnd for acessado de mais de um thread, o
# lock tem que entrar AQUI.
_pools: dict[int, GdiPool] = {}


def get_pool(hwnd: int) -> GdiPool:
    """Devolve (ou cria) o pool GDI para a janela."""
    if hwnd not in _pools:
        _pools[hwnd] = GdiPool(hwnd)
    return _pools[hwnd]


def release_pool(hwnd: int) -> None:
    """Libera os recursos GDI da janela. Idempotente."""
    pool = _pools.pop(hwnd, None)
    if pool is not None:
        pool.close()


def _capture_with_pool(
    hwnd: int, pool: GdiPool, *, use_printwindow: bool
) -> np.ndarray | None:
    """Captura usando recursos pré-alocados do pool (sem alocar/liberar GDI)."""
    try:
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        cw, ch = right - left, bottom - top
        if cw <= 0 or ch <= 0:
            return None

        if use_printwindow:
            wl, wt, wr, wb = win32gui.GetWindowRect(hwnd)
            ww, wh = wr - wl, wb - wt
            if ww <= 0 or wh <= 0:
                return None
            largura, altura = ww, wh
            modo = 'printwindow'
        else:
            largura, altura = cw, ch
            modo = 'bitblt'

        if not pool.ensure(largura, altura, modo):
            return None

        if use_printwindow:
            win32gui.PrintWindow(
                hwnd, pool.mem_dc.GetSafeHdc(), PW_RENDERFULLCONTENT
            )
        else:
            pool.mem_dc.BitBlt(
                (0, 0), (largura, altura), pool.src_dc, (0, 0), win32con.SRCCOPY
            )

        info = pool.bitmap.GetInfo()
        raw = pool.bitmap.GetBitmapBits(True)
        imagem = np.frombuffer(raw, dtype=np.uint8).reshape(
            (info["bmHeight"], info["bmWidth"], 4)
        )
        quadro = cv2.cvtColor(imagem.copy(), cv2.COLOR_BGRA2BGR)

        if use_printwindow:
            dx, dy = client_offset(hwnd)
            if dy + ch <= quadro.shape[0] and dx + cw <= quadro.shape[1]:
                quadro = quadro[dy:dy + ch, dx:dx + cw]
            else:
                return None

        return quadro
    except Exception:
        return None


def _raw_capture(hwnd: int, use_printwindow: bool) -> np.ndarray | None:
    """Captura a ÁREA DE CLIENTE da janela, por PrintWindow ou por BitBlt.

    ARMADILHA QUE CUSTOU CARO E ESTÁ DOCUMENTADA AQUI PARA NÃO VOLTAR:

    `GetWindowDC` devolve um contexto da JANELA INTEIRA -- barra de título e
    bordas incluídas -- com origem no canto da janela. Se o bitmap é dimensionado
    pela área de cliente mas desenhado a partir dessa origem, o resultado contém
    a barra de título no topo e TODO o conteúdo do jogo aparece deslocado para
    baixo pela altura dela (uns 28 px).

    O deslocamento não atrapalha quando só se pergunta "este elemento está na
    tela?", mas estraga qualquer coordenada derivada de um elemento localizado:
    um clique calculado a partir dele cai 28 px abaixo do alvo. Como os campos
    de usuário e senha ficam a 30 px um do outro, o clique na senha caía dentro
    do campo de usuário.

    Correção: PrintWindow captura a janela inteira e o recorte da área de
    cliente é feito depois; BitBlt usa `GetDC`, cujo contexto já tem origem na
    área de cliente.

    =========================================================================
    OS RECURSOS DE GDI SÃO LIBERADOS NO `finally`, E ISSO NÃO É ZELO
    =========================================================================

    Antes a liberação ficava no CAMINHO FELIZ, entre a leitura dos bits e o
    `return`. Toda exceção levantada depois de `GetWindowDC` -- e há várias
    candidatas reais: `CreateCompatibleBitmap` falhando por pressão de GDI,
    `PrintWindow` numa janela que acabou de fechar, `GetBitmapBits` numa janela
    grande sem memória -- pulava direto para o `except` de baixo, que devolvia
    `None` em silêncio. O contexto de dispositivo e o bitmap ficavam para trás.

    POR QUE ISSO DERRUBA O BOT. O Windows limita objetos de GDI por processo
    (10.000 por padrão). Este bot captura a tela muitas vezes por segundo, vezes
    o número de contas. Vazar uma fração das capturas basta para chegar no teto
    em algumas horas -- e no teto:

      * `CreateCompatibleBitmap` passa a falhar SEMPRE;
      * portanto toda captura devolve `None`;
      * portanto todo template deixa de casar;
      * e o bot fica rodando sem conseguir ver nada. Da tela, é um congelamento.

    Handles esgotados também derrubam o processo sem mensagem, que é o outro
    sintoma relatado.

    O comportamento observável não muda: as mesmas capturas devolvem os mesmos
    quadros, e as mesmas falhas continuam devolvendo `None`.
    """
    origem_dc = None
    src_dc = None
    mem_dc = None
    bitmap = None
    try:
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        cw, ch = right - left, bottom - top
        if cw <= 0 or ch <= 0:
            return None

        if use_printwindow:
            # PrintWindow desenha a JANELA inteira; captura tudo e recorta.
            wl, wt, wr, wb = win32gui.GetWindowRect(hwnd)
            ww, wh = wr - wl, wb - wt
            if ww <= 0 or wh <= 0:
                return None
            origem_dc = win32gui.GetWindowDC(hwnd)
            largura, altura = ww, wh
        else:
            # GetDC devolve contexto com origem na ÁREA DE CLIENTE.
            origem_dc = win32gui.GetDC(hwnd)
            largura, altura = cw, ch

        src_dc = win32ui.CreateDCFromHandle(origem_dc)
        mem_dc = src_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(src_dc, largura, altura)
        mem_dc.SelectObject(bitmap)

        if use_printwindow:
            win32gui.PrintWindow(hwnd, mem_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)
        else:
            mem_dc.BitBlt((0, 0), (largura, altura), src_dc, (0, 0),
                          win32con.SRCCOPY)

        info = bitmap.GetInfo()
        raw = bitmap.GetBitmapBits(True)
        imagem = np.frombuffer(raw, dtype=np.uint8).reshape(
            (info["bmHeight"], info["bmWidth"], 4)
        )

        # A CÓPIA É NECESSÁRIA. `np.frombuffer` NÃO copia: o array aponta para o
        # buffer devolvido pelo bitmap. Como o bitmap é destruído no `finally`
        # logo abaixo, devolver uma view dele seria devolver memória liberada.
        # Antes isso não aparecia porque a liberação vinha depois da conversão de
        # cor -- que copia por acaso. Depender de um efeito colateral de terceiro
        # para a memória não ser liberada cedo demais é frágil demais para ficar
        # implícito.
        quadro = cv2.cvtColor(imagem.copy(), cv2.COLOR_BGRA2BGR)

        if use_printwindow:
            dx, dy = client_offset(hwnd)
            if dy + ch <= quadro.shape[0] and dx + cw <= quadro.shape[1]:
                quadro = quadro[dy:dy + ch, dx:dx + cw]
            else:
                # Sem espaço para o recorte: a captura não é confiável.
                return None

        return quadro
    except Exception:
        return None
    finally:
        # Cada liberação no seu próprio `try`: se a primeira falhar, as outras
        # ainda precisam acontecer. Uma falha aqui não pode virar exceção, senão
        # ela substituiria o `return None` e subiria para quem chamou.
        if bitmap is not None:
            try:
                win32gui.DeleteObject(bitmap.GetHandle())
            except Exception:
                pass
        if mem_dc is not None:
            try:
                mem_dc.DeleteDC()
            except Exception:
                pass
        if src_dc is not None:
            try:
                src_dc.DeleteDC()
            except Exception:
                pass
        if origem_dc is not None:
            try:
                win32gui.ReleaseDC(hwnd, origem_dc)
            except Exception:
                pass


def capture_window(hwnd: int) -> np.ndarray | None:
    """Captura a área de cliente. Devolve BGR utilizável, ou None.

    Tenta PrintWindow e, se o resultado vier em branco, tenta BitBlt. Se
    nenhum dos dois produzir imagem com conteúdo, devolve None -- e quem chama
    deve tratar isso como "captura indisponível" em vez de "tela desconhecida".

    Usa pool de GDI pré-alocado: os recursos (DC, bitmap) são criados uma vez
    por janela e reutilizados, eliminando o ciclo de alocação/liberação que
    saturava o subsistema GDI sob carga. Se o pool falhar, cai de volta para
    _raw_capture (alocação descartável).
    """
    try:
        pool = get_pool(hwnd)
    except Exception:
        pool = None

    if pool is not None:
        frame = _capture_with_pool(hwnd, pool, use_printwindow=True)
        if not frame_is_blank(frame):
            return frame
        frame = _capture_with_pool(hwnd, pool, use_printwindow=False)
        if not frame_is_blank(frame):
            return frame
        return None

    # Fallback: pool indisponível → alocação descartável tradicional
    frame = _raw_capture(hwnd, use_printwindow=True)
    if not frame_is_blank(frame):
        return frame
    frame = _raw_capture(hwnd, use_printwindow=False)
    if not frame_is_blank(frame):
        return frame
    return None


def capture_available(hwnd: int) -> bool:
    """Diz se dá para capturar a janela com conteúdo real."""
    return capture_window(hwnd) is not None


class TemplateLibrary:
    """Carrega e cacheia templates .bmp/.png de uma pasta."""

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)
        self._cache: dict[str, np.ndarray] = {}

    def load(self, name: str) -> np.ndarray | None:
        if name in self._cache:
            return self._cache[name]
        path = self.folder / name
        if not path.exists():
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
        path = self.folder / name
        if not path.exists():
            return None
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is not None:
            self._cache[chave] = img
        return img

    def load_all(self) -> dict[str, np.ndarray]:
        result: dict[str, np.ndarray] = {}
        if not self.folder.is_dir():
            return result
        for path in sorted(self.folder.iterdir()):
            if path.suffix.lower() not in (".bmp", ".png", ".jpg"):
                continue
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                result[path.name] = img
        return result


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


# Cor da linha selecionada na lista de servidores (azul do realce).
# Medida em print real: RGB aproximado (51, 68, 153).
HIGHLIGHT_BGR = (153, 68, 51)


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


# ===========================================================================
# QUADRO DO ALVO -- quanta vida o mob selecionado ainda tem, lido da TELA
# ===========================================================================
#
# POR QUE PELA TELA E NÃO PELA MEMÓRIA: o bot tem `Memory.target_hp()` e ele é
# mais barato. Mas o ponteiro de alvo se mostrou instável nos testes do usuário
# -- "acabava bugando e não matava os mobs que deveria" --, e foi por isso que a
# fase dos guardas foi reescrita para não depender dele. A tela é a fonte que
# não bugou.
#
# COMO O QUADRO É LOCALIZADO -- e por que NÃO é uma coordenada fixa:
#
# Medido em dois prints do usuário, com o mesmo personagem no mesmo lugar:
#
#     janela 1024 de largura -> barra de HP nas linhas 43..50, x 464..601
#     janela 1025 de largura -> barra de HP nas linhas 38..45, x 467..604
#
# UM pixel de diferença na largura da janela moveu o quadro 5 linhas para cima.
# Uma região fixa erraria a faixa por 5 das 8 linhas dela.
#
# A âncora saiu da própria medição: a barra AZUL de mana do alvo tem largura
# constante (137 px nos quatro arquivos medidos) e está presente com o mob VIVO
# e MORTO -- é a barra vermelha que esvazia, não a azul. Achar a corrida azul
# localiza o quadro sozinha, sem template e sem coordenada à mão.
#
# A faixa vermelha fica SEMPRE 13-14 linhas acima da azul (conferido nos quatro
# arquivos), e a PRIMEIRA linha dela é a borda do desenho -- vermelha cheia
# mesmo com o mob morto. Por isso ela é descartada da conta:
#
#     mob vivo (cheio) .... 957 a 1094 de ~960 pixels possíveis
#     mob MORTO ...........   0 pixels
#
# Zero contra novecentos. É por isso que este caminho não precisa de limiar
# calibrado como o casamento de template precisa.

# Largura mínima da corrida azul para ela ser a barra de mana do alvo. Não é a
# largura exata (137) porque a UI do jogo pode ter outra escala em resolução
# diferente; o que importa é ser uma faixa azul LONGA e contígua, e nada mais na
# parte de cima da tela é assim.
LARGURA_MINIMA_DA_BARRA = 100

# Distância da barra vermelha para a azul, em linhas, e altura da faixa.
LINHAS_ENTRE_HP_E_MP = 7
ALTURA_DA_BARRA = 8

# Região de busca do quadro do alvo, ancorada no TOPO CENTRAL da janela.
# Medido em 1024x768: o centro da barra está em ~(528, 48).
# A faixa horizontal vai de 30% a 70% da largura (mesma lógica de antes).
# A faixa vertical vai do topo (y=0) até y=140 na base 1024x768.
# Usamos _from_base com âncora TOP_CENTER para escalar corretamente.
def _regiao_quadro_alvo(largura: int, altura: int) -> tuple[int, int, int, int]:
    """Região (x0, y0, x1, y1) onde buscar o quadro do alvo, para a janela dada."""
    # x: 30% a 70% da largura (relativo ao centro)
    x0 = int(largura * 0.30)
    x1 = int(largura * 0.70)
    # y: 0 a 140 na base 1024x768, ancorado no topo
    # TOP_CENTER anchor: origem é (largura//2, 0)
    # Ponto base medido: y=140 no topo -> dy = 140
    spot_y_max = coords_mod._from_base(0, 140, coords_mod.Anchor.TOP_CENTER)
    y1 = spot_y_max.at(largura, altura)[1]
    y0 = 0
    return x0, y0, x1, y1


def _corrida_mais_longa(linha: np.ndarray) -> tuple[int, int]:
    """Maior sequência contígua de True. Devolve (início, comprimento)."""
    melhor_i, melhor_n, i = 0, 0, 0
    n = len(linha)
    while i < n:
        if linha[i]:
            j = i
            while j < n and linha[j]:
                j += 1
            if j - i > melhor_n:
                melhor_i, melhor_n = i, j - i
            i = j
        else:
            i += 1
    return melhor_i, melhor_n


# Limiar do marcador de inimigo morto. Sprite pequeno (26x22) num quadro de UI,
# então é alto -- e errar para MAIS é o lado certo: falso positivo aqui declara
# morte e gasta um TAB, falso negativo só devolve o comportamento de hoje.
LIMIAR_DO_MARCADOR_DE_MORTE = 0.85


def alvo_morto_na_tela(
    frame: np.ndarray | None,
    template: np.ndarray | None,
) -> bool | None:
    """O marcador de "inimigo morto" está no quadro do alvo?

    `True` = está lá, e é CONFIRMAÇÃO de morte. `False` = não está, e isso **NÃO
    é confirmação de vida** -- é só ausência do marcador. `None` = não deu para
    olhar (sem quadro ou sem template).

    Quem consome só pode agir no `True`. Tratar `False` como "está vivo"
    reintroduziria o defeito que o `VigiaDoAlvo` existe para corrigir: "não sei"
    valendo como resposta.

    PROCURA SÓ NA FAIXA DO QUADRO DO ALVO, a mesma que `vida_do_alvo` usa (topo
    do meio da tela). Não é economia: o quadro do PRÓPRIO personagem fica no
    canto superior esquerdo e é igual, então varrer a tela inteira arriscaria
    confundir os dois -- e "eu morri" lido como "o mob morreu" é o pior desfecho
    possível.
    """
    if frame is None or frame.size == 0 or template is None:
        return None

    altura, largura = frame.shape[:2]
    x0, y0, x1, y1 = _regiao_quadro_alvo(largura, altura)
    regiao = (x0, y0, x1 - x0, y1 - y0)
    if regiao[2] <= 0 or regiao[3] <= 0:
        return None

    achou, _escore = marcador_de_morte(frame, template, regiao=regiao)
    return achou


def marcador_de_morte(
    frame: np.ndarray | None,
    template: np.ndarray | None,
    regiao: tuple[int, int, int, int] | None = None,
) -> tuple[bool | None, float | None]:
    """O mesmo que `alvo_morto_na_tela`, mas devolve o ESCORE junto.

    ==================================================================
    POR QUE O ESCORE PRECISA SAIR DAQUI
    ==================================================================

    Medido em produção em 19/08/2026: **69 leituras seguidas, nenhuma achou o
    marcador**, e o bot ficou 38 s batendo num cadáver sem dar TAB. Com só
    `True`/`False` na mão não há como saber QUAL das três coisas está errada:

      * o limiar (`LIMIAR_DO_MARCADOR_DE_MORTE`) está alto demais;
      * a faixa (`FAIXA_DO_QUADRO_DE_ALVO`) não contém o marcador;
      * ou o marcador simplesmente não está na tela nesse estado.

    Um `False` não distingue "casou 0,84 e faltou 0,01" de "casou 0,12". Então o
    escore vai para o LOG -- não para a decisão -- e a próxima run responde por
    medição. É o mesmo desenho do `loot_window_open()`: quem não decide, informa.

    `escore` é `None` só quando não deu para olhar.
    """
    if frame is None or frame.size == 0 or template is None:
        return None, None

    if regiao is None:
        altura, largura = frame.shape[:2]
        x0, y0, x1, y1 = _regiao_quadro_alvo(largura, altura)
        regiao = (x0, y0, x1 - x0, y1 - y0)

    rx, ry, rw, rh = regiao
    if rw <= 0 or rh <= 0:
        return None, None

    cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)[ry:ry + rh, rx:rx + rw]
    if (cinza.shape[0] < template.shape[0]
            or cinza.shape[1] < template.shape[1]):
        return None, None

    escore = float(cv2.minMaxLoc(
        cv2.matchTemplate(cinza, template, cv2.TM_CCOEFF_NORMED))[1])
    return escore >= LIMIAR_DO_MARCADOR_DE_MORTE, escore


def marcador_de_morte_em_cor(
    frame: np.ndarray | None,
    template_colorido: np.ndarray | None,
    regiao: tuple[int, int, int, int] | None = None,
) -> tuple[float | None, float | None]:
    """O mesmo marcador, casado em COR, e a fração de VERMELHO onde ele casou.

    ==================================================================
    POR QUE EM COR, E POR QUE ISTO AINDA NÃO DECIDE
    ==================================================================

    Medido em 20/08/2026, com o bot dando três TAB em nove segundos num mob de
    35 de vida, fonte única `marcador de morte na tela`, escore **0,971**:

        EnemyDead.png    128 x 22
        em CINZA         min 2, max 98, média 39,7, desvio 23,3
                         a linha do meio é 27 chapado
        em COR           B 61,4   G 36,4   R 37,9      -- AZULADO
        vermelhos        161 de 2816 pixels = **5,7%**

    Uma barra VIVA a 35% tem ~35% de vermelho. Em cinza, com
    `TM_CCOEFF_NORMED` -- que normaliza brilho e contraste --, vermelho médio e
    cinza escuro ficam parecidos; **em cor não ficam.**

    É o MESMO defeito já medido no `boss_2_fase.png`: em cinza a fase 1 marcava
    0,874 e teria disparado a Break Soul no primeiro segundo; em cor caiu para
    0,792 contra 0,985 da fase 2, e o vão apareceu. Mesma classe, mesma cura.

    **DEVOLVE NÚMERO, NÃO VEREDITO**, e é decisão: o limiar em cor não está
    medido, e escolher um "no olho" é o que este projeto proíbe. Os dois valores
    vão para o LOG ao lado do escore em cinza; quando houver runs suficientes, o
    vão entre morto e vivo aparece e aí o limiar entra com medição atrás.

    A fração de vermelho é calculada com o MESMO teste de `vida_do_alvo` -- um
    número lido por dois lados mora num lugar só.
    """
    if frame is None or frame.size == 0 or template_colorido is None:
        return None, None
    if template_colorido.ndim != 3:
        return None, None

    if regiao is None:
        altura, largura = frame.shape[:2]
        x0, y0, x1, y1 = _regiao_quadro_alvo(largura, altura)
        regiao = (x0, y0, x1 - x0, y1 - y0)

    rx, ry, rw, rh = regiao
    if rw <= 0 or rh <= 0:
        return None, None

    zona = frame[ry:ry + rh, rx:rx + rw]
    th, tw = template_colorido.shape[:2]
    if zona.shape[0] < th or zona.shape[1] < tw:
        return None, None

    mapa = cv2.matchTemplate(zona, template_colorido, cv2.TM_CCOEFF_NORMED)
    _minv, escore, _minl, local = cv2.minMaxLoc(mapa)
    recorte = zona[local[1]:local[1] + th, local[0]:local[0] + tw].astype(int)
    b, g, r = recorte[:, :, 0], recorte[:, :, 1], recorte[:, :, 2]
    vermelho = (r > 90) & (r > g * 1.6) & (r > b * 1.6)
    return float(escore), float(vermelho.mean())


# ===========================================================================
# A SEGUNDA FASE DO BOSS, LIDA NA TELA
# ===========================================================================
#
# Limiar do casamento da barra de vida AMARELA da fase 2, e ele é EM COR por
# necessidade medida, não por gosto.
#
#     o modelo contra SI MESMO          cinza 1.000   cor 1.000
#     o modelo contra a FASE 1          cinza 0.874   cor 0.792
#     fase 2 degradada (jpeg 70+ruído)                cor 0.985
#     fase 2 com 12% menos brilho                     cor 1.000
#
# EM CINZA A FASE 1 MARCA 0,874 -- acima do limiar que este arquivo usa para
# marcador de UI (0,85). Ou seja, em cinza a Break Soul começaria a sair no
# primeiro segundo da luta do boss, que é EXATAMENTE o defeito que ela existe
# para evitar. É a mesma lição que `TemplateLibrary.load_color` já traz medida:
# forma igual e matiz diferente é indistinguível em luminância.
#
# Em cor sobra um vão limpo entre 0,792 e 0,985. `0.92` fica no meio dele, e é o
# mesmo valor que o `package_courage` já usa em cor.
#
# (A fase 1 usada na medição é SINTÉTICA: o mesmo recorte com a faixa de vida
# recolorida para o vermelho saturado que `vida_do_alvo` procura, preservando a
# luminância linha a linha. O que ela mede é a pergunta certa -- "cinza separa
# duas barras de mesma forma e matiz diferente?" -- e a resposta é não.)
LIMIAR_DA_FASE_2_DO_BOSS = 0.92


def boss_na_segunda_fase(
    frame: np.ndarray | None,
    template: np.ndarray | None,
) -> bool | None:
    """A barra AMARELA -- a primeira das duas vidas da fase 2 -- está na tela?

    ===================================================================
    A FASE 2 TEM DUAS BARRAS DE VIDA, E A AMARELA É A PRIMEIRA
    ===================================================================

    Palavras do usuário: *"a segunda fase do boss tem 2 barras de vida, uma
    amarela que é a primeira e depois que terminar a amarela vem a barra
    vermelha, normal como outros mobs; aí quando zera a barra vermelha ele
    morre."*

    Então o amarelo é um SINAL COM PRAZO: ele existe só no primeiro trecho da
    fase 2, no MESMO lugar da barra de vida, e depois dá lugar ao vermelho de
    sempre. Duas consequências de projeto:

    1. **A bandeira que ele levanta é LATCH -- nunca baixa.** Quem lê isto a cada
       segundo enquanto a bandeira está baixa pega o amarelo com folga (é uma
       barra de vida inteira de boss, não um piscar), e depois PARA de olhar. Se
       a bandeira pudesse baixar num `False`, a Break Soul sairia de rotação
       exatamente na metade final da fase 2 -- a que decide a run.
    2. **Ausência de amarelo não é fase 1.** Pode ser fase 2 já no vermelho. Por
       isso `False` não é resposta, só ausência de sinal.

    `True` = está lá, e é CONFIRMAÇÃO de que a segunda fase começou. `False` =
    não está, e isso **NÃO é prova de que a luta está na fase 1** -- é só
    ausência do sinal (barra fora da faixa, alvo trocado, captura ruim no
    instante). `None` = não deu para olhar.

    Quem consome só pode agir no `True`, e a bandeira que ele levanta NUNCA
    baixa por um `False` -- mesma regra do `alvo_morto_na_tela`, e pelo mesmo
    motivo: "não sei" valendo como resposta é o defeito que o `VigiaDoAlvo`
    existe para corrigir.

    ===================================================================
    O RECORTE É O PAR HP+MP DO QUADRO DO ALVO -- MEDIDO
    ===================================================================

    Rodando os MESMOS testes de cor do `vida_do_alvo` sobre o modelo:

        linhas 15-20   100% "azul"        -> é a barra de MANA
        linhas  2- 9     0% "vermelho"    -> é a barra de VIDA, e ela é AMARELA
        linha   1      100% "vermelho"    -> a borda, que `vida_do_alvo` descarta

    E a geometria fecha com as constantes que já estavam aqui: mana começando em
    y=15 põe `fim = 15 - LINHAS_ENTRE_HP_E_MP = 8` e `comeco = 1`, então a faixa
    de vida lida é `[2:9]` -- exatamente as linhas amarelas. Ou seja: o amarelo
    ocupa a MESMA fatia de tela que a barra vermelha ocupa nas outras lutas, o
    que confirma que ele é a primeira vida da fase 2 e não um enfeite ao lado.

    O recorte é um PEDAÇO do meio da barra (sem as pontas), então casa em
    qualquer x enquanto a barra for mais larga que ele -- e a barra só encurta à
    medida que a primeira vida cai, muito depois de a bandeira ter subido.

    ===================================================================
    CONSEQUÊNCIA QUE NÃO ERA O PEDIDO: `vida_do_alvo` LÊ 0.0 NA FASE 2
    ===================================================================

    Enquanto a primeira vida da fase 2 está na tela ela é AMARELA, falha no teste
    `r > g * 1.6`, e a fração de "vermelho" na faixa sai ZERO. Medido, colando o
    recorte na faixa do quadro do alvo com largura de barra realista:
    **`vida_do_alvo` devolve `0.0`**, que neste arquivo significa "barra vazia com
    o quadro presente: o mob morreu".

    O trecho é limitado -- assim que o amarelo acaba, o vermelho volta e a leitura
    volta a valer. Mas "limitado" aqui é uma barra de vida inteira de boss.

    NÃO É DEFEITO ATIVO, e é por sorte de desenho: o veredito de morte só é
    consultado quando quem chama pede TAB (`if tabs_ao_morrer and ...`), e a luta
    do boss usa `tabs_ao_morrer=0` -- quem encerra o boss é SAIR DE BATALHA. Então
    ninguém pergunta, e a leitura errada nunca é usada.

    É BOMBA ARMADA, e fica registrada aqui em vez de "consertada": alargar o
    teste de vermelho para aceitar amarelo mexeria no número que descarta o FUNDO
    ALARANJADO DA CAVERNA (vermelho alto com verde alto junto -- ver o comentário
    em `vida_do_alvo`), e amarelo é exatamente isso. Trocaria um defeito dormente
    por um falso positivo na leitura de vida dos guardas. Ver
    `docs/decisoes/combate.md`.

    ===================================================================
    A FAIXA, E POR QUE ELA NÃO PODE SER A TELA INTEIRA
    ===================================================================

    Mesma região do `vida_do_alvo` e do `alvo_morto_na_tela` (topo central).
    O quadro do PRÓPRIO personagem fica no canto superior esquerdo e é um par
    HP+MP igual, e o painel de time também mora na esquerda -- varrer a tela
    inteira faria "a MINHA barra" ou "a barra de um aliado" levantar a bandeira da
    fase 2. A faixa começa em 30% da largura, então os dois ficam de fora.
    """
    if frame is None or frame.size == 0 or template is None:
        return None

    altura, largura = frame.shape[:2]
    x0, y0, x1, y1 = _regiao_quadro_alvo(largura, altura)
    regiao = (x0, y0, x1 - x0, y1 - y0)
    if regiao[2] <= 0 or regiao[3] <= 0:
        return None

    # `find_all_templates` e não `find_template` porque só ele sabe comparar em
    # COR -- o `find_template` converte para cinza sempre, e em cinza a fase 1
    # marca 0,874. O custo do NMS sobre uma região de ~409x140 é irrelevante, e
    # de brinde vem o guarda de `ndim` que grita quando a carga do modelo erra o
    # modo, em vez de devolver "não tem" silenciosamente.
    return bool(find_all_templates(frame, template,
                                   threshold=LIMIAR_DA_FASE_2_DO_BOSS,
                                   region=regiao, colorido=True))


# ===========================================================================
# A BARRA DO ALVO POR OFFSET FIXO -- medida pelo usuário em 25/08/2026
# ===========================================================================
#
# A medição foi feita com um calibrador que mostra a posição do cursor RELATIVA
# À ÁREA DE CLIENTE (via `ClientToScreen`) e a cor do pixel embaixo dele:
#
#     x=600, y=47   (188-190, 0, 2-3)   vermelho -- ponta presa ao retrato
#     x=539, y=47   (190, 0, 2)         vermelho -- meio da barra
#     x=466, y=47   (188, 0, 3)         vermelho -- outra ponta
#     x=529, y=50   ( 55, 9, 45)        roxo escuro -- a cor do VAZIO
#
# ---------------------------------------------------------------------------
# A BARRA NÃO ESCALA COM A RESOLUÇÃO, E ISSO FOI CONFIRMADO EM DUAS
# ---------------------------------------------------------------------------
#
# O usuário trocou o jogo de 1024x768 para 1680x1050 **sem mexer em coordenada
# nenhuma** e a leitura continuou acompanhando o dano de 100% a 0%. Ou seja: a
# barra fica sempre no mesmo offset a partir do canto superior esquerdo da área
# de cliente.
#
# Isso não contraria o `CLAUDE.md` -- CONFIRMA a regra que ele já escreve
# ("a UI do jogo NÃO escala"). Quem estava fora da regra era a busca por faixa
# PROPORCIONAL (`largura * 0.30`) que este arquivo usava, e ela quebra fora de
# 1024: a 1680 de largura a faixa começa em x=504, e os 466 da barra ficam de
# fora -- sobram 96 px dos 134, abaixo de `LARGURA_MINIMA_DA_BARRA`, e a leitura
# devolvia `None` para sempre.
BARRA_DO_ALVO_X0 = 466
BARRA_DO_ALVO_X1 = 600            # exclusivo -> 134 colunas
BARRA_DO_ALVO_Y0 = 46
BARRA_DO_ALVO_Y1 = 49             # exclusivo -> 3 linhas

# A fração da faixa que precisa ser reconhecida (vida ou vazio) para a leitura
# valer. Abaixo disso o recorte está olhando outra coisa -- e a resposta certa é
# "não sei", nunca um número.
#
# ISTO É O CONSERTO DO DEFEITO MEDIDO EM 21/08: na conta APP a leitura antiga
# devolveu float confiante com piso em 14,2%, 14 valores distintos e vãos --
# estava medindo um retângulo que não era a barra do alvo, e não tinha como
# dizer isso.
MINIMO_RECONHECIDO_NA_FAIXA = 0.70


@dataclass(frozen=True)
class LeituraDaBarra:
    """O que a faixa da barra do alvo mostra AGORA.

    Contagem por COLUNA, não por área, e a diferença é medida: a leitura antiga
    dividia pixels vermelhos pela área inteira do retângulo, então a borda e as
    linhas de cima diluíam o valor -- era daí que vinha o piso de 0,7% que o
    usuário via com o mob morto. Coluna cheia é coluna de vida; coluna vazia é
    coluna vazia.
    """

    vermelho: float                 # 0..1 das colunas
    amarelo: float                  # 0..1 das colunas
    vazio: float                    # 0..1 das colunas
    colunas: int
    primeiro_x: int | None          # primeira coluna com VIDA (relativa à faixa)
    ultimo_x: int | None            # última coluna com VIDA
    fonte: str                      # "offset_fixo" | "ancora_azul"

    @property
    def vida(self) -> float:
        """A fração da barra DESENHADA agora.

        Com as duas barras do boss sobrepostas, a que está por cima é a amarela;
        enquanto ela existe, é ela que está descendo. Quando ela acaba, a
        vermelha que estava por baixo passa a ser a barra da vez.
        """
        return self.amarelo if self.amarelo > 0.0 else self.vermelho

    @property
    def na_segunda_fase(self) -> bool:
        """Amarelo na faixa = as duas barras estão sobrepostas = fase 2."""
        return self.amarelo > 0.0

    def total_do_boss(self, segunda_fase: bool) -> float:
        """Vida TOTAL do boss em 0..1, juntando as duas barras.

        Palavras do usuário: *"a barra amarela sobrepõe a vermelha e conforme
        ela vai baixando vai aparecendo a vermelha"*, e *"amarelo na tela você
        começa em 100% e quando vier o vermelho quer dizer que é 50% para
        menos"*.

        Então, com a amarela na tela, o total vai de 100% a 50%; sem ela, na fase
        2, a vermelha vai de 50% a 0%. Na fase 1 a vermelha é a vida inteira.
        """
        if self.amarelo > 0.0:
            return 0.5 + 0.5 * self.amarelo
        return 0.5 * self.vermelho if segunda_fase else self.vermelho


def _classificar_colunas(faixa: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Classifica cada COLUNA da faixa em vermelho / amarelo / vazio.

    Uma coluna vale pelo que a MAIORIA das suas linhas mostra. Três linhas com
    ruído de compressão em uma não estragam a coluna, e uma linha isolada de
    borda não cria vida onde não tem.

    As cores vêm da medição do usuário (vermelho `(188-190, 0, 2-3)`, vazio
    `(55, 9, 45)`), com folga para brilho e compressão. **O AMARELO NÃO FOI
    MEDIDO** -- é a única cor aqui por dedução (vermelho e verde altos, azul
    baixo), e o log grava a contagem bruta justamente para a primeira luta de
    boss confirmá-la ou derrubá-la.
    """
    b = faixa[:, :, 0].astype(int)
    g = faixa[:, :, 1].astype(int)
    r = faixa[:, :, 2].astype(int)

    vermelho = (r > 120) & (g < 70) & (b < 70)
    amarelo = (r > 120) & (g > 100) & (b < 90)
    vazio = (r < 100) & (g < 60) & (b < 100) & ((r + b) > 30)

    metade = faixa.shape[0] / 2.0
    return (vermelho.sum(axis=0) > metade,
            amarelo.sum(axis=0) > metade,
            vazio.sum(axis=0) > metade)


def ler_barra_do_alvo(frame: np.ndarray | None) -> LeituraDaBarra | None:
    """A faixa da barra do alvo, no offset fixo medido. `None` = não sei.

    NÃO PROCURA NADA. A posição é conhecida (ver o bloco de `BARRA_DO_ALVO_X0`),
    então não há corrida azul para achar, não há geometria para escorregar, e não
    há como acabar medindo a barra do próprio personagem ou a de um membro do
    time -- que foi o que produziu o piso de 14,2% na conta APP.

    A única forma de errar que sobra é o recorte cair fora do quadro do alvo, e
    contra isso existe `MINIMO_RECONHECIDO_NA_FAIXA`: se as cores da faixa não
    forem as da barra, a resposta é `None`.
    """
    if frame is None or frame.size == 0:
        return None
    altura, largura = frame.shape[:2]
    if largura < BARRA_DO_ALVO_X1 or altura < BARRA_DO_ALVO_Y1:
        return None

    faixa = frame[BARRA_DO_ALVO_Y0:BARRA_DO_ALVO_Y1,
                  BARRA_DO_ALVO_X0:BARRA_DO_ALVO_X1]
    if faixa.size == 0:
        return None

    col_vermelho, col_amarelo, col_vazio = _classificar_colunas(faixa)
    colunas = int(col_vermelho.size)
    if colunas == 0:
        return None

    reconhecidas = int((col_vermelho | col_amarelo | col_vazio).sum())
    if reconhecidas < colunas * MINIMO_RECONHECIDO_NA_FAIXA:
        return None

    com_vida = col_vermelho | col_amarelo
    onde = np.where(com_vida)[0]
    return LeituraDaBarra(
        vermelho=float(col_vermelho.sum()) / colunas,
        amarelo=float(col_amarelo.sum()) / colunas,
        vazio=float(col_vazio.sum()) / colunas,
        colunas=colunas,
        primeiro_x=int(onde[0]) if onde.size else None,
        ultimo_x=int(onde[-1]) if onde.size else None,
        fonte="offset_fixo",
    )


def _barra_vermelha_e_hp_valida(faixa: np.ndarray) -> bool:
    """Valida que a faixa vermelha se comporta como barra de HP:
    - preenche da ESQUERDA para direita (sem buracos grandes no meio)
    - é contígua (uma única corrida principal por linha)
    - não tem 'piso' alto quando deveria ser zero
    - largura geral não aumenta de cima para baixo (monotonicidade grosseira)
    """
    if faixa.size == 0:
        return False

    altura, largura = faixa.shape
    if altura < 2 or largura < 10:
        return False

    # Para cada linha, a barra deve ser uma corrida contígua começando perto do x=0
    # (relativo ao início da barra de mana). HP não tem buracos GRANDES no meio.
    linhas_validas = 0
    for y in range(altura):
        linha = faixa[y]
        if not np.any(linha):
            # Linha totalmente vazia - aceitável em qualquer posição (ruído/compressão)
            # mas contamos apenas linhas com sinal
            continue

        linhas_validas += 1

        # Encontrar primeiro e último pixel True
        primeiros = np.where(linha)[0]
        primeiro = primeiros[0]
        ultimo = primeiros[-1]

        # Deve começar perto do 0 (tolerância 3px por ruído/compressão/jpeg)
        if primeiro > 3:
            return False

        # Não deve ter buracos GRANDES: permitir até 2 buracos de 1px por linha
        # (compressão JPEG pode criar pixels isolados falsos)
        segmento = linha[primeiro:ultimo + 1]
        buracos = np.sum(~segmento)
        if buracos > 2:
            return False

    # Precisa de pelo menos 2 linhas com sinal (ruído pode matar linhas isoladas)
    if linhas_validas < 2:
        return False

    # Verificar monotonicidade geral: largura não deve aumentar de cima para baixo
    # (a barra de HP só encurta, nunca alonga, à medida que a vida cai)
    # Tolerância maior (5px) para ruído de captura/compressão
    larguras = [np.sum(faixa[y]) for y in range(altura) if np.any(faixa[y])]
    for i in range(1, len(larguras)):
        if larguras[i] > larguras[i - 1] + 5:
            return False

    return True


# ===========================================================================
# INTERRUPTOR: o offset fixo é a régua; a âncora azul é a reserva
# ===========================================================================
#
# `True`  = lê pelo offset medido (`ler_barra_do_alvo`) e só cai para a busca
#           pela barra de mana se o recorte não reconhecer a faixa.
# `False` = comportamento anterior, só a busca pela âncora azul.
#
# A reserva NÃO é enfeite: o offset fixo foi medido em DUAS resoluções, mas em
# um cliente só. Se um dia a barra sair do lugar, a busca ainda acha -- e o
# `fonte` da leitura diz no log qual das duas respondeu, então trocar de régua
# no meio da run não passa despercebido.
USAR_OFFSET_FIXO_DA_BARRA = True


def vida_do_alvo(frame: np.ndarray | None) -> float | None:
    """Fração de vida da barra DESENHADA do alvo (0.0 a 1.0), ou `None`.

    `None` quando o quadro não foi encontrado -- sem alvo, quadro expirado
    depois da morte, ou captura ruim. Quem chama decide o que fazer com isso;
    aqui não se adivinha.

    `0.0` é a barra VAZIA com o quadro presente: o mob morreu.

    NA FASE 2 DO BOSS ELA DEVOLVE A AMARELA, que é a barra de cima. Quem precisa
    da vida TOTAL das duas usa `ler_barra_do_alvo(...).total_do_boss(...)` -- a
    conta de juntar as duas mora lá, num lugar só.
    """
    if USAR_OFFSET_FIXO_DA_BARRA:
        leitura = ler_barra_do_alvo(frame)
        if leitura is not None:
            return leitura.vida
    return _vida_por_ancora_azul(frame)


def _vida_por_ancora_azul(frame: np.ndarray | None) -> float | None:
    """A RESERVA: acha a barra de mana e mede a vida logo acima dela.

    Era a régua principal até 25/08/2026. Continua inteira porque ela não depende
    de a barra estar num lugar conhecido -- só de ela estar acima de uma corrida
    azul longa. Ver `USAR_OFFSET_FIXO_DA_BARRA`.
    """
    if frame is None or frame.size == 0:
        return None

    altura, largura = frame.shape[:2]
    x0, y0, x1, y1 = _regiao_quadro_alvo(largura, altura)
    if x1 <= x0 or y1 <= y0:
        return None

    zona = frame[y0:y1, x0:x1].astype(int)
    if zona.size == 0:
        return None

    b, g, r = zona[:, :, 0], zona[:, :, 1], zona[:, :, 2]
    # Os limiares de cor vêm dos prints: a barra de mana é azul saturado e a de
    # vida é vermelho saturado. Exigir dominância sobre os OUTROS dois canais
    # (e não só valor alto) é o que descarta o fundo alaranjado da caverna, que
    # tem vermelho alto mas verde alto junto.
    azul = (b > 90) & (b > r * 1.4) & (b > g * 1.2)
    vermelho = (r > 90) & (r > g * 1.6) & (r > b * 1.6)

    for y in range(azul.shape[0]):
        inicio, comprimento = _corrida_mais_longa(azul[y])
        if comprimento < LARGURA_MINIMA_DA_BARRA:
            continue

        # Achou a barra de mana. A de vida termina `LINHAS_ENTRE_HP_E_MP` acima,
        # e a primeira linha dela é borda -- descartada (ver o comentário acima).
        fim = y - LINHAS_ENTRE_HP_E_MP
        comeco = fim - ALTURA_DA_BARRA + 1
        if comeco < 0:
            continue  # tenta próxima linha de mana, não aborta tudo

        faixa = vermelho[comeco + 1:fim + 1, inicio:inicio + comprimento]
        if faixa.size == 0:
            continue

        # VALIDAÇÃO CRÍTICA: a faixa vermelha deve se comportar como HP.
        # Isso descarta a mana do próprio personagem / membros do time no APP,
        # que têm geometria parecida mas a "vida" medida não é uma barra contígua
        # preenchendo da esquerda (piso 14.2%, vãos, valores discretos).
        if not _barra_vermelha_e_hp_valida(faixa):
            continue

        return float(faixa.sum()) / float(faixa.size)

    # Não encontrou barra azul de mana válida COM vida válida abaixo =
    # quadro do alvo não está na tela (sem alvo, alvo morto, captura ruim,
    # ou azul achado era de outro elemento UI).
    # Retornar None em vez de float confiante errado é a correção do defeito
    # medido no APP (piso 14.2%, vãos, 21 valores discretos) e na BC (geometria
    # instável: 4 larguras diferentes na mesma coleta).
    return None
