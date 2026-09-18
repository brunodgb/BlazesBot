"""A AFERIÇÃO DO DELETADOR — fotografa e DESENHA o que casaria, sem apagar.

SAIU DE `bot/deletador.py` EM 18/09/2026, pela catraca de tamanho: o arquivo
bateu em 799 linhas de um teto de 800, e a regra do projeto é que a próxima
linha paga a extração. O corte é o natural — o deletador APAGA, isto aqui só
MOSTRA: não clica em item, não manda tecla e não muda estado nenhum.

COMPORTAMENTO IDÊNTICO: a função veio linha por linha, sem uma alteração.

FICA EM `bot/` E NÃO EM `bot/app/` porque a pergunta que ela responde não é do
APP: "o que seria apagado se eu ligasse isso agora?" vale para qualquer
ecossistema que apague lixo, e `bot/hh/` não pode importar de `bot/app/`.

DEPENDÊNCIA CRUZADA — mexer no deletador mexe aqui. Ela usa as peças internas
dele (`_carregar`, `regioes_visiveis`, `_casamentos_nas_regioes`,
`_achar_icone`) de propósito: a conferência tem de enxergar EXATAMENTE o que a
exclusão enxerga. Duas leituras diferentes fariam a aferição mentir — e o
motivo de ela existir é justamente não confiar nos modelos sem olhar.

Quem chama: `bot/app/afericao.py`.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..core import vision
from . import deletador

if TYPE_CHECKING:
    from .context import BotContext


def conferir(ctx: BotContext, destino: Path | None = None) -> dict[str, Any]:
    """Fotografa a bolsa e DESENHA o que os templates reconheceriam.

    Não clica, não manda tecla, não apaga. Existe porque os 81 templates vieram
    do ver.6139 de OUTRO bot e nunca foram medidos contra o nosso cliente --
    e o custo de descobrir um falso positivo apagando é um item perdido, sem
    desfazer.

    Devolve `{"ok", "erro", "achados", "arquivo"}`; a imagem tem um retângulo
    por casamento, com o nome do modelo e a nota.
    """
    import cv2

    if not deletador.PASTA_DO_LIXO.is_dir():
        return {"ok": False, "erro": f"A pasta {deletador.PASTA_DO_LIXO} não existe.",
                "achados": [], "arquivo": ""}

    quadro = vision.capture_window(ctx.hwnd)
    if quadro is None or vision.frame_is_blank(quadro):
        return {"ok": False, "erro": "Não consegui capturar a tela do jogo.",
                "achados": [], "arquivo": ""}

    templates = deletador._carregar(ctx)
    if not templates:
        return {"ok": False, "erro": f"Nenhum modelo em {deletador.PASTA_DO_LIXO}.",
                "achados": [], "arquivo": ""}

    regioes = deletador.regioes_visiveis(ctx, quadro)
    marcado = quadro.copy()
    # Desenha a REGIÃO antes dos itens: é o que mostra, de relance, que o
    # equipamento ficou de fora da conta.
    for rotulo, (x, y, larg_r, alt_r) in regioes:
        cv2.rectangle(marcado, (x, y), (x + larg_r, y + alt_r), (255, 200, 0), 2)
        cv2.putText(marcado, rotulo, (x, max(10, y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1)

    achados: list[dict[str, Any]] = []
    for nome, tpl in templates.items():
        alt, larg = tpl.shape[:2]
        for centro in deletador._casamentos_nas_regioes(quadro, tpl, regioes):
            achados.append({"modelo": nome, "x": centro[0], "y": centro[1]})
            x0, y0 = centro[0] - larg // 2, centro[1] - alt // 2
            cv2.rectangle(marcado, (x0, y0), (x0 + larg, y0 + alt),
                          (0, 0, 255), 2)
            cv2.putText(marcado, nome, (x0, max(10, y0 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

    icone = deletador._achar_icone(ctx, quadro)
    if icone is not None:
        cv2.circle(marcado, icone, 16, (0, 255, 0), 2)
        cv2.putText(marcado, "deletar", (icone[0] - 24, icone[1] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

    caminho = destino or (Path("logs") / "afericao-do-deletador.png")
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(caminho), marcado)
    except OSError as exc:
        return {"ok": False, "erro": f"Não consegui salvar: {exc}",
                "achados": achados, "arquivo": ""}

    return {"ok": True, "erro": "", "achados": achados,
            "arquivo": str(caminho), "modelos": len(templates),
            "inventario_aberto": icone is not None}
