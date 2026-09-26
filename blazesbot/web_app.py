"""
Ponte Python ⇄ interface web (pywebview + WebView2).

É a interface do BlazesBot -- a única. O pywebview abre o frontend em `web/` (HTML/CSS/JS) numa janela do WebView2
Runtime (embutido no Windows 11 — nada a instalar); este módulo expõe ao
JavaScript as operações da interface, via o objeto `js_api`, usando
o MESMO backend (`BotConfig`, `Account`, `BotManager`, `stats_diarias`). Nenhuma
regra de negócio fica no frontend — ele só chama estes métodos.

Nome do módulo (`web_app.py`) é histórico: antes era `eel_app.py` quando a ponte
usava a biblioteca `Eel`. Hoje a ponte é pywebview; o frontend continua o mesmo.

A config é `data/config.json`, a mesma que os supervisores leem.

THREADS E LOG
=============
O `webview.start()` bloqueia a thread principal. Os supervisores rodam nas
próprias threads e só enchem o log via `logging`. Para empurrar o log à web SEM
chamar o bridge de outras threads, este módulo usa um
handler enfileira tudo numa `deque` e o JavaScript PUXA as linhas novas a cada
~300 ms (`puxar_log`). Status e estatísticas também são puxados por poll
(`estado`, `stats_conta`). Assim não há chamada JS←Python assíncrona de outras
threads.

Thread-safety da config: as funções de escrita mutam o objeto `Account`/`BotConfig`
e gravam via `config.save()` (que já é atômico e com lock); o único risco novo é
gravar da thread do bridge do pywebview enquanto um supervisor lê o mesmo objeto
na thread dele — cenário aceitável.
"""
from __future__ import annotations

import ctypes
import logging
from collections import deque
from datetime import date
from itertools import islice
from pathlib import Path
from typing import Any

import webview

from . import web_lixo

# TEMPORÁRIO: botões "Testar Venda" e "Amostrar Cliques"
from .bot.app import afericao
from .bot.bc import amostragem_de_cliques, teste_venda
from .bot.supervisor import BotManager
from .config import (
    DEFAULT_CONFIG_PATH,
    ICONE_DO_APP,
    LIMITE_DO_NOME_DO_GRUPO,
    MAX_BOLSAS,
    MINIMO_DE_ESPERA_DO_APP_MS,
    MOUNT_SPEEDS,
    PASSOS_DO_APP,
    PET_FEED_MINUTES,
    SELL_CLICK_OPTIONS,
    SLOTS_POR_BOLSA,
    Account,
    BotConfig,
    mount_multiplier,
    normalizar_modelos,
    normalizar_modo_do_reset,
    normalizar_pct,
    normalizar_time_logins,
    normalizar_time_modo,
    pet_feed_na_faixa,
)
from .core import i18n, logmodo, quedas, secrets, stats_diarias
from .core.coords import (
    SUPPORTED_RESOLUTIONS,
    VALIDATED_RESOLUTION,
    get_coords,
)
from .core.raiz import raiz_do_bot

POSITIONS = ["Left", "Center", "Right"]

# Coords para a lista de servidores e para normalizar o servidor exibido.
# Calculado uma vez, é barato.
_COORDS = get_coords(VALIDATED_RESOLUTION)

# Linhas guardadas em memória para permitir refiltrar por conta.
MAX_LINHAS_GUARDADAS = 12000


def format_duracao(segundos: float) -> str:
    """Formata segundos como '1d 2h 3m 4s', omitindo o que for zero.

    """
    total = int(max(0, segundos))
    dias, resto = divmod(total, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, segs = divmod(resto, 60)
    if dias:
        return f"{dias}d {horas}h {minutos}m"
    if horas:
        return f"{horas}h {minutos}m {segs}s"
    if minutos:
        return f"{minutos}m {segs}s"
    return f"{segs}s"


def _nick(conta: Account) -> str:
    return (conta.last_char_name or "").strip() or conta.login


class _LogHandler(logging.Handler):
    """Enfileira o log para a web, marcando de qual conta veio.

    O nome do logger é sempre `blazes.<login>`, então dá para separar as linhas
    por conta. O handler só dá `append`
    numa `deque` -- operação atômica, sem thread -- e a web puxa em lote.
    """

    def __init__(self, fila: deque[tuple[str, str]]) -> None:
        super().__init__()
        self.fila = fila
        self.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            partes = record.name.split(".", 1)
            conta = partes[1] if len(partes) > 1 else ""
            self.fila.append((conta, self._formatar(record)))
        except Exception:
            pass

    def _formatar(self, record: logging.LogRecord) -> str:
        """Como `self.format(record)`, mas troca o TEMPLATE da mensagem pela
        tradução quando existe uma para `i18n.idioma_atual_do_log()`.

        NUNCA mexe no `record`: outro handler no mesmo logger (o log de dev,
        por exemplo) recebe o MESMO objeto e tem que continuar vendo o PT-BR
        original -- por isso a tradução é uma string calculada aqui, não uma
        mutação em `record.msg`. Sem entrada no catálogo, ou em PT-BR, o
        caminho é idêntico ao de antes desta função existir.
        """
        if i18n.idioma_atual_do_log() == i18n.IDIOMA_PADRAO:
            return self.format(record)
        template = i18n.traduzir_mensagem_de_log(str(record.msg))
        if template == str(record.msg):
            return self.format(record)
        try:
            mensagem = template % record.args if record.args else template
        except Exception:
            return self.format(record)
        hora = self.formatter.formatTime(record, self.formatter.datefmt)
        return f"{hora}  {mensagem}"


class _App:
    """Estado da interface web: a config e o manager que os supervisores usam."""

    def __init__(self) -> None:
        self.config = BotConfig.load(DEFAULT_CONFIG_PATH)
        self.manager: BotManager | None = None
        # Fila que as threads do bot alimentam, e o histórico completo (para
        # refiltrar por conta).
        self._fila_log: deque[tuple[str, str]] = deque(maxlen=40000)
        self._historico: deque[tuple[str, str]] = deque(
            maxlen=MAX_LINHAS_GUARDADAS)
        self._contagem_por_conta: dict[str, int] = {}
        self._total = 0
        # Log NOVO (a partir de agora) já sai no idioma salvo -- não só o texto
        # da UI. Ver `i18n.traduzir_mensagem_de_log`.
        i18n.definir_idioma_do_log(self.config.idioma)

    # ------------------------------------------------------------------
    # helpers internos
    # ------------------------------------------------------------------

    def _conta(self, uid: str) -> Account:
        """Conta pelo `uid` -- a identidade ESTÁVEL da conta.

        ERA O ÍNDICE NA LISTA, e valia enquanto a lista não podia ser
        reordenada. A tabela ganhou arraste para reordenar, e isso quebra a
        premissa: com a ordem do disco diferente da ordem da tela, um
        `definir_senha` gravaria a senha NA CONTA ERRADA -- login quebrado e
        senha certa perdida, sem desfazer.

        O login não serve de chave: conta recém-criada nasce sem login
        (`nova_conta`) e precisa ser editável antes de ter nome. Por isso `uid`, e
        não login.
        """
        conta = self.config.conta_por_uid(uid)
        if conta is None:
            raise ValueError(f"conta não encontrada (uid {uid})")
        return conta

    def _por_login(self) -> dict[str, Account]:
        return {c.login: c for c in self.config.accounts if c.login}

    def _status(self, login: str, mensagem: str) -> None:
        """Loga uma linha da conta (ou geral), passando pelo handler da web."""
        nome = f"blazes.{login}" if login else "blazes"
        logging.getLogger(nome).info(mensagem)

    def _guardar_log(self, conta: str, linha: str) -> None:
        self._fila_log.append((conta, linha))

    def _candidatas_do_time(self, lider: Account) -> dict[str, object]:
        """Quem DÁ para convocar para o time do APP desta conta.

        INELEGÍVEL NÃO APARECE (07/09/2026, pedido do usuário). Antes ia na
        lista desabilitada e com o motivo, para o usuário não procurar uma conta
        que ele sabe que cadastrou -- e o resultado, com muitas contas, foi uma
        lista que só cresce e onde o que se pode escolher fica escondido no meio
        do que não se pode. `docs/INVARIANTES.md` sempre disse que conta
        farmando a cave "não aparece na escolha do time"; era o código que
        divergia. A contagem do que ficou de fora vai junto, para a conta que
        sumiu ter explicação em vez de virar mistério.

        A REGRA MORA AQUI, num lugar só: a tela recebe o motivo pronto em vez de
        remontá-lo a partir de três campos soltos.

        QUEM JÁ ESTÁ NO TIME APARECE SEMPRE, inelegível ou não -- e HABILITADO.
        Esconder o que está gravado faria `lerTimeDoApp` salvar sem ele, e
        `time_logins` perderia o login por causa de um clique em BC que é
        reversível (`docs/INVARIANTES.md`: "sair do time por `bc_farm` não apaga
        o login"). Marcada e com o motivo à vista, o conflito é visível e a
        decisão de tirar continua sendo do líder.
        """
        ja_no_time = {str(x) for x in lider.settings.app.time_logins}
        visiveis: list[dict[str, object]] = []
        ocultas = 0
        for o in self.config.accounts:
            if o is lider or not o.login:
                continue
            motivo = ""
            if not o.enabled:
                motivo = "inativa"
            elif o.bc_farm:
                motivo = "farmando a cave"
            elif o.hh_farm:
                motivo = "farmando a HH"
            elif o.settings.app.enabled:
                # O APP PRÓPRIO TAMBÉM ESCONDE (07/09/2026, pedido do usuário
                # olhando a tela: o líder de um time aparecia como candidato
                # para as outras contas). Isto NÃO impede montar time: seguidor
                # roda com a caixa "Ativar Modo APP" DELE desmarcada -- é a
                # convocação que o faz rodar (`_SupervisorDaConta._lider_do_time`).
                # Candidata com a caixa marcada é conta que já trabalha por si.
                motivo = ("líder de um time" if o.settings.app.time_logins
                          else "rodando o APP")
            else:
                outro = self.config.lider_do_time_do_app(
                    o.login, ignorar=lider.login)
                if outro:
                    motivo = f"já no time de {outro}"
            if motivo and o.login not in ja_no_time:
                ocultas += 1
                continue
            visiveis.append({"login": o.login,
                             "nick": o.last_char_name.strip(),
                             "motivo": motivo})
        return {"contas_do_time": visiveis, "contas_do_time_ocultas": ocultas}

    def _aplicar(self) -> None:
        try:
            self.config.save()
        except Exception as exc:
            self._status("", f"Não foi possível salvar a configuração: {exc}")

    def _sincronizar(self) -> list[str]:
        """Põe o bot em execução de acordo com as contas ativas agora."""
        if not (self.manager and self.manager.running()):
            return []
        try:
            return self.manager.sync_accounts()
        except Exception as exc:
            self._status("", f"erro ao sincronizar: {exc}")
            return []

    # ------------------------------------------------------------------
    # Constantes e leitura
    # ------------------------------------------------------------------

    def constantes(self) -> dict[str, Any]:
        coords = get_coords(VALIDATED_RESOLUTION)
        return {
            "positions": POSITIONS,
            "mounts": [
                {"pct": p, "texto": f"{p}%   ({mount_multiplier(p):.1f}x)"}
                for p in MOUNT_SPEEDS
            ],
            "pet_feed_minutes": PET_FEED_MINUTES,
            "max_bolsas": MAX_BOLSAS,
            "slots_por_bolsa": SLOTS_POR_BOLSA,
            "bolsa_opcoes": [
                {"n": n, "texto": f"{n} bolsa{'s' if n > 1 else ''}"
                                  f"   ({n * SLOTS_POR_BOLSA} espaços)"}
                for n in range(1, MAX_BOLSAS + 1)
            ],
            "passos_app": PASSOS_DO_APP,
            "sell_cliques": list(SELL_CLICK_OPTIONS),
            "resolucoes": [
                {"valor": res,
                 "rotulo": f"{res}   (validada)" if res == VALIDATED_RESOLUTION
                           else res}
                for res in SUPPORTED_RESOLUTIONS
            ],
            "resolucao_validada": VALIDATED_RESOLUTION,
            "servidores": list(coords.server_rows),
            "dpapi": secrets.dpapi_available(),
            # Os 3 idiomas já resolvidos (fallback decidido aqui, não no JS) —
            # a Web troca de idioma sem round-trip ao Python.
            "traducoes": {
                idioma: i18n.resolver_idioma(idioma)
                for idioma in i18n.IDIOMAS_SUPORTADOS
            },
            "idiomas_suportados": list(i18n.IDIOMAS_SUPORTADOS),
        }

    def config_atual(self) -> dict[str, Any]:
        c = self.config
        return {
            "client_bat": c.client_bat,
            "resolution": c.resolution,
            "launch_delay": c.launch_delay,
            "minimize_clients": c.minimize_clients,
            "reuse_login_screen_clients": c.reuse_login_screen_clients,
            "idioma": c.idioma,
        }

    def contas(self) -> list[dict[str, Any]]:
        """Lista as contas para a tabela. A senha NUNCA sai daqui.

        `uid` é a identidade que a web usa para TODAS as operações. Era o índice
        na lista, e deixou de ser quando a tabela ganhou arraste: com a ordem da
        tela diferente da ordem do disco, uma escrita por índice cairia na conta
        errada (ver `_conta`). Login não serve de chave — conta nova nasce sem
        login e precisa ser editável antes de ter nome.

        `ordem` vai junto só para a tela conseguir conferir se está desatualizada
        em relação ao disco; ela NÃO é fonte de verdade de nada.
        O servidor vem NORMALIZADO.
        """
        # ANTES DE A TELA RECEBER A LISTA. A leitura do arquivo já desfaz uid
        # repetido, mas conta criada em MEMÓRIA nunca passa por lá -- e a tela
        # endereça por uid, então duas iguais são indistinguíveis para ela:
        # arrastar a segunda moveria a primeira. Barato (uma passada) e fecha o
        # caminho de vez.
        self.config.garantir_uids_unicos()
        # UMA passada para todos os líderes, em vez de uma varredura por conta
        # (era O(n²) por leitura da tabela). Ver `lideres_do_time_do_app`.
        lideres = self.config.lideres_do_time_do_app()
        out = []
        for i, c in enumerate(self.config.accounts):
            out.append({
                "uid": c.uid,
                "ordem": i,
                "grupo": c.grupo,
                # QUEM PUXA ESTA CONTA como seguidora do time do APP, ou "".
                #
                # Sem isto a tabela chamava de "só login" uma conta que na
                # verdade roda a macro de outra: `AppConfig.enabled` fica
                # DESLIGADO na seguidora (quem liga o APP é o líder), então as
                # três caixas vazias contavam uma mentira. Ver
                # `docs/INVARIANTES.md`, "Time do APP".
                "lider_do_time": lideres.get((c.login or "").strip().lower(), ""),
                "login": c.login,
                "enabled": c.enabled,
                "position": c.position,
                "server": _COORDS.normalize_server(c.server),
                # A FUNÇÃO ATIVA, resolvida pelo backend. As três chaves
                # abaixo continuam para compatibilidade de leitura, mas quem
                # manda é esta -- as três são mutuamente exclusivas.
                "funcao": self.config.funcao_ativa_da_conta(c),
                "bc_farm": c.bc_farm,
                "hh_farm": c.hh_farm,
                "app_enabled": c.settings.app.enabled,
                "nick": _nick(c),
                "tem_senha": bool(c.password_enc),
            })
        return out

    def conta_editor(self, uid: str) -> dict[str, Any]:
        c = self._conta(uid)
        st = c.settings
        k = st.keys
        ataques = list(k.attack_skills) + [""] * 4
        buffs = list(k.buffs) + [""] * 4
        return {
            "login": c.login,
            "tem_senha": bool(c.password_enc),
            "nick": c.last_char_name,
            "grupo": c.grupo,
            "accept_team_invites": st.accept_team_invites,
            # A CONTA DE RESET, no nível da CONTA -- uma para todas as caves.
            # Estava em `bc` e `hh`; ver `AccountSettings.reset_nick`.
            "reset_nick": st.reset_nick,
            # O TOTAL DE CLIQUES DA VENDA, no nível da CONTA -- vale para toda
            # cave. Ver `AccountSettings.sell_clicks`.
            "sell_clicks": st.sell_clicks,
            # AS CANDIDATAS A RESETER. O campo "conta que reseta a cave" deixou
            # de ser texto livre: o reseter precisa ser uma conta cadastrada
            # AQUI, porque é isso que permite ao bot perceber que ela caiu e
            # segurar a entrada em vez de entrar sem reset e perder a run.
            #
            # `disponivel=False` é a conta marcada que ainda NÃO LOGOU: sem nick
            # (ele é lido da memória no primeiro login) selecioná-la gravaria
            # string vazia, que em `AccountSettings.reset_nick` significa
            # "não usar reset de time" -- um jeito silencioso de desligar a
            # função achando que ligou.
            "contas_de_reset": [
                {"nick": r.last_char_name.strip(),
                 "login": r.login,
                 "disponivel": bool(r.last_char_name.strip())}
                for r in self.config.reset_accounts() if r is not c
            ],
            # AS CANDIDATAS DO TIME DO APP -- ver `_candidatas_do_time`.
            **self._candidatas_do_time(c),
            "usar_catador": st.usar_catador,
            "mount_speed_pct": st.mount_speed_pct,
            "farm": c.bc_farm,
            "farm_hh": c.hh_farm,
            "pet": {
                "summon_on_login": st.pet.summon_on_login,
                "feed_on_start": st.pet.feed_on_start,
                "feed_every_minutes": st.pet.feed_every_minutes,
            },
            "potions": {
                "hp_pct": st.potions.hp_pct,
                "battle_hp_pct": st.potions.battle_hp_pct,
                "emergency_pct": st.potions.emergency_pct,
            },
            "bags": {"bolsas": st.bags.bolsas},
            "app": {
                "enabled": st.app.enabled,
                "apagar_lixo_a_cada": st.app.apagar_lixo_a_cada,
                "apagaveis": st.app.apagaveis,
                "travar_posicao": st.app.travar_posicao,
                "shuffle_apos_n_voltas": st.app.shuffle_apos_n_voltas,
                # A LINHA 0 da macro: o tempo depois do TAB.
                "espera_depois_do_tab_ms": st.app.espera_depois_do_tab_ms,
                "time_logins": st.app.time_logins,
                "time_modo": st.app.time_modo,
                "fada": st.app.fada,
                "cura_pedir_pct": st.app.cura_pedir_pct,
                "cura_parar_pct": st.app.cura_parar_pct,
                "steps": [{"key": p.key, "delay_ms": p.delay_ms}
                          for p in st.app.steps],
            },
            "keys": {
                "attack_skills": ataques[:4],
                "aoe_skill": k.aoe_skill,
                "break_soul": k.break_soul,
                "super_skill": k.super_skill,
                "heal_skill": k.heal_skill,
                "revive_skill": k.revive_skill,
                "buffs": buffs[:4],
                "hp_potion": k.hp_potion,
                "battle_hp_potion": k.battle_hp_potion,
                "pet_food": k.pet_food,
                "stone_charm": k.stone_charm,
                "mount": k.mount,
                "speed_skill": k.speed_skill,
                "guild_token": k.guild_token,
                "pet_summon": k.pet_summon,
                "next_target": k.next_target,
                "sit": k.sit,
                "self_target": k.self_target,
                "follow": k.follow,
                "inventory": k.inventory,
                "friend_list": k.friend_list,
                "hotbar_page_1": k.hotbar_page_1,
                "hide_players": k.hide_players,
            },
            "bc": {
                "boss_name": st.bc.boss_name,
                "attack_delay": st.bc.attack_delay,
                "heal_before_second_phase": st.bc.heal_before_second_phase,
                "aoe_until_mana_pct": st.bc.aoe_until_mana_pct,
                "usar_skill_de_velocidade": st.bc.usar_skill_de_velocidade,
                "vendor": {
                    "runs_before_selling": st.bc.vendor.runs_before_selling,
                    "sell_start_slot": st.bc.vendor.sell_start_slot,
                    "buy_return_charm": st.bc.vendor.buy_return_charm,
                },
            },
            # A HH é ecossistema próprio: bloco próprio, e não campos dentro do
            # `bc`. Misturar os dois faria a interface parecer que a HH é um
            # "modo" da Bewitcher Cave -- e ela não é.
            "hh": {
                "modo_do_reset": st.hh.modo_do_reset,
                "attack_delay": st.hh.attack_delay,
                "aoe_until_mana_pct": st.hh.aoe_until_mana_pct,
                "limpar_mobs_a_cada": st.hh.limpar_mobs_a_cada,
                "deletar_lixo": st.hh.deletar_lixo,
                "apagaveis": st.hh.apagaveis,
                "vendor": {
                    "sell_start_slot": st.hh.vendor.sell_start_slot,
                    "runs_before_selling": st.hh.vendor.runs_before_selling,
                },
            },
        }

    # ------------------------------------------------------------------
    # escrita (tempo real)
    # ------------------------------------------------------------------

    def salvar_config(self, dados: dict[str, Any]) -> None:
        cfg = self.config
        cfg.client_bat = str(dados.get("client_bat", "")).strip()
        cfg.resolution = str(dados.get("resolution", "auto") or "auto")
        cfg.launch_delay = float(dados.get("launch_delay", 8.0) or 8.0)
        cfg.minimize_clients = bool(dados.get("minimize_clients", False))
        cfg.reuse_login_screen_clients = bool(
            dados.get("reuse_login_screen_clients", False))
        self._aplicar()

    def definir_idioma(self, idioma: str) -> None:
        idioma = idioma if idioma in i18n.IDIOMAS_SUPORTADOS else i18n.IDIOMA_PADRAO
        self.config.idioma = idioma
        self.config.save()
        # Log GERADO A PARTIR DAQUI sai traduzido; o que já foi escrito não
        # muda -- ver `i18n.traduzir_mensagem_de_log`.
        i18n.definir_idioma_do_log(idioma)

    def definir_senha(self, uid: str, nova: str) -> None:
        c = self._conta(uid)
        c.set_password(str(nova or ""))
        self._aplicar()

    def definir_login(self, uid: str, novo: str) -> None:
        """Login editável direto na tabela.

        Vazio NÃO apaga o login atual — mesmo contrato do campo de login do
        editor (`salvar_personagem`). Um campo em branco na tabela costuma
        ser clique acidental, e apagar a chave de uma conta ativa derrubaria
        o vínculo com o supervisor que já está rodando aquela conta.
        """
        c = self._conta(uid)
        novo_login = str(novo or "").strip()
        if novo_login:
            c.login = novo_login
        self._aplicar()

    def definir_posicao(self, uid: str, posicao: str) -> None:
        """Posição da janela do cliente (Left|Center|Right) — combo da tabela."""
        c = self._conta(uid)
        if str(posicao or "") in POSITIONS:
            c.position = str(posicao)
        self._aplicar()

    def definir_servidor(self, uid: str, servidor: str) -> None:
        """Servidor da conta — combo da tabela (nomes canônicos de server_rows)."""
        c = self._conta(uid)
        c.server = str(servidor or "").strip()
        self._aplicar()

    def nova_conta(self) -> None:
        # Com o bot rodando a conta nasce INATIVA de propósito:
        # o usuário preenche com calma e, ao marcar "Ativa", entra no ar.
        rodando = bool(self.manager and self.manager.running())
        nova = Account(enabled=not rodando)
        nova.garantir_uid()   # nasce com identidade: a tela endereça por ela
        self.config.accounts.append(nova)
        self._aplicar()

    def reordenar_contas(self, itens: list[tuple[str, object]]) -> None:
        """Nova ordem das contas e o rótulo de grupo de cada uma.

        A ordem é a do array -- não existe campo de ordem. O grupo vem no mesmo
        pacote porque arrastar para dentro de outro grupo muda o rótulo: em duas
        chamadas, uma podia gravar e a outra falhar.

        UMA gravação no fim, e só se algo mudou de verdade.
        """
        uids = [uid for uid, _ in itens]
        mudou = self.config.reordenar_contas(uids)
        for uid, grupo in itens:
            conta = self.config.conta_por_uid(uid)
            if conta is None:
                continue
            novo = str(grupo or "").strip()[:LIMITE_DO_NOME_DO_GRUPO]
            if conta.grupo != novo:
                conta.grupo = novo
                mudou = True
        if mudou:
            self._aplicar()

    def definir_grupo(self, uid: str, grupo: object) -> None:
        """Rótulo de organização (`Account.grupo`). Não representa time nenhum."""
        c = self._conta(uid)
        c.grupo = str(grupo or "").strip()[:LIMITE_DO_NOME_DO_GRUPO]
        self._aplicar()

    def bloqueio_de_reseter(self, uid: str, acao: str) -> str | None:
        """Por que esta conta NÃO pode ser tirada do ar. `None` = pode.

        Quem responde é `BotConfig.accounts_reset_by`.

        POR QUE IMPEDIR, E NÃO SÓ AVISAR. Sem o reseter, a conta que depende
        dele não reseta a cave -- e sem reset o boss não renasce e a run é
        perdida. O sintoma ("o boss parou de nascer") aparece horas depois e
        não aponta para cá em nada. Aqui o usuário está com a tela na mão:
        trocar o reset da outra conta primeiro é um clique.
        """
        try:
            conta = self._conta(uid)
        except Exception:
            return None
        dependentes = self.config.accounts_reset_by(conta)
        if not dependentes:
            return None
        quem = ", ".join(f"'{c.login}'" for c in dependentes)
        return (
            f"Não dá para {acao} '{conta.login}': ela é a conta de RESET de "
            f"{quem}. Sem ela essa(s) conta(s) não resetam a Bewitcher Cave, "
            "o boss não renasce e a run é perdida. Troque o reset na edição "
            "dessa(s) conta(s) primeiro."
        )

    def remover_conta(self, uid: str) -> None:
        """Remove a conta com este `uid`. Uid desconhecido não faz nada.

        Remove por IDENTIDADE e não por posição: a tabela pode estar reordenada
        em relação ao disco, e apagar por índice apagaria a conta errada -- com a
        senha cifrada dela, sem desfazer.
        """
        conta = self.config.conta_por_uid(uid)
        if conta is None:
            return
        login = conta.login
        self.config.accounts = [c for c in self.config.accounts
                                if c.uid != conta.uid]
        # Limpa o contador de log desta conta — sem isso o dict acumula
        # entradas órfãs para sempre (vazamento lento, mas real).
        if login and login in self._contagem_por_conta:
            del self._contagem_por_conta[login]
        self._aplicar()

    def alternar(self, uid: str, ativa: bool) -> list[str]:
        c = self._conta(uid)
        c.enabled = bool(ativa)
        self._aplicar()
        return self._sincronizar()

    # RÓTULO DE CADA FUNÇÃO, para a mensagem de status. Num lugar só.
    _NOME_DA_FUNCAO = {"bc": "BC (Bewitcher Cave)",
                       "hh": "HH (Black Wind Camp)",
                       "app": "modo APP"}

    def definir_funcao(self, uid: str, qual: str) -> str:
        """Liga UMA função nesta conta e desliga as outras. `""` desliga todas.

        SUBSTITUI `alternar_farm`, `alternar_hh` e `alternar_app`, que eram três
        escritas independentes -- e é por isso que duas ficavam ligadas ao mesmo
        tempo. A partir de 06/09/2026 as três são MUTUAMENTE EXCLUSIVAS: marcar
        uma TROCA, nunca soma. Quem impõe é `BotConfig.definir_funcao_da_conta`,
        um ponto de escrita só.

        VALE COM O BOT RODANDO, como já valia antes: o supervisor consulta os
        campos a cada volta e a conta migra no próximo ponto seguro. O aviso diz
        o que a troca custa -- trocar no meio de uma run da cave perde aquela run
        (teleporte gasto, boss vivo). Bloquear seria tirar uma função que o
        usuário usa; avisar deixa a decisão com ele.
        """
        c = self._conta(uid)
        antes = self.config.funcao_ativa_da_conta(c)
        agora = self.config.definir_funcao_da_conta(c, qual)
        if self.manager and self.manager.running() and antes != agora:
            if agora and antes:
                self._status(c.login,
                             f"trocando de {self._NOME_DA_FUNCAO[antes]} para "
                             f"{self._NOME_DA_FUNCAO[agora]} em tempo real — a "
                             "volta em andamento é perdida")
            elif agora:
                self._status(
                    c.login,
                    f"{self._NOME_DA_FUNCAO[agora]} LIGADA em tempo real")
            else:
                self._status(c.login,
                             f"{self._NOME_DA_FUNCAO[antes]} desligada em tempo "
                             "real — a conta fica só no login e relogin")
        self._aplicar()
        return agora

    def salvar_personagem(self, uid: str, dados: dict[str, Any]) -> None:
        """Aplica o editor da conta (espelha `AccountDialog._aplicar`).

        O login é editável AQUI (campo do editor). Vazio não apaga o login
        atual; diferente, renomeia. É o mesmo efeito do login editável da
        célula da tabela.
        """
        c = self._conta(uid)
        st = c.settings

        novo_login = str(dados.get("login", "") or "").strip()
        if novo_login:
            c.login = novo_login

        c.last_char_name = str(dados.get("nick", "")).strip()
        # Rótulo de organização. Não representa time nenhum -- ver `Account.grupo`.
        c.grupo = str(dados.get("grupo", "") or "").strip()[:LIMITE_DO_NOME_DO_GRUPO]
        st.accept_team_invites = bool(dados.get("accept_team_invites", False))
        st.reset_nick = str(dados.get("reset_nick", "") or "").strip()
        st.sell_clicks = int(dados.get("sell_clicks", 24) or 24)
        st.usar_catador = bool(dados.get("usar_catador", False))
        st.mount_speed_pct = int(dados.get("mount_speed_pct") or MOUNT_SPEEDS[0])

        pet = dados.get("pet", {})
        st.pet.summon_on_login = bool(pet.get("summon_on_login", True))
        st.pet.feed_on_start = bool(pet.get("feed_on_start", False))
        st.pet.feed_every_minutes = pet_feed_na_faixa(
            pet.get("feed_every_minutes"))

        pot = dados.get("potions", {})
        st.potions.hp_pct = int(pot.get("hp_pct", 85))
        # 15 e nao 90: em batalha o bot nao se cura, a pocao de batalha e
        # reserva. Ver o comentario do campo em `config.py`.
        st.potions.battle_hp_pct = int(pot.get("battle_hp_pct", 15))
        st.potions.emergency_pct = int(pot.get("emergency_pct", 25))

        bags = dados.get("bags", {})
        st.bags.bolsas = int(bags.get("bolsas", 1))

        app = dados.get("app", {})
        st.app.enabled = bool(app.get("enabled", False))
        st.app.apagar_lixo_a_cada = max(
            0, int(app.get("apagar_lixo_a_cada", 10) or 0))
        # A LISTA DE ITENS QUE ESTA CONTA APAGA. O padrão do `get` é O VALOR
        # ATUAL: a janela dos itens é outra tela, e um payload do editor sem a
        # chave APAGARIA a seleção inteira, em silêncio.
        st.app.apagaveis = normalizar_modelos(
            app.get("apagaveis", st.app.apagaveis))
        st.app.travar_posicao = bool(app.get("travar_posicao", True))
        st.app.shuffle_apos_n_voltas = max(
            1, int(app.get("shuffle_apos_n_voltas") or 30) or 30)
        # O PISO DE 100 ms TAMBÉM AQUI. A tela já o impõe no campo, mas a ponte
        # aceita o que o JavaScript mandar -- e "a tela impõe" não é garantia,
        # é boa vontade. Ver `MINIMO_DE_ESPERA_DO_APP_MS`.
        st.app.espera_depois_do_tab_ms = max(
            MINIMO_DE_ESPERA_DO_APP_MS,
            int(app.get("espera_depois_do_tab_ms", 1000) or 0))
        # O TIME. O padrão do `get` é O VALOR ATUAL, e não o default do
        # dataclass: enquanto a tela do time não existir, um payload sem a
        # chave APAGARIA o time já configurado -- em silêncio, que é como este
        # projeto perde configuração. Chave ausente significa "não mexi nisto".
        st.app.time_logins = normalizar_time_logins(
            app.get("time_logins", st.app.time_logins))
        st.app.time_modo = normalizar_time_modo(
            app.get("time_modo", st.app.time_modo))
        st.app.fada = bool(app.get("fada", st.app.fada))
        st.app.cura_pedir_pct = normalizar_pct(
            app.get("cura_pedir_pct"), st.app.cura_pedir_pct)
        st.app.cura_parar_pct = normalizar_pct(
            app.get("cura_parar_pct"), st.app.cura_parar_pct)
        passos = (app.get("steps") or [])[:PASSOS_DO_APP]
        for i, passo in enumerate(st.app.steps):
            bruto = passos[i] if i < len(passos) else {}
            passo.key = str(bruto.get("key", "") or "").upper()
            passo.delay_ms = max(MINIMO_DE_ESPERA_DO_APP_MS,
                                 int(bruto.get("delay_ms", 800) or 0))

        k = dados.get("keys", {})
        st.keys.attack_skills = [
            str(x).upper() for x in (k.get("attack_skills") or [])
            if str(x).strip()
        ]
        st.keys.aoe_skill = str(k.get("aoe_skill", "") or "").upper()
        st.keys.break_soul = str(k.get("break_soul", "") or "").upper()
        st.keys.super_skill = str(k.get("super_skill", "") or "").upper()
        st.keys.heal_skill = str(k.get("heal_skill", "") or "").upper()
        st.keys.revive_skill = str(k.get("revive_skill", "") or "").upper()
        st.keys.buffs = [
            str(x).upper() for x in (k.get("buffs") or []) if str(x).strip()
        ]
        st.keys.hp_potion = str(k.get("hp_potion", "") or "").upper()
        st.keys.battle_hp_potion = str(
            k.get("battle_hp_potion", "") or "").upper()
        st.keys.pet_food = str(k.get("pet_food", "") or "").upper()
        st.keys.stone_charm = str(k.get("stone_charm", "") or "").upper()
        st.keys.mount = str(k.get("mount", "") or "").upper()
        st.keys.speed_skill = str(k.get("speed_skill", "") or "").upper()
        st.keys.guild_token = str(k.get("guild_token", "") or "").upper()
        st.keys.pet_summon = str(k.get("pet_summon", "") or "").upper()
        st.keys.next_target = str(k.get("next_target", "") or "").upper()
        st.keys.sit = str(k.get("sit", "") or "").upper()
        st.keys.self_target = str(k.get("self_target", "") or "").upper()
        st.keys.follow = str(k.get("follow", "") or "").upper()
        st.keys.inventory = str(k.get("inventory", "") or "").upper()
        st.keys.friend_list = str(k.get("friend_list", "") or "").upper()
        st.keys.hotbar_page_1 = str(
            k.get("hotbar_page_1", "") or "").upper()
        st.keys.hide_players = str(
            k.get("hide_players", "") or "").upper()

        bc = dados.get("bc", {})
        st.bc.boss_name = str(bc.get("boss_name", "")).strip()
        st.bc.attack_delay = float(bc.get("attack_delay", 0.5) or 0.5)
        st.bc.heal_before_second_phase = bool(
            bc.get("heal_before_second_phase", True))
        st.bc.aoe_until_mana_pct = int(bc.get("aoe_until_mana_pct", 30))
        st.bc.usar_skill_de_velocidade = bool(
            bc.get("usar_skill_de_velocidade", True))

        # --- HH -----------------------------------------------------------
        # Sem esta leitura os campos voltam ao padrão a cada abertura do editor
        # -- a mesma armadilha que o `apagar_lixo_a_cada` e o `usar_catador` já
        # pagaram. Travado por `test_config_ida_e_volta.py`.
        hh = dados.get("hh", {})
        st.hh.modo_do_reset = normalizar_modo_do_reset(hh.get("modo_do_reset"))
        st.hh.attack_delay = float(hh.get("attack_delay", 0.5) or 0.5)
        st.hh.aoe_until_mana_pct = int(hh.get("aoe_until_mana_pct", 30))
        st.hh.limpar_mobs_a_cada = int(hh.get("limpar_mobs_a_cada", 3))
        # PADRÃO FALSE, e o padrão é a decisão: apagar é irreversível.
        st.hh.deletar_lixo = bool(hh.get("deletar_lixo", False))
        st.hh.apagaveis = normalizar_modelos(
            hh.get("apagaveis", st.hh.apagaveis))
        VH = hh.get("vendor", {})
        st.hh.vendor.sell_start_slot = int(VH.get("sell_start_slot", 3))
        st.hh.vendor.runs_before_selling = int(
            VH.get("runs_before_selling", 5))

        V = bc.get("vendor", {})
        st.bc.vendor.runs_before_selling = int(V.get("runs_before_selling", 5))
        st.bc.vendor.sell_start_slot = int(V.get("sell_start_slot", 3))
        st.bc.vendor.buy_return_charm = bool(V.get("buy_return_charm", False))

        self._aplicar()

    # ------------------------------------------------------------------
    # controle do bot
    # ------------------------------------------------------------------

    def iniciar(self) -> dict[str, Any]:
        problemas = self.config.validate()
        if problemas:
            return {"ok": False, "erros": problemas}

        self.manager = BotManager(self.config, on_status=self._status)
        erros = self.manager.start()
        if erros:
            self.manager = None
            return {"ok": False, "erros": erros}
        return {"ok": True, "erros": []}

    def parar(self) -> None:
        if self.manager:
            self.manager.stop()

    def pausar(self) -> None:
        if self.manager:
            self.manager.pause()

    def retomar(self) -> None:
        if self.manager:
            self.manager.resume()

    # TEMPORÁRIO ------------------------------------------------------
    def testar_venda(self, uid: str) -> dict[str, Any]:
        """Roda só a venda, na conta selecionada. Bloqueia até terminar.

        Bloquear é seguro: o pywebview atende cada chamada do frontend em uma
        thread própria, então o poll do log (300 ms) continua correndo e o
        usuário acompanha o teste ao vivo.
        """
        if self.manager and self.manager.running():
            return {"ok": False, "erro": (
                "Pare o bot antes de testar a venda — os dois disputariam o "
                "teclado e o mouse do mesmo cliente.")}
        try:
            conta = self._conta(uid)
        except ValueError as exc:
            return {"ok": False, "erro": str(exc)}
        return teste_venda.rodar(self.config, conta, on_status=self._status)

    def cancelar_teste_venda(self) -> None:
        """Interrompe a venda em andamento.

        Existe porque o botão Parar da barra fica desabilitado com o bot
        parado -- e o teste roda justamente com o bot parado. Quem cancela é o
        próprio botão do teste, que troca de papel enquanto a venda corre.
        """
        teste_venda.cancelar()

    def amostrar_cliques(self, uid: str) -> dict[str, Any]:
        """Varre coordenadas de clique DIREITO no ponto onde o personagem está.

        Bloqueia como o teste de venda, e pelo mesmo motivo: cada chamada do
        frontend já vem em sua própria thread no pywebview.
        """
        if self.manager and self.manager.running():
            return {"ok": False, "erro": (
                "Pare o bot antes de amostrar — os dois disputariam o teclado "
                "e o mouse do mesmo cliente.")}
        try:
            conta = self._conta(uid)
        except ValueError as exc:
            return {"ok": False, "erro": str(exc)}
        return amostragem_de_cliques.rodar(self.config, conta,
                                           on_status=self._status)

    def cancelar_amostragem(self) -> None:
        """Interrompe a amostragem em andamento (o próprio botão cancela)."""
        amostragem_de_cliques.cancelar()

    def conferir_modelos_de_exclusao(self, uid: str) -> dict[str, Any]:
        """Fotografa a bolsa e DESENHA o que seria apagado. Não apaga nada."""
        if self.manager and self.manager.running():
            return {"ok": False, "erro": (
                "Pare o bot antes de conferir — os dois disputariam o teclado "
                "e o mouse do mesmo cliente.")}
        try:
            conta = self._conta(uid)
        except ValueError as exc:
            return {"ok": False, "erro": str(exc)}
        return afericao.rodar(self.config, conta, on_status=self._status)

    def lixo_da_conta(self, uid: str, lista: Any = "app") -> dict[str, Any]:
        """Os modelos daquela lista, com miniatura, nome e o estado da conta."""
        try:
            conta = self._conta(uid)
        except ValueError as exc:
            return {"ok": False, "erro": str(exc), "itens": []}
        try:
            return web_lixo.itens(conta, str(lista))
        except ValueError as exc:
            return {"ok": False, "erro": str(exc), "itens": []}

    def salvar_lixo_da_conta(self, uid: str, lista: Any,
                             apagaveis: Any) -> dict[str, Any]:
        """Grava a seleção. Vale na limpeza SEGUINTE, sem religar o bot.

        Não é promessa: a thread da conta lê `settings` no momento da limpeza, e
        é o mesmo objeto que esta linha muta. Ver `deletador.modelos_ativos`.
        """
        try:
            conta = self._conta(uid)
            resposta = web_lixo.guardar(conta, str(lista), apagaveis)
        except ValueError as exc:
            return {"ok": False, "erro": str(exc)}
        self._aplicar()
        return resposta

    def contas_sem_itens_para_apagar(self) -> list[dict[str, Any]]:
        """As contas ativas que vão abrir a bolsa e não apagar nada.

        Consultada pelo botão Iniciar. Lista vazia = ninguém para avisar.
        """
        return web_lixo.contas_ociosas(self.config)

    def desligar_funcao_sem_itens(self, uids: Any) -> dict[str, Any]:
        """Desliga a função dessas contas (e dos times delas) e grava.

        Elas continuam ATIVAS: logam e relogam, só não farmam -- para o usuário
        ajustar a seleção enquanto o resto do bot roda.
        """
        desligadas = web_lixo.desligar_funcao(self.config, uids)
        if desligadas:
            self._aplicar()
        return {"ok": True, "erro": "", "desligadas": desligadas}

    def exportar_lixo_da_conta(self, uid: str, lista: Any,
                               apagaveis: Any) -> dict[str, Any]:
        """Grava a seleção num `.json` que o usuário escolhe onde salvar."""
        try:
            conta = self._conta(uid)
            return web_lixo.exportar(conta, str(lista), apagaveis)
        except ValueError as exc:
            return {"ok": False, "erro": str(exc)}

    def importar_lixo_da_conta(self, uid: str, lista: Any) -> dict[str, Any]:
        """Lê um `.json` e DEVOLVE a seleção. Não grava: quem aplica é a tela,
        e por isso o Cancelar da janela ainda desfaz."""
        try:
            conta = self._conta(uid)
            return web_lixo.importar(conta, str(lista))
        except ValueError as exc:
            return {"ok": False, "erro": str(exc)}

    def abrir_imagem_da_afericao(self, caminho: Any) -> dict[str, Any]:
        try:
            import os

            os.startfile(str(Path(str(caminho)).resolve()))
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "erro": str(exc)}
    # ------------------------------------------------------- TEMPORÁRIO

    def estado(self) -> dict[str, Any]:
        rodando = bool(self.manager and self.manager.running())
        resumo = self.manager.summary() if rodando else {}
        total = {"runs": 0, "success": 0, "fail": 0, "relogins": 0}
        por_login = self._por_login()
        contas = []
        for login, d in resumo.items():
            for chave in ("runs", "success", "fail", "relogins"):
                total[chave] += d[chave]
            conta = por_login.get(login)
            contas.append({
                "login": login,
                # UID para a tela achar a LINHA certa. Ela casava por login, e
                # login repetido (o campo é livre) atualizava a primeira linha
                # encontrada -- que podia ser de outra conta. É a mesma classe de
                # defeito que o uid existe para fechar.
                "uid": conta.garantir_uid() if conta else "",
                "nick": _nick(conta) if conta else login,
                "farm": bool(d.get("farm")),
                # Ver `BotManager.summary`: "está na lista" não é "está no ar".
                "funcao": str(d.get("funcao") or ""),
                "conectada": bool(d.get("conectada")),
                "relogando": bool(d.get("relogando")),
                # DO RESUMO, e não da configuração em disco: é o mesmo lugar
                # de onde `farm` vem, então as duas caixas contam a mesma
                # história. Sem esta chave o espelho lia `undefined`, e
                # `!!undefined` é False -- ele DESMARCARIA a caixa da HH a cada
                # volta do polling.
                "farm_hh": bool(d.get("farm_hh")),
                "runs": d.get("runs", 0),
                "success": d.get("success", 0),
                "fail": d.get("fail", 0),
                "relogins": d.get("relogins", 0),
                "uptime": d.get("uptime", 0.0),
                "last_run": d.get("last_run", 0.0),
                "total_run": d.get("total_run", 0.0),
                # Tempo decorrido da run EM ANDAMENTO (cronômetro ao vivo);
                # 0.0 quando a conta está online parada, entre runs.
                "run_now": d.get("run_now", 0.0),
                # Tempo do trajeto até o boss na run atual (congela na chegada)
                # e se ele já foi alcançado -- alimenta o cronômetro ao vivo.
                "boss_now": d.get("boss_now", 0.0),
                "boss_atingido": d.get("boss_atingido", False),
            })
        return {
            "rodando": rodando,
            "pausado": bool(self.manager.paused) if self.manager else False,
            "total": total,
            "contas": sorted(contas, key=lambda x: x["nick"]),
            # Ambiente de log (dev/prod) e nível atual do logger `blazes`: a
            # web usa para mostrar/ocultar o toggle "log detalhado".
            "modo": logmodo.modo_atual(),
            "dev": logmodo.eh_dev(),
            "nivel_log": logging.getLevelName(
                logging.getLogger("blazes").getEffectiveLevel()),
        }

    # ------------------------------------------------------------------
    # histórico de quedas
    # ------------------------------------------------------------------

    def historico_de_quedas(self, conta: Any = None) -> dict[str, Any]:
        """As quedas dos últimos dias, já traduzidas para português de gente.

        O Python entrega PRONTO: as frases, a lista de contas do seletor e o
        caminho do print. O JS só desenha -- traduzir em dois lugares divergiria
        na primeira frase que alguém ajustasse.
        """
        login = (str(conta) if conta else "").strip() or None
        return {
            "quedas": quedas.listar(login),
            "contas": quedas.contas_com_quedas(),
            "dias": quedas.DIAS_GUARDADOS,
        }

    def copiar_relatorio_de_quedas(self, conta: Any = None) -> dict[str, Any]:
        """O texto do "Copiar relatório" — COM os detalhes técnicos.

        O clipboard em si é feito no JS (o pywebview não expõe API para isso);
        aqui se monta o texto, que é regra de negócio e mora no Python.
        """
        login = (str(conta) if conta else "").strip() or None
        return {"texto": quedas.relatorio(quedas.listar(login))}

    def print_da_queda(self, nome: Any) -> dict[str, Any]:
        """O print INTEIRO, embutido, pedido quando o usuário clica na miniatura."""
        return {"imagem": quedas.imagem_embutida(str(nome) if nome else None)}

    def abrir_pasta_de_quedas(self) -> dict[str, Any]:
        """Abre `logs/quedas/` no Explorer — onde ficam os prints."""
        try:
            import os

            quedas.PASTA.mkdir(parents=True, exist_ok=True)
            os.startfile(str(quedas.PASTA.resolve()))
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "erro": str(exc)}

    # ------------------------------------------------------------------
    # estatísticas (persistidas + sessão)
    # ------------------------------------------------------------------

    def personagens_com_runs(self) -> list[dict[str, Any]]:
        resumo = (self.manager.summary()
                  if (self.manager and self.manager.running()) else {})
        candidatos = []
        for c in self.config.accounts:
            login = c.login
            if not login:
                continue
            dia = stats_diarias.ultimos_dias(login, 1)[0][1]
            sess = resumo.get(login, {})
            total = dia.get("runs", 0) + sess.get("runs", 0)
            if total <= 0:
                continue
            candidatos.append({"login": login, "nick": _nick(c),
                               "total": total})
        candidatos.sort(key=lambda t: -t["total"])
        return candidatos

    def stats(self, login: str) -> dict[str, Any]:
        resumo = (self.manager.summary()
                  if (self.manager and self.manager.running()) else {})
        sess = resumo.get(login, {})
        hoje = stats_diarias.ultimos_dias(login, 1)[0][1]
        runs = hoje.get("runs", 0)

        cards = {
            "runs_hoje": {"rotulo": "Runs hoje", "valor": str(runs)},
            "success_hoje": {"rotulo": "Sucesso hoje",
                             "valor": str(hoje.get("success", 0))},
            "fail_hoje": {"rotulo": "Falhas hoje",
                          "valor": str(hoje.get("fail", 0))},
            "taxa_hoje": {"rotulo": "Taxa de sucesso",
                          "valor": "—" if not runs else
                          f"{100.0 * hoje.get('success', 0) / runs:.0f}%"},
            "media_hoje": {"rotulo": "T. médio hoje",
                           "valor": "—" if not runs else format_duracao(
                               hoje.get("total_run_seconds", 0.0) / runs)},
            "boss_ult": {"rotulo": "T. até boss (últ.)",
                         "valor": "—" if not runs else format_duracao(
                             hoje.get("last_boss_seconds", 0.0))},
            "total_ult": {"rotulo": "T. total (últ.)",
                          "valor": "—" if not sess else format_duracao(
                              sess.get("last_run", 0.0))},
            "total_hoje": {"rotulo": "T. total das runs hoje",
                           "valor": "—" if not runs else format_duracao(
                               hoje.get("total_run_seconds", 0.0))},
            "sessao_runs": {"rotulo": "Runs na sessão",
                            "valor": str(sess.get("runs", 0))},
            "sessao_ok": {"rotulo": "Sessão (ok/falhas)",
                          "valor": f"{sess.get('success', 0)} ok / "
                                   f"{sess.get('fail', 0)} falhas"},
        }

        # Dias anteriores (não inclui hoje) -- espelho de `_preencher_historico`.
        historico = []
        hoje_iso = date.today().isoformat()
        if stats_diarias.conhece(login):
            for dia, d in stats_diarias.ultimos_dias(login):
                if dia == hoje_iso:
                    continue
                media = d["total_run_seconds"] / d["runs"] if d["runs"] else None
                boss = (d.get("total_boss_seconds", 0.0) / d["runs"]
                        if d["runs"] else None)
                historico.append({
                    "dia": dia,
                    "runs": str(d["runs"]),
                    "success": str(d["success"]),
                    "fail": str(d["fail"]),
                    "boss": "—" if boss is None else format_duracao(boss),
                    "media": "—" if media is None else format_duracao(media),
                })
        return {"cards": cards, "historico": historico}

    # ------------------------------------------------------------------
    # log
    # ------------------------------------------------------------------

    def puxar_log(self, desde: int) -> dict[str, Any]:
        """Drena a fila nova e devolve as linhas novas desde o índice pedido.

        Se o histórico já descartou o `desde` (corte de `MAX_LINHAS_GUARDADAS`),
        devolve tudo o que tem -- o frontend refaz a tela inteira.
        """
        while self._fila_log:
            conta, linha = self._fila_log.popleft()
            self._historico.append((conta, linha))
            self._total += 1
            if conta:
                self._contagem_por_conta[conta] = (
                    self._contagem_por_conta.get(conta, 0) + 1
                )

        try:
            desde_i = int(desde)
        except (TypeError, ValueError):
            desde_i = 0
        # ================================================================
        # O CURSOR É ABSOLUTO; A DEQUE É UMA JANELA. TRADUZIR É OBRIGATÓRIO.
        # ================================================================
        #
        # `_total` só cresce (é o número da última linha já enfileirada, de
        # sempre). `_historico` é uma deque com `maxlen=MAX_LINHAS_GUARDADAS`:
        # passado esse teto, ela DESCARTA pela frente e o índice 0 dela deixa de
        # ser a linha 0 da execução.
        #
        # A versão anterior comparava o cursor absoluto direto com
        # `len(self._historico)`:
        #
        #     corte = desde_i if 0 <= desde_i <= len(self._historico) else 0
        #
        # Enquanto o total era menor que o teto, os dois coincidiam e funcionava.
        # NA LINHA 12 001 ele quebra PARA SEMPRE: `desde_i` continua subindo,
        # `len(_historico)` fica preso em 12 000, a condição passa a ser sempre
        # falsa e `corte` vira 0 -- o histórico INTEIRO é devolvido a cada poll de
        # 300 ms, indefinidamente.
        #
        # ISSO É A CAUSA DO CONGELAMENTO DA INTERFACE APÓS HORAS, e explica o
        # sintoma exato relatado: o bot continua rodando (as threads dele não
        # passam por aqui) e só a janela morre. Cada retorno de método `js_api` do
        # pywebview é embutido num literal JS e executado por `evaluate_js`, que
        # chama `webview.Invoke(...)` -- ou seja ~2 MB de script na THREAD DE UI
        # do WebView2, 3,3 vezes por segundo. E o backoff do frontend nunca liga,
        # porque com linhas voltando sempre ele acha que há novidade sempre.
        #
        # A tradução: quantas linhas já saíram pela frente da deque é
        # `_total - len(_historico)`. O cursor do frontend menos isso é a posição
        # dentro da janela. `max(0, ...)` cobre o frontend atrasado (as linhas que
        # ele perdeu não existem mais); `min(..., len)` cobre o cursor à frente do
        # total, que é o poll ocioso e deve devolver vazio.
        descartadas = self._total - len(self._historico)
        corte = max(0, min(desde_i - descartadas, len(self._historico)))
        # `islice` sobre a deque EVITA a cópia integral que `list(self._historico)`
        # fazia a cada poll de 300 ms. Com 12 000 linhas acumuladas, aquela cópia
        # alocava ~3,6 MB por poll x 3,3 polls/s = ~12 MB/s de pressão de GC —
        # era a causa primária do congelamento progressivo da interface após horas.
        novas = [{"conta": c, "linha": l}
                 for c, l in islice(self._historico, corte, None)]
        return {"linhas": novas, "total": self._total,
                "por_conta": dict(self._contagem_por_conta)}

    def limpar_log(self) -> None:
        self._fila_log.clear()
        self._historico.clear()
        self._contagem_por_conta.clear()
        self._total = 0


_APP = _App()

# Janela aberta pelo pywebview, preenchida em `run()`. Usada por
# `minimizar_janela`/`fechar_janela` (os botões da barra customizada).
_JANELA: Any = None


class Api:
    """Objeto exposto ao frontend como `js_api` do pywebview.

    Métodos públicos viram `window.pywebview.api.<nome>(...)` no JavaScript
    (cada chamada resolve uma Promise com o retorno). Métodos cujo nome começa
    com `_` NÃO são expostos (contrato do pywebview) — por isso o `_app` fica
    privado. São exatamente os `@eel.expose` de antes, só que como métodos de
    uma instância. Nenhuma regra de negócio nova aqui: só delegam para `_APP`.
    """

    def __init__(self, app: _App) -> None:
        self._app = app

    # ---- leitura e constantes ----

    def obter_constantes(self) -> dict[str, Any]:
        return self._app.constantes()

    def obter_config(self) -> dict[str, Any]:
        return self._app.config_atual()

    def obter_contas(self) -> list[dict[str, Any]]:
        return self._app.contas()

    def obter_conta(self, uid: Any) -> dict[str, Any]:
        return self._app.conta_editor(uid)

    # ---- escrita (tempo real) ----

    def salvar_config_geral(self, dados: Any) -> dict[str, Any]:
        self._app.salvar_config(dados)
        return {"ok": True}

    def definir_idioma(self, idioma: Any) -> dict[str, Any]:
        self._app.definir_idioma(str(idioma))
        return {"ok": True}

    def definir_senha(self, uid: Any, nova: Any) -> dict[str, Any]:
        # A cifra RECUSA sem DPAPI (`core/secrets.encrypt`), e a tela precisa
        # saber: sem este `except`, o erro sumia no `chamar()` do JS e a tela
        # dizia "senha gravada" com a senha antiga valendo.
        try:
            self._app.definir_senha(uid, nova)
        except Exception as exc:
            return {"ok": False, "erro": str(exc)}
        return {"ok": True}

    def definir_login(self, uid: Any, novo: Any) -> dict[str, Any]:
        self._app.definir_login(uid, novo)
        return {"ok": True}

    def definir_posicao(self, uid: Any, posicao: Any) -> dict[str, Any]:
        self._app.definir_posicao(uid, posicao)
        return {"ok": True}

    def definir_servidor(self, uid: Any, servidor: Any) -> dict[str, Any]:
        self._app.definir_servidor(uid, servidor)
        return {"ok": True}

    def reordenar_contas(self, ordem: Any) -> dict[str, Any]:
        """Grava a nova ordem das contas. UMA chamada por arraste.

        SÍNCRONA E SEM DEBOUNCE, de propósito: debounce é justamente o que perde a
        última alteração quando a janela fecha, e o drop é evento raro e
        deliberado (não é digitação). Medido: `config.json` tem ~19 KB com 7
        contas, a gravação é atômica (`.tmp` + `os.replace`) e cada caixa
        clicada na tabela já grava o arquivo inteiro hoje.

        Devolve a lista de contas depois da gravação, para a tela redesenhar do
        que está NO DISCO em vez de confiar no que ela mesma reorganizou. Se esta
        chamada falhar, a tela volta à ordem anterior (ver `aoSoltarLinha`).
        """
        if not isinstance(ordem, list):
            return {"ok": False, "erro": "ordem inválida"}
        # Cada item é `{uid, grupo}`: a ordem e os rótulos vêm JUNTOS, numa
        # chamada só. Separados, uma podia gravar e a outra falhar, e a tabela
        # ficaria com a ordem nova e o grupo velho.
        try:
            itens = [(str(i.get("uid", "")), i.get("grupo", ""))
                     for i in ordem if isinstance(i, dict)]
        except AttributeError:
            return {"ok": False, "erro": "ordem inválida"}
        try:
            self._app.reordenar_contas(itens)
        except Exception as exc:
            return {"ok": False, "erro": str(exc)}
        return {"ok": True, "contas": self._app.contas()}

    def definir_grupo(self, uid: Any, grupo: Any) -> dict[str, Any]:
        """Rótulo de organização da conta. NÃO É TIME -- ver `Account.grupo`."""
        try:
            self._app.definir_grupo(uid, grupo)
        except Exception as exc:
            return {"ok": False, "erro": str(exc)}
        return {"ok": True}

    def nova_conta(self) -> dict[str, Any]:
        self._app.nova_conta()
        return {"ok": True}

    def remover_conta(self, uid: Any) -> dict[str, Any]:
        # O BLOQUEIO É AQUI, NO BACKEND, e não só na tela: o frontend também
        # avisa, mas quem garante é este ponto -- é por onde toda remoção passa.
        bloqueio = self._app.bloqueio_de_reseter(uid, "remover")
        if bloqueio:
            return {"ok": False, "erro": bloqueio}
        self._app.remover_conta(uid)
        return {"ok": True}

    def ativar_conta(self, uid: Any, ativa: Any) -> dict[str, Any]:
        if not bool(ativa):
            bloqueio = self._app.bloqueio_de_reseter(uid, "desativar")
            if bloqueio:
                return {"ok": False, "erro": bloqueio}
        return {"ok": True, "iniciadas": self._app.alternar(uid, bool(ativa))}

    def definir_funcao(self, uid: Any, qual: Any) -> dict[str, Any]:
        """Liga UMA função na conta e desliga as outras.

        UMA chamada no lugar das três `alternar_*`: se a tela mandasse "desliga
        BC" e "liga HH" em duas chamadas, entre elas existiria um instante com
        as duas ligadas -- e o supervisor lê os campos a cada volta.
        """
        try:
            ativa = self._app.definir_funcao(uid, qual)
        except Exception as exc:
            return {"ok": False, "erro": str(exc)}
        return {"ok": True, "funcao": ativa}

    def salvar_personagem(self, uid: Any, dados: Any) -> dict[str, Any]:
        # DESMARCAR 'aceitar convites' de um reseter é o mesmo estrago que
        # deletar ou desativar, por outra porta: a conta fica no ar mas para de
        # aceitar o convite, e quem depende dela não reseta mais a cave.
        if not bool((dados or {}).get("accept_team_invites", False)):
            bloqueio = self._app.bloqueio_de_reseter(
                uid, "tirar a marca de 'aceitar convites de time' de")
            if bloqueio:
                return {"ok": False, "erro": bloqueio}
        self._app.salvar_personagem(uid, dados)
        return {"ok": True}

    # ---- controle do bot ----

    def iniciar(self) -> dict[str, Any]:
        return self._app.iniciar()

    def parar(self) -> dict[str, Any]:
        self._app.parar()
        return {"ok": True}

    def pausar(self) -> dict[str, Any]:
        self._app.pausar()
        return {"ok": True}

    def retomar(self) -> dict[str, Any]:
        self._app.retomar()
        return {"ok": True}

    def estado(self) -> dict[str, Any]:
        return self._app.estado()

    def personagens_com_runs(self) -> list[dict[str, Any]]:
        return self._app.personagens_com_runs()

    def historico_de_quedas(self, conta: Any = None) -> dict[str, Any]:
        return self._app.historico_de_quedas(conta)

    def copiar_relatorio_de_quedas(self, conta: Any = None) -> dict[str, Any]:
        return self._app.copiar_relatorio_de_quedas(conta)

    def print_da_queda(self, nome: Any) -> dict[str, Any]:
        return self._app.print_da_queda(nome)

    def abrir_pasta_de_quedas(self) -> dict[str, Any]:
        return self._app.abrir_pasta_de_quedas()

    def stats_conta(self, login: Any) -> dict[str, Any]:
        return self._app.stats(login)

    def testar_venda(self, uid: Any) -> dict[str, Any]:
        return self._app.testar_venda(uid)

    def cancelar_teste_venda(self) -> dict[str, Any]:
        self._app.cancelar_teste_venda()
        return {"ok": True}

    def amostrar_cliques(self, uid: Any) -> dict[str, Any]:
        return self._app.amostrar_cliques(uid)

    def cancelar_amostragem(self) -> dict[str, Any]:
        self._app.cancelar_amostragem()
        return {"ok": True}

    def conferir_modelos_de_exclusao(self, uid: Any) -> dict[str, Any]:
        return self._app.conferir_modelos_de_exclusao(uid)

    def lixo_da_conta(self, uid: Any, lista: Any = "app") -> dict[str, Any]:
        return self._app.lixo_da_conta(uid, lista)

    def salvar_lixo_da_conta(self, uid: Any, lista: Any,
                             apagaveis: Any) -> dict[str, Any]:
        return self._app.salvar_lixo_da_conta(uid, lista, apagaveis)

    def contas_sem_itens_para_apagar(self) -> list[dict[str, Any]]:
        return self._app.contas_sem_itens_para_apagar()

    def desligar_funcao_sem_itens(self, uids: Any) -> dict[str, Any]:
        return self._app.desligar_funcao_sem_itens(uids)

    def exportar_lixo_da_conta(self, uid: Any, lista: Any,
                               apagaveis: Any) -> dict[str, Any]:
        return self._app.exportar_lixo_da_conta(uid, lista, apagaveis)

    def importar_lixo_da_conta(self, uid: Any, lista: Any) -> dict[str, Any]:
        return self._app.importar_lixo_da_conta(uid, lista)

    def abrir_imagem_da_afericao(self, caminho: Any) -> dict[str, Any]:
        return self._app.abrir_imagem_da_afericao(caminho)

    # ---- log ----

    def puxar_log(self, desde: Any) -> dict[str, Any]:
        return self._app.puxar_log(desde)

    def limpar_log(self) -> dict[str, Any]:
        self._app.limpar_log()
        return {"ok": True}

    def definir_nivel_log(self, nivel: str) -> dict[str, Any]:
        """Ajusta o nível do logger `blazes` .

        Só vale no ambiente dev (`BLAZES_MODO=dev`): é o toggle "log detalhado"
        da web. Em prod o nível é sempre INFO+ e a chamada é ignorada -- o
        usuário não recebe log de desenvolvimento.
        """
        blazes = logging.getLogger("blazes")
        if not logmodo.eh_dev():
            blazes.setLevel(logging.INFO)
            return {"ok": True, "nivel": logging.INFO}
        nome = str(nivel or "").upper()
        nivel_novo = getattr(logging, nome, None)
        if not isinstance(nivel_novo, int):
            return {"ok": False, "erro": f"nível inválido: {nivel}"}
        blazes.setLevel(nivel_novo)
        return {"ok": True, "nivel": nivel_novo}

    # ---- janela e utilitários ----

    def procurar_client_bat(self) -> Any:
        """Seletor nativo do Client.bat.

        O WebView2 não consegue ler o caminho real de um `<input type=file>`
        (o Chromium devolve só um caminho fictício), então o diálogo fica no
        Python. Tkinter só é importado aqui, dentro do método — não é a
        interface, é um utilitário. Se Tkinter faltar, devolve None e o campo
        mantém o texto digitado.
        """
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            caminho = filedialog.askopenfilename(
                title="Escolha o Client.bat do Talisman Online",
                filetypes=[("Client.bat", "Client.bat"), ("Arquivo BAT", "*.bat"),
                           ("Todos os arquivos", "*.*")],
                parent=root,
            )
            root.destroy()
            return caminho or None
        except Exception:
            return None

    def minimizar_janela(self) -> bool:
        """Minimiza a janela da webview (botão da barra customizada)."""
        try:
            _JANELA.minimize()
            return True
        except Exception:
            return False

    def fechar_janela(self) -> bool:
        """Fecha a janela da webview (botão ✕ da barra customizada)."""
        try:
            _JANELA.destroy()
            return True
        except Exception:
            return False

    def abrir_pasta_logs(self) -> bool:
        """Abre a pasta `logs/` no Explorer."""
        try:
            import os

            pasta = Path("logs")
            pasta.mkdir(exist_ok=True)
            os.startfile(str(pasta.resolve()))
            return True
        except Exception:
            return False


def run() -> None:
    """Sobe a interface web. O lançador já exigiu admin e ligou o logging.

    O WebView2 Runtime usado pelo pywebview já vem embutido no Windows 11 (e é
    atualizado pelo Windows Update), então NÃO dependemos de navegador externo
    instalado — diferente do antigo `eel.start(mode=...)`, que exigia Chrome/
    Edge/Opera na máquina. `private_mode=False` preserva o `localStorage`
    (tema escuro/claro) entre sessões — mas faz o WebView2 cachear a página
    file://; por isso a URL do dist ganha `?v=<mtime>` (ver `run()`): só muda
    quando o `npm run build` regenera o dist, então reabrir depois de um build
    sempre carrega o frontend novo.
    """
    global _JANELA

    # IDENTIDADE PRÓPRIA NA BARRA DE TAREFAS.
    #
    # O `icon=` do `webview.start` JÁ funcionava -- medido: a janela ganha ícone
    # próprio (`WM_GETICON` devolve handle nos dois tamanhos). O que faltava era
    # isto: sem um AppUserModelID, o Windows agrupa a janela sob o processo que a
    # criou -- o `python.exe` -- e o botão da barra de tarefas usa o ícone DELE,
    # a cobrinha azul e amarela, por mais bonito que seja o ícone da janela.
    #
    # Com o ID próprio, o BlazesBot passa a ser um aplicativo para o Windows:
    # ícone certo na barra, no Alt+Tab e na fixação. Falha tolerada -- ícone
    # errado não pode impedir o bot de abrir.
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "BlazesOfGamer.BlazesBot")
    except Exception as exc:                       # pragma: no cover
        logging.getLogger("blazes").debug(
            "AppUserModelID não aplicado: %s", exc)

    logger = logging.getLogger("blazes")
    if not any(isinstance(h, _LogHandler) for h in logger.handlers):
        logger.addHandler(_LogHandler(_APP._fila_log))
    # DEBUG SÓ EM DEV.
    #
    # Era `logging.DEBUG` incondicional, e isso DESFAZIA o nível que
    # `setup_logging` acabara de definir: em prod ele põe `blazes` em INFO, e
    # esta linha voltava tudo para DEBUG duas linhas depois.
    #
    # O custo não era estético. A rotina relê posição a cada 0,12 s por conta;
    # com 4-5 contas o volume de log sobe ~10x, e o teto de
    # `MAX_LINHAS_GUARDADAS` era atingido em MINUTOS em vez de horas — o que
    # antecipava o defeito do cursor de `puxar_log` (o congelamento da janela)
    # para quase o começo da execução.
    #
    # Também contrariava o contrato de `definir_nivel_log`, que já recusa trocar
    # o nível fora de dev, e a regra do `core/logmodo.py`.
    logger.setLevel(logging.DEBUG if logmodo.eh_dev() else logging.INFO)

    # Frontend compilado pelo Vite (`npm run build`). A edição da UI acontece
    # na pasta web/, mas o Python só enxerga as mudanças após o build gerar o
    # dist/. Se o dist não existir, instrua a rodar `npm run build`.
    # EMPACOTADO, `__file__` aponta para dentro do bundle temporário e o `dist/`
    # fica ao lado do `.exe` -- ver `core/raiz.py`.
    index = raiz_do_bot() / "dist" / "index.html"
    if not index.exists():
        raise FileNotFoundError(
            f"Não encontrei o frontend compilado:\n  {index}\n"
            "Rode `npm run build` na raiz do projeto antes de iniciar a web."
        )

    # Cache-busting do WebView2. Com `private_mode=False` o pywebview serve o
    # dist pelo server HTTP interno (http://127.0.0.1:<porta>/), preservando o
    # localStorage (tema) na origem. Só que o WebView2 pode devolver a página
    # ANTIGA do cache quando o `npm run build` regenera o dist com o MESMO URL.
    # Fix: anexar `?v=<mtime>` ao CAMINHO local (não converter em file:// — isso
    # quebra o load). O mtime só muda quando o build regenera o dist, então
    # reabrir depois de um build pega um URL novo (cache-busting) mantendo a
    # mesma origem http (tema preservado). pywebview trata `path?v=` como uma
    # URL local: o relpath vira `index.html?v=...` servido pelo HTTP interno.
    url = f"{index}?v={int(index.stat().st_mtime)}"
    _JANELA = webview.create_window(
        "BlazesBot",
        url,
        js_api=Api(_APP),
        width=1200,
        height=800,
        # Sem barra do Windows (frameless): o controle fica 100% na barra
        # customizada do frontend (`.titlebar`). Sem título nativo também não há
        # botão de maximizar — só minimizar/fechar, que o frontend já tem. Com o
        # tamanho travado (`resizable=False`) não existe nem redimensionar pela
        # borda, então o visual é limpo e não pode "estourar" o layout de alta
        # densidade.
        frameless=True,
        # easy_drag=False: o default do pywebview (True) deixa a janela INTEIRA
        # arrastável em modo frameless (JS registra mousedown global em qualquer
        # ponto). Com ele desligado, o arrasto fica restrito à região apontada
        # por `webview.settings['DRAG_REGION_SELECTOR']` (o `.titlebar`), logo
        # abaixo do create_window.
        easy_drag=False,
        resizable=False,
    )
    # O arrasto da janela frameless é 100% JS no pywebview/WebView2 — o CSS
    # `-webkit-app-region: drag` do frontend NÃO move a janela (ficou claro
    # quando easy_drag=False deixou o app sem área de arrasto nenhuma). O
    # seletor abaixo torna o `.titlebar` (barra "BlazesBot" + botões 🌙/—/✕) a
    # ÚNICA área arrastável; clicar em qualquer outro ponto do app não move a
    # janela.
    webview.settings["DRAG_REGION_SELECTOR"] = ".titlebar"
    # ÍCONE DA JANELA E DA BARRA DE TAREFAS. A janela é `frameless`, então o
    # ícone não aparece em barra de título nenhuma -- ele existe para a BARRA DE
    # TAREFAS e o Alt+Tab, que sem isto mostravam o ícone genérico do Python.
    # `icon=` é ignorado por alguns backends do pywebview, então a falha é
    # tolerada: ficar sem ícone não pode impedir o bot de abrir.
    icone = str(ICONE_DO_APP) if ICONE_DO_APP.exists() else None
    try:
        try:
            if icone:
                webview.start(private_mode=False, icon=icone)
            else:
                webview.start(private_mode=False)
        except TypeError:
            # Backend do pywebview sem suporte a `icon=`: abre sem ícone. Ficar
            # sem ícone não pode impedir o bot de subir.
            webview.start(private_mode=False)
    finally:
        if _APP.manager:
            _APP.manager.stop()
        try:
            _APP.config.save()
        except Exception:
            pass


def _main() -> None:
    """Entrada usada pelo INICIAR-WEB.bat (interface web).

    Reaproveita a exigência de admin e o logging do `main.py` SEM editar o
    `main.py`.
    """
    from main import require_admin, setup_logging  # raiz do projeto

    require_admin()
    setup_logging(verbose=True)
    run()


if __name__ == "__main__":
    _main()