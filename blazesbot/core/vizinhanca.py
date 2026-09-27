"""QUEM ESTÁ EM VOLTA — a pergunta que separa "não tem mob" de "não estou agindo".

Nasceu no ciclo da morte (*"morri com um mob só ou com quatro em cima?"*) e subiu
para o `core/` em 06/09/2026, quando o mesmo dado passou a ser necessário na
aquisição de alvo. O caso que forçou a promoção está no log daquele dia:

```
20:25:18  APP: o TAB não trouxe mob vivo (1 salto) — só cadáver por aqui.
20:25:20  APP: 1 TAB(s) seguidos e o alvo não mudou — a tecla 'TAB' não pega.
   ...    (96 minutos sem uma única linha, com TAB saindo a cada 2 s)
```

Duas causas produzem exatamente esse silêncio e pedem consertos opostos:

* **não há mob vivo ao alcance** — o bot está certo, o spot esvaziou, e o que
  falta é DIZER isso em vez de calar;
* **há mob e a tecla não chega ao jogo** — o bot está mudo de verdade, e o
  desfecho certo é tratar como queda.

Ler a tabela de entidades responde qual das duas é, e é a única coisa que
responde: a tecla "não pegar" é indistinguível de "não tem o que pegar" olhando
só o `TARGET_ID`.
"""

from __future__ import annotations

from .memory import ESCALA_DE_INIMIGO
from .zones import distancia_linear

# Raio, em unidades de jogo, do que conta como "em volta".
#
# Não é régua de decisão -- é o recorte da pergunta. 40 é largo o bastante para
# pegar o trem de mobs que mata um personagem de macro e estreito o bastante
# para não descrever o spot inteiro.
RAIO = 40


def _e_mob_vivo(entidade) -> bool:
    """A régua de `Memory.inimigos_proximos`: vida máxima na escala 100, vida > 0.

    `entidades_vivas()` devolve também o pet, os jogadores e os cadáveres. Até
    27/09/2026 `contar` contava todos como mob -- com 4 contas APP no mesmo
    ponto, 221 de 246 ERROR de "TAB sem resposta, HÁ mob" tinham o "mob" a 1
    unidade: o companheiro. `resumo` não usa este filtro, de propósito.
    """
    return (entidade.get("max_hp") == ESCALA_DE_INIMIGO
            and (entidade.get("hp") or 0) > 0)


def contar(memoria, raio: int = RAIO) -> tuple[int, float | None]:
    """`(quantos mobs vivos em volta, distância do mais perto)`.

    `(0, None)` também é a resposta para "não deu para ler" -- e quem chama tem
    de tratar os dois casos igual, porque não há como distingui-los sem inventar.
    Ver `resumo` quando o destino for log: lá a diferença aparece em texto.
    """
    try:
        eu = memoria.position()
        if eu is None:
            return 0, None
        distancias = sorted(
            distancia_linear(e["pos"], eu)
            for e in memoria.entidades_vivas()
            if e.get("pos") is not None and _e_mob_vivo(e)
        )
    except Exception:
        return 0, None
    perto = [d for d in distancias if d <= raio]
    return len(perto), (perto[0] if perto else None)


def resumo(memoria, raio: int = RAIO) -> str:
    """A mesma leitura em uma linha de log, com os nomes e as distâncias.

    NUNCA LEVANTA: diagnóstico que derruba quem o chamou é pior que diagnóstico
    nenhum. Falha vira texto, e o texto diz que falhou.
    """
    try:
        eu = memoria.position()
        if eu is None:
            return "vizinhança=? (posição ilegível)"
        perto = []
        for e in memoria.entidades_vivas():
            pos = e.get("pos")
            if pos is None:
                continue
            d = distancia_linear(pos, eu)
            if d <= raio:
                perto.append((d, f"{e.get('nome') or '?'}@{d:.0f}"))
        perto.sort()
        return (f"mobs vivos a até {raio}: {len(perto)} "
                f"[{', '.join(t for _d, t in perto[:8])}]")
    except Exception as exc:
        return f"vizinhança=? ({exc})"

def contar_pelo_injetado(ler) -> tuple[int, float | None]:
    """`(quantos, o mais perto)`. `(0, None)` = nenhum OU não deu para ler.

    A MESMA pergunta de `contar`, para quem recebe a leitura como FUNÇÃO em vez
    de receber a memória -- é o caso do executor do APP, que não abre memória.

    Veio de `bot/app/executor._quantos_mobs_por_perto` em 07/09/2026, quando o
    aviso do teclado mudo subiu para `core/teclado_mudo.py` e passou a precisar
    da mesma resposta. `ler` é injetado -- este módulo não abre memória.

    "NÃO SEI" VIRA `(0, None)`, e quem chama trata os dois iguais de propósito:
    a decisão que depende disto (acusar a tecla ou dizer que o spot está vazio)
    só pode ser tomada com leitura, e sem ela o texto genérico é o honesto.
    """
    if ler is None:
        return 0, None
    try:
        return ler()
    except Exception:
        return 0, None
