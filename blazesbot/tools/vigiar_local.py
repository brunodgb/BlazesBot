"""
Vigia o ponteiro do nome do lugar, ao vivo, em todos os clientes abertos.

=========================================================================
PARA QUE SERVE
=========================================================================

O nome do lugar parou de ser lido duas vezes em produção, no personagem que
rodava a BC, e voltou ao normal só depois de fechar e reabrir o jogo. Não
sabemos AINDA em que momento exato ele quebra -- a suspeita é o final da cave,
no covil do boss.

Esta ferramenta responde essa pergunta sem depender do bot: ela fica lendo o
ponteiro a cada segundo, mostra na tela e grava tudo em
`logs\\localizacao.log`. Quando a leitura quebrar, o arquivo terá:

  * o instante exato;
  * a posição do personagem naquele momento (ou seja, ONDE na cave ele estava);
  * o valor de CADA elo da cadeia de ponteiros, que diz se o objeto foi
    liberado, se o ponteiro foi sobrescrito ou se a cadeia mudou;
  * as três interpretações da leitura do texto, com o que cada uma devolveu.

Rode isto em paralelo com o bot e deixe rodando. Da próxima vez que o bug
acontecer, o arquivo já vai ter a resposta.

=========================================================================
COMO LER A SAÍDA
=========================================================================

    PID 54856 | pos=(78,-397) | 8tcher Cave -> 'Bewitcher Cave' (parcial)

  A memória devolveu `'8tcher Cave'` (truncado) e o bot reconheceu como
  `'Bewitcher Cave'`. Isto é NORMAL e não é o bug: a versão nova completa o
  nome pela cauda.

    PID 54856 | pos=(80,-406) | ILEGIVEL | elo +0xF4 = 0x00000000

  Aqui está o bug. O terceiro elo da cadeia virou nulo, o que significa que o
  objeto que guardava o nome deixou de existir para aquele ponteiro. Se isso
  aparecer sempre na mesma posição, encontramos o gatilho.
"""
from __future__ import annotations

import time

from ..core import diario
from ..core.memory import Memory


def _janela_de(pid: int) -> str:
    import win32gui
    import win32process

    achadas: list[str] = []

    def cb(handle, _extra):
        if not win32gui.IsWindowVisible(handle):
            return True
        try:
            _, dono = win32process.GetWindowThreadProcessId(handle)
        except Exception:
            return True
        if dono == pid:
            achadas.append((win32gui.GetWindowText(handle) or "").strip())
        return True

    try:
        win32gui.EnumWindows(cb, None)
    except Exception:
        pass
    return achadas[0] if achadas else "(sem janela)"


def _texto_do_rastro(rastro: list[tuple[str, int | None]]) -> str:
    partes = []
    for rotulo, valor in rastro:
        if valor is None:
            partes.append(f"{rotulo}=<nao leu>")
        else:
            partes.append(f"{rotulo}=0x{valor:08X}")
    return " -> ".join(partes)


class _Vigia:
    """Estado por cliente: só registra quando algo MUDA.

    Uma linha por segundo por cliente encheria o arquivo e afogaria o momento da
    quebra. O que interessa é a transição -- e o batimento esparso só para provar
    que a ferramenta continuou rodando.
    """

    BATIMENTO = 60.0

    def __init__(self, pid: int, titulo: str) -> None:
        self.pid = pid
        self.titulo = titulo
        self.memoria: Memory | None = None
        self.ultimo_estado: str | None = None
        self.ultimo_batimento = 0.0
        self.quebrou_em: tuple[int, int] | None = None
        self.preso_em: tuple[int, int] | None = None

    @staticmethod
    def _nome_preso(nome: str, posicao: tuple[int, int] | None) -> bool:
        """O nome afirma uma área da cave que a coordenada desmente?"""
        from ..bot.bc import mapa_bc
        from ..core.lugares import e_dentro_da_cave

        return e_dentro_da_cave(nome) and mapa_bc.posicao_esta_fora_da_cave(posicao)

    def abrir(self) -> bool:
        try:
            self.memoria = Memory(self.pid)
            return True
        except Exception as exc:
            print(f"PID {self.pid}: não consegui abrir o processo ({exc}). "
                  "Está rodando como administrador?")
            return False

    def fechar(self) -> None:
        if self.memoria is not None:
            self.memoria.close()
            self.memoria = None

    def passo(self) -> str:
        """Uma leitura. Devolve a linha para mostrar na tela."""
        assert self.memoria is not None
        m = self.memoria
        agora = time.time()

        posicao = m.position()
        hp = m.hp()
        detalhe = m.location_detail()
        nome = detalhe.get("nome")
        brutos = detalhe.get("brutos") or {}
        reconhecimento = detalhe.get("reconhecimento")

        if posicao is None and hp is None:
            linha = f"PID {self.pid:>6} | fora do mundo (login, fila ou carregando)"
            estado = "fora"
        elif nome and self._nome_preso(nome, posicao):
            # A OUTRA FORMA DE QUEBRA. Esta ferramenta foi escrita para o nome
            # ILEGÍVEL, e por isso classificava como "ok" um nome que lê e mente:
            # imprimia `pos=(1395,-629) | 'Secret Cemetery' (exato)` sem estranhar
            # que a coordenada estivesse a mil unidades da cave. Era o que estava
            # na tela do usuário enquanto o bot se perdia.
            linha = (f"PID {self.pid:>6} | pos={posicao} | NOME PRESO em "
                     f"{nome!r} -- a coordenada está FORA da cave")
            estado = f"preso:{nome}"
            if self.preso_em is None:
                self.preso_em = posicao
                diario.localizacao().warning(
                    "VIGIA | %s (PID %s) | NOME PRESO | pos=%s hp=%s | "
                    "memória=%r | o cliente não reescreveu o campo ao sair da "
                    "instância | leituras=%s",
                    self.titulo, self.pid, posicao, hp, nome, brutos,
                )
                print("       ^-- o nome do lugar está PRESO numa área da cave "
                      "estando o personagem")
                print("           FORA dela. Vale a coordenada. Entrar na cave "
                      "de novo reescreve o campo.")
        elif nome:
            bruto_principal = next(iter(brutos.values()), "")
            linha = (f"PID {self.pid:>6} | pos={posicao} | "
                     f"{bruto_principal!r} -> {nome!r} ({reconhecimento})")
            estado = f"ok:{nome}:{reconhecimento}"
            if self.preso_em is not None:
                diario.localizacao().info(
                    "VIGIA | %s (PID %s) | NOME LIBERADO | pos=%s nome=%r "
                    "(havia travado em %s)",
                    self.titulo, self.pid, posicao, nome, self.preso_em,
                )
                print(f"       ^-- DESTRAVOU (o nome havia ficado preso em "
                      f"{self.preso_em})")
                self.preso_em = None
            if self.quebrou_em is not None:
                diario.localizacao().info(
                    "VIGIA | %s (PID %s) | RECUPERADO sem reabrir o jogo | "
                    "pos=%s nome=%r",
                    self.titulo, self.pid, posicao, nome,
                )
                print(f"       ^-- RECUPEROU sozinho (havia quebrado em "
                      f"{self.quebrou_em})")
                self.quebrou_em = None
        else:
            rastro = _texto_do_rastro(m.location_trace())
            linha = (f"PID {self.pid:>6} | pos={posicao} | ILEGIVEL | "
                     f"leituras={brutos} | {rastro}")
            estado = f"ilegivel:{detalhe.get('ponteiro')}"
            if self.quebrou_em is None:
                self.quebrou_em = posicao
                diario.localizacao().warning(
                    "VIGIA | %s (PID %s) | QUEBROU AQUI | pos=%s hp=%s | "
                    "ponteiro=%s | leituras=%s | %s",
                    self.titulo, self.pid, posicao, hp,
                    detalhe.get("ponteiro"), brutos, rastro,
                )
                print("       ^-- PRIMEIRA falha desta janela; gravada em "
                      "logs\\localizacao.log")

        if estado != self.ultimo_estado:
            self.ultimo_estado = estado
            self.ultimo_batimento = agora
            diario.localizacao().info("VIGIA | %s (PID %s) | %s",
                                      self.titulo, self.pid, linha)
        elif agora - self.ultimo_batimento >= self.BATIMENTO:
            self.ultimo_batimento = agora
            diario.localizacao().debug("VIGIA | %s (PID %s) | %s",
                                       self.titulo, self.pid, linha)
        return linha


def run(intervalo: float = 1.0) -> int:
    """Laço principal. Ctrl+C encerra."""
    from ..bot.watchdog import client_pids

    print("BlazesBot — vigia do ponteiro de localização")
    print("=" * 72)
    print("Deixe rodando em paralelo com o bot. Ctrl+C para sair.")
    print("Tudo também é gravado em logs\\localizacao.log — é esse arquivo")
    print("que responde onde e quando o ponteiro quebra.")
    print("=" * 72)

    diario.localizacao().info("VIGIA | inicio da vigilancia")
    vigias: dict[int, _Vigia] = {}

    try:
        while True:
            pids = sorted(client_pids())

            # Solta clientes que fecharam, para não segurar handle morto.
            for pid in list(vigias):
                if pid not in pids:
                    vigias.pop(pid).fechar()

            if not pids:
                print("nenhum client.exe aberto — esperando…")

            for pid in pids:
                if pid not in vigias:
                    vigia = _Vigia(pid, _janela_de(pid))
                    if not vigia.abrir():
                        continue
                    vigias[pid] = vigia
                try:
                    print(vigias[pid].passo())
                except Exception as exc:
                    print(f"PID {pid}: erro ao ler ({exc})")
                    vigias.pop(pid).fechar()

            if pids:
                print("-" * 72)
            time.sleep(intervalo)
    except KeyboardInterrupt:
        print("\nencerrado.")
    finally:
        for vigia in vigias.values():
            vigia.fechar()
        diario.localizacao().info("VIGIA | fim da vigilancia")
    return 0
