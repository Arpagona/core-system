"use strict";
addEventListener("offline",()=>{const l=document.querySelector(".live"); if(l) l.textContent="● Hors ligne";});
addEventListener("online",()=>{const l=document.querySelector(".live"); if(l) l.textContent="● En ligne";});
const $ = (id) => document.getElementById(id);
const HEADERS = { "Content-Type": "application/json", "X-Arpagona": "1", "X-Gona": "1" };
const cmdBubbles = [];
const CMDKEY = "mc_cmd_bubbles";
function saveBubbles() {
  try { sessionStorage.setItem(CMDKEY, JSON.stringify(cmdBubbles.map(b => { const c = b.cloneNode(true); c.querySelectorAll("button,input,select").forEach(x => x.remove()); return c.innerHTML; }))); } catch(e) {}
}
function restoreBubbles() {
  try { for(const h of JSON.parse(sessionStorage.getItem(CMDKEY) || "[]")) { const b = document.createElement("div"); b.className = "msg system cmd"; b.innerHTML = h; cmdBubbles.push(b); } } catch(e) {}
}
restoreBubbles();
let busy = false, session = null, snapshot = null, missionFilter = "", lastMessages = null;
let stream = null, streamTimer = null, lastToolLine = null, commands = [], menuItems = [], menuIndex = 0;
let lastStreamSign = Date.now(), lastBusyOn = 0;
const PENDING = "arpagona-alpha-pending";
const escapeHtml = text => String(text == null ? "" : text).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = text => typeof renderMarkdown === "function" ? renderMarkdown(text) : escapeHtml(text);
// Accès pour voice.js (bouton micro) : session courante, messages, rafraîchissement.
window.MC = Object.assign(window.MC || {}, {
  session: () => session, messages: () => lastMessages || [],
  refresh: () => loadConversation(), busy: () => busy
});
async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {method:"POST",headers:HEADERS,body:JSON.stringify(body)});
  const data = await res.json();
  if(res.status===401) show("login");
  if(!res.ok) throw new Error(data.error || "Source indisponible");
  return data;
}

function show(view) {
  $("login-view").hidden = view !== "login";
  $("app-view").hidden = view !== "app";
  $("who").hidden = view !== "app";
}

function stamp(ts) {
  if(!ts) return "";
  const d = new Date(ts * 1000), now = new Date();
  const hm = d.toLocaleTimeString("fr-FR", {hour:"2-digit", minute:"2-digit"});
  return d.toDateString() === now.toDateString() ? hm : d.toLocaleDateString("fr-FR", {day:"2-digit", month:"2-digit"}) + " " + hm;
}
function addMessage(role, text, status, extra, ts) {
  const el = document.createElement("div");
  el.className = "msg " + role + (status === "failed" || status === "error" ? " failed" : "") + (extra ? " " + extra : "");
  if(role === "assistant" || role === "system") el.innerHTML = fmt(text);
  else el.textContent = text;
  if(ts && (role === "user" || role === "assistant")) { const t = document.createElement("time"); t.className = "msg-time"; t.textContent = stamp(ts); el.appendChild(t); }
  $("log").appendChild(el);
  $("log").scrollTop = $("log").scrollHeight;
  return el;
}

async function loadConversation(force) {
  if(!session) return;
  const data = await api("/api/channel/messages?id="+encodeURIComponent(session));
  lastMessages = data.messages || [];
  if(stream && stream.active && !force) return;
  const sig=JSON.stringify(data.messages);
  if($("log").dataset.signature===sig) return;
  const bottom=$("log").scrollHeight-$("log").scrollTop-$("log").clientHeight<100;
  $("log").replaceChildren();
  for(const m of data.messages || []) addMessage(m.role==="user"?"user":"assistant",m.text || m.content || "","",null,m.ts);
  for(const b of cmdBubbles) $("log").append(b);
  $("log").dataset.signature=sig;
  if(bottom) $("log").scrollTop=$("log").scrollHeight;
}
async function pollReply() {
  const saved=sessionStorage.getItem(PENDING); if(!saved) return;
  const p=JSON.parse(saved);
  let r;
  try { r=await api("/api/channel/reply?id="+encodeURIComponent(p.id)+"&submission="+encodeURIComponent(p.submission_id)); }
  catch(e) {
    if(/Session (Telegram )?active/.test(e.message)) {
      sessionStorage.removeItem(PENDING);
      if(!$("text").value) $("text").value=p.text||"";
      setBusy(false,"La conversation a changé : message non envoyé, renvoie-le.");
      await syncSession();
      return;
    }
    throw e;
  }
  await loadConversation();
  // Repli alpha (20/11) : quand l'agent est occupé, le gateway met le message en file et perd son submission_id.
  // On retrouve alors l'envoi par son texte (message utilisateur identique postérieur à l'envoi).
  if(r.state==="waiting" && Array.isArray(lastMessages)) {
    const t0=(p.t||0)/1000-30;
    const i=lastMessages.findIndex(m=>m.role==="user" && (m.text||m.content||"").trim()===(p.text||"").trim() && (!m.ts || m.ts>=t0));
    if(i>=0) {
      const done=lastMessages.slice(i+1).some(m=>m.role==="assistant");
      const other=lastMessages.slice(i+1).some(m=>m.role==="user");
      r.state = done ? (other?"ambiguous":"ready") : "working";
    }
  }
  // Garde-fou alpha (20/11) : un envoi jamais arrivé dans le fil (waiting) ou une attente sans fin ne bloque plus le chat.
  const age=Date.now()-(p.t||0);
  if((r.state==="waiting" && age>120000) || (r.state==="working" && age>900000)) {
    sessionStorage.removeItem(PENDING);
    if(r.state==="waiting" && !$("text").value) $("text").value=p.text||"";
    setBusy(false, r.state==="waiting" ? "Message non arrivé dans le fil : vérifie puis renvoie-le." : "Réponse longue : consulte le fil (Telegram).");
    return;
  }
  if(["ready","ambiguous"].includes(r.state)) {
    sessionStorage.removeItem(PENDING);
    setBusy(false,r.state==="ambiguous"?"Une autre intervention est intervenue ; consulte le fil.":"");
  } else setBusy(true,"L’agent prépare…"+(window.MC_BACKEND==="api"?"":" · même fil que Telegram"));
}
function setBusy(on, label) {
  busy = on;
  $("send").disabled = on || !$("text").value.trim();
  $("stop").hidden = !on;
  $("chat-status").textContent = label || "";
}

function closeStream() {
  if(stream && stream.es) stream.es.close();
  stream = null;
  if(streamTimer) { clearTimeout(streamTimer); streamTimer = null; }
}

function scheduleStream(delay) {
  if(streamTimer) clearTimeout(streamTimer);
  streamTimer = setTimeout(() => { streamTimer = null; if(session) startStream(); }, delay || 1500);
}

function startStream() {
  if(!session || !window.EventSource) return;
  closeStream();
  const es = new EventSource("/api/stream?id=" + encodeURIComponent(session));
  stream = { es, active: false, bubble: null, raw: "", tool: null, queued: false };
  es.onmessage = ev => {
    if(!stream || stream.es !== es) return;
    let data;
    try { data = JSON.parse(ev.data); } catch(e) { return; }
    handleStream(data);
  };
  es.onerror = () => {
    if(!stream || stream.es !== es) return;
    if(es.readyState === EventSource.CLOSED) {
      closeStream();
      $("chat-status").textContent = "Flux interrompu · actualisation automatique…";
      loadConversation(true).catch(() => {});
      scheduleStream(5000);
    } else {
      $("chat-status").textContent = "Reconnexion au flux…";
    }
  };
}

function streamBubble() {
  if(!stream) return null;
  if(!stream.bubble) {
    stream.bubble = addMessage("assistant", "", null, "streaming");
    stream.raw = "";
  }
  return stream.bubble;
}

function paintStream() {
  if(!stream || !stream.bubble || stream.queued) return;
  stream.queued = true;
  const paint = () => {
    if(!stream) return;
    stream.queued = false;
    if(!stream.bubble) return;
    const bottom = $("log").scrollHeight - $("log").scrollTop - $("log").clientHeight < 120;
    stream.bubble.innerHTML = fmt(stream.raw) + '<span class="caret" aria-hidden="true"></span>';
    if(bottom) $("log").scrollTop = $("log").scrollHeight;
  };
  if(window.requestAnimationFrame) requestAnimationFrame(paint); else setTimeout(paint, 30);
}

function finishStreamBubble() {
  if(!stream || !stream.bubble) return null;
  const el = stream.bubble;
  el.classList.remove("streaming");
  el.innerHTML = fmt(stream.raw);
  return el;
}

function addToolLine(name, preview, failed) {
  const text = (name || "outil") + (preview ? " · " + preview : "");
  const el = node("div", text, "tool-line" + (failed ? " failed" : ""));
  $("log").append(el);
  lastToolLine = el;
  $("log").scrollTop = $("log").scrollHeight;
  return el;
}

function genericError() { return "Source indisponible ; aucune confirmation d’effet"; }

function controlCard(prompt) {
  const card = node("article", "", "control-card");
  card.dataset.prompt = prompt.prompt_id || "";
  card.dataset.kind = prompt.kind || "";
  card.append(node("small", prompt.kind === "approval" ? "Approbation requise" : "GONA demande une précision"));
  if(prompt.kind === "approval") {
    if(prompt.description) card.append(node("p", prompt.description, "control-question"));
    if(prompt.command) card.append(node("pre", prompt.command, "control-command"));
  } else {
    card.append(node("p", prompt.question || "Ta réponse", "control-question"));
  }
  const row = node("div", "", "control-actions");
  const send = (value) => respondControl(card, prompt, value);
  if(prompt.kind === "approval") {
    const labels = { once: "Autoriser une fois", session: "Autoriser la session", always: "Toujours autoriser", deny: "Refuser" };
    for(const choice of prompt.choices || ["once", "deny"]) {
      const b = node("button", labels[choice] || choice, "btn" + (choice === "deny" ? " danger" : choice === "once" ? " primary" : ""));
      b.onclick = () => send(choice);
      row.append(b);
    }
  } else {
    for(const choice of prompt.choices || []) {
      const b = node("button", choice, "btn");
      b.onclick = () => send(choice);
      row.append(b);
    }
    const input = node("input", "", "control-answer");
    input.placeholder = "Autre réponse…";
    input.maxLength = 4000;
    const b = node("button", "Répondre", "btn primary");
    b.onclick = () => { if(input.value.trim()) send(input.value.trim()); };
    input.onkeydown = ev => { if(ev.key === "Enter") { ev.preventDefault(); b.click(); } };
    row.append(input, b);
  }
  card.append(row);
  $("log").append(card);
  $("log").scrollTop = $("log").scrollHeight;
  return card;
}

async function respondControl(card, prompt, value) {
  card.querySelectorAll("button,input").forEach(el => el.disabled = true);
  try {
    const body = { id: session, kind: prompt.kind, prompt_id: prompt.prompt_id, generation: prompt.generation };
    if(prompt.kind === "approval") body.choice = value; else body.answer = value;
    await api("/api/control/respond", body);
    card.classList.add("resolved");
    card.append(node("p", "Réponse transmise.", "hint"));
  } catch(e) {
    card.querySelectorAll("button,input").forEach(el => el.disabled = false);
    card.append(node("p", e.message || genericError(), "error"));
  }
}

function findControl(promptId) {
  for(const card of document.querySelectorAll(".control-card")) {
    if(card.dataset.prompt === promptId) return card;
  }
  return null;
}

function settleControls(kind, promptId) {
  for(const card of document.querySelectorAll(".control-card")) {
    if(card.dataset.kind !== kind) continue;
    if(promptId && card.dataset.prompt !== promptId) continue;
    card.classList.add("resolved");
    card.querySelectorAll("button,input").forEach(el => el.disabled = true);
  }
}

function handleStream(data) {
  lastStreamSign = Date.now();
  if(!stream) return;
  if(data.type === "snapshot") {
    for(const p of data.prompts || []) if(!findControl(p.prompt_id)) controlCard(p);
    if(data.running) setBusy(true, "GONA travaille…");
    else if(!(data.prompts || []).length) setBusy(false, "");
    return;
  }
  if(data.type === "writing") {
    stream.active = true; setBusy(true, "GONA écrit…"); streamBubble(); return;
  }
  if(data.type === "delta") {
    stream.active = true; setBusy(true, "GONA écrit…");
    streamBubble();
    stream.raw += data.text || "";
    paintStream();
    return;
  }
  if(data.type === "tool") {
    stream.active = true;
    const previous = finishStreamBubble();
    if(previous && !stream.raw) previous.remove();
    stream.bubble = null; stream.raw = "";
    addToolLine(data.name, data.preview, false);
    setBusy(true, data.name ? "GONA utilise " + data.name + "…" : "GONA travaille…");
    return;
  }
  if(data.type === "tool_done") {
    if(lastToolLine) {
      lastToolLine.classList.add("done");
      if(data.is_error) lastToolLine.classList.add("failed");
    }
    return;
  }
  if(data.type === "complete") {
    stream.active = false;
    sessionStorage.removeItem(PENDING);
    setBusy(false, "");
    const text = data.text || stream.raw || "";
    if(stream.bubble && text) {
      finishStreamBubble();
      stream.bubble.innerHTML = fmt(text);
      if(data.status === "error") stream.bubble.classList.add("failed");
    } else if(stream.bubble) {
      stream.bubble.remove();
    } else if(text) addMessage("assistant", text, data.status);
    if(data.warning) addMessage("system", data.warning, "failed");
    // Haut-parleur : lire la réponse à une question tapée ici (la voix gère ses propres réponses).
    const typed = window.__mcTypedReply && Date.now() - window.__mcTypedReply < 30 * 60 * 1000;
    if(typed && text && data.status !== "error" && window.MCVoice && window.MCVoice.enabled() && !window.MCVoice.busy()) {
      window.__mcTypedReply = 0; window.MCVoice.speakText(text);
    } else if(typed) window.__mcTypedReply = 0;
    closeStream();
    setTimeout(() => loadConversation(true).catch(() => {}), 250);
    return;
  }
  if(data.type === "control") {
    setBusy(true, "Décision attendue…");
    controlCard(data.prompt);
    return;
  }
  if(data.type === "control_settled") {
    settleControls(data.kind, data.prompt_id);
    return;
  }
  if(data.type === "notice" && data.text) { addMessage("system", data.text); return; }
  if(data.type === "info" && data.info) { return; }
  if(data.type === "gap") {
    if(stream) stream.active = false;
    closeStream();
    addMessage("system", "Le flux a sauté : le fil vient d’être rechargé.");
    loadConversation(true).catch(() => {});
    scheduleStream(1500);
    return;
  }
  if(data.type === "fatal") {
    if(stream) stream.active = false;
    closeStream();
    setBusy(false, "Flux direct indisponible ; actualisation automatique.");
    loadConversation(true).catch(() => {});
    scheduleStream(15000);
  }
}

// Resynchronise l'id de session (après un /new fait ailleurs, ex. Telegram). Renvoie true si changé.
async function syncSession() {
  const ch = await api("/api/channels").catch(() => null);
  const s = ch && ((ch.channels || []).find(c => !c.thread) || (ch.channels || [])[0] || {}).session;
  if(!s || s === session) return false;
  session = s; sessionStorage.removeItem(PENDING);
  closeStream();
  await loadConversation(true).catch(() => {}); startStream();
  return true;
}
async function start() {
  const res = await fetch("/api/me");
  if (res.status !== 200) { show("login"); return; }
  const me = await res.json();
  const sw = $("switch-atlas");
  if (sw) {  // même hôte, port voisin : 8710 → 8700 (ou 18710 → 18700 sur l'iMac). Le cookie signé d'Atlas ouvre aussi GONA.
    sw.href = location.protocol + "//" + location.hostname + ":" + (parseInt(location.port || "80", 10) - 10) + "/";
    sw.hidden = false;
  }
  $("who-name").textContent = me.name; window.MC_BACKEND = me.backend || "telegram";
  if (me.atlas) {
    // Même hôte, port voisin : 8710 → 8700. La session de 90 jours émise par Atlas reste valable des deux côtés.
    const sw = $("switch-atlas");
    sw.href = location.protocol + "//" + location.hostname + ":" + (parseInt(location.port || "80", 10) - 10) + "/";
    sw.hidden = false;
  }
  show("app");
  const channels = await api("/api/channels");
  session=(channels.channels.find(c=>!c.thread) || channels.channels[0] || {}).session;
  await loadConversation(); await pollReply();
  loadKanban();
  loadCommands().catch(() => {});
  startStream();
  $("text").focus();
}

async function loadCommands() {
  const data = await api("/api/commands");
  commands = data.commands || [];
}

$("login-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  $("login-error").textContent = "";
  const res = await fetch("/api/login", { method: "POST", headers: HEADERS,
    body: JSON.stringify({ login: $("login").value, password: $("password").value }) });
  if (res.status === 200) { $("password").value = ""; start(); return; }
  const data = await res.json().catch(() => ({}));
  $("login-error").textContent = data.error || "Connexion impossible.";
});

$("logout").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST", headers: HEADERS, body: "{}" });
  closeStream();
  $("log").replaceChildren();
  show("login");
});

$("chat-form").addEventListener("submit",async ev=>{
  ev.preventDefault(); const text=$("text").value.trim();
  if(!text || !session) return;
  if(text.startsWith("/")) { await runCommand(text); return; }
  if(busy) return;
  const p={id:session,text,submission_id:"imac-mc-"+crypto.randomUUID(),t:Date.now()};
  sessionStorage.setItem(PENDING,JSON.stringify(p)); setBusy(true,"Envoi…");
  window.__mcTypedReply = Date.now();
  const echo = addMessage("user", text);
  try { let r; try { r = await api("/api/chat",p); } catch(e) {
          if(!/Session (Telegram )?active/.test(e.message) || !(await syncSession())) throw e;
          p.id=session; sessionStorage.setItem(PENDING,JSON.stringify(p)); r = await api("/api/chat",p); }
        // Rotation automatique (session-lifecycle) : le serveur a ouvert une session neuve avant l'envoi.
        // On la suit sans vider le fil : l'utilisateur ne voit pas de différence.
        if(r && r.session && r.session !== session) {
          session = r.session; p.id = session; sessionStorage.setItem(PENDING,JSON.stringify(p));
          closeStream(); startStream();
        }
        $("text").value=""; if(!stream || !stream.es) startStream(); await pollReply(); }
  catch(e) { echo.remove(); setBusy(true,e.message+" · Envoi non confirmé : ne pas renvoyer automatiquement. Consulte le fil."); }
});
// Commandes « / » : réponse affichée comme note de service, jamais envoyée à l'agent.
function modelPicker(box, out) {
  const list = node("div", "", "picker-list");
  const providers = (out.providers || []).filter(p => p && p.slug && Array.isArray(p.models));
  if(!providers.length) {
    box.append(node("p", (out.shortcuts || []).length ? "Changer : " + out.shortcuts.map(x => "/model " + x.alias).join(" · ") : "Aucun fournisseur authentifié.", "hint"));
    return;
  }
  function showProviders() {
    list.replaceChildren();
    for(const a of out.shortcuts || []) {
      const qb = node("button", a.alias + (a.model === out.model ? " · actuel" : ""), "btn" + (a.model === out.model ? " primary" : ""));
      qb.title = a.model + " (" + a.provider + ")";
      qb.onclick = () => switchModel(a.model, a.provider, box, qb);
      list.append(qb);
    }
    list.append(node("p", "Tous les fournisseurs :", "hint"));
    for(const p of providers) {
      const b = node("button", (p.name || p.slug) + " · " + p.models.length, "btn");
      b.onclick = () => {
        list.replaceChildren(node("p", p.name || p.slug, "hint"));
        const back = node("button", "← Fournisseurs", "btn ghost");
        back.onclick = showProviders;
        list.append(back);
        for(const m of p.models.slice(0, 40)) {
          const mb = node("button", typeof m === "string" ? m : (m.label || m.id || m.model || String(m)), "btn");
          mb.onclick = () => switchModel(typeof m === "string" ? m : (m.id || m.model || m), p.slug, box, mb);
          list.append(mb);
        }
      };
      list.append(b);
    }
  }
  showProviders();
  box.append(list);
}

async function switchModel(model, provider, box, btn) {
  box.querySelectorAll(".picker-list button").forEach(x => x.disabled = true);
  if(btn) btn.classList.add("primary");
  const note = node("p", "Changement vers " + model + "…", "hint"); box.append(note);
  box.scrollIntoView({block: "end", behavior: "smooth"});
  const done = (txt, err) => { note.textContent = txt; note.className = err ? "error" : "hint ok";
    box.querySelectorAll(".picker-list button").forEach(x => x.disabled = false); box.scrollIntoView({block: "end"}); };
  try {
    const r = await api("/api/command", { id: session, command: "/model " + model + (provider ? " --provider " + provider : "") });
    if(r.ok === false) { done("⚠ " + (r.error || "Modèle refusé"), true); return; }
    if(r.kind === "confirm") {
      done(r.text || "Confirmation requise.");
      const b = node("button", "Confirmer " + model, "btn primary");
      b.onclick = () => { b.disabled = true; runCommand(r.confirm_command); };
      box.append(b);
      return;
    }
    done("✔ " + (r.text || "Modèle changé."));
  } catch(e) { done("⚠ " + (e.message || genericError()), true); }
}

function reasoningPicker(box, out) {
  const list = node("div", "", "picker-list");
  for(const level of out.levels || ["low", "medium", "high", "xhigh", "reset"]) {
    const b = node("button", level + (level === out.current ? " · actuel" : ""), "btn" + (level === out.current ? " primary" : ""));
    b.onclick = () => runCommand("/reasoning " + level);
    list.append(b);
  }
  box.append(list);
}

async function runCommand(text) {
  setBusy(true, "Commande " + text.split(" ")[0] + "…");
  let out;
  try { out = await api("/api/command", { id: session, command: text }); }
  catch(e) { out = { ok: false, error: e.message }; }
  const running = !!(stream && stream.active);
  setBusy(running, running ? "GONA travaille…" : "");
  if(out.kind === "new" && out.ok) {
    // Suivre la nouvelle session : le gateway l'a déjà rebranchée sur Telegram.
    for(let i = 0; i < 10; i++) {
      const ch = await api("/api/channels").catch(() => ({ channels: [] }));
      const s = ((ch.channels || []).find(c => !c.thread) || (ch.channels || [])[0] || {}).session;
      if(s && s !== session) { session = s; break; }
      await new Promise(r => setTimeout(r, 1500));
    }
    closeStream();
    $("log").replaceChildren(); sessionStorage.removeItem(PENDING);
    await loadConversation(true).catch(() => {});
    startStream();
    $("text").value = "";
    return;
  }
  const b = node("div", "", "msg system cmd");
  cmdBubbles.push(b); if(cmdBubbles.length > 6) cmdBubbles.shift();
  setTimeout(saveBubbles, 1500);
  b.append(node("small", text));
  if(out.ok === false) b.append(node("pre", "⚠ " + (out.error || "Commande refusée")));
  else if(out.kind === "help") {
    b.append(node("pre", out.text || "Commandes disponibles :"));
    for(const [c, d] of out.items || []) b.append(node("p", c + " — " + d, "hint"));
    b.append(node("p", "/stop — interrompre le tour en cours", "hint"));
  } else if(out.kind === "status") {
    b.append(node("p", (out.agent || "GONA") + " · " + (out.model_label || out.model) + " (" + (out.provider || "?") + ")" +
      (out.reasoning ? " · réflexion " + out.reasoning : "") + (out.running ? " · en train de travailler" : "")));
  } else if(out.kind === "models") {
    b.append(node("p", (out.agent || "GONA") + " · " + (out.model_label || out.model) + " (" + (out.provider || "?") + ") · réflexion " + (out.reasoning || "—")));
    modelPicker(b, out);
  } else if(out.kind === "reasoning") {
    b.append(node("p", "Niveau de réflexion actuel : " + (out.current || "profil"), "hint"));
    reasoningPicker(b, out);
  } else if(out.kind === "confirm") {
    b.append(node("pre", out.text || "Confirmation requise."));
    const btn = node("button", "Confirmer", "btn primary");
    btn.onclick = () => { btn.disabled = true; runCommand(out.confirm_command); };
    b.append(btn);
  } else {
    b.append(node("pre", out.text || JSON.stringify(out)));
  }
  $("log").append(b);
  $("log").scrollTop = $("log").scrollHeight;
  $("text").value = "";
  hideCommandMenu();
}

function updateCommandMenu() {
  const ta = $("text"), menu = $("command-menu");
  const value = ta.value;
  if(!value.startsWith("/") || /\s/.test(value)) { hideCommandMenu(); return; }
  menuItems = commands.filter(c => c.command.startsWith(value.toLowerCase())).slice(0, 8);
  if(!menuItems.length) { hideCommandMenu(); return; }
  menuIndex = Math.min(menuIndex, menuItems.length - 1);
  menu.replaceChildren();
  menuItems.forEach((c, i) => {
    const b = node("button", "", "command-item" + (i === menuIndex ? " on" : ""));
    b.type = "button"; b.setAttribute("role", "option");
    b.append(node("strong", c.command));
    b.append(node("small", c.description || ""));
    b.onmousedown = ev => { ev.preventDefault(); selectCommand(c); };
    menu.append(b);
  });
  menu.hidden = false;
}

function hideCommandMenu() {
  const menu = $("command-menu");
  if(menu) menu.hidden = true;
  menuItems = [];
  menuIndex = 0;
}

function selectCommand(command) {
  const ta = $("text");
  hideCommandMenu();
  if(["/model", "/reasoning"].includes(command.command)) {
    ta.value = command.command + " ";
    ta.focus();
    return;
  }
  ta.value = command.command;
  $("chat-form").requestSubmit();
}

$("stop").addEventListener("click", () => runCommand("/stop"));
$("text").addEventListener("input", updateCommandMenu);
$("text").addEventListener("input", () => { if(!busy) $("send").disabled = !$("text").value.trim(); });
$("text").addEventListener("keydown", (ev) => {
  const menu = $("command-menu");
  if(!menu.hidden) {
    if(ev.key === "ArrowDown" || ev.key === "ArrowUp") {
      ev.preventDefault();
      const step = ev.key === "ArrowDown" ? 1 : -1;
      menuIndex = (menuIndex + step + menuItems.length) % menuItems.length;
      updateCommandMenu();
      return;
    }
    if(ev.key === "Tab" || (ev.key === "Enter" && !ev.shiftKey)) {
      ev.preventDefault();
      if(menuItems[menuIndex]) selectCommand(menuItems[menuIndex]);
      return;
    }
    if(ev.key === "Escape") { ev.preventDefault(); hideCommandMenu(); return; }
  }
  if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); $("chat-form").requestSubmit(); }
});



async function loadDrafts() {
  const box=$("drafts-list");
  try {
    const data=await api("/api/decisions"); box.replaceChildren();
    box.append(node("pre",data.text,"decision-text"));
    for(const m of data.text.matchAll(/^(\d+)\. /gm)) {
      const row=node("article","Question "+m[1],"card");
      for(const [action,label] of [["accept","Accepter"],["refuse","Refuser"],["defer","Plus tard"],["seen","Vu"]]) {
        const b=node("button",label,"btn"); b.onclick=async()=>{
          if(!confirm(label+" la question "+m[1]+" ?")) return;
          b.disabled=true;
          try { await api("/api/decisions/decide",{target:m[1],action}); await loadDrafts(); }
          catch(e) { row.append(node("p",e.message,"error")); b.disabled=false; }
        }; row.append(b);
      } box.append(row);
    }
  } catch(e) { box.textContent=e.message; }
}

for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.toggle("on", t === tab));
    const view = tab.dataset.view;
    $("app-view").dataset.view = view;
    $("view-chat").hidden = !["chat", "kanban"].includes(view);
    $("view-engagements").hidden = view !== "engagements";
    $("view-drafts").hidden = view !== "drafts";
    // Engagements masqués : aucune source GONA équivalente.
    if (view === "drafts") loadDrafts();
    if (view === "kanban") loadKanban();
  });
}

const COLUMNS = [["todo", "À faire", ["triage", "todo", "ready"]], ["running", "En cours", ["running", "review"]], ["blocked", "Bloqué (agent) / Planifié", ["blocked", "scheduled"]], ["done", "Terminé", ["done"]]];
let gateItems = [];
let selectedCard = null;
async function kanban(op, data) {
  const res = await fetch("/api/kanban/" + op, data ? {method:"POST", headers:HEADERS, body:JSON.stringify(data)} : {});
  const result = await res.json();
  if (!res.ok) throw new Error(result.error || "Kanban indisponible");
  return result;
}
function node(tag, text, cls) {
  const el = document.createElement(tag); el.textContent = text; if(cls) el.className = cls; return el;
}
// Les missions de kanban_map sont des fichiers ; les ombrelles sont des noms courts.
function missionFor(key,p,map) {
  if(map.umbrellas[p.mission]) return p.mission;
  if(key==="cours-cprp") return "cours";
  return ({prof:"formations",gonasys:"hermes",lab3d:"lab3d",etsy:"lab3d",nvtr:"nvtr",arpagona:"arpagona"})[p.tenant] || "";
}
function waiting(t) { return t.status==="blocked" && t.block_kind==="needs_input" || t.status==="needs_input"; }
// Sans responsable : champ natif assignee vide. Pas de badge pour une attente humaine, une carte terminée/archivée ou une ombrelle (sans responsable par choix).
function unowned(t) {
  const umbrellas=Object.values((snapshot&&snapshot.mapping&&snapshot.mapping.umbrellas)||{});
  return !String(t.assignee||"").trim() && !waiting(t) && t.block_kind!=="needs_input" && !["done","archived"].includes(t.status) && !umbrellas.includes(t.id);
}
function taskButton(t) {
  const b=node("button",t.title,"task"+(waiting(t)?" needs-input":"")+(unowned(t)?" unowned":""));
  if(unowned(t)) b.append(node("span","Sans responsable","badge-unowned"));
  b.append(node("small",(t.tenant || "Sans tenant")+" · "+(waiting(t)?"Attend ta décision":t.assignee || "Non affectée")));
  b.onclick=()=>openCard(t.id); return b;
}
function renderKanban() {
  if(!snapshot) return;
  const {tasks,mapping:map}=snapshot, tenant=$("tenant-filter").value;
  const entries=Object.entries(map.projects), known=new Set([...Object.values(map.umbrellas),...entries.map(([,p])=>p.card)]);
  const filtered=tasks.filter(t=>(!tenant || t.tenant===tenant) && t.status!=="archived");
  const group=$("mission-groups"); group.replaceChildren();
  renderGate();
  const filters=node("div","","mission-filters"), all=node("button","Toutes les missions","btn");
  all.onclick=()=>{missionFilter="";renderKanban();};filters.append(all);
  for(const [mission,id] of Object.entries(map.umbrellas)) {
    const ids=new Set([id,...entries.filter(([k,p])=>missionFor(k,p,map)===mission).map(([,p])=>p.card)]);
    const count=filtered.filter(t=>ids.has(t.id)).length;
    if(tenant && !count) continue;
    const umbrella=tasks.find(t=>t.id===id);
    const b=node("button",(umbrella?.title || mission)+" · "+count,"btn"+(missionFilter===mission?" primary":""));
    b.onclick=()=>{missionFilter=missionFilter===mission?"":mission;renderKanban();}; filters.append(b);
  } group.append(filters);
  const ids=missionFilter?new Set([map.umbrellas[missionFilter],...entries.filter(([k,p])=>missionFor(k,p,map)===missionFilter).map(([,p])=>p.card)]):null;
  const visible=filtered.filter(t=>(!ids || ids.has(t.id)) && ($("history-filter").checked || known.has(t.id)));
  $("board").replaceChildren();
  for(const [key,title,states] of COLUMNS) {
    let cards=visible.filter(t=>states.includes(t.status) && !waiting(t));
    if(key==="done") cards=cards.sort((a,b)=>(b.completed_at||0)-(a.completed_at||0));
    const col=node(key==="done"?"details":"section","","column"); col.dataset.status=key;
    const h=node(key==="done"?"summary":"h3",title);h.append(node("span",String(cards.length)));col.append(h);
    if(key==="done") cards=cards.slice(0,15);
    for(const t of cards) {
      const entry=entries.find(([,p])=>p.card===t.id);
      const mission=entry?missionFor(entry[0],entry[1],map):Object.keys(map.umbrellas).find(k=>map.umbrellas[k]===t.id);
      const b=taskButton(t);if(mission) b.prepend(node("small",mission+(entry?" · Projet":" · Ombrelle")));
      if(entry) b.title=entry[1].mission;col.append(b);
    } $("board").append(col);
  }
  $("kanban-status").textContent=tasks.length+" cartes au total · "+tasks.filter(t=>t.status==="archived").length+" archivées · "+visible.length+" affichées · actualisation 10 s";
}
// Portail de décision : ce qui attend Thibaud, en Oui / Non. Préciser = texte dans le chat.
function renderGate() {
  const g=$("gate"); if(!g) return; g.replaceChildren();
  const h=node("h3","Ta décision · "+gateItems.length); g.append(h);
  if(!gateItems.length) { g.append(node("p","Rien n’attend ta décision. ✔","hint")); return; }
  for(const it of gateItems) {
    const c=node("article","","gate-card"); c.dataset.id=it.id;
    c.append(node("small",(it.tenant||"")+" · "+it.title));
    c.append(node("p",it.question||"GONA attend une information de ta part.","gate-q"));
    if(it.context && !it.question) c.append(node("p",it.context,"hint"));
    const row=node("div","","gate-actions");
    if(it.question) {
      for(const [ans,label,cls,note] of [["oui","✔ Oui","gate-yes",it.oui],["non","✖ Non","gate-no",it.non]]) {
        const b=node("button",label,"btn "+cls); if(note) b.title=note;
        b.onclick=()=>gateDecide(it,ans,c); row.append(b);
      }
    }
    const p=node("button","💬 Préciser","btn gate-more");
    p.onclick=()=>{ const ta=$("text"); ta.value="["+it.title+"] "; ta.focus(); };
    row.append(p);
    if(it.kind==="card") { const o=node("button","Voir la carte","btn ghost"); o.onclick=()=>openCard(it.id); row.append(o); }
    c.append(row);
    if(it.question && (it.oui||it.non)) c.append(node("p","Oui → "+(it.oui||"—")+" · Non → "+(it.non||"—"),"hint gate-effects"));
    g.append(c);
  }
}
async function gateDecide(it,answer,el) {
  el.querySelectorAll("button").forEach(b=>b.disabled=true);
  try {
    const r=await fetch("/api/gate/decide",{method:"POST",headers:HEADERS,body:JSON.stringify({kind:it.kind,id:it.id,answer})});
    const d=await r.json(); if(!r.ok || d.error) throw new Error(d.error||"refusé");
    el.classList.add(answer==="oui"?"gate-done-yes":"gate-done-no");
    el.querySelector(".gate-actions").replaceChildren(node("strong",(answer==="oui"?"✔ Oui":"✖ Non")+" enregistré"));
    setTimeout(loadKanban,1500);
  } catch(e) { el.querySelectorAll("button").forEach(b=>b.disabled=false); el.append(node("p",e.message,"error")); }
}
async function loadKanban() {
  if($("app-view").hidden) return;
  try {
    try { const r=await fetch("/api/gate"); if(r.ok) gateItems=(await r.json()).items||[]; } catch(e) {}
    snapshot=await kanban("list");const current=$("tenant-filter").value;
    const all=node("option","Tous");all.value="";$("tenant-filter").replaceChildren(all);
    for(const tenant of [...new Set(snapshot.tasks.map(t=>t.tenant).filter(Boolean))].sort()) {
      const o=node("option",tenant);o.value=tenant;$("tenant-filter").append(o);
    } $("tenant-filter").value=current;renderKanban();
  } catch(e) { $("kanban-status").textContent=e.message; }
}
$("tenant-filter").onchange=()=>{missionFilter="";renderKanban();};
$("history-filter").onchange=renderKanban;
async function openCard(id) {
  try {
    const result = await kanban("show?id=" + encodeURIComponent(id));
    const task = result.task || result;
    selectedCard = id;
    $("create-card").hidden = true; $("card-detail").hidden = false;
    $("card-title").textContent = task.title;
    $("detail-body").textContent = task.body || "Sans description.";
    $("detail-meta").textContent = (COLUMNS.find(c => c[2].includes(task.status)) || [null,task.status])[1] + " · " + (task.assignee || "Non affectée");
    $("comments").replaceChildren(...(result.comments || task.comments || []).map(c => node("p", (c.author || "Équipe") + " · " + (c.body || c.text || c.content || ""))));
    $("card-actions").replaceChildren();
    // Cartes existantes strictement en lecture seule.
    $("card-error").textContent = "";
    if(!$("card-dialog").open) $("card-dialog").showModal();
  } catch(err) { $("kanban-status").textContent = err.message; }
}
$("new-card").addEventListener("click", () => {
  selectedCard = null; $("card-title").textContent = "Nouvelle carte";
  $("create-card").hidden = false; $("card-detail").hidden = true;
  $("create-card").reset(); $("card-error").textContent = ""; $("card-dialog").showModal();
});
$("close-card").addEventListener("click", () => $("card-dialog").close());
$("create-card").addEventListener("submit", async ev => {
  ev.preventDefault(); const btn = ev.submitter; btn.disabled = true;
  try { await kanban("create", {title:$("card-name").value,body:$("card-body").value}); $("card-dialog").close(); await loadKanban(); }
  catch(err) { $("card-error").textContent = err.message; }
  finally { btn.disabled = false; }
});
// Chien de garde : si « occupé » dure sans aucun signe du flux et que le serveur dit qu'aucun tour n'est en cours, on libère le bouton.
setInterval(async()=>{
  if($("app-view").hidden || !busy) { lastBusyOn = 0; return; }
  if(!lastBusyOn) lastBusyOn = Date.now();
  if(Date.now() - Math.max(lastBusyOn, lastStreamSign) < 45000) return;
  try {
    const r = await api("/api/channel/idle?id=" + encodeURIComponent(session));
    if(r && r.idle) { sessionStorage.removeItem(PENDING); if(stream) stream.active = false; setBusy(false, ""); lastBusyOn = 0; await loadConversation(true).catch(()=>{}); }
  } catch(e) {}
}, 10000);
setInterval(async()=>{
  if($("app-view").hidden) return;
  try { if(!busy && !sessionStorage.getItem(PENDING) && await syncSession()) return;
        if(sessionStorage.getItem(PENDING)) await pollReply(); else if(!busy && !(stream && stream.active)) await loadConversation(); }
  catch(e) { $("chat-status").textContent = navigator.onLine ? e.message : "Hors ligne · reconnexion automatique…"; }
},4000);
setInterval(loadKanban,10000);
$("send").disabled = true;
start();
