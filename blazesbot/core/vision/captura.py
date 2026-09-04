"""
Captura da janela do cliente -- PrintWindow, BitBlt, GdiPool.

É o subdomínio de baixo nível: lê pixels da janela do jogo. Tudo o que vem
depois (templates, marcadores, barra) consome o BGR que esta parte devolve.

A captura usa PrintWindow com PW_RENDERFULLCONTENT, que funciona com janela
em background e, na maioria dos casos, minimizada. Se voltar quadro preto,
o cliente precisa estar visível (ver README).
"""
from __future__ import annotations

import cv2
import numpy as np
import win32con
import win32gui
import win32ui

PW_RENDERFULLCONTENT = 0x00000002

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
