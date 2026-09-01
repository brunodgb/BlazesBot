/* ============================================================
   BlazesBot — lógica da interface web (pywebview).
   NENHUMA regra de negócio aqui: este arquivo só chama o backend
   Python via `window.pywebview.api.*` e desenha o resultado.
   Espelho da GUI PyQt6 (blazesbot/gui/). Regra das duas
   interfaces: mudou um lado, muda o outro.
   ============================================================ */

"use strict";

/* ---------- helpers ---------- */
function chamar(nome, ...args) {
  // Cada método exposto pelo pywebview resolve uma Promise com o retorno.
  // Falha na chamada vira null (mesma tolerância do antigo bridge do Eel).
  const api = (window.pywebview && window.pywebview.api) || null;
  const fn = api ? api[nome] : null;
  if (typeof fn !== "function") return Promise.resolve(null);
  return Promise.resolve(fn(...args)).catch(() => null);
}

const $ = (sel) => document.querySelector(sel);
const $$ = (sel, root = document) =>
  Array.from(root.querySelectorAll(sel));

function esc(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function toast(msg, tipo = "info") {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "toast " + tipo;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (el.className = "toast escondida"), 2600);
}

function toastCurto(msg, tipo = "info", ms = 1800) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "toast " + tipo;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (el.className = "toast escondida"), ms);
}

function confirmar(msg) {
  return new Promise((resolve) => {
    confirmar._cb = resolve;
    $("#lbl-confirmar-msg").textContent = msg;
    $("#modal-confirmar").classList.remove("escondida");
  });
}
$("#btn-confirmar-ok").addEventListener("click", () => {
  $("#modal-confirmar").classList.add("escondida");
  if (confirmar._cb) confirmar._cb(true);
});
$("#btn-confirmar-nao").addEventListener("click", () => {
  $("#modal-confirmar").classList.add("escondida");
  if (confirmar._cb) confirmar._cb(false);
});

/* AVISO BLOQUEANTE — modal, nunca toast.
 *
 * O toast some em 2,6 s e é fácil de não ver. Quando a ação foi RECUSADA, o
 * usuário precisa saber por quê e o que fazer no lugar, então a mensagem
 * interrompe e fica na tela até ele confirmar que leu.
 *
 * Reusa o modal de confirmação escondendo o "Cancelar" e trocando o rótulo do
 * outro botão: um segundo modal no HTML seria a mesma caixa com outro id, e
 * duas caixas iguais divergem de estilo no primeiro ajuste de tema.
 */
function avisar(msg) {
  const nao = $("#btn-confirmar-nao");
  const ok = $("#btn-confirmar-ok");
  const rotulo = ok.textContent;
  nao.classList.add("escondida");
  ok.textContent = "Entendi";
  return confirmar(msg).then((r) => {
    nao.classList.remove("escondida");
    ok.textContent = rotulo;
    return r;
  });
}

/* ---------- estado global ---------- */
let constantes = null;
let contasCache = [];
// UID da conta selecionada na tabela, ou `null`.
//
// Era o ÍNDICE, e por isso `!contaUidSelecionado` tratava a PRIMEIRA conta
// (índice 0) como "nada selecionado" -- o botão Remover não ligava para ela.
// Com uid (texto) a comparação com `null` é a única que existe.
let contaUidSelecionado = null;
let contaUidEditando = null;
let statsLogin = null;

// Caches de render das estatísticas (ver `atualizarSeletorStats`/`carregarStats`).
// O poll de `estado` roda a cada 1,5 s; sem eles, reconstruiríamos o <select> e
// os cards/histórico de stats a cada poll mesmo quando nada mudou.
// - `ultimoSeletorSig` guarda a assinatura das opções do <select>; se igual,
//   não reconstruímos o <select> nem re-renderizamos stats (mesmos dados).
// - `ultimoStatsJson` guarda o último corpo de `stats_conta`; se o conteúdo é
//   o mesmo, pulamos a reconstrução de DOM (cards + histórico) idêntica do poll.
let ultimoSeletorSig = null;
let ultimoStatsJson = null;

let logCursor = 0;
let logCache = [];
let filtroLog = "";
// Comportamento do log idêntico ao desktop: por padrão acompanha a última
// linha; só para quando o usuário rola para cima (barra ou roda) e retoma ao
// voltar ao fim. `renderizadoAte`/`filtroRenderido` controlam o append-only.
let logSeguirFim = true;
let renderizadoAte = 0;
let filtroRenderido = null;
// Backoff do poll de log: intervalo normal (300 ms) quando há linhas novas;
// sobe progressivamente quando ocioso, até 5 s, para reduzir trabalho no
// backend quando o bot está quieto. O `logPollId` guarda o timer atual para
// poder reescalonar com o intervalo novo.
let logPollInterval = 300;
let logPollId = null;

/* ---------- cronômetro da run atual ----------
   O backend manda a cada poll de `estado` (1,5 s):
     - `run_now`      -> tempo total da run EM ANDAMENTO (0.0 entre runs);
     - `boss_now`     -> tempo do trajeto até o boss na run atual, congelado
                         no valor da chegada quando `boss_atingido` é true.
   Entre polls, o JS extrapola localmente com base no valor recebido e no
   relógio local, então os tempos CORREM visualmente em vez de saltar a cada
   1,5 s. Quando a run termina (ou a conta fica parada online) `run_now` volta
   a 0.0 -- aí o cronômetro mostra "—". */
let cronometroTotal = null; // {base, marcadoEm} com base = run_now do último poll
let cronometroBoss = null;  // {base, marcadoEm, fixo} -- `fixo` = boss já alcançado
let cronometroTimer = null;
let ultimoEstado = null; // último `estado()` recebido, para re-sincronizar o cronômetro

function formatarDuracao(segundos) {
  const t = Math.floor(Math.max(0, segundos));
  const dias = Math.floor(t / 86400);
  const horas = Math.floor((t % 86400) / 3600);
  const min = Math.floor((t % 3600) / 60);
  const seg = t % 60;
  if (dias) return `${dias}d ${horas}h ${min}m`;
  if (horas) return `${horas}h ${min}m ${seg}s`;
  if (min) return `${min}m ${seg}s`;
  return `${seg}s`;
}

function renderCronometro() {
  const elTotal = $("#cronometro-total-valor");
  const elBoss = $("#cronometro-boss-valor");
  const aviso = $("#cronometro-boss-aviso");
  const agora = performance.now();
  let total = 0;
  if (cronometroTotal) total = cronometroTotal.base + (agora - cronometroTotal.marcadoEm) / 1000;
  let boss = 0;
  if (cronometroBoss) {
    // Congela no valor da chegada quando o boss foi alcançado nesta run.
    boss = cronometroBoss.fixo
      ? cronometroBoss.base
      : cronometroBoss.base + (agora - cronometroBoss.marcadoEm) / 1000;
  }
  if (elTotal) elTotal.textContent = total > 0 ? formatarDuracao(total) : "—";
  if (elBoss) elBoss.textContent = boss > 0 ? formatarDuracao(boss) : "—";
  if (aviso) aviso.textContent = cronometroBoss && cronometroBoss.fixo ? "✓ boss alcançado" : "";
}

function sincronizarCronometro(est) {
  // A conta selecionada no seletor de estatísticas é a que tem o cronômetro.
  const conta = (est.contas || []).find((c) => c.login === statsLogin);
  const runNow = conta ? (conta.run_now || 0) : 0;
  const bossNow = conta ? (conta.boss_now || 0) : 0;
  const bossFixo = conta ? !!conta.boss_atingido : false;
  const agora = performance.now();

  if (runNow > 0) {
    cronometroTotal = { base: runNow, marcadoEm: agora };
  } else {
    cronometroTotal = null;
  }
  if (bossFixo) {
    // Boss alcançado: mostra o valor exato da chegada, sem extrapolar.
    cronometroBoss = { base: bossNow, marcadoEm: agora, fixo: true };
  } else if (bossNow > 0) {
    cronometroBoss = { base: bossNow, marcadoEm: agora, fixo: false };
  } else {
    cronometroBoss = null;
  }

  if (cronometroTotal || cronometroBoss) {
    if (!cronometroTimer) cronometroTimer = setInterval(renderCronometro, 200);
  } else {
    if (cronometroTimer) { clearInterval(cronometroTimer); cronometroTimer = null; }
  }
  renderCronometro();
}

/* ---------- navegação ---------- */
function navegar(secao) {
  $$(".secao").forEach((s) => s.classList.toggle("painel-visivel",
                                                 s.id === "secao-" + secao));
  $$(".nav-item").forEach((b) => b.classList.toggle("nav-ativo",
                                                    b.dataset.secao === secao));
  // O histórico de quedas carrega ao ABRIR, e não no poll: ele traz as
  // miniaturas embutidas e queda é evento raro (ver `carregarQuedas`).
  if (secao === "quedas") carregarQuedas();
  // O LOG SÓ TEM LAYOUT AGORA. Ver o item 1 de "SEGUIR O FIM DO LOG": tudo que
  // `renderLog` tentou rolar enquanto a seção estava `display: none` não teve
  // efeito, e sem este aviso o usuário entra na aba olhando o topo.
  if (secao === "log") colarNoFimDoLog();
}
$$(".nav-item").forEach((b) =>
  b.addEventListener("click", () => navegar(b.dataset.secao)));

/* ---------- barra de título ---------- */
$("#btn-fechar").addEventListener("click", () => chamar("fechar_janela"));
$("#btn-minimizar").addEventListener("click", () => chamar("minimizar_janela"));
$("#btn-tema").addEventListener("click", () => {
  const raiz = document.documentElement;
  const escuro = raiz.dataset.tema !== "claro";
  raiz.dataset.tema = escuro ? "claro" : "escuro";
  $("#btn-tema").textContent = escuro ? "☀️" : "🌙";
  try { localStorage.setItem("tema", raiz.dataset.tema); } catch (_) {}
});
(function temaInicial() {
  try {
    const t = localStorage.getItem("tema");
    if (t === "claro") {
      document.documentElement.dataset.tema = "claro";
      $("#btn-tema").textContent = "☀️";
    }
  } catch (_) {}
})();

/* ============================================================
   CONTAS
   ============================================================ */

// Quantas colunas a tabela de contas tem -- o `colSpan` do cabeçalho de grupo
// precisa cobrir todas. Num lugar só: errar aqui deixa o cabeçalho estreito e a
// tabela torta, e o erro é silencioso.
const COLUNAS_DA_TABELA_DE_CONTAS = 9;

function renderContas() {
  const corpo = $("#corpo-contas");
  corpo.innerHTML = "";
  const frag = document.createDocumentFragment();

  const servidores = (constantes && constantes.servidores) || [];

  // CABEÇALHO DE GRUPO. O grupo é rótulo de organização escolhido pelo usuário
  // (`Account.grupo`) e NÃO representa time nenhum -- time do APP continua em
  // `time_logins` (por login, no líder). Os grupos são os valores distintos na
  // ordem em que aparecem na lista, então a ordem dos grupos também sai do
  // array: uma fonte de verdade só sobre ordem.
  //
  // CONTA SEM GRUPO GANHA UM CABEÇALHO APAGADO, e isto é conserto de um defeito
  // visto na tela: sem ele, as contas sem grupo que vêm DEPOIS de um grupo
  // ficam colados nele e parecem pertencer a ele -- o cabeçalho dizia "1 conta"
  // com três linhas embaixo. "Ausência de rótulo é o rótulo" só funciona quando
  // o bloco sem grupo está isolado, e ele não está.
  //
  // Só que no PRIMEIRO bloco o cabeçalho é ruído: não há grupo antes para
  // confundir com. Por isso ele só aparece quando já houve grupo.
  let grupoDesenhado = null;
  let jaTeveGrupo = false;

  contasCache.forEach((c) => {
    const grupo = (c.grupo || "").trim();
    if (grupo !== grupoDesenhado) {
      grupoDesenhado = grupo;
      if (grupo || jaTeveGrupo) {
        const trGrupo = document.createElement("tr");
        trGrupo.className = grupo ? "linha-grupo" : "linha-grupo linha-sem-grupo";
        trGrupo.dataset.grupo = grupo;
        const td = document.createElement("td");
        td.colSpan = COLUNAS_DA_TABELA_DE_CONTAS;
        const rot = document.createElement("span");
        rot.className = "grupo-rotulo";
        rot.textContent = grupo || "sem grupo";
        const qtd = document.createElement("span");
        qtd.className = "grupo-contagem";
        // Conta as do MESMO rótulo em toda a lista, não só as deste bloco: o
        // mesmo grupo pode aparecer em dois pedaços se o usuário arrastar uma
        // conta para o meio de outro, e o número tem de continuar verdadeiro.
        const n = contasCache.filter(
          (x) => (x.grupo || "").trim() === grupo).length;
        qtd.textContent = n === 1 ? "1 conta" : `${n} contas`;
        td.appendChild(rot);
        td.appendChild(qtd);
        trGrupo.appendChild(td);
        frag.appendChild(trGrupo);
      }
      if (grupo) jaTeveGrupo = true;
    }
    const tr = document.createElement("tr");
    tr.dataset.uid = c.uid;
    // O login fica no atributo só para depuração e para a estatística casar por
    // nome; QUEM identifica a linha é o `data-uid` acima. O poll de estado
    // buscava por login e login é campo livre: dois iguais faziam a busca
    // acertar a primeira linha, que podia ser de outra conta.
    tr.dataset.login = c.login || "";
    if (c.uid === contaUidSelecionado) tr.classList.add("linha-ativa");

    // ALÇA DE ARRASTE. Coluna própria porque a linha é quase toda campo de
    // entrada (login, senha, dois combos, três caixas, botão): arrastar pela
    // linha inteira brigaria com selecionar texto no login.
    const tdAlca = document.createElement("td");
    tdAlca.className = "ctr cel-alca";
    const alca = document.createElement("span");
    alca.className = "alca-arraste";
    alca.dataset.acao = "arrastar";
    alca.textContent = "⠿";
    alca.title = "Arraste para reordenar";
    tdAlca.appendChild(alca);

    const tdAtiva = document.createElement("td");
    tdAtiva.className = "ctr";
    const chkAtiva = document.createElement("input");
    chkAtiva.type = "checkbox"; chkAtiva.className = "chk";
    chkAtiva.dataset.acao = "ativa"; chkAtiva.checked = c.enabled;
    tdAtiva.appendChild(chkAtiva);

    // Login — editável inline, como a célula COL_LOGIN da tabela da GUI.
    const tdLogin = document.createElement("td");
    const inpLogin = document.createElement("input");
    inpLogin.type = "text";
    inpLogin.className = "cel-texto";
    inpLogin.dataset.acao = "login";
    inpLogin.value = c.login || "";
    inpLogin.placeholder = "—";
    tdLogin.appendChild(inpLogin);

    // Senha — inline, tipo password. A senha real NUNCA sai do Python
    // (DPAPI); só um indicador visual de que existe uma gravada.
    const tdSenha = document.createElement("td");
    const inpSenha = document.createElement("input");
    inpSenha.type = "password";
    inpSenha.className = "cel-texto cel-senha";
    inpSenha.dataset.acao = "senha";
    inpSenha.value = "";
    if (c.tem_senha) {
      inpSenha.classList.add("tem-senha");
      inpSenha.placeholder = "•••• (trocar)";
    } else {
      inpSenha.placeholder = "nova";
    }
    tdSenha.appendChild(inpSenha);

    // Posição — combo inline, como o QComboBox da tabela da GUI.
    const tdPos = document.createElement("td");
    const selPos = document.createElement("select");
    selPos.className = "cel-opt";
    selPos.dataset.acao = "posicao";
    ["Left", "Center", "Right"].forEach((p) => {
      const o = document.createElement("option");
      o.value = p; o.textContent = p;
      selPos.appendChild(o);
    });
    selPos.value = c.position || "Center";
    tdPos.appendChild(selPos);

    // Servidor — combo inline com a lista canônica (server_rows).
    const tdServ = document.createElement("td");
    const selSrv = document.createElement("select");
    selSrv.className = "cel-opt cel-opt-largo";
    selSrv.dataset.acao = "servidor";
    const todosServ = servidores.slice();
    if (c.server && !todosServ.includes(c.server)) todosServ.unshift(c.server);
    todosServ.forEach((s) => {
      const o = document.createElement("option");
      o.value = s; o.textContent = s;
      selSrv.appendChild(o);
    });
    selSrv.value = c.server || "";
    tdServ.appendChild(selSrv);

    const tdBC = document.createElement("td");
    tdBC.className = "ctr";
    const chkBC = document.createElement("input");
    chkBC.type = "checkbox"; chkBC.className = "chk";
    chkBC.dataset.acao = "bc"; chkBC.checked = c.bc_farm;
    tdBC.appendChild(chkBC);

    const tdAPP = document.createElement("td");
    tdAPP.className = "ctr";
    const chkAPP = document.createElement("input");
    chkAPP.type = "checkbox"; chkAPP.className = "chk";
    chkAPP.dataset.acao = "app"; chkAPP.checked = c.app_enabled;
    tdAPP.appendChild(chkAPP);

    const tdEdit = document.createElement("td");
    tdEdit.className = "ctr";
    const btnEdit = document.createElement("button");
    btnEdit.className = "bt-editar"; btnEdit.textContent = "✏️  Editar";
    btnEdit.dataset.acao = "editar";
    tdEdit.appendChild(btnEdit);

    [tdAlca, tdAtiva, tdLogin, tdSenha, tdPos, tdServ, tdBC, tdAPP, tdEdit]
      .forEach((td) => tr.appendChild(td));
    frag.appendChild(tr);
  });

  corpo.appendChild(frag);
  atualizarFiltroLog();
}

/* ============================================================
   ARRASTAR PARA REORDENAR AS CONTAS
   ============================================================
   POINTER EVENTS, e não HTML5 Drag & Drop. Três razões, em ordem de peso:

   1. A linha é quase toda CAMPO DE ENTRADA -- login editável, senha, dois
      combos, três caixas e o botão Editar. Arrastar pela linha inteira brigaria
      com selecionar texto no login, então o arraste sai de uma ALÇA dedicada, e
      alça é trivial aqui e chata no DnD nativo.
   2. `<tr>` é hostil ao DnD nativo: a imagem de arraste de uma linha de tabela
      sai deformada, e `<table>` não aceita placeholder arbitrário entre linhas.
   3. Zero dependência nova. O WebView2 abre por `file://`, onde CDN não carrega.

   O DOM SÓ É REORDENADO NO SOLTAR (um `insertBefore`). Durante o arraste o
   feedback é `transform`, que não causa reflow de layout -- é o que mantém o
   custo plano com 50 contas.

   GRAVAÇÃO SÍNCRONA, SEM DEBOUNCE: debounce é justamente o que perde a última
   alteração quando a janela fecha. E se a gravação falhar, a tabela VOLTA à
   ordem anterior -- a tela nunca mostra uma ordem que o disco não tem.
*/

// Quanto o ponteiro precisa andar para virar arraste. Abaixo disto é clique --
// sem esta folga, clicar na alça já reordenava por tremor de mão.
const FOLGA_PARA_ARRASTAR = 4;

let arraste = null;

function linhasDeConta() {
  return $$("#corpo-contas tr[data-uid]");
}

function aoPegarAlca(e) {
  if (e.button !== 0) return;
  // UM arraste por vez. Sem esta guarda, um segundo `pointerdown` (segundo
  // dedo, caneta) sobrescrevia o arraste em curso e o primeiro ficava com o
  // `transform` pendurado na linha, sem nada para limpá-lo.
  if (arraste) return;
  const alca = e.target.closest('[data-acao="arrastar"]');
  if (!alca) return;
  const linha = alca.closest("tr[data-uid]");
  if (!linha) return;
  e.preventDefault();

  const linhas = linhasDeConta();
  // RÉGUA DO TBODY INTEIRO, cabeçalhos de grupo incluídos.
  //
  // O destino é decidido pela posição REAL do ponteiro contra estas faixas, e
  // não por "quantas alturas de linha ele andou". É isso que permite saber que
  // a conta caiu ABAIXO de um cabeçalho -- ou seja, DENTRO daquele grupo -- e
  // conserta o gesto mais natural de todos: soltar como PRIMEIRA linha de outro
  // grupo. Medindo por múltiplos de altura, aquele caso herdava o grupo da
  // vizinha de cima, que é a última do grupo ANTERIOR.
  //
  // Medidas tiradas UMA vez: durante o arraste as linhas estão deslocadas por
  // `transform`, e medir de novo leria a posição fingida.
  const faixas = $$("#corpo-contas tr").map((tr) => {
    const r = tr.getBoundingClientRect();
    return {
      topo: r.top,
      base: r.bottom,
      conta: tr.hasAttribute("data-uid"),
      grupo: tr.classList.contains("linha-grupo")
        ? (tr.dataset.grupo || "") : null,
    };
  });

  arraste = {
    pointerId: e.pointerId,
    alca,
    linha,
    y0: e.clientY,
    movendo: false,
    faixas,
    alturas: linhas.map((l) => l.getBoundingClientRect().height),
    linhas,
    de: linhas.indexOf(linha),
    para: linhas.indexOf(linha),
    grupoDestino: (contasCache.find((c) => c.uid === linha.dataset.uid)
                   || {}).grupo || "",
  };
  alca.setPointerCapture(e.pointerId);
}

// Onde a conta cai, e em que grupo ela entra, para um `clientY`.
//
// `posicao` é o índice ENTRE AS CONTAS (faixa de cabeçalho não conta), e
// `grupo` é o do último cabeçalho acima do ponteiro -- `""` quando não há
// nenhum, que é justamente o bloco sem grupo.
function destinoDoArraste(clientY) {
  const { faixas, de, linhas } = arraste;
  let contasAntes = 0;
  let grupo = "";
  let passou = 0;
  for (const f of faixas) {
    if (clientY < (f.topo + f.base) / 2) break;
    passou++;
    if (f.grupo !== null) grupo = f.grupo;
    else if (f.conta) contasAntes++;
  }
  if (!passou) {
    // Acima de tudo: entra no grupo do primeiro bloco, se ele tiver rótulo.
    const primeira = faixas[0];
    grupo = primeira && primeira.grupo !== null ? primeira.grupo : "";
  }
  // A própria linha arrastada não conta como "antes" de si mesma.
  let posicao = contasAntes > de ? contasAntes - 1 : contasAntes;
  posicao = Math.max(0, Math.min(linhas.length - 1, posicao));
  return { posicao, grupo };
}

function aoMoverArraste(e) {
  if (!arraste || e.pointerId !== arraste.pointerId) return;
  const dy = e.clientY - arraste.y0;
  if (!arraste.movendo) {
    if (Math.abs(dy) < FOLGA_PARA_ARRASTAR) return;
    arraste.movendo = true;
    document.body.classList.add("arrastando-conta");
    arraste.linha.classList.add("linha-arrastada");
  }

  const { posicao, grupo } = destinoDoArraste(e.clientY);
  arraste.para = posicao;
  arraste.grupoDestino = grupo;
  const destino = posicao;
  const altura = arraste.alturas[arraste.de] || 1;

  arraste.linha.style.transform = `translateY(${dy}px)`;
  // As vizinhas abrem espaço; ninguém muda de lugar no DOM ainda.
  arraste.linhas.forEach((l, i) => {
    if (l === arraste.linha) return;
    let desloca = 0;
    if (arraste.de < destino && i > arraste.de && i <= destino) desloca = -altura;
    if (arraste.de > destino && i >= destino && i < arraste.de) desloca = altura;
    l.style.transform = desloca ? `translateY(${desloca}px)` : "";
  });
}

function limparArraste() {
  if (!arraste) return;
  // SOLTAR A CAPTURA EXPLICITAMENTE. Cancelando por Esc, o ponteiro seguia
  // capturado pela alça até o usuário largar o botão -- e enquanto isso a
  // tabela não recebia mais evento nenhum.
  try {
    if (arraste.alca.hasPointerCapture(arraste.pointerId)) {
      arraste.alca.releasePointerCapture(arraste.pointerId);
    }
  } catch (_) { /* o navegador já soltou */ }
  document.body.classList.remove("arrastando-conta");
  arraste.linha.classList.remove("linha-arrastada");
  arraste.linhas.forEach((l) => { l.style.transform = ""; });
  arraste = null;
}

function aoSoltarLinha(e) {
  if (!arraste) return;
  if (e && e.pointerId !== undefined && e.pointerId !== arraste.pointerId) return;
  const { movendo, de, para, linhas, grupoDestino } = arraste;
  limparArraste();
  if (!movendo) return;

  // A ordem nova, calculada sobre os UIDS -- nunca sobre posições de tela.
  const uids = linhas.map((l) => l.dataset.uid);
  const [movido] = uids.splice(de, 1);
  uids.splice(para, 0, movido);

  // A CONTA HERDA O GRUPO DO DESTINO.
  //
  // Sem isto, arrastar uma conta para dentro de outro grupo a deixava com o
  // rótulo antigo, e o cabeçalho do grupo antigo aparecia DUAS vezes na tabela
  // -- visto na tela. E o agrupamento não serviria para o que existe: organizar.
  //
  // Mover de grupo é seguro porque o grupo é RÓTULO: não é o time do APP
  // (`time_logins`, por login, no líder) nem a party do BC
  // (`accept_team_invites`). Nada do bot muda de comportamento por causa dele --
  // era isso que a decisão "só reordena" protegia.
  //
  // Quem diz o grupo é o CABEÇALHO acima de onde o ponteiro soltou
  // (`destinoDoArraste`), não a conta vizinha. A regra da vizinha errava justo
  // no gesto mais natural: soltar como PRIMEIRA linha de outro grupo, onde a
  // vizinha de cima é a última do grupo ANTERIOR.
  const grupoPorUid = new Map(contasCache.map((c) => [c.uid, (c.grupo || "").trim()]));
  const grupoNovo = (grupoDestino || "").trim();
  const grupoAntigo = grupoPorUid.get(movido) || "";
  grupoPorUid.set(movido, grupoNovo);
  // Nem a posição nem o rótulo mudaram: não gasta gravação.
  if (de === para && grupoNovo === grupoAntigo) return;

  // UMA chamada leva ordem e rótulos juntos: se fossem duas, uma podia gravar e
  // a outra falhar, e a tabela ficaria com a ordem nova e o grupo velho.
  const ordem = uids.map((u) => ({ uid: u, grupo: grupoPorUid.get(u) || "" }));

  chamar("reordenar_contas", ordem).then((r) => {
    if (r && r.ok && Array.isArray(r.contas)) {
      // Redesenha do que está NO DISCO, não do que a tela reorganizou.
      contasCache = r.contas;
      renderContas();
      return;
    }
    // FALHOU: RECARREGA DO BACKEND, não de uma cópia local.
    //
    // Reconstruir a ordem anterior de memória parece mais simples e está errado
    // por dois motivos, os dois achados na revisão: uma conta que tenha entrado
    // no cache durante a chamada DESAPARECERIA da tabela, e a chamada pode ter
    // gravado no disco e falhado só na resposta -- e aí a "ordem anterior"
    // seria justamente a que o disco NÃO tem. Quem sabe a verdade é o disco.
    avisar((r && r.erro) || "Não foi possível salvar a nova ordem.");
    carregarContas();
  });
}

$("#corpo-contas").addEventListener("pointerdown", aoPegarAlca);
$("#corpo-contas").addEventListener("pointermove", aoMoverArraste);
$("#corpo-contas").addEventListener("pointerup", aoSoltarLinha);
// Cancelar de verdade: `pointercancel` (o sistema tomou o ponteiro) e Esc.
$("#corpo-contas").addEventListener("pointercancel", limparArraste);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && arraste) limparArraste();
});

$("#corpo-contas").addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-uid]");
  if (!tr) return;
  const uid = tr.dataset.uid;

  if (e.target.dataset.acao === "editar") {
    abrirEditor(uid);
    return;
  }

  // seleção para remover (ignora cliques nos controles)
  if (e.target.closest("input,button,select")) return;
  contaUidSelecionado = uid === contaUidSelecionado ? null : uid;
  $$("#corpo-contas tr").forEach((r) =>
    r.classList.toggle("linha-ativa", r.dataset.uid === contaUidSelecionado));
  $("#btn-remover-conta").disabled = contaUidSelecionado === null;
});

$("#corpo-contas").addEventListener("change", (e) => {
  const tr = e.target.closest("tr[data-uid]");
  if (!tr || !e.target.dataset.acao) return;
  const uid = tr.dataset.uid;
  const acao = e.target.dataset.acao;
  const ligado = e.target.checked;
  const valor = e.target.value;

  if (acao === "ativa") {
    chamar("ativar_conta", uid, ligado).then((r) => {
      // DESATIVAR um reseter deixa outra conta órfã. O backend recusa; aqui a
      // caixa volta ao estado real porque `carregarContas` re-renderiza a linha
      // a partir da configuração, que não mudou.
      if (r && r.ok === false) {
        avisar(r.erro || "Não foi possível desativar.");
        carregarContas();
        return;
      }
      if (r && Array.isArray(r.iniciadas) && r.iniciadas.length) {
        toast("Bot em execução: contas subidas → " + r.iniciadas.join(", "), "ok");
      }
      carregarContas();
    });
  } else if (acao === "bc") {
    chamar("alternar_farm", uid, ligado).then(() => {
      toast(ligado ? "BC farm ligado" : "BC farm desligado");
      carregarContas();
    });
  } else if (acao === "app") {
    chamar("alternar_app", uid, ligado).then(() => {
      toast(ligado ? "Modo APP ligado" : "Modo APP desligado");
      carregarContas();
    });
  } else if (acao === "posicao") {
    chamar("definir_posicao", uid, valor).then(() => {
      const c = contasCache.find((x) => x.uid === uid);
      if (c) c.position = valor;
      toast("Posição: " + valor);
    });
  } else if (acao === "servidor") {
    chamar("definir_servidor", uid, valor).then(() => {
      const c = contasCache.find((x) => x.uid === uid);
      if (c) c.server = valor;
      toast("Servidor: " + valor);
    });
  } else if (acao === "login") {
    const novo = e.target.value.trim();
    if (novo && novo !== (contasCache.find((x) => x.uid === uid) || {}).login) {
      chamar("definir_login", uid, novo).then(() => {
        toast("Login atualizado.");
        carregarContas();
      });
    }
  } else if (acao === "senha") {
    // Não fazer trim: a senha pode conter espaços/bytes iniciais.
    const senha = e.target.value;
    if (senha) {
      chamar("definir_senha", uid, senha).then(() => {
        toast("Senha gravada (cifrada com o Windows).");
        carregarContas();
      });
    } else {
      // Deixou vazio = manteve a atual. Reconstrói a linha para limpar o campo.
      carregarContas();
    }
  }
});

// Enter dentro de um campo inline de login/senha grava na hora (sem precisar
// sair da célula) — o blur dispara o `change` que comita o valor.
$("#corpo-contas").addEventListener("keydown", (e) => {
  const acao = e.target && e.target.dataset && e.target.dataset.acao;
  if (!acao || (acao !== "login" && acao !== "senha")) return;
  if (e.key === "Enter") {
    e.preventDefault();
    e.target.blur();
  } else if (e.key === "Escape") {
    e.preventDefault();
    e.target.value = (e.target.dataset.acao === "senha") ? "" : (
      (contasCache.find((x) => x.uid === e.target.closest("tr[data-uid]").dataset.uid) || {}).login || ""
    );
    e.target.blur();
  }
});

function carregarContas() {
  chamar("obter_contas").then((lista) => {
    contasCache = lista || [];
    renderContas();
  });
}

$("#btn-adicionar-conta").addEventListener("click", () => {
  chamar("nova_conta").then(() => {
    toast("Conta adicionada (inativa). Preencha e marque Ativa.");
    carregarContas();
  });
});

$("#btn-remover-conta").addEventListener("click", () => {
  if (contaUidSelecionado === null) return;
  const sel = contasCache.find((x) => x.uid === contaUidSelecionado);
  const rotulo = (sel && (sel.login || sel.nick)) ||
    "esta conta";
  confirmar(`Remover a conta "${rotulo}"?`).then((ok) => {
    if (!ok) return;
    chamar("remover_conta", contaUidSelecionado).then((r) => {
      // RECUSADO porque esta conta é o reset de outra: aviso bloqueante, e a
      // conta continua onde estava. Quem decide é o backend.
      if (r && r.ok === false) { avisar(r.erro || "Não foi possível remover."); return; }
      toast("Conta removida.");
      contaUidSelecionado = null;
      $("#btn-remover-conta").disabled = true;
      carregarContas();
    });
  });
});

/* ---------- controle do bot ---------- */
$("#btn-iniciar").addEventListener("click", () => {
  $("#btn-iniciar").disabled = true;
  chamar("iniciar").then((r) => {
    $("#btn-iniciar").disabled = false;
    if (!r) { toast("Não foi possível iniciar."); return; }
    if (r.ok) {
      toast("Bot iniciado.");
    } else {
      toast("Não foi possível iniciar:\n" + (r.erros || []).join("\n"), "erro");
    }
  });
});
$("#btn-parar").addEventListener("click", () => chamar("parar").then(() => toast("Bot parado.")));
$("#btn-pausar").addEventListener("click", () => chamar("pausar").then(() => toast("Pausado.")));
$("#btn-retomar").addEventListener("click", () => chamar("retomar").then(() => toast("Retomado.")));

/* ============================================================
   EDITOR DE CONTA
   ============================================================ */

const ABA_PADRAO = "aba-personagem";

function trocarAba(aba) {
  const modal = $("#modal-editor");
  $$(".aba", modal).forEach((b) =>
    b.classList.toggle("aba-ativa", b.dataset.aba === aba));
  $$(".painel-aba", modal).forEach((p) =>
    p.classList.toggle("aba-visivel", p.id === aba));
  $$(".aba-conteudo", modal).forEach((p) =>
    p.classList.toggle("aba-visivel", p.id === aba));
}
$$(".aba").forEach((b) =>
  b.addEventListener("click", () => trocarAba(b.dataset.aba)));

// A explicação do modo do time acompanha a escolha. Sem ela, os três nomes do
// <select> parecem sinônimos -- e a diferença entre eles é o que o time faz.
{
  const selModoTime = $("#ed-app-time-modo");
  if (selModoTime) selModoTime.addEventListener("change", explicarModoDoTime);
}

function abrirEditor(uid) {
  contaUidEditando = uid;
  const sel = contasCache.find((x) => x.uid === uid);
  const rotulo = (sel && (sel.login || sel.nick)) || "conta nova";
  $("#modal-editor-titulo").textContent = "Editar conta — " + rotulo;
  $("#ed-login").value = "";
  $("#ed-senha").value = "";
  trocarAba(ABA_PADRAO);
  $("#modal-editor").classList.remove("escondida");

  chamar("obter_conta", uid).then((d) => preencherEditor(d));
}

function fecharEditor() {
  $("#modal-editor").classList.add("escondida");
  contaUidEditando = null;
}
$("#btn-fechar-modal").addEventListener("click", fecharEditor);
$("#btn-cancelar-modal").addEventListener("click", fecharEditor);

function preencherEditor(d) {
  if (!d) return;
  $("#ed-login").value = d.login || "";
  $("#ed-nick").value = d.nick || "";
  $("#ed-grupo").value = d.grupo || "";
  $("#ed-aceitar-time").checked = !!d.accept_team_invites;
  $("#ed-usar-catador").checked = !!d.usar_catador;
  $("#ed-montaria").value = String(d.mount_speed_pct);
  $("#ed-pet-summon").checked = !!d.pet.summon_on_login;
  $("#ed-pet-feed-start").checked = !!d.pet.feed_on_start;
  $("#ed-pet-feed-min").value = d.pet.feed_every_minutes;
  $("#ed-hp").value = d.potions.hp_pct; $("#val-hp").textContent = d.potions.hp_pct + "%";
  $("#ed-bhp").value = d.potions.battle_hp_pct; $("#val-bhp").textContent = d.potions.battle_hp_pct + "%";
  $("#ed-emergencia").value = d.potions.emergency_pct; $("#val-emergencia").textContent = d.potions.emergency_pct + "%";
  $("#ed-bolsas").value = String(d.bags.bolsas);
  $("#ed-app-ligado").checked = !!d.app.enabled;
  $("#ed-app-limpar").value = String(d.app.apagar_lixo_a_cada ?? 10);
  $("#ed-app-travar").checked = !!d.app.travar_posicao;
  $("#ed-app-shuffle").value = String(d.app.shuffle_apos_n_voltas ?? 30);
  $("#ed-app-time-modo").value = d.app.time_modo || "largada";
  $("#ed-app-fada").checked = !!d.app.fada;
  $("#ed-app-cura-pedir").value = String(d.app.cura_pedir_pct ?? 30);
  $("#ed-app-cura-parar").value = String(d.app.cura_parar_pct ?? 90);
  explicarModoDoTime();
  // Como a lista do reseter, as candidatas vêm do EDITOR e não do bloco `app`:
  // elas são as OUTRAS contas, e `app` só sabe de si mesmo.
  montarListaDoTime(d.contas_do_time || [], d.app.time_logins || []);

  preencherTeclas(d.keys);
  preencherApp(d.app.steps, d.app, d.keys);
  // A LISTA DO RESETER VEM DO EDITOR, não do bloco `bc`: ela é montada a
  // partir das OUTRAS contas, e `bc` só sabe de si mesmo. Tem que vir ANTES
  // de `preencherBC`, que é quem seleciona o valor gravado.
  montarListaDeReset(d.contas_de_reset || [], (d.bc && d.bc.reset_nick) || "");
  preencherBC(d.bc);

  const senhaForte = $("#ed-senha");
  senhaForte.placeholder = d.tem_senha
    ? "senha já existe — digite para trocar, deixe vazio para manter"
    : "digite a senha (vazio não salva)";
}

const CAMPO_TECLA = [
  ["ed-k-atk0", "attack_skills", 0],
  ["ed-k-atk1", "attack_skills", 1],
  ["ed-k-atk2", "attack_skills", 2],
  ["ed-k-atk3", "attack_skills", 3],
  ["ed-k-aoe", "aoe_skill"], ["ed-k-break", "break_soul"],
  ["ed-k-super", "super_skill"], ["ed-k-heal", "heal_skill"],
  ["ed-k-buff1", "buffs", 0], ["ed-k-buff2", "buffs", 1],
  ["ed-k-buff3", "buffs", 2], ["ed-k-buff4", "buffs", 3],
  ["ed-k-hp", "hp_potion"], ["ed-k-bhp", "battle_hp_potion"],
  ["ed-k-petfood", "pet_food"], ["ed-k-stone", "stone_charm"],
  ["ed-k-mount", "mount"], ["ed-k-speed", "speed_skill"],
  ["ed-k-guild", "guild_token"], ["ed-k-pet", "pet_summon"],
  ["ed-k-sit", "sit"], ["ed-k-next", "next_target"],
  ["ed-k-self", "self_target"],
  ["ed-k-inv", "inventory"], ["ed-k-fl", "friend_list"],
  ["ed-k-hotbar", "hotbar_page_1"],
  ["ed-k-esconder", "hide_players"],
];

function preencherTeclas(k) {
  CAMPO_TECLA.forEach(([id, campo, idx]) => {
    let v = "";
    const val = k[campo];
    if (Array.isArray(val)) v = val[idx] || "";
    else v = val || "";
    $("#" + id).value = v;
  });
}

// Piso de qualquer tempo do APP. Espelha `MINIMO_DE_ESPERA_DO_APP_MS` do
// Python — a ponte reaplica o piso, então a tela não é a única guarda.
/* ---------- TEMPO: A TELA FALA EM MILISSEGUNDOS ----------
   Todo campo de delay ou espera aparece em ms, com mínimo de 100 -- pedido do
   usuário, para não haver três unidades diferentes na mesma interface (havia
   segundos, milissegundos e minutos).

   O ARMAZENAMENTO NÃO MUDOU. `attack_delay` e `launch_delay` continuam `float`
   de SEGUNDOS no `config.json`, porque é o que `combat.py` e o supervisor leem, e
   o laço de ataque é a parte mais medida do projeto -- trocar a unidade lá
   dentro exigiria migrar todo `config.json` existente para ganhar nada. A
   conversão é de apresentação e mora só nestas duas funções. */
const MINIMO_DELAY_MS = 100;

function segundosParaMs(segundos) {
  const ms = Math.round((Number(segundos) || 0) * 1000);
  return Math.max(MINIMO_DELAY_MS, ms);
}

function msParaSegundos(ms) {
  const limpo = Math.max(MINIMO_DELAY_MS, Number(ms) || MINIMO_DELAY_MS);
  // 3 casas: 100 ms é 0,1 s exato, e 8500 ms é 8,5 s -- nada de dízima.
  return Number((limpo / 1000).toFixed(3));
}

const MINIMO_ESPERA_APP = MINIMO_DELAY_MS;
// Teto igual ao `setRange(MINIMO_DE_ESPERA_DO_APP_MS, 10000)` da GUI
// (`account_dialog._aba_app`) -- as duas interfaces com a mesma faixa.
const MAXIMO_ESPERA_APP = 10000;
const PASSO_ESPERA_APP = 100;

function preencherApp(steps, app, keys) {
  const corpo = $("#corpo-app");
  corpo.innerHTML = "";

  // ============================================================
  // A LINHA 0: o TAB, e o tempo depois dele
  // ============================================================
  //
  // "Como a macro 0, mas sem poder editar o botão e não pode colocar em outro
  // lugar, sempre será a primeira, e o tempo sim será editável."
  //
  // A tecla é ESPELHO da aba Teclas > Próximo alvo, e não um "TAB" escrito
  // aqui: quem trocou a tecla veria a tela mentir sobre o que o bot aperta.
  //
  // Ela NÃO tem a classe `app-linha`, e é isso que a mantém fora da lista de
  // passos — quem monta os `steps` e a prévia seleciona por essa classe.
  const trTab = document.createElement("tr");
  trTab.className = "linha-do-tab";
  const tdNT = document.createElement("td"); tdNT.textContent = "0";
  const tdKT = document.createElement("td");
  const inpKT = document.createElement("input");
  inpKT.className = "captura"; inpKT.type = "text";
  inpKT.readOnly = true; inpKT.disabled = true;
  inpKT.value = (keys && keys.next_target) || "TAB";
  inpKT.title = "A tecla de 'Próximo alvo' da aba Teclas. O bot aperta esta "
    + "tecla sozinho quando o alvo morre — ela não é uma linha da macro e não "
    + "sai de lugar.";
  tdKT.appendChild(inpKT);
  const tdDT = document.createElement("td");
  const inpDT = document.createElement("input");
  inpDT.id = "ed-app-espera-tab";
  // Passo de 100 ms, não 50: é a granularidade útil de um delay de macro e é o
  // número que a roda do mouse já usava aqui (as setinhas discordavam, em 50).
  inpDT.type = "number"; inpDT.min = String(MINIMO_ESPERA_APP);
  inpDT.max = String(MAXIMO_ESPERA_APP); inpDT.step = String(PASSO_ESPERA_APP);
  inpDT.value = (app && app.espera_depois_do_tab_ms) || 1000;
  inpDT.title = "Quanto esperar entre o TAB e a linha 1. Curto demais, a "
    + "primeira skill da rotação se perde.";
  tdDT.appendChild(inpDT);
  trTab.appendChild(tdNT); trTab.appendChild(tdKT); trTab.appendChild(tdDT);
  corpo.appendChild(trTab);

  const n = constantes ? constantes.passos_app : 20;
  for (let i = 0; i < n; i++) {
    const s = (steps && steps[i]) || { key: "", delay_ms: 800 };
    const tr = document.createElement("tr");
    tr.className = "app-linha";
    const tdN = document.createElement("td"); tdN.textContent = i + 1;
    const tdK = document.createElement("td");
    const inpK = document.createElement("input");
    inpK.className = "captura app-tecla"; inpK.type = "text"; inpK.readOnly = true;
    inpK.value = s.key || "";
    tdK.appendChild(inpK);
    const tdD = document.createElement("td");
    const inpD = document.createElement("input");
    inpD.type = "number"; inpD.min = String(MINIMO_ESPERA_APP);
    inpD.max = String(MAXIMO_ESPERA_APP); inpD.step = String(PASSO_ESPERA_APP);
    inpD.value = s.delay_ms || 800;
    tdD.appendChild(inpD);
    tr.appendChild(tdN); tr.appendChild(tdK); tr.appendChild(tdD);
    corpo.appendChild(tr);
  }
  atualizarPreviaApp();
}

// Prévia do modo APP: mostra a sequência exata que será enviada (espelha a
// prévia do AccountDialog da GUI). Linha com tecla roda; vazia é ignorada.
function atualizarPreviaApp() {
  const el = $("#lbl-previa-app");
  if (!el) return;
  const ativas = $$("#corpo-app tr.app-linha").map((tr) => {
    const tecla = tr.querySelector(".app-tecla").value;
    const delay = Number(tr.querySelector("input[type=number]").value) || 0;
    return tecla ? { tecla, delay } : null;
  }).filter(Boolean);
  if (!ativas.length) {
    el.textContent = "Nenhuma tecla preenchida — o modo APP não teria o que enviar.";
    el.title = "";
    return;
  }
  const desenho = ativas.map((a) => `${a.tecla} (${a.delay}ms)`).join(" → ");
  const total = ativas.reduce((s, a) => s + a.delay, 0);
  const maxChars = 120;
  let exibicao = desenho;
  if (desenho.length > maxChars) {
    exibicao = desenho.slice(0, maxChars) + " …";
  }
  el.textContent =
    `Sequência: ${exibicao} → recomeça. ` +
    `${ativas.length} linha(s), volta completa em ${(total / 1000).toFixed(1)}s.`;
  el.title = desenho; // tooltip com sequência completa
}
$("#corpo-app").addEventListener("input", atualizarPreviaApp);

/* Seletor da conta que reseta a cave.
 *
 * O campo era texto livre e virou lista fechada. Espelha
 * `AccountDialog._montar_lista_de_reset` da GUI PyQt — as duas interfaces
 * precisam oferecer exatamente as mesmas opções, e quem decide quais são é o
 * backend (`BotConfig.reset_accounts`).
 *
 * Três casos, e o terceiro é o que não pode sumir:
 *   1. conta marcada e já logada        -> opção normal;
 *   2. conta marcada que nunca logou    -> DESABILITADA (sem nick, selecionar
 *      gravaria string vazia, que significa "não usar reset de time" — seria
 *      desligar a função achando que ligou);
 *   3. o que está gravado e não é nenhuma das duas -> entra no fim, marcado
 *      como problema, e continua SELECIONADO. Sumir com ele seria apagar a
 *      configuração de alguém sem avisar.
 */
function montarListaDeReset(candidatas, atual) {
  const sel = $("#ed-reset-nick");
  sel.innerHTML = "";
  const opcao = (texto, valor, ativa) => {
    const o = document.createElement("option");
    o.textContent = texto;
    o.value = valor;
    if (!ativa) o.disabled = true;
    sel.appendChild(o);
  };

  opcao("Nenhuma (sem reset de time)", "", true);
  const conhecidos = new Set();
  candidatas.forEach((c) => {
    if (c.disponivel && c.nick) {
      opcao(`${c.nick} — (${c.login})`, c.nick, true);
      conhecidos.add(c.nick.toLowerCase());
    } else {
      opcao(`(${c.login}) — ainda não logou, sem nick`, "", false);
    }
  });

  const gravado = (atual || "").trim();
  if (gravado && !conhecidos.has(gravado.toLowerCase())) {
    opcao(`${gravado} — ⚠ não é conta de reset deste bot`, gravado, true);
  }
  sel.value = gravado;
}

// ===========================================================================
// O TIME DO APP — quem roda a macro desta conta junto com ela
// ===========================================================================
//
// Molde: `montarListaDeReset`. A diferença é que aqui a escolha é MÚLTIPLA e
// tem teto, então não dá para ser um <select>.
//
// Conta inelegível aparece DESABILITADA com o motivo escrito, em vez de sumir
// da lista: some é o usuário procurando uma conta que ele sabe que cadastrou.

// Espelha `MAXIMO_DE_SEGUIDORES_DO_TIME` do config.py. O líder não conta.
const MAXIMO_DO_TIME = 4;

const EXPLICA_MODO_DO_TIME = {
  copiar:
    "As contas rodam a mesma macro, cada uma no seu ritmo. Ninguém espera ninguém.",
  largada:
    "Todas dão o TAB e começam cada volta juntas; cada uma bate no alvo dela. " +
    "Quem se atrasar continua batendo e entra na largada seguinte.",
  mesmo_alvo:
    "Como a de cima, e ainda dão TAB até ficarem todas no mesmo alvo do líder " +
    "antes de começar a bater.",
};

function atualizarContagemDoTime() {
  const marcadas = $$("#ed-app-time-lista input:checked");
  const conta = $("#ed-app-time-conta");
  if (conta) conta.textContent = `${marcadas.length}/${MAXIMO_DO_TIME}`;
  // TETO SEM MENSAGEM DE ERRO: ao chegar em 4, o que sobra fica desabilitado.
  // Deixar clicar e recusar depois é pior -- o usuário clica, nada acontece e
  // ele não sabe se o clique falhou ou se a regra existe.
  $$("#ed-app-time-lista input").forEach((el) => {
    if (el.dataset.bloqueada === "1") return;
    el.disabled = !el.checked && marcadas.length >= MAXIMO_DO_TIME;
    el.closest("label").classList.toggle("opacity-40", el.disabled);
  });
}

function montarListaDoTime(candidatas, escolhidos) {
  const caixa = $("#ed-app-time-lista");
  if (!caixa) return;
  caixa.innerHTML = "";
  const marcados = new Set((escolhidos || []).map((x) => String(x)));

  if (!candidatas.length) {
    const p = document.createElement("p");
    p.className = "text-[10.5px] text-dim leading-snug";
    p.textContent = "Nenhuma outra conta cadastrada.";
    caixa.appendChild(p);
    return;
  }

  candidatas.forEach((c) => {
    const rot = document.createElement("label");
    rot.className = "campo-check w-full";
    const cx = document.createElement("input");
    cx.type = "checkbox";
    cx.className = "chk";
    cx.value = c.login;
    cx.checked = marcados.has(c.login);

    // O motivo de não poder entrar, quando existe. Farmar a cave e rodar o APP
    // são excludentes: convocar uma conta no meio de uma run da cave perderia
    // a run (teleporte gasto, boss vivo). Ver docs/INVARIANTES.md, "Time do APP".
    let motivo = "";
    if (c.farmando_bc) motivo = "farmando a cave";
    else if (c.lider_de_outro) motivo = `já no time de ${c.lider_de_outro}`;
    if (motivo) {
      cx.checked = false;
      cx.disabled = true;
      cx.dataset.bloqueada = "1";
      rot.classList.add("opacity-40");
    }
    cx.addEventListener("change", atualizarContagemDoTime);

    const txt = document.createElement("span");
    txt.textContent = c.nick ? `${c.nick} — (${c.login})` : `(${c.login})`;
    if (motivo) txt.textContent += ` — ${motivo}`;

    rot.appendChild(cx);
    rot.appendChild(txt);
    caixa.appendChild(rot);
  });
  atualizarContagemDoTime();
}

function explicarModoDoTime() {
  const sel = $("#ed-app-time-modo");
  const alvo = $("#ed-app-time-explica");
  if (sel && alvo) alvo.textContent = EXPLICA_MODO_DO_TIME[sel.value] || "";
}

function lerTimeDoApp() {
  return $$("#ed-app-time-lista input:checked")
    .map((el) => el.value)
    .slice(0, MAXIMO_DO_TIME);
}

function preencherBC(bc) {
  $("#ed-boss").value = bc.boss_name || "";
  // TELA EM MS, ARMAZENAMENTO EM SEGUNDOS. `attack_delay` é `float` de segundos
  // no `config.json` e no `combat.py`; converter o campo mudaria o formato de
  // configuração e o laço de ataque, que é a parte mais medida do projeto. A
  // padronização em ms é de APRESENTAÇÃO: a conversão mora só aqui e no `lerBC`.
  $("#ed-ataque-delay").value = segundosParaMs(bc.attack_delay);
  $("#ed-heal-fase2").checked = !!bc.heal_before_second_phase;
  $("#ed-aoe-mana").value = bc.aoe_until_mana_pct;
  $("#val-aoe-mana").textContent = bc.aoe_until_mana_pct + "%";
  $("#ed-sk-velocidade").checked = !!bc.usar_skill_de_velocidade;
  // `reset_nick` NÃO é lido aqui: quem seleciona é `montarListaDeReset`, que
  // roda antes e é a única dona da lista. Dois lugares escrevendo o mesmo campo
  // divergiriam em silêncio no dia em que um deles mudasse.
  $("#ed-runs-venda").value = bc.vendor.runs_before_selling;
  $("#ed-slot-venda").value = bc.vendor.sell_start_slot;
  $("#ed-cliques-venda").value = String(bc.vendor.sell_clicks);
  $("#ed-recomprar-charm").checked = !!bc.vendor.buy_return_charm;
}

/* sliders com rótulo */
[["ed-hp", "val-hp"], ["ed-bhp", "val-bhp"],
 ["ed-emergencia", "val-emergencia"], ["ed-aoe-mana", "val-aoe-mana"]]
  .forEach(([inp, val]) => {
    $(`#${inp}`).addEventListener("input", () => {
      $(`#${val}`).textContent = $(`#${inp}`).value + "%";
    });
  });

function lerTeclas() {
  const out = {
    attack_skills: [], aoe_skill: "", break_soul: "", super_skill: "",
    heal_skill: "", buffs: [], hp_potion: "", battle_hp_potion: "",
    pet_food: "", stone_charm: "", mount: "", speed_skill: "",
    guild_token: "", pet_summon: "", next_target: "", sit: "",
    inventory: "", friend_list: "",
  };
  CAMPO_TECLA.forEach(([id, campo, idx]) => {
    const v = $("#" + id).value;
    if (Array.isArray(out[campo])) out[campo][idx] = v;
    else out[campo] = v;
  });
  return out;
}

function salvarEditor() {
  if (contaUidEditando === null) return;
  const senhaNova = $("#ed-senha").value;

  // `tr.app-linha` exclui a linha 0 (o TAB), que não é um passo da macro.
  const appSteps = $$("#corpo-app tr.app-linha").map((tr) => ({
    key: tr.querySelector(".app-tecla").value || "",
    delay_ms: Math.max(
      MINIMO_ESPERA_APP,
      Number(tr.querySelector("input[type=number]").value) || 0),
  }));

  const dados = {
    login: $("#ed-login").value.trim(),
    nick: $("#ed-nick").value.trim(),
    grupo: $("#ed-grupo").value.trim(),
    accept_team_invites: $("#ed-aceitar-time").checked,
    usar_catador: $("#ed-usar-catador").checked,
    mount_speed_pct: Number($("#ed-montaria").value),
    pet: {
      summon_on_login: $("#ed-pet-summon").checked,
      feed_on_start: $("#ed-pet-feed-start").checked,
      feed_every_minutes: Number($("#ed-pet-feed-min").value),
    },
    potions: {
      hp_pct: Number($("#ed-hp").value),
      battle_hp_pct: Number($("#ed-bhp").value),
      emergency_pct: Number($("#ed-emergencia").value),
    },
    bags: { bolsas: Number($("#ed-bolsas").value) },
    app: {
      enabled: $("#ed-app-ligado").checked,
      apagar_lixo_a_cada: Math.max(0, Number($("#ed-app-limpar").value) || 0),
      travar_posicao: $("#ed-app-travar").checked,
      shuffle_apos_n_voltas: Math.max(1, Number($("#ed-app-shuffle").value) || 30),
      espera_depois_do_tab_ms: Math.max(
        MINIMO_ESPERA_APP,
        Number(($("#ed-app-espera-tab") || {}).value) || 1000),
      time_modo: $("#ed-app-time-modo").value,
      fada: $("#ed-app-fada").checked,
      cura_pedir_pct: Math.max(1, Math.min(100, Number($("#ed-app-cura-pedir").value) || 30)),
      cura_parar_pct: Math.max(1, Math.min(100, Number($("#ed-app-cura-parar").value) || 90)),
      time_logins: lerTimeDoApp(),
      steps: appSteps,
    },
    keys: lerTeclas(),
    bc: {
      boss_name: $("#ed-boss").value.trim(),
      attack_delay: msParaSegundos($("#ed-ataque-delay").value),
      heal_before_second_phase: $("#ed-heal-fase2").checked,
      aoe_until_mana_pct: Number($("#ed-aoe-mana").value),
      usar_skill_de_velocidade: $("#ed-sk-velocidade").checked,
      reset_nick: $("#ed-reset-nick").value.trim(),
      vendor: {
        runs_before_selling: Number($("#ed-runs-venda").value),
        sell_start_slot: Number($("#ed-slot-venda").value),
        sell_clicks: Number($("#ed-cliques-venda").value),
        buy_return_charm: $("#ed-recomprar-charm").checked,
      },
    },
  };

  const senhaP = senhaNova
    ? chamar("definir_senha", contaUidEditando, senhaNova)
    : Promise.resolve(null);

  senhaP.then(() =>
    chamar("salvar_personagem", contaUidEditando, dados)
  ).then((r) => {
    // RECUSADO: desmarcar "aceitar convites de time" numa conta que é o reset
    // de outra é o mesmo estrago que deletar, por outra porta. O editor fica
    // ABERTO, com o que o usuário digitou, para ele desfazer sem perder nada.
    if (r && r.ok === false) { avisar(r.erro || "Não foi possível salvar."); return; }
    toast("Conta salva.");
    fecharEditor();
    carregarContas();
  });
}
$("#btn-salvar-conta").addEventListener("click", salvarEditor);

/* ---------- balão de ajuda ---------- */
/*
 * Um balão só, criado uma vez e reaproveitado por todos os "?" da tela.
 *
 * Ele mora no <body> de propósito: os painéis do modal rolam, e um balão
 * posicionado dentro deles seria cortado na borda. Com `position: fixed` no
 * body ele escapa de qualquer recorte -- em troca, a posição precisa ser
 * calculada aqui, a partir de onde o "?" está na tela.
 */
let balao = null;

function mostrarAjuda(icone) {
  const texto = icone.dataset.ajuda;
  if (!texto) return;
  if (!balao) {
    balao = document.createElement("div");
    balao.id = "balao-ajuda";
    document.body.appendChild(balao);
  }
  balao.textContent = texto;
  balao.classList.add("visivel");

  // Medir DEPOIS de preencher: o tamanho depende do texto.
  const r = icone.getBoundingClientRect();
  const b = balao.getBoundingClientRect();
  const folga = 8;

  // WebView2 frameless: window.screenX/screenY dá a posição da janela na tela.
  // getBoundingClientRect() é relativo ao viewport, então somamos o offset
  // da janela para posicionar corretamente quando a janela não está em (0,0).
  const winX = window.screenX || window.screenLeft || 0;
  const winY = window.screenY || window.screenTop || 0;

  // Abre para a esquerda se não couber à direita, e para cima se não couber
  // embaixo. Sem isto o balão sai da janela nos campos da borda -- e a janela
  // é travada em 1200x800, então isso acontece de verdade.
  let x = r.left + winX;
  if (x + b.width + folga > window.innerWidth + winX) {
    x = window.innerWidth + winX - b.width - folga;
  }
  let y = r.bottom + winY + 6;
  if (y + b.height + folga > window.innerHeight + winY) {
    y = r.top + winY - b.height - 6;
  }
  balao.style.left = `${Math.max(folga, x)}px`;
  balao.style.top = `${Math.max(folga, y)}px`;
}

function esconderAjuda() {
  if (balao) balao.classList.remove("visivel");
}

document.addEventListener("mouseover", (e) => {
  const icone = e.target.closest && e.target.closest(".ajuda");
  if (icone) mostrarAjuda(icone);
});
document.addEventListener("mouseout", (e) => {
  if (e.target.closest && e.target.closest(".ajuda")) esconderAjuda();
});

/* ---------- captura de tecla ---------- */
let capturando = null;
document.addEventListener("focusin", (e) => {
  if (e.target.classList && e.target.classList.contains("captura")) {
    capturando = e.target;
    e.target.classList.add("capturando");
    // Feedback visual: toast curto informando que está capturando
    toastCurto("Pressione uma tecla… (Esc para limpar)", "info", 1500);
  }
});
document.addEventListener("focusout", (e) => {
  if (e.target === capturando) {
    capturando = null;
    e.target.classList.remove("capturando");
  }
});
document.addEventListener("keydown", (e) => {
  if (!capturando) return;
  e.preventDefault();
  e.stopPropagation();
  if (e.key === "Escape") {
    capturando.value = "";
    capturando.blur();
    return;
  }
  let val;
  if (e.key === " ") val = "SPACE";
  else if (e.key === "Tab") val = "TAB";
  else val = String(e.key).toUpperCase();

  // TECLA REPETIDA NÃO PASSA. O jogo não permite a mesma tecla em duas funções
  // -- cada uma tem um destino só no Keys Setting --, então aceitar aqui
  // descreveria algo que não existe: o bot acha que trocou de barra e na
  // verdade disparou uma skill, sem nunca perceber.
  //
  // A ABA APP NÃO TEM FILTRO, e isso é regra de ecossistema, não detalhe.
  //
  // O campo em captura sai inteiro da verificação quando é do APP: nem contra a
  // aba Teclas, nem contra os outros campos do próprio APP. Lá a MESMA tecla se
  // repete na sequência por desenho — é o uso normal do módulo, e barrar isso
  // proibiria a macro que o usuário quer montar.
  //
  // Antes só metade disso valia: os campos do APP não têm `id^=ed-k-`, então
  // não conflitavam ENTRE SI, mas o campo em captura ainda era comparado com a
  // aba Teclas — e uma tecla já usada no BC era recusada no APP. A GUI já
  // estava certa (`KeyCapture()` sem `conflito` nos passos do APP); era só a
  // web que barrava.
  const doApp = capturando.classList.contains("app-tecla");
  const emUso = doApp ? null : [...document.querySelectorAll('[id^="ed-k-"]')].find(
    (i) => i !== capturando && i.value && i.value.toUpperCase() === val);
  if (emUso) {
    const onde = emUso.closest("label");
    const nome = onde ? onde.childNodes[0].textContent.trim() : "outra função";

    // NOVO: scroll para o campo conflitante e highlight temporário
    emUso.scrollIntoView({ behavior: "smooth", block: "center" });
    emUso.classList.add("conflito-tecla");
    setTimeout(() => emUso.classList.remove("conflito-tecla"), 3000);

    // NOVO: trocar aba automaticamente se estiver em outra aba
    const painel = emUso.closest(".aba-conteudo, .painel-aba");
    if (painel) {
      const abaId = painel.id;
      const abaBtn = document.querySelector(`.aba[data-aba="${abaId}"]`);
      if (abaBtn && !abaBtn.classList.contains("aba-ativa")) abaBtn.click();
    }

    toast(`A tecla ${val} já está em "${nome}". O jogo não aceita a mesma ` +
          `tecla em duas funções.`, "err");
    capturando.blur();
    return;
  }

  capturando.value = val;
  capturando.blur();
});

/* ============================================================
   CLIENTE
   ============================================================ */

function preencherConfig(cfg) {
  $("#in-client-bat").value = cfg.client_bat || "";
  $("#in-resolucao").value = cfg.resolution || "auto";
  $("#in-delay-lancamento").value = segundosParaMs(cfg.launch_delay);
  $("#ck-minimizar").checked = !!cfg.minimize_clients;
  $("#ck-reaproveitar").checked = !!cfg.reuse_login_screen_clients;
}

$("#btn-salvar-config").addEventListener("click", () => {
  const dados = {
    client_bat: $("#in-client-bat").value.trim(),
    resolution: $("#in-resolucao").value,
    launch_delay: msParaSegundos($("#in-delay-lancamento").value),
    minimize_clients: $("#ck-minimizar").checked,
    reuse_login_screen_clients: $("#ck-reaproveitar").checked,
  };
  chamar("salvar_config_geral", dados).then(() =>
    toast("Configuração do cliente salva.", "ok"));
});

$("#btn-procurar-bat").addEventListener("click", () => {
  chamar("procurar_client_bat").then((p) => {
    if (p) $("#in-client-bat").value = p;
  });
});

/* ============================================================
   ESTATÍSTICAS
   ============================================================ */

function atualizarSeletorStats(lista) {
  // Assinatura das opções (login|nick|total). `personagens_com_runs` roda a cada
  // poll de 1,5 s; se nada mudou, não há porquê reconstruir o <select> nem
  // re-renderizar stats (o carregamento mostraria os mesmos cards/histórico).
  const sig = (lista || [])
    .map((p) => `${p.login}${p.nick}${p.total}`)
    .join("");
  if (sig === ultimoSeletorSig) return; // inalterado: preserva seleção + stats
  ultimoSeletorSig = sig;

  const sel = $("#sel-personagem");
  const atual = sel.value;
  sel.innerHTML = "";
  if (!lista || !lista.length) {
    $("#aviso-sem-runs").classList.remove("escondida");
    $("#cards-estatisticas").innerHTML = "";
    $("#corpo-historico").innerHTML = "";
    statsLogin = null;
    ultimoStatsJson = null; // stats zerados: cache antigo não vale mais
    return;
  }
  $("#aviso-sem-runs").classList.add("escondida");
  lista.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.login;
    opt.textContent = `${p.nick}  (${p.total} runs)`;
    sel.appendChild(opt);
  });
  // mantém a escolha; senão, pega o primeiro (mais runs, como na PyQt6)
  const valido = lista.some((p) => p.login === atual);
  statsLogin = valido ? atual : lista[0].login;
  sel.value = statsLogin;
  carregarStats();
}

function carregarStats() {
  if (!statsLogin) return;
  // Troca de personagem: re-sincroniza o cronômetro imediatamente usando o
  // último estado conhecido (sem esperar o próximo poll de 1,5 s).
  if (ultimoEstado) sincronizarCronometro(ultimoEstado);
  chamar("stats_conta", statsLogin).then((r) => {
    if (!r) return;
    // Re-renderizar cards/histórico a cada poll quando o conteúdo não mudou é
    // trabalho desperdiçado. Compara por conteúdo (JSON) e pula idênticos —
    // atualiza ao vivo quando os números mudam de fato.
    const chave = JSON.stringify(r);
    if (chave === ultimoStatsJson) return;
    ultimoStatsJson = chave;
    const grade = $("#cards-estatisticas");
    grade.innerHTML = "";
    Object.values(r.cards).forEach((c) => {
      const card = document.createElement("div");
      card.className = "card-stat";
      const rot = document.createElement("span");
      rot.className = "card-rotulo"; rot.textContent = c.rotulo;
      const val = document.createElement("span");
      val.className = "card-valor"; val.textContent = c.valor;
      card.appendChild(rot); card.appendChild(val);
      grade.appendChild(card);
    });
    const corpo = $("#corpo-historico");
    corpo.innerHTML = "";
    (r.historico || []).forEach((h) => {
      const tr = document.createElement("tr");
      [h.dia, h.runs, h.success, h.fail, h.boss, h.media]
        .forEach((v) => {
          const td = document.createElement("td"); td.textContent = v;
          tr.appendChild(td);
        });
      corpo.appendChild(tr);
    });
    if (!r.historico.length) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 6; td.textContent = "Sem histórico de dias anteriores.";
      td.style.color = "var(--text-faint)";
      tr.appendChild(td); corpo.appendChild(tr);
    }
  });
}

$("#sel-personagem").addEventListener("change", (e) => {
  statsLogin = e.target.value;
  carregarStats();
});

/* ============================================================
   LOG
   ============================================================ */

function atualizarFiltroLog() {
  const sel = $("#sel-filtro-conta");
  const atual = sel.value;
  sel.innerHTML = "";
  const tudo = document.createElement("option");
  tudo.value = ""; tudo.textContent = "Todas as contas";
  sel.appendChild(tudo);
  contasCache.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.login;
    opt.textContent = c.nick || c.login;
    sel.appendChild(opt);
  });
  sel.value = contasCache.some((c) => c.login === atual) ? atual : "";
  filtroLog = sel.value;
}
$("#sel-filtro-conta").addEventListener("change", (e) => {
  filtroLog = e.target.value;
  renderLog();
});

function corConta(login) {
  let h = 0;
  for (const ch of login) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return `hsl(${h} 45% 55%)`;
}

// login -> nick do personagem. O `conta` das linhas é o LOGIN (nome do logger
// `blazes.<login>`); o nick (last_char_name) é o que o usuário quer ver.
// Mapa pequeno, refeito a cada render -- contasCache é uma lista curta.
function nickPorLogin() {
  const mapa = new Map();
  contasCache.forEach((c) => mapa.set(c.login, c.nick || c.login));
  return mapa;
}

// EFEITOS DO LOG (chegada da linha e rolagem que desliza) LIGADOS À FORÇA.
//
// A media query `prefers-reduced-motion` seria o portão natural aqui, e ela foi
// TIRADA com medição atrás: o Windows desta máquina está com animação de janela
// desligada (`HKCU\Control Panel\Desktop\WindowMetrics\MinAnimate = 0`) e o
// Chromium traduz isso em `prefers-reduced-motion: reduce` -- as duas instâncias
// de Chrome abertas para conferir a tela reportaram `reduce`. Com o portão, os
// efeitos que o usuário PEDIU não apareceriam nem uma vez no bot dele.
//
// Interruptor, não comentário: `false` devolve o respeito automático à
// preferência do sistema.
const EFEITOS_DO_LOG = true;
const MOVIMENTO_REDUZIDO = window.matchMedia("(prefers-reduced-motion: reduce)");

// Verdadeiro quando a tela pode animar. Um lugar só para os dois efeitos.
function podeAnimarOLog() {
  return EFEITOS_DO_LOG || !MOVIMENTO_REDUZIDO.matches;
}

// Teto do lote que ganha o efeito de chegada -- ver `animar` em `renderLog`.
const LOTE_MAXIMO_ANIMADO_NO_LOG = 12;

// A HORA QUE ABRE CADA LINHA. O handler da web formata
// "%(asctime)s  %(message)s" com "%H:%M:%S" (`web_app._LogHandler`), então a
// hora é sempre o começo do texto. Separá-la é o que permite ao CSS dar peso
// diferente para referência (hora) e conteúdo (mensagem). Linha que NÃO casar
// entra inteira na coluna da mensagem -- nunca se perde texto.
const RE_HORA_DA_LINHA = /^(\d{2}:\d{2}:\d{2})\s+/;

function renderLog() {
  const caixa = $("#caixa-log");
  // Se mudou o filtro de conta, reconstrói tudo; senão, só ACRESCENTA as
  // linhas novas no fim (append-only). Não reconstruir o innerHTML inteiro é
  // metade do conserto: não engasga o scroll e não destrói a seleção de texto
  // que o usuário faz a cada poll de 300 ms -- é o que permite copiar livre.
  const reconstruiu = filtroLog !== filtroRenderido;
  if (reconstruiu) {
    caixa.innerHTML = "";
    renderizadoAte = 0;
    filtroRenderido = filtroLog;
  }

  const linhas = filtroLog
    ? logCache.filter((l) => l.conta === filtroLog)
    : logCache;
  const nicks = nickPorLogin();

  // EFEITO DE CHEGADA: só nas linhas que ACABARAM de chegar, e só quando são
  // poucas. Sem os dois limites o efeito trabalharia contra si mesmo: a troca
  // de filtro repinta até `LOG_CACHE_MAX` linhas de uma vez e o primeiro
  // carregamento traz o histórico inteiro -- animar aquilo é a tela toda
  // piscando, e milhares de elementos compostos para nada. Em rajada (250
  // linhas por poll no teste de volume) o lote passa do teto e nada anima, que
  // é o certo: ali o que importa é alcançar o fim, não enfeitar a chegada.
  const chegando = linhas.length - renderizadoAte;
  const animar = !reconstruiu
    && chegando > 0
    && chegando <= LOTE_MAXIMO_ANIMADO_NO_LOG
    && podeAnimarOLog();

  for (let i = renderizadoAte; i < linhas.length; i++) {
    const l = linhas[i];
    const span = document.createElement("span");
    span.className = animar ? "linha-log log-chegando" : "linha-log";
    span.style.cursor = "copy";
    span.title = "Clique direito para copiar esta linha";
    // TRÊS PEDAÇOS, TRÊS COLUNAS: hora | conta | mensagem. É SÓ APRESENTAÇÃO --
    // o texto copiado (clique direito e botão "Copiar") continua saindo de
    // `l.linha` inteira, com a hora no lugar. Sem esta separação o CSS não tem
    // onde pegar: a linha era um texto solto e as 35 linhas da tela saíam todas
    // com o mesmo peso, sem coluna para a quebra de linha longa se alinhar.
    const casouHora = RE_HORA_DA_LINHA.exec(l.linha);
    if (casouHora) {
      const hora = document.createElement("span");
      hora.className = "log-hora";
      hora.textContent = casouHora[1];
      span.appendChild(hora);
    }
    // Nick do personagem só no filtro "Todas as contas" -- ajuda a saber de
    // quem é a linha. Com filtro de uma conta só, o nick é redundante.
    if (l.conta && !filtroLog) {
      const nick = document.createElement("span");
      nick.className = "log-conta-nick";
      nick.style.color = corConta(l.conta);
      nick.textContent = nicks.get(l.conta) || l.conta;
      span.appendChild(nick);
    }
    const msg = document.createElement("span");
    msg.className = "log-msg";
    msg.textContent = casouHora ? l.linha.slice(casouHora[0].length) : l.linha;
    span.appendChild(msg);
    // NOVO: clique direito copia a linha individual
    span.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      copiarTexto(l.linha).then(ok => toastCurto(ok ? "Linha copiada" : "Falha ao copiar", ok ? "ok" : "err"));
    });
    caixa.appendChild(span);
  }
  renderizadoAte = linhas.length;

  // Segue o fim como o desktop: acompanha a última linha até o usuário rolar
  // para cima; quando ele volta ao fim, volta a acompanhar (ver `aoRolarLog`).
  if (logSeguirFim) seguirOFimDoLog();
  $("#lbl-log-count").textContent = `${linhas.length} linhas exibidas`;
}

/* ============================================================
   SEGUIR O FIM DO LOG
   ============================================================
   Contrato (o mesmo do desktop): o log acompanha a última linha até o usuário
   rolar para cima; quando ele volta ao fim, volta a acompanhar.

   TRÊS COISAS QUE A VERSÃO ANTERIOR ERRAVA, todas medidas no navegador:

   1. **A CAIXA NASCE SEM LAYOUT e ninguém a avisava quando ela ganhava um.**
      `.secao` é `display: none` e o app abre em Contas, então o log só passa a
      existir quando o usuário clica na aba. Enquanto escondida, `scrollHeight`
      e `clientHeight` são 0: o `scrollTop = scrollHeight` de todo `renderLog`
      não fazia NADA. Medido ao entrar na aba com 35 linhas já no cache:
      `scrollTop: 0` com **381 px sobrando abaixo** -- e o `renderLog` seguinte
      só chega quando vem linha nova, que em backoff demora até 5 s. Era o
      "tenho que arrastar a barra à mão para ele começar a acompanhar", e é
      intermitente por isso: quando o bot está falando muito, a linha seguinte
      chega antes de o usuário perceber. `navegar()` agora avisa.

   2. **A TOLERÂNCIA DE 8 px ERA UMA ARMADILHA.** Arrastar a barra e parar 20 px
      antes do fim é a coisa mais fácil que existe -- e desligava o
      acompanhamento em silêncio, sem nada na tela dizendo por quê. Agora a
      margem é uma LINHA inteira: quem parou a menos de uma linha do fim quis
      dizer "fim".

   3. **ROLAGEM SUAVE dispara `scroll` em cada quadro da animação**, todos em
      posições intermediárias. Lendo `scrollTop` cru, a própria animação
      desligaria o seguir-fim no meio do movimento que ela mesma pediu -- por
      isso a trava `rolagemDaTela`.
*/

// Uma linha de log (12px × 1.55 + 7px de padding) arredondada para cima. Quem
// parou a menos de UMA LINHA do fim quis dizer "fim" -- ver o item 2.
const MARGEM_DO_FIM_DO_LOG = 26;

// Salto acima disto vai INSTANTÂNEO. Suave é bom na chegada normal (uma ou duas
// linhas por poll); em rajada não é só feio, é errado: no teste de volume chegam
// 250 linhas por poll de 300 ms, e uma tela que ainda está deslizando nunca
// alcançaria o fim. Acima do teto, alcançar vale mais que enfeitar.
const SALTO_SUAVE_MAXIMO_DO_LOG = 340;

// Fração da distância que falta vencida por quadro.
//
// POR QUE PERSEGUIÇÃO E NÃO UMA ANIMAÇÃO COM COMEÇO E FIM: durante a rolagem
// CHEGAM MAIS LINHAS e o fim se move. Uma transição para um alvo fixo ficaria
// sempre atrás do fim de verdade. Esta recalcula o alvo a cada quadro e vence
// uma fração do que falta, então ela persegue o fim de AGORA. Em 60 fps, 0.28
// leva ~10 quadros (≈170 ms) para vencer duas linhas -- perceptível como
// movimento, curto o bastante para não parecer preguiça.
const APROXIMACAO_POR_QUADRO_DO_LOG = 0.28;

// A tela está rolando sozinha. Enquanto isto está ligado, `aoRolarLog` não
// decide nada: os eventos que chegam são da animação, não do usuário.
let rolagemDaTela = false;
let quadroDaRolagem = null;

// POR QUE UM LAÇO PRÓPRIO E NÃO `scrollTo({behavior: "smooth"})`: aquele mira um
// alvo FIXO, decidido no instante da chamada. Aqui o fim se move -- chegam mais
// linhas enquanto a tela desliza -- e ele terminaria a animação num ponto que já
// não é o fim, ficando permanentemente atrás. Este laço recalcula o alvo a cada
// quadro. (Ele também não depende de o motor animar scroll programático, que é
// comportamento que varia.)
function pararRolagemDaTela() {
  if (quadroDaRolagem !== null) cancelAnimationFrame(quadroDaRolagem);
  quadroDaRolagem = null;
  rolagemDaTela = false;
}

function seguirOFimDoLog() {
  const caixa = $("#caixa-log");
  // Sem layout (aba escondida) não há o que rolar; quem resolve é `navegar()`.
  if (!caixa.clientHeight) return;
  const salto = caixa.scrollHeight - caixa.clientHeight - caixa.scrollTop;
  if (salto <= 0) return;

  if (salto > SALTO_SUAVE_MAXIMO_DO_LOG || !podeAnimarOLog()) {
    pararRolagemDaTela();
    caixa.scrollTop = caixa.scrollHeight - caixa.clientHeight;
    return;
  }
  if (quadroDaRolagem !== null) return;   // já perseguindo

  rolagemDaTela = true;
  const passo = () => {
    const alvo = caixa.scrollHeight - caixa.clientHeight;
    const resta = alvo - caixa.scrollTop;
    // Chegou, ou o log disparou e virou rajada no meio da perseguição: nos dois
    // casos cola no fim e encerra.
    if (resta <= 1 || resta > SALTO_SUAVE_MAXIMO_DO_LOG) {
      caixa.scrollTop = alvo;
      pararRolagemDaTela();
      return;
    }
    caixa.scrollTop += Math.max(1, resta * APROXIMACAO_POR_QUADRO_DO_LOG);
    quadroDaRolagem = requestAnimationFrame(passo);
  };
  quadroDaRolagem = requestAnimationFrame(passo);
}

// GESTO DO USUÁRIO MANDA. Sem isto a perseguição brigaria com o arrasto dele,
// puxando a tela de volta enquanto ele tenta subir. `wheel` e `pointerdown`
// chegam ANTES do `scroll` que eles causam, então a trava já caiu quando
// `aoRolarLog` for decidir.
["wheel", "pointerdown", "keydown", "touchstart"].forEach((ev) =>
  $("#caixa-log").addEventListener(ev, pararRolagemDaTela, { passive: true }));

function aoRolarLog() {
  const caixa = $("#caixa-log");
  // Caixa sem layout: as medidas são 0 e não querem dizer nada.
  if (!caixa.clientHeight) return;
  const noFim = caixa.scrollTop + caixa.clientHeight
                >= caixa.scrollHeight - MARGEM_DO_FIM_DO_LOG;
  // Rolagem nossa: nenhum quadro intermediário dela decide nada. Quem solta a
  // trava é o fim da perseguição (ou um gesto do usuário), não este evento.
  if (rolagemDaTela) return;
  logSeguirFim = noFim;
}
$("#caixa-log").addEventListener("scroll", aoRolarLog);

// ENTRAR NA ABA LOG É PEDIR PARA VER O QUE ESTÁ ACONTECENDO AGORA. Religa o
// acompanhamento e cola no fim -- ver o item 1. `requestAnimationFrame` porque
// neste instante a seção acabou de trocar de `display` e a caixa ainda não tem
// altura medida; sem esperar o layout, `scrollHeight` ainda é 0.
function colarNoFimDoLog() {
  logSeguirFim = true;
  requestAnimationFrame(() => {
    const caixa = $("#caixa-log");
    if (!caixa.clientHeight) return;
    caixa.scrollTop = caixa.scrollHeight - caixa.clientHeight;
  });
}

// Teto do cache de log do frontend. O DOM acompanha: `renderizadoAte` e´ quantos
// filhos a caixa tem, e a poda remove os dois lados juntos.
const LOG_CACHE_MAX = 4000;

// PODA ALINHADA AO DOM -- o conserto de um defeito que fazia o log da tela
// PARAR DE CRESCER em silencio.
//
// `renderizadoAte` e´ um indice absoluto em `linhas` (o cache, ou o filtro
// dele). A versao anterior podava com `logCache.shift()` por linha, dentro do
// `forEach`, sem tocar em `renderizadoAte` nem no DOM. Duas consequencias:
//
//   1. cada `shift()` deslocava os indices, e o render PULAVA silenciosamente
//      tantas linhas quantas tinham sido descartadas;
//   2. saturado em LOG_CACHE_MAX, `logCache.length` ficava constante e
//      `renderizadoAte` igualava esse valor PARA SEMPRE -- o laco
//      `for (i = renderizadoAte; i < linhas.length; i++)` nunca executava e
//      NENHUMA linha nova era desenhada, com o contador travado em
//      "4000 linhas exibidas".
//
// Alem disso `shift()` e´ O(n): com o backend reenviando historico (o defeito
// irmao, em `web_app.puxar_log`) eram ~8000 shifts sobre 4000 elementos por
// poll, 3,3x/s, na thread principal do WebView2.
//
// Aqui a poda e´ UM `splice`, e remove da caixa exatamente os filhos que saem do
// cache -- so os que estavam DESENHADOS, que com filtro ativo nao sao todos.
function podarCache() {
  const excedente = logCache.length - LOG_CACHE_MAX;
  if (excedente <= 0) return;
  const saindo = logCache.splice(0, excedente);
  const caixa = $("#caixa-log");
  const desenhadas = filtroRenderido
    ? saindo.filter((l) => l.conta === filtroRenderido).length
    : saindo.length;
  for (let i = 0; i < desenhadas && caixa.firstChild; i++) {
    caixa.removeChild(caixa.firstChild);
  }
  renderizadoAte = Math.max(0, renderizadoAte - desenhadas);
}

function pollLog() {
  chamar("puxar_log", logCursor).then((r) => {
    if (!r) return;
    // `typeof` e nao `||`: um `total` legitimo de 0 (outra aba chamou
    // `limpar_log`, ou o backend foi recriado) seria tratado como "sem valor" e
    // o cursor antigo ficaria pedindo linhas que nao existem mais.
    if (typeof r.total === "number") {
      if (r.total < logCursor) {
        // O backend RETROCEDEU: o historico daqui e´ fantasma. Reconstroi.
        logCache = [];
        renderizadoAte = 0;
        filtroRenderido = null;
        $("#caixa-log").innerHTML = "";
      }
      logCursor = r.total;
    }
    const temNovas = r.linhas && r.linhas.length;
    (r.linhas || []).forEach((l) => logCache.push(l));
    podarCache();
    if (temNovas) {
      renderLog();
      // Volta ao intervalo normal: há atividade.
      if (logPollInterval !== 300) {
        logPollInterval = 300;
        clearInterval(logPollId);
        logPollId = setInterval(pollLog, logPollInterval);
      }
    } else {
      // Backoff progressivo: 300 → 600 → 1200 → 2400 → 5000 ms.
      logPollInterval = Math.min(5000, logPollInterval * 2);
      clearInterval(logPollId);
      logPollId = setInterval(pollLog, logPollInterval);
    }
  });
}

$("#btn-limpar-log").addEventListener("click", () => {
  chamar("limpar_log").then(() => {
    logCache = [];
    logCursor = 0;
    // Força a reconstrução (append-only): `filtroRenderido = null` diverge do
    // filtro e o `renderLog` limpa a caixa antes de renderizar de novo.
    renderizadoAte = 0;
    filtroRenderido = null;
    renderLog();
    toast("Log limpo.");
  });
});

// Toggle "log detalhado" (ambiente dev): paridade com o `ck_debug` da GUI.
// Em prod o elemento fica oculto e o backend ignora a chamada.
$("#ck-log-detall").addEventListener("change", () => {
  chamar("definir_nivel_log", $("#ck-log-detall").checked ? "DEBUG" : "INFO");
});

$("#btn-copiar-log").addEventListener("click", () => {
  const linhas = filtroLog
    ? logCache.filter((l) => l.conta === filtroLog)
    : logCache;
  const texto = linhas
    .map((l) => (l.conta ? `[${l.conta}] ${l.linha}` : l.linha))
    .join("\n");
  if (!texto) { toast("Nada para copiar ainda."); return; }
  copiarTexto(texto).then((ok) => {
    toast(ok ? "Log copiado para a área de transferência."
             : "Não foi possível copiar o log.");
  });
});

function copiarTexto(texto) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(texto).then(() => true).catch(() =>
      copiarTextoLegado(texto));
  }
  return Promise.resolve(copiarTextoLegado(texto));
}
function copiarTextoLegado(texto) {
  try {
    const ta = document.createElement("textarea");
    ta.value = texto;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch (_) { return false; }
}

/* ============================================================
   ESTADO (rodapé lateral + diagnóstico)
   ============================================================ */

// Liga/desliga os botões de controle conforme o estado do bot e põe o brilho
// (bt-destaque) no botão que representa a AÇÃO PRINCIPAL disponível agora —
// assim dá para saber o estado e o que clicar de relance:
//   Parado  -> só "Iniciar" habilitado (destaque nele)
//   Rodando -> "Parar" e "Pausar" habilitados (destaque em "Parar")
//   Pausado -> "Parar" e "Retomar" habilitados (destaque em "Retomar")
function atualizarBotoesControle(est) {
  const rodando = !!est.rodando;
  const pausado = !!est.pausado;
  const parar = rodando;              // sempre pode parar enquanto não está parado
  const pausar = rodando && !pausado; // pausar só faz sentido rodando normalmente
  const retomar = rodando && pausado; // retomar só faz sentido quando pausado
  const iniciar = !rodando;           // iniciar só quando parado

  const definir = (btn, habilitado, destaque) => {
    btn.disabled = !habilitado;
    btn.classList.toggle("bt-destaque", destaque);
  };
  definir($("#btn-iniciar"), iniciar, iniciar);
  definir($("#btn-parar"), parar, parar && !pausado);
  definir($("#btn-pausar"), pausar, false);
  definir($("#btn-retomar"), retomar, retomar);
}

function atualizarEstado(est) {
  if (!est) return;
  ultimoEstado = est;
  sincronizarCronometro(est);
  atualizarBotoesControle(est);
  atualizarBotoesTemporarios(est);
  const roda = $("#estado-roda");
  if (est.rodando && est.pausado) {
    roda.textContent = "⏸ Pausado";
    roda.className = "estado-roda estado-pausado";
  } else if (est.rodando) {
    roda.textContent = "● Rodando";
    roda.className = "estado-roda estado-rodando";
  } else {
    roda.textContent = "● Parado";
    roda.className = "estado-roda estado-parado";
  }
  const t = est.total || {};
  // Confirmação visual do estado NA faixa de stats (runs/ok/falhas/relogins/
  // contas): mesmo com 0 runs enquanto as contas ainda logam ou esperam, a
  // primeira linha deixa claro que o bot está iniciado — não só o pontinho.
  $("#estado-resumo").textContent =
    `${t.runs || 0} runs · ${t.success || 0} ok · ${t.fail || 0} falhas` +
    `\n${t.relogins || 0} relogins · ${(est.contas || []).length} contas`;
  $("#diag-status").textContent =
    est.rodando ? (est.pausado ? "Pausado" : "Rodando") : "Parado";

  // Reflete ao vivo o BC farm das contas rodando. O backend pode desligá-lo
  // sozinho (ex.: a conta tentou ir vender sem tecla de retorno configurada) —
  // deixa o checkbox da tabela acompanhar, sem re-renderizar a linha inteira
  // (que apagaria uma edição inline em andamento).
  (est.contas || []).forEach((c) => {
    // POR UID, não por login: o login é campo livre e dois iguais faziam esta
    // busca acertar a primeira linha, que podia ser de outra conta. Cai fora
    // sem uid em vez de adivinhar pelo login.
    if (!c.uid) return;
    const tr = $("#corpo-contas").querySelector(`tr[data-uid="${CSS.escape(c.uid)}"]`);
    if (!tr) return;
    const chkBC = tr.querySelector('input[data-acao="bc"]');
    if (chkBC && chkBC.checked !== !!c.farm) chkBC.checked = !!c.farm;
  });

  // Toggle "log detalhado": só existe no ambiente dev (`BLAZES_MODO=dev`). Em
  // prod o backend força INFO+; aqui só expomos o controle de quem desenvolve
  // e refletimos o nível atual do logger `blazes`.
  const lblLog = $("#lbl-log-detall");
  if (lblLog) lblLog.classList.toggle("hidden", !est.dev);
  const ckLog = $("#ck-log-detall");
  if (ckLog && est.dev) {
    const det = (est.nivel_log || "INFO") === "DEBUG";
    if (ckLog.checked !== det) ckLog.checked = det;
  }
}

// NOVO: gerencia estado dos botões temporários (Testar Venda, Amostrar Cliques, Conferir Exclusão)
// Só habilitados quando: bot PARADO E conta selecionada
function atualizarBotoesTemporarios(est) {
  const temConta = contaUidSelecionado !== null;
  const botParado = !est.rodando;
  const habilitado = temConta && botParado;

  ["btn-testar-venda", "btn-amostrar-cliques", "btn-conferir-exclusao"].forEach(id => {
    const bt = document.getElementById(id);
    if (bt) {
      bt.disabled = !habilitado;
      bt.title = habilitado ? "" : (!temConta ? "Selecione uma conta na aba Contas" : "Pare o bot primeiro");
    }
  });
}

function pollEstado() {
  chamar("estado").then(atualizarEstado);
  // personagens com runs mudam com o tempo; atualiza o seletor
  chamar("personagens_com_runs").then(atualizarSeletorStats);
}

/* ============================================================
   DIAGNÓSTICO / LOGS
   ============================================================ */

function abrirLogs() { chamar("abrir_pasta_logs"); }
$("#btn-abrir-pasta-log").addEventListener("click", abrirLogs);
$("#btn-abrir-pasta-logs").addEventListener("click", abrirLogs);

// TEMPORÁRIO: testa SÓ a venda (personagem já em Stone City). Ver
// blazesbot/bot/teste_venda.py — para remover o teste, apague este bloco e o
// botão no index.html.
const ROTULO_TESTE_VENDA = "Testar Venda (Conta Selecionada)";
let testeDeVendaRodando = false;

$("#btn-testar-venda").addEventListener("click", () => {
  const bt = $("#btn-testar-venda");

  // Enquanto a venda roda, este botão é o CANCELAR: o botão Parar da barra
  // fica desabilitado com o bot parado, e o teste roda justamente assim.
  if (testeDeVendaRodando) {
    bt.disabled = true;
    bt.textContent = "Cancelando…";
    chamar("cancelar_teste_venda");
    return;
  }

  if (contaUidSelecionado === null) {
    toast("Selecione a conta na aba Contas primeiro.", "erro");
    return;
  }
  testeDeVendaRodando = true;
  bt.textContent = "Vendendo… (clique para parar)";
  toast("Teste de venda iniciado — acompanhe pelo log.");
  // A chamada só resolve quando a venda termina (pode levar minutos); o log
  // continua sendo puxado normalmente porque o pywebview atende cada chamada
  // do frontend em uma thread própria.
  chamar("testar_venda", contaUidSelecionado).then((r) => {
    testeDeVendaRodando = false;
    bt.disabled = false;
    bt.textContent = ROTULO_TESTE_VENDA;
    if (!r) { toast("Erro de comunicação.", "erro"); return; }
    if (r.ok) {
      toast(`Teste concluído: ${r.vendidos ?? 0} item(ns) vendido(s).`);
    } else {
      toast("Falha no teste: " + (r.erro || ""), "erro");
    }
  });
});

// TEMPORÁRIO: amostragem de coordenadas de clique direito. Ver
// blazesbot/bot/amostragem_de_cliques.py — para remover, apague este bloco e o
// botão no index.html.
const ROTULO_AMOSTRAGEM = "Amostrar Cliques (Ponto Atual)";
let amostragemRodando = false;

$("#btn-amostrar-cliques").addEventListener("click", () => {
  const bt = $("#btn-amostrar-cliques");

  // Mesmo desenho do teste de venda: com o bot parado, o botão Parar da barra
  // fica desabilitado, então o próprio botão é o cancelar.
  if (amostragemRodando) {
    bt.disabled = true;
    bt.textContent = "Cancelando…";
    chamar("cancelar_amostragem");
    return;
  }

  if (contaUidSelecionado === null) {
    toast("Selecione a conta na aba Contas primeiro.", "erro");
    return;
  }
  amostragemRodando = true;
  bt.textContent = "Amostrando… (clique para parar)";
  toast("Amostragem iniciada — acompanhe pelo log.");
  chamar("amostrar_cliques", contaUidSelecionado).then((r) => {
    amostragemRodando = false;
    bt.disabled = false;
    bt.textContent = ROTULO_AMOSTRAGEM;
    if (!r) { toast("Erro de comunicação.", "erro"); return; }
    if (!r.ok) { toast("Falha na amostragem: " + (r.erro || ""), "erro"); return; }
    // O veredito vem PRONTO do Python (`amostragem_de_cliques.resumir_curto`):
    // o JS só exibe. O relatório completo já está no log, linha a linha.
    toast(r.resumo_curto || "Amostragem concluída.");
  });
});

// Conferir os modelos de exclusão: fotografa a bolsa e desenha o que seria
// apagado, SEM apagar nada. Ver blazesbot/bot/app/afericao.py.
$("#btn-conferir-exclusao").addEventListener("click", () => {
  const bt = $("#btn-conferir-exclusao");
  if (contaUidSelecionado === null) {
    toast("Selecione a conta na aba Contas primeiro.", "erro");
    return;
  }
  bt.disabled = true;
  toast("Conferindo os modelos — abrindo o inventário…");
  chamar("conferir_modelos_de_exclusao", contaUidSelecionado).then((r) => {
    bt.disabled = false;
    if (!r) { toast("Erro de comunicação.", "erro"); return; }
    if (!r.ok) { toast("Falha: " + (r.erro || ""), "erro"); return; }
    // O veredito vem PRONTO do Python (`afericao.resumir`): o JS só exibe.
    toast(r.resumo || "Conferência concluída.");
    if (r.arquivo) chamar("abrir_imagem_da_afericao", r.arquivo);
  });
});

/* ============================================================
   HISTÓRICO DE QUEDAS
   ============================================================ */

// NÃO entra no poll de 1,5 s, e isso é decisão. Cada carregamento traz as
// miniaturas embutidas (a página roda em file:// e o WebView2 recusa <img src>
// para arquivo local), e queda é evento raro: recarregar isso duas vezes por
// segundo seria megabytes por minuto para mostrar a mesma lista. Carrega ao
// ABRIR a seção e ao trocar a conta.
let quedasCarregadas = false;

function textoTecnico(q) {
  const partes = [];
  if (q.run) partes.push(`run ${q.run}`);
  if (q.rodando_texto) partes.push(`rodando há ${q.rodando_texto}`);
  if (q.relogin) partes.push(`religou sozinho (relogin #${q.relogin})`);
  return partes.join(" · ");
}

function desenharQuedas(dados) {
  const caixa = $("#lista-quedas");
  const lista = (dados && dados.quedas) || [];
  $("#quedas-dias").textContent = (dados && dados.dias) || 3;

  if (!lista.length) {
    caixa.innerHTML =
      '<div class="aviso-banner aviso-neutro">Nenhuma queda nos últimos ' +
      ((dados && dados.dias) || 3) + " dias. 👍</div>";
    return;
  }

  caixa.innerHTML = "";
  lista.forEach((q) => {
    const cartao = document.createElement("div");
    cartao.className = "cartao-queda";

    const corpo = document.createElement("div");
    corpo.className = "queda-corpo";

    const topo = document.createElement("div");
    topo.innerHTML =
      `<span class="queda-quando">${q.quando_texto || ""}</span>` +
      `<span class="queda-conta"> — conta ${q.conta || "?"}` +
      (q.personagem ? ` (${q.personagem})` : "") + "</span>";
    corpo.appendChild(topo);

    const motivo = document.createElement("div");
    motivo.className = "queda-motivo";
    motivo.textContent = (q.motivo_texto || "") + ".";
    corpo.appendChild(motivo);

    const fazendo = document.createElement("div");
    fazendo.className = "queda-fazendo";
    fazendo.textContent =
      (q.fazendo_texto || "") + (q.onde_texto ? `, em ${q.onde_texto}` : "") + ".";
    corpo.appendChild(fazendo);

    const tec = textoTecnico(q);
    if (tec) {
      const linha = document.createElement("div");
      linha.className = "queda-tecnico";
      linha.textContent = tec;
      corpo.appendChild(linha);
    }
    cartao.appendChild(corpo);

    // O print só existe quando o jogo perdeu a conexão — nos outros dois casos
    // a janela já tinha morrido quando a queda foi percebida. Sem print, o
    // cartão simplesmente não mostra imagem (nada de explicação técnica).
    if (q.print_mini) {
      const img = document.createElement("img");
      img.className = "queda-print";
      img.src = q.print_mini;
      img.alt = "Print da tela no momento da queda";
      img.addEventListener("click", () => abrirPrintGrande(q.print));
      cartao.appendChild(img);
    }
    caixa.appendChild(cartao);
  });
}

function abrirPrintGrande(nome) {
  chamar("print_da_queda", nome).then((r) => {
    if (!r || !r.imagem) { toast("Não consegui abrir o print.", "erro"); return; }
    $("#lupa-print-img").src = r.imagem;
    $("#lupa-print").classList.remove("escondida");
  });
}

$("#lupa-print").addEventListener("click", () => {
  $("#lupa-print").classList.add("escondida");
  $("#lupa-print-img").src = "";
});

function carregarQuedas() {
  const conta = $("#sel-conta-quedas").value || "";
  chamar("historico_de_quedas", conta).then((dados) => {
    if (!dados) return;
    atualizarSeletorDeQuedas(dados.contas || []);
    desenharQuedas(dados);
    quedasCarregadas = true;
  });
}

function atualizarSeletorDeQuedas(contas) {
  const sel = $("#sel-conta-quedas");
  const atual = sel.value;
  const desejado = ["", ...contas].join("|");
  if (sel.dataset.sig === desejado) return;   // inalterado: preserva a escolha
  sel.dataset.sig = desejado;
  sel.innerHTML = "";
  // "Todas as contas" é a primeira e o padrão: a pergunta real é "o que
  // aconteceu essa noite", e ela atravessa contas.
  const todas = document.createElement("option");
  todas.value = "";
  todas.textContent = "Todas as contas";
  sel.appendChild(todas);
  contas.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    sel.appendChild(opt);
  });
  sel.value = contas.includes(atual) ? atual : "";
}

$("#sel-conta-quedas").addEventListener("change", carregarQuedas);

$("#btn-copiar-quedas").addEventListener("click", () => {
  const conta = $("#sel-conta-quedas").value || "";
  chamar("copiar_relatorio_de_quedas", conta).then((r) => {
    if (!r || !r.texto) { toast("Nada para copiar.", "erro"); return; }
    navigator.clipboard.writeText(r.texto).then(
      () => toast("Relatório copiado — pode colar e enviar para o suporte."),
      () => toast("Não consegui copiar.", "erro"));
  });
});

$("#btn-abrir-pasta-quedas").addEventListener("click", () => {
  chamar("abrir_pasta_de_quedas");
});

/* ============================================================
   INICIALIZAÇÃO
   ============================================================ */

function popularSeletores() {
  const c = constantes;

  const selRes = $("#in-resolucao");
  selRes.innerHTML = "";
  const auto = document.createElement("option");
  auto.value = "auto";
  auto.textContent = "detectar automaticamente";
  selRes.appendChild(auto);
  (c.resolucoes || []).forEach((r) => {
    const opt = document.createElement("option");
    opt.value = r.valor;
    opt.textContent = r.rotulo;
    selRes.appendChild(opt);
  });

  const selMont = $("#ed-montaria");
  selMont.innerHTML = "";
  (c.mounts || []).forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m.pct;
    opt.textContent = m.texto;
    selMont.appendChild(opt);
  });

  const selBolsa = $("#ed-bolsas");
  selBolsa.innerHTML = "";
  (c.bolsa_opcoes || []).forEach((b) => {
    const opt = document.createElement("option");
    opt.value = b.n;
    opt.textContent = b.texto;
    selBolsa.appendChild(opt);
  });

  const selCliques = $("#ed-cliques-venda");
  selCliques.innerHTML = "";
  (c.sell_cliques || []).forEach((n) => {
    const opt = document.createElement("option");
    opt.value = n;
    opt.textContent = n;
    selCliques.appendChild(opt);
  });

  // diagnóstico
  $("#diag-resolucao").textContent = c.resolucao_validada || "—";
  $("#diag-dpapi").textContent = c.dpapi
    ? "Disponível (senhas cifradas com o Windows)"
    : "INDISPONÍVEL — senhas não podem ser guardadas";
  $("#diag-dpapi").style.color = c.dpapi ? "" : "var(--err)";
}

function init() {
  if (!window.pywebview ||
      typeof (window.pywebview.api || {}).obter_constantes !== "function") {
    $("#caixa-log").textContent =
      "pywebview não carregado. Abra pela INICIAR-WEB.bat (não pelo navegador direto).";
    return;
  }
  chamar("obter_constantes").then((c) => {
    constantes = c;
    popularSeletores();
    chamar("obter_config").then(preencherConfig);
    carregarContas();
  });
  pollEstado();
  renderLog();
  setInterval(pollEstado, 1500);
  logPollId = setInterval(pollLog, logPollInterval);
}

/* O pywebview injeta o objeto `window.pywebview` DEPOIS da página carregar
   (na navegação concluída do WebView2) e então dispara `pywebviewready`.
   Neste ponto `window.pywebview.api` ainda não existe — por isso esperamos o
   evento. O fallback cobre o caso de o evento já ter disparado (recarga/debug). */
let _iniciado = false;
function iniciarComPywebview() {
  if (_iniciado) return;
  _iniciado = true;
  init();
}
window.addEventListener("pywebviewready", iniciarComPywebview);
setTimeout(() => {
  if (window.pywebview &&
      typeof (window.pywebview.api || {}).obter_constantes === "function") {
    iniciarComPywebview();
  }
}, 250);
/* ============================================================
   RODA DO MOUSE NOS CAMPOS NUMÉRICOS
   ============================================================
   Rolar a roda com o cursor sobre um campo numérico sobe e desce o valor. Vale
   para `type="number"` e `type="range"`, e para os campos que a aba APP cria em
   tempo de execução -- é por isso que o ouvinte é delegado no `document` em vez
   de instalado campo por campo.

   O PASSO DE CADA CAMPO É O ATRIBUTO `step` DELE, e não há tabela aqui: quem
   descreve o campo é o campo, no `index.html`, onde a escolha de cada passo está
   justificada. Isso também acerta as SETINHAS do input, que leem o mesmo `step`
   -- a versão anterior usava 100 fixo para tudo dentro de `#corpo-app` enquanto
   as setinhas daqueles mesmos campos andavam 50: dois passos diferentes no mesmo
   campo, dependendo de como você mexia nele.

   `data-passo-roda` é a EXCEÇÃO, e existe por causa dos sliders: em
   `type="range"` o `step` manda na GRADE de valores válidos, não só no tamanho
   do toque. Com `min="1"` e `step="5"` a grade vira 1, 6, 11 ... 96, e valores
   redondos como 90% -- que é o mínimo de vida para começar uma run -- ficam
   INALCANÇÁVEIS, inclusive arrastando. Então o slider fica com `step="1"` (pousa
   em qualquer inteiro, como sempre) e declara à parte o passo grosso da roda.

   TRÊS COISAS QUE A VERSÃO ANTERIOR NÃO FAZIA, e todas as três são defeito:

   1. **AVISAR QUEM ESCUTA.** Os rótulos de porcentagem dos sliders
      (`val-hp` e companhia) são escritos por ouvintes de `input`: mexer no
      `.value` calado deixava o slider numa posição e o rótulo com o número
      antigo -- conferido, o rótulo agora acompanha. O mesmo ouvinte alimenta
      `atualizarPreviaApp` ("volta completa em X s"), que hoje sai no
      `if (!el) return` porque **`#lbl-previa-app` não existe no `index.html`**
      (a prévia da sequência é funcionalidade só da GUI PyQt6 -- divergência
      registrada em `docs/decisoes/interface.md`, não consertada aqui). Quando o
      elemento entrar, este ouvinte já o alimenta.
   2. **RESPEITAR `min` E `max`.** Ela só cuidava de não passar de zero. O slot
      de venda é 1..24 (`config.validar` recusa fora disso, e a GUI já usava
      `setRange(1, 24)`): rolar até 30 só produzia erro na hora de salvar.
   3. **ARREDONDAR PELA CASA DECIMAL DO PASSO.** Em ponto flutuante, 0,5 + 0,1
      dá 0.6000000000000001 -- e esse texto ia direto para dentro do campo.

   `Shift` multiplica o passo por 10. É convenção de UI e evita configurar um
   segundo passo para o caso de querer atravessar a faixa toda.
*/
const MULTIPLICADOR_DA_RODA_COM_SHIFT = 10;

// Quantas casas decimais o passo tem -- é por ela que o resultado é arredondado.
function casasDecimaisDoPasso(passo) {
  const texto = String(passo);
  const ponto = texto.indexOf(".");
  return ponto < 0 ? 0 : texto.length - ponto - 1;
}

document.addEventListener("wheel", (e) => {
  const campo = e.target;
  if (!(campo instanceof HTMLInputElement)) return;
  if (campo.type !== "number" && campo.type !== "range") return;
  if (campo.disabled || campo.readOnly) return;

  const declarado = Number(campo.dataset.passoRoda ?? campo.step);
  const passo = (Number.isFinite(declarado) && declarado > 0 ? declarado : 1)
    * (e.shiftKey ? MULTIPLICADOR_DA_RODA_COM_SHIFT : 1);

  // Campo em branco vale o mínimo (ou zero): rolar sobre um campo vazio tem que
  // dar um número, nunca `NaN`.
  const lido = Number(campo.value);
  const atual = Number.isFinite(lido) && campo.value !== ""
    ? lido : (Number(campo.min) || 0);

  let novo = atual + (e.deltaY < 0 ? passo : -passo);
  const minimo = campo.min === "" ? null : Number(campo.min);
  const maximo = campo.max === "" ? null : Number(campo.max);
  if (minimo !== null && novo < minimo) novo = minimo;
  if (maximo !== null && novo > maximo) novo = maximo;
  novo = Number(novo.toFixed(casasDecimaisDoPasso(passo)));

  // O campo CONSOME a roda mesmo já estando no limite: rolar sobre um campo
  // nunca move o painel atrás dele, senão o gesto viraria loteria perto das
  // pontas da faixa.
  e.preventDefault();
  if (novo === atual) return;
  campo.value = String(novo);
  // Ver o item 1: sem estes dois a tela fica desatualizada em silêncio.
  campo.dispatchEvent(new Event("input", { bubbles: true }));
  campo.dispatchEvent(new Event("change", { bubbles: true }));
}, { passive: false });