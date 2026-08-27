"""
BlazesBot — ponto de entrada.

Modos:
    python main.py               interface gráfica
    python main.py --check       diagnóstico de memória (rode isto primeiro)
    python main.py --headless    roda com a config salva, sem interface

O modo --check é obrigatório antes do primeiro uso: ele confirma se o mapa
de offsets ainda vale para a sua versão do cliente.
"""
from __future__ import annotations

import argparse
import ctypes
import logging
import sys
from pathlib import Path

from blazesbot.config import DEFAULT_CONFIG_PATH, BotConfig


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def require_admin() -> None:
    """O bot precisa de elevação. Não é opcional.

    O jogo roda elevado, e o Windows aplica UIPI: um processo de integridade
    média não consegue enviar mensagens de janela para um processo elevado
    nem abrir handle da memória dele. Sem admin, as mensagens são
    descartadas SILENCIOSAMENTE — nenhum erro, simplesmente nada acontece.
    """
    if is_admin():
        return
    print("=" * 68)
    print("  ERRO: o BlazesBot precisa ser executado COMO ADMINISTRADOR.")
    print()
    print("  O cliente do jogo roda elevado. Sem elevação, o Windows bloqueia")
    print("  tanto a leitura de memória quanto o envio de cliques e teclas —")
    print("  e faz isso sem gerar erro, o que torna o problema difícil de")
    print("  diagnosticar: o bot simplesmente não faz nada.")
    print()
    print("  Feche, clique com o botão direito e escolha")
    print("  'Executar como administrador'.")
    print("=" * 68)
    sys.exit(1)


def setup_logging(verbose: bool = True) -> None:
    """Configura o log com dois ambientes (dev/prod) e nível por destino.

    O ambiente vem de ``BLAZES_MODO`` (ver ``blazesbot.core.logmodo``):

      * dev (default) -- DEBUG na interface e nos arquivos de texto, e o JSON
        estruturado de dev em ``logs/dev/blazes-dev.jsonl`` (o que o dev lê
        para debugar). O toggle "log detalhado" da interface liga/desliga o
        DEBUG.
      * prod -- interface e arquivos em INFO+ (visão limpa para o usuário),
        sem toggle de debug e sem ``logs/dev/``: o detalhe de dev só existe na
        máquina de quem desenvolve, nunca na de quem usa o bot.

    O arquivo é sempre escrito, mesmo que a interface falhe -- assim sempre
    existe onde olhar.
    """
    Path("logs").mkdir(exist_ok=True)
    from blazesbot.core import logmodo
    from blazesbot.core.log_json import LogJsonHandler
    from blazesbot.core.log_limitado import LINHAS_MAXIMAS, ArquivoDeLogLimitado

    dev = logmodo.eh_dev()
    # Em dev, `verbose` (a tecla --quiet da GUI) pode forçar INFO; em prod o
    # nível é sempre INFO -- usuário não recebe o detalhe de desenvolvimento.
    nivel = logging.DEBUG if (dev and verbose) else logging.INFO

    formato = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)-28s %(message)s", "%H:%M:%S"
    )

    raiz = logging.getLogger()
    raiz.setLevel(nivel)
    for h in list(raiz.handlers):
        raiz.removeHandler(h)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formato)
    raiz.addHandler(console)

    # Arquivo da sessão atual, sempre recriado, e um histórico acumulado.
    #
    # OS DOIS TÊM TETO DE LINHAS. Passando dele, as mais antigas saem -- o arquivo
    # guarda sempre as últimas `LINHAS_MAXIMAS`. Antes o histórico crescia sem
    # limite nenhum, sessão após sessão.
    # `encoding="utf-8"` EXPLÍCITO nos dois. Sem ele o `FileHandler` usa o
    # encoding do SISTEMA (cp1252 nesta máquina), e qualquer caractere fora dele
    # levanta `UnicodeEncodeError` dentro do `logging` -- a linha some e o
    # traceback vai para o stderr. Descoberto em 25/08/2026 montando o log de
    # vida do alvo; o resto do bot escapou até hoje por sorte, porque acentos
    # cabem no cp1252 e nada mais passou por aqui.
    atual = ArquivoDeLogLimitado(Path("logs") / "sessao-atual.log", mode="w",
                                 encoding="utf-8")
    atual.setFormatter(formato)
    raiz.addHandler(atual)

    historico = ArquivoDeLogLimitado(Path("logs") / "blazesbot.log",
                                     encoding="utf-8")
    historico.setFormatter(formato)
    raiz.addHandler(historico)

    blazes = logging.getLogger("blazes")
    blazes.setLevel(nivel)

    # As últimas linhas de cada conta, guardadas em memória para a hora da
    # queda (tela "Histórico de Quedas"). É AQUI porque este é o único lugar
    # que as duas interfaces já compartilham para configurar log -- e a queda é
    # gravada por uma thread do supervisor, que não conhece interface nenhuma.
    # Idempotente: chamar `setup_logging` de novo não duplica o handler.
    from blazesbot.core.quedas import instalar_captura_de_log

    instalar_captura_de_log()

    extra = ""
    if dev:
        # JSON estruturado de dev, SÓ no ambiente de dev: é o que o
        # desenvolvedor lê para debugar. Em prod a pasta `logs/dev/` nem é
        # criada -- o detalhe não existe na máquina do usuário.
        dev_json = LogJsonHandler(Path("logs") / "dev" / "blazes-dev.jsonl")
        blazes.addHandler(dev_json)
        extra = " + JSON dev em logs\\dev\\blazes-dev.jsonl"

    blazes.info(
        "log iniciado — ambiente %s | %s | arquivos em logs\\sessao-atual.log "
        "e logs\\blazesbot.log (máx. %s linhas cada)%s",
        logmodo.modo_atual(),
        "DETALHADO" if nivel == logging.DEBUG else "normal",
        LINHAS_MAXIMAS, extra,
    )


def _diagnostico_da_camera(memoria) -> None:
    """Imprime o estado da câmera e diz QUAL caminho serve para corrigi-la.

    Escreve na struct e restaura -- o pior caso é a câmera piscar. Ver
    `Memory.diagnostico_da_camera` para o porquê de a prova ser o termômetro,
    e `Memory._provar_campo_da_camera` para as três perguntas de cada campo.
    """
    from blazesbot.core.memory import ANGULO_DA_CAMERA, TOLERANCIA_DO_ANGULO

    try:
        r = memoria.diagnostico_da_camera()
    except Exception as exc:
        print(f"  [câmera] o diagnóstico falhou: {exc!r}")
        return

    lido = r.get("termometro")
    if lido is None:
        print(f"  [câmera] NÃO consegui ler o termômetro em "
              f"{r['termometro_endereco']:#010x} -- sem ele não dá para saber se "
              f"a câmera está certa.")
    else:
        fora = abs(lido - ANGULO_DA_CAMERA)
        marca = "ok" if fora <= TOLERANCIA_DO_ANGULO else "FORA"
        print(f"  [câmera {marca}] ângulo = {lido:.6f} | esperado "
              f"{ANGULO_DA_CAMERA:.6f} | diferença {fora:.6f}")

    achou = False
    entrada = False
    for c in r.get("candidatos", []):
        ponteiro = c.get("ponteiro")
        print(f"  [câmera] {c['rotulo']} ({c['base']:#010x}) -> "
              f"{'NULO' if not ponteiro else f'{ponteiro:#010x}'}: {c['situacao']}")
        for p in c.get("provas", []):
            endereco = p.get("endereco")
            print(f"      {p['campo']:8} {'' if endereco is None else f'{endereco:#010x}'} "
                  f"= {p.get('original')} -> {p.get('escrito')}")
            print(f"               {p.get('situacao')}")
            antes, depois = p.get("termometro_antes"), p.get("termometro_depois")
            if antes is not None and depois is not None:
                print(f"               termômetro {antes:.6f} -> {depois:.6f} "
                      f"(em {p.get('segundos', 0.0):.2f}s)")
            if p.get("moveu_o_termometro"):
                achou = True
                print("               <== ESTE É O CAMINHO")
            elif p.get("o_jogo_manteve"):
                entrada = True

    if achou:
        print("  [câmera] ACHOU: dá para corrigir o ângulo por escrita de "
              "memória, sem mexer no mouse nem abrir tela nenhuma.")
        return

    if entrada:
        print("  [câmera] o jogo MANTEVE valores escritos (campo de entrada, "
              "não derivado), mas o termômetro não mexeu.")
        print("           DESEMPATE: rode o `2-DIAGNOSTICO` olhando a TELA do "
              "jogo. Se a câmera piscar, o termômetro mede OUTRO eixo")
        print("           e é ele que está errado -- não a struct.")
        return

    print("  [câmera] NENHUM dos candidatos moveu a câmera. O `set_camera` "
          "de hoje não corrige o ângulo --")
    print("           o caminho passa a ser o Lock the View (opções de "
          "Gráficos) ou achar o endereço de entrada.")
def run_check() -> int:
    """Diagnóstico: valida o mapa de offsets em TODOS os clientes abertos.

    Testar só o primeiro cliente dava falso alarme: se ele estivesse na tela de
    login ou na fila, o objeto do jogador não existe e todas as leituras falham
    legitimamente. O que importa é se EXISTE algum cliente no mundo cuja memória
    é legível.
    """

    from blazesbot.bot.watchdog import client_pids
    from blazesbot.core.janelas import titulo_do_pid
    from blazesbot.core.memory import Memory

    print("BlazesBot — diagnóstico de memória")
    print("=" * 68)

    pids = sorted(client_pids())
    if not pids:
        print("Nenhum client.exe em execução.")
        print("Abra o jogo, ENTRE COM UM PERSONAGEM e rode de novo.")
        return 1

    print(f"Clientes abertos: {pids}\n")

    # O TÍTULO DA JANELA saiu daqui para `core/janelas.py` em 26/08/2026,
    # quando o `9-VIGIAR-COMBATE` passou a precisar da mesma varredura. Ver o
    # cabeçalho de lá para o porquê da promoção.
    titulo_de = titulo_do_pid

    algum_no_mundo = False
    for pid in pids:
        print("-" * 68)
        print(f"PID {pid}   janela: '{titulo_de(pid)}'")
        try:
            memoria = Memory(pid)
        except Exception as exc:
            print(f"  não foi possível abrir o processo: {exc}")
            continue

        # Mostrar IMAGE_BASE real do processo (para validar RVAs do Cheat Engine)
        from blazesbot.core.memory import IMAGE_BASE
        print(f"  IMAGE_BASE atual: {hex(IMAGE_BASE)}  (RVA 0xD5CB80 = {hex(IMAGE_BASE + 0xD5CB80)})")

        campos = memoria.probe()
        for rotulo, (valor, ok) in campos.items():
            marca = " ok " if ok else "FALHA"
            print(f"  [{marca}] {rotulo:22} = {valor}")

        # ==============================================================
        # A CÂMERA, e é a primeira vez que ela aparece aqui
        # ==============================================================
        #
        # `set_camera` escreve zoom/rotação/ângulo desde sempre, depois de todo
        # View Reset -- e NINGUÉM nunca conferiu se aquilo chega a algum lugar.
        # `ADDR_CAMERA` é herança da versão 6139 e não está na lista do rebase,
        # que já precisou de +0x60 para outros estáticos do mesmo banco.
        #
        # A prova não é "o ponteiro resolve": é o TERMÔMETRO se mexer quando se
        # escreve. Ver `Memory.diagnostico_da_camera`.
        _diagnostico_da_camera(memoria)

        # DETALHE DA LOCALIZAÇÃO, sempre. É a leitura que já quebrou duas vezes
        # em produção, e imprimir só "None" não dizia nada: agora aparece o que
        # cada interpretação da cadeia devolveu e onde ela parou. Com isso dá
        # para distinguir "a cadeia quebrou" de "leu mas eu não reconheci".
        detalhe = memoria.location_detail()
        if detalhe.get("nome") is None:
            print("  [detalhe da localização] NÃO reconheci o nome do lugar:")
            print(f"      ponteiro final ....... {detalhe.get('ponteiro')}")
            print(f"      reconhecimento ....... {detalhe.get('reconhecimento')}")
            for origem, bruto in (detalhe.get("brutos") or {}).items():
                print(f"      leitura {origem:<16} {bruto!r}")
            for rotulo, valor in memoria.location_trace():
                mostrado = "<nao leu>" if valor is None else f"0x{valor:08X}"
                print(f"      elo {rotulo:<32} {mostrado}")
            print("      --> rode o 8-VIGIAR-LOCALIZACAO.bat em paralelo com o")
            print("          bot para descobrir ONDE na cave isso acontece.")
        else:
            print(f"  [detalhe da localização] reconhecido como "
                  f"{detalhe.get('nome')!r} ({detalhe.get('reconhecimento')}, "
                  f"pela leitura '{detalhe.get('origem')}')")

            # A COORDENADA CONFERE O NOME. Ler o nome não é o mesmo que ler o
            # nome certo: ao sair da instância o cliente às vezes deixa o campo
            # preso na última área de dentro, e o diagnóstico antigo imprimia
            # 'Secret Cemetery' com toda a confiança do mundo estando o
            # personagem em (1395,-629), do lado de fora. Quem desmente é a
            # coordenada, e agora ela aparece ao lado.
            from blazesbot.bot.bc import mapa_bc as _mapa
            from blazesbot.core.lugares import e_dentro_da_cave as _na_cave

            pos_atual = memoria.position()
            if (_na_cave(detalhe.get("nome"))  # type: ignore[arg-type]
                    and _mapa.posicao_esta_fora_da_cave(pos_atual)):
                print(f"      !! NOME PRESO: a memória diz "
                      f"{detalhe.get('nome')!r}, que é área da cave, mas a")
                print(f"         coordenada {pos_atual} está FORA da caixa da "
                      f"cave {_mapa.CAIXA_DA_CAVE}.")
                print("         Vale a COORDENADA. O bot não vai tratar isto "
                      "como estar na instância.")
                print("         O campo só é reescrito por uma troca de mapa de "
                      "verdade -- entrar")
                print("         na cave de novo resolve; não precisa passar por "
                      "outra cidade.")
            else:
                print(f"      coordenada ....... {pos_atual}, "
                      f"área por coordenada={_mapa.area_da_posicao(pos_atual)!r} "
                      f"(confere com o nome)")

        # O ALVO, INTEIRO, PELA MEMÓRIA.
        #
        # Este bloco É a conferência de que a leitura por memória continua
        # funcionando -- ele substituiu as ferramentas temporárias que serviram
        # para DESCOBRIR como ela funciona (`10-DESCOBRIR-ALVO`,
        # `16-TESTAR-CORRELACAO-ALVO`, `18-CASAR-ALVO`). Descoberto o mecanismo,
        # a pergunta que sobra é "ainda responde?", e ela é de diagnóstico.
        #
        # SE O JOGO ATUALIZAR e o alvo parar de ser lido, é aqui que aparece:
        # `id` respondendo e entidade não achada significa que
        # `ADDR_ENTITY_SCAN_BASE` andou; `id` não respondendo significa que
        # `ADDR_TARGET_ID` andou. Ver `docs/decisoes/memoria-primeiro.md`.
        from blazesbot.core.memory import ADDR_TARGET_ID

        alvo_id = memoria.id_do_alvo()
        if alvo_id is None:
            print(f"  [alvo] NÃO consegui ler {ADDR_TARGET_ID:#010x}")
        elif alvo_id == 0:
            print("  [alvo] nenhum alvo selecionado")
        else:
            alvo = memoria.alvo_atual()
            if alvo is None:
                print(f"  [alvo] id = {alvo_id:#010x}, mas NENHUMA entidade tem "
                      f"esse id em +0x8")
                print("      o array de entidades pode ter mudado de endereço "
                      "-- ver ADDR_ENTITY_SCAN_BASE")
            else:
                print(f"  [alvo] {alvo['nome']!r} nv{alvo['nivel']} "
                      f"hp={alvo['hp']}/{alvo['max_hp']} "
                      f"({100.0 * alvo['pct']:.1f}%) pos={alvo['pos']}")
                print(f"      id={alvo['id']:#010x} -> entidade "
                      f"{alvo['obj']:#010x}  (o id é chave: a entidade guarda "
                      f"ele em +0x8)")

        # LEITURAS DE UI POR MEMÓRIA, vindas da auditoria do GhostBot. Ainda NÃO
        # decidem nada no bot: aparecem aqui para serem conferidas contra a tela.
        # Se funcionarem, substituem template matching que hoje falha com a janela
        # minimizada (PrintWindow devolve quadro preto fora de primeiro plano).
        arredores = memoria.surroundings_first()
        dialogo = memoria.dialog_open()
        print("  [UI por memória — EM VALIDAÇÃO, não decide nada ainda]")
        if arredores is None:
            print("      arredores ....... não leu (painel fechado, ou o offset do")
            print("                        GhostBot não vale neste cliente)")
        else:
            print(f"      arredores ....... 1º resultado: {arredores["nome"]!r} em "
                  f"{arredores["coords"]}")
        print(f"      diálogo NPC ..... {'ABERTO' if dialogo else ('fechado' if dialogo is False else 'não leu')}")
        print("      --> abra o painel de arredores (ou fale com um NPC) e rode de")
        print("          novo: se estes dois casarem com a tela, o bot passa a ler")
        print("          a interface por memória e funciona minimizado.")

        # TABELA DE ENTIDADES. É o caminho que não depende de `jogador+0x80C` --
        # aquele campo apontou para o pet com o boss selecionado e sendo ferido.
        vizinhos = memoria.entidades_vivas()
        print(f"  [entidades vivas por perto] {len(vizinhos)} na tabela do cliente")
        if vizinhos:
            print(f"      {'dist':>5}  {'struct':>10}  {'nv':>3}  {'HP':>9}  "
                  f"{'posicao':>14}  nome")
            for e in vizinhos[:8]:
                print(f"      {e['distancia']:5.0f}  {e['obj']:#010x}  "
                      f"{e['nivel']:>3}  {e['hp']:>4}/{e['max_hp']:<4}  "
                      f"{e['pos']!s:>14}  {e['nome']!r}")
            print("      --> a mais próxima e VIVA é o que o bot vai atacar. Se a")
            print("          lista casar com o que está na sua tela, o alvo deixa")
            print("          de depender do campo jogador+0x80C.")

        if memoria.critical_ok():
            algum_no_mundo = True
            print("  --> memória LEGÍVEL: este cliente está no mundo e pronto.")
        else:
            base = campos["ponteiro base"][0]
            if base in (None, "0x0"):
                print("  --> objeto do jogador VAZIO. Normal se este cliente")
                print("      estiver na tela de login, na fila ou carregando.")
            else:
                print("  --> ponteiro base existe mas os campos não leem:")
                print("      é aqui que o mapa de offsets estaria desatualizado.")
        memoria.close()

    print("=" * 68)
    if algum_no_mundo:
        print("DIAGNÓSTICO: o mapa de memória está VÁLIDO nesta versão do cliente.")
        print("Se algum cliente apareceu como vazio, é porque não está no mundo.")
        return 0

    print("DIAGNÓSTICO: nenhum cliente com memória legível.")
    print()
    print("Antes de concluir que os offsets mudaram, confirme que existe pelo")
    print("menos um cliente COM PERSONAGEM NO MUNDO -- não na tela de login,")
    print("não na fila, não carregando. Se houver e ainda assim falhar, rode o")
    print("7-DESCOBRIR-MEMORIA.bat para achar o novo ponteiro base.")
    return 1


def run_find_base(char_name: str) -> int:
    """Descobre o ponteiro base do jogador para esta versão do cliente."""
    from blazesbot.bot.watchdog import client_pids
    from blazesbot.tools.find_base import run as find_base_run

    pids = sorted(client_pids())
    if not pids:
        print("Nenhum client.exe em execução.")
        print("Abra o jogo, ENTRE COM O PERSONAGEM e rode de novo.")
        return 1

    if not char_name:
        print("Informe o nome do personagem logado. Exemplo:")
        print('   main.py --find-base --char "BlazesOfWizz"')
        return 1

    codigo = 1
    for pid in pids:
        print()
        codigo = min(codigo, find_base_run(pid, char_name))
    return codigo


def run_capture_test() -> int:
    """Salva em PNG exatamente o que o bot consegue capturar da janela.

    É o teste decisivo quando o bot fica em "tela desconhecida": se o arquivo
    sair preto, o problema é a captura, não os templates.
    """
    import cv2
    import win32gui

    from blazesbot.bot.login_states import LoginStateDetector
    from blazesbot.bot.watchdog import client_pids
    from blazesbot.core.janelas import janela_do_pid
    from blazesbot.core.memory import Memory
    from blazesbot.core.vision import _raw_capture, client_offset, frame_is_blank

    print("BlazesBot — teste de captura de tela")
    print("-" * 60)

    pids = sorted(client_pids())
    if not pids:
        print("Nenhum client.exe em execução. Abra o jogo e rode de novo.")
        return 1

    Path("logs").mkdir(exist_ok=True)
    any_ok = False

    for pid in pids:
        # A VARREDURA é a compartilhada (`core/janelas.py`), promovida em
        # 26/08/2026 -- ela estava escrita QUATRO vezes neste arquivo.
        hwnd, title = janela_do_pid(pid)
        if not hwnd:
            print(f"PID {pid}: janela não encontrada")
            continue
        dx, dy = client_offset(hwnd)
        cl, ct, cr, cb = win32gui.GetClientRect(hwnd)
        print(f"\nPID {pid} | hwnd {hwnd}")
        print(f"  título: '{title}'")
        print(f"  área de cliente: {cr - cl}x{cb - ct}")
        print(f"  deslocamento da área de cliente na janela: ({dx}, {dy})")
        print(f"     (a barra de título tem ~{dy} px — a captura recorta isso fora)")

        for method, use_pw in (("PrintWindow", True), ("BitBlt", False)):
            frame = _raw_capture(hwnd, use_printwindow=use_pw)
            if frame is None:
                print(f"  {method:12} -> falhou (exceção)")
                continue
            blank = frame_is_blank(frame)
            h, w = frame.shape[:2]
            print(f"  {method:12} -> {w}x{h}, desvio={frame.std():6.2f}"
                  f" {'[EM BRANCO]' if blank else '[TEM CONTEUDO]'}")
            out = Path("logs") / f"captura_{pid}_{method}.png"
            cv2.imwrite(str(out), frame)
            print(f"                 salvo em {out}")
            if not blank:
                any_ok = True

        memory = Memory(pid)
        detector = LoginStateDetector(hwnd, memory)
        det = detector.detect()
        print(f"  estado detectado: {det.screen.value}")
        print(f"  servidor no título: {det.server_in_title}")
        print(f"  captura utilizável: {det.capture_ok}")
        memory.close()

    print("\n" + "-" * 60)
    if any_ok:
        print("A captura FUNCIONA em pelo menos um método.")
        print("Abra os PNGs em logs\\ para confirmar que a imagem está correta.")
    else:
        print("A captura NÃO funciona nesta janela — os PNGs saíram em branco.")
        print()
        print("Isso é comum em cliente DirectX fora de primeiro plano, e NÃO")
        print("impede o bot de funcionar: o login opera pelo roteiro, guiado")
        print("pelo título da janela e pela memória. O que se perde é a")
        print("detecção automática de erro de senha e de fila.")
        print()
        print("Se quiser a detecção por imagem, deixe a janela do jogo visível")
        print("(não minimizada e não coberta) enquanto o bot faz o login.")
    return 0


def _janela_de(pid: int) -> tuple[int, str]:
    """Primeira janela visível de um PID, com o título. (0, "") se não houver.

    A VARREDURA saiu daqui para `core/janelas.py` em 26/08/2026: ela estava
    escrita TRÊS vezes neste arquivo, cada uma com um recorte diferente do
    mesmo resultado. Ver o cabeçalho de lá para o porquê da promoção.
    """
    from blazesbot.core.janelas import janela_do_pid

    return janela_do_pid(pid)


def run_list_windows() -> int:
    """Lista janelas visíveis dos client.exe abertos com PID, título e personagem."""
    from blazesbot.bot.watchdog import client_pids
    from blazesbot.core.janelas import janelas_do_pid
    from blazesbot.core.memory import Memory

    print("BlazesBot — janelas do client.exe")
    print("=" * 68)

    pids = sorted(client_pids())
    if not pids:
        print("Nenhum client.exe em execução.")
        return 1

    for pid in pids:
        print(f"\nPID {pid}:")
        try:
            memoria = Memory(pid)
        except Exception as exc:
            print(f"  não foi possível abrir o processo: {exc}")
            continue

        # A VARREDURA é a compartilhada (`core/janelas.py`), promovida em
        # 26/08/2026 -- ela estava escrita três vezes neste arquivo.
        for handle, titulo in janelas_do_pid(pid):
            if not titulo:
                continue
            personagem = memoria.char_name()
            print(f"  hwnd {handle} | '{titulo}' | personagem: {personagem or '—'}")

        memoria.close()

    print("\n" + "=" * 68)
    print("Use o PID desejado com --pid <PID> nos outros comandos.")
    return 0


def run_detect() -> int:
    """Mostra AO VIVO qual tela o bot reconhece em cada cliente aberto.

    É o teste para usar quando o login empaca: mostra, a cada segundo, o que o
    bot está vendo. "tela desconhecida" com captura indisponível significa que o
    bot está operando pelo roteiro; "tela desconhecida" COM captura significa
    template faltando ou desatualizado.
    """
    import time

    from blazesbot.bot.login_states import LoginStateDetector
    from blazesbot.bot.watchdog import client_pids
    from blazesbot.core.memory import Memory

    print("BlazesBot — detecção de tela ao vivo")
    print("Ctrl+C para sair.")
    print("=" * 68)

    detectores: dict[int, tuple[LoginStateDetector, Memory]] = {}
    try:
        while True:
            pids = sorted(client_pids())
            if not pids:
                print("nenhum client.exe aberto — esperando…")

            # Solta o que morreu, para não segurar handle de processo encerrado.
            for pid in list(detectores):
                if pid not in pids:
                    detectores.pop(pid)[1].close()

            for pid in pids:
                hwnd, titulo = _janela_de(pid)
                if not hwnd:
                    print(f"PID {pid}: sem janela visível")
                    continue
                if pid not in detectores:
                    try:
                        memoria = Memory(pid)
                    except Exception as exc:
                        print(f"PID {pid}: não consegui abrir o processo ({exc})."
                              " Está rodando como administrador?")
                        continue
                    detectores[pid] = (LoginStateDetector(hwnd, memoria), memoria)
                detector, memoria = detectores[pid]

                det = detector.detect()
                # O nick aparece aqui de propósito: é a informação que decide se
                # o bot vai reconhecer esta janela na próxima execução.
                personagem = memoria.char_name()
                print(
                    f"PID {pid:>6} | {det.screen.value:<22} | "
                    f"captura={'ok' if det.capture_ok else 'indisponível':<12} | "
                    f"servidor={det.server_in_title or '—'} | "
                    f"personagem={personagem or '—'} | título={titulo!r}"
                )
            print("-" * 68)
            time.sleep(0.75)
    except KeyboardInterrupt:
        print("\nencerrado.")
    finally:
        for _detector, memoria in detectores.values():
            memoria.close()
    return 0


def run_login_test(config_path: Path) -> int:
    """Faz SOMENTE o login da primeira conta ativa e para.

    Usa a máquina de produção inteira -- adoção de janela já aberta,
    LoginSequence, espera da memória e gravação do nick do personagem. Testar
    por um caminho paralelo não provaria nada sobre o caminho real.

    Como todo o resto do bot, NÃO fecha o cliente ao terminar.
    """
    from blazesbot.bot.supervisor import AccountSupervisor

    config = BotConfig.load(config_path)
    ativas = config.enabled_accounts()
    if not ativas:
        print(f"Nenhuma conta ativa em {config_path}.")
        print("Cadastre uma conta pela interface (3-INICIAR.bat) e volte.")
        return 1

    if not Path(config.client_bat).exists():
        print(f"Client.bat não encontrado em: {config.client_bat}")
        return 1

    conta = ativas[0]
    problemas = conta.validate()
    if problemas:
        print(f"A conta '{conta.login}' está incompleta:")
        for p in problemas:
            print(f"  • {p}")
        return 1

    print(f"Testando o login de '{conta.login}'.")
    if conta.last_char_name:
        print(f"Nick guardado: '{conta.last_char_name}' — se a janela dele já "
              "estiver aberta, o bot assume o controle sem relogar.")
    else:
        print("Esta conta ainda não tem nick guardado; ele será gravado assim "
              "que o personagem entrar no mundo.")
    print("=" * 68)

    class _SomenteLogin(AccountSupervisor):
        """Supervisor que para onde o farm começaria."""

        def _operate(self, ctx) -> None:
            self._status(
                "Login concluído — o teste para aqui. O jogo continua aberto."
            )

    supervisor = _SomenteLogin(config, conta)
    supervisor.start()
    try:
        while supervisor.is_alive():
            supervisor.join(timeout=1.0)
    except KeyboardInterrupt:
        print("\nParando (o jogo continua aberto)…")
        supervisor.request_stop("Ctrl+C")
        supervisor.join(timeout=20.0)

    print("=" * 68)
    if conta.last_char_name:
        print(f"Personagem identificado: '{conta.last_char_name}'")
        print(f"Gravado em {config.config_path} — na próxima execução o bot")
        print("reconhece esta janela e não passa pela fila de login.")
    else:
        print("O login terminou sem que eu conseguisse ler o nome do personagem.")
        print("Rode o 2-DIAGNOSTICO.bat para ver se a memória está legível.")
    return 0


def run_headless(config_path: Path) -> int:
    from blazesbot.bot.supervisor import BotManager

    config = BotConfig.load(config_path)
    problems = config.validate()
    if problems:
        print("Configuração inválida:")
        for problem in problems:
            print(f"  • {problem}")
        print("\nRode sem --headless para configurar pela interface.")
        return 1

    manager = BotManager(config)
    if manager.start():
        return 1

    print("BlazesBot rodando. Ctrl+C para parar.")
    try:
        while manager.running():
            manager.join(timeout=1.0)
    except KeyboardInterrupt:
        print("\nParando…")
        manager.stop()
        manager.join(timeout=15.0)
    return 0


def run_gui(config_path: Path) -> int:
    from PyQt6.QtWidgets import QApplication

    from blazesbot.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow(config_path)
    window.show()
    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="BlazesBot",
        description="Bot de boss-rush da Bewitcher Cave para Talisman Online",
    )
    parser.add_argument("--check", action="store_true",
                        help="valida o mapa de memória e sai")
    parser.add_argument("--login-test", action="store_true",
                        help="testa SOMENTE o login e para")
    parser.add_argument("--detect", action="store_true",
                        help="mostra ao vivo qual tela o bot reconhece")
    parser.add_argument("--capture-test", action="store_true",
                        help="salva em PNG o que o bot consegue capturar")
    parser.add_argument("--find-base", action="store_true",
                        help="descobre o ponteiro base do jogador")
    parser.add_argument("--watch-location", action="store_true",
                        help="vigia o ponteiro do nome do lugar ao vivo")
    parser.add_argument("--watch-combat", action="store_true",
                        help="vigia a flag de combate e o quadro do alvo ao vivo")
    parser.add_argument("--ler-camera", action="store_true",
                        help="vigia a struct da camera AO VIVO (so le)")
    parser.add_argument("--segundos", type=float, default=0.0,
                        help="teto em segundos para --ler-camera / --watch-combat")
    parser.add_argument("--pid", type=int, default=0,
                        help="PID específico do client.exe (usado com --check/--detect/--ler-camera). 0 = todos")
    parser.add_argument("--char", default="",
                        help="nome do personagem logado (usado com --find-base)")
    parser.add_argument("--list-windows", action="store_true",
                        help="lista janelas visíveis dos client.exe abertos (PID, título, personagem)")
    parser.add_argument("--headless", action="store_true",
                        help="roda sem interface, usando a config salva")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH),
                        help="caminho do arquivo de configuração")
    parser.add_argument("-v", "--verbose", action="store_true", default=True,
                        help="log detalhado (padrão enquanto está em ajuste)")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="log resumido")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("O BlazesBot só funciona no Windows.")
        return 1

    require_admin()
    setup_logging(verbose=not args.quiet)

    config_path = Path(args.config)
    if args.check:
        return run_check()
    if args.find_base:
        return run_find_base(args.char)
    if args.ler_camera:
        from blazesbot.bot.watchdog import client_pids
        from blazesbot.tools.ler_camera import SEGUNDOS_PADRAO, run_ler_camera

        pids = sorted(client_pids())
        if not pids:
            print("Nenhum client.exe em execução.")
            return 1
        if args.pid != 0:
            if args.pid not in pids:
                print(f"PID {args.pid} não está na lista de clientes abertos: "
                      f"{pids}")
                return 1
            pids = [args.pid]
        elif len(pids) > 1:
            # Vários clientes e nenhum escolhido: a câmera é POR JANELA, então
            # misturar os dois na mesma tela não responde nada.
            print(f"Há {len(pids)} clientes abertos: {pids}")
            print("Rode de novo com --pid <PID> -- a câmera é de UMA janela, e "
                  "misturar duas não responde nada.")
            return 1

        segundos = args.segundos if args.segundos > 0 else SEGUNDOS_PADRAO
        return run_ler_camera(pids[0], segundos)
    if args.list_windows:
        return run_list_windows()
    if args.watch_location:
        from blazesbot.tools.vigiar_local import run as vigiar

        return vigiar()
    if args.watch_combat:
        # O 9-VIGIAR-COMBATE VOLTOU em 26/08/2026, e voltou DIFERENTE: em vez de
        # ter a própria leitura de alvo por ponteiro -- que foi o que fez a
        # versão antiga ser apagada --, ele chama o MESMO `TargetHybrid` que o
        # bot chama, e imprime a MESMA linha. Ferramenta de diagnóstico que
        # reimplementa a leitura não diagnostica o bot: diagnostica a cópia.
        from blazesbot.tools.vigiar_combate import run_vigiar_combate
        return run_vigiar_combate(args.pid, args.segundos)

    if args.capture_test:
        return run_capture_test()
    if args.detect:
        return run_detect()
    if args.login_test:
        return run_login_test(config_path)
    if args.headless:
        return run_headless(config_path)
    return run_gui(config_path)


if __name__ == "__main__":
    sys.exit(main())
