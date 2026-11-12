"use strict";
const $ = (id) => document.getElementById(id);
const HEADERS = { "Content-Type": "application/json", "X-Arpagona": "1" };
let busy = false;

function show(view) {
  $("login-view").hidden = view !== "login";
  $("app-view").hidden = view !== "app";
  $("who").hidden = view !== "app";
}

function addMessage(role, text, status) {
  const el = document.createElement("div");
  el.className = "msg " + role + (status === "failed" ? " failed" : "");
  el.textContent = text;
  $("log").appendChild(el);
  $("log").scrollTop = $("log").scrollHeight;
  return el;
}

async function loadConversation() {
  const res = await fetch("/api/conversation");
  if (res.status === 401) { show("login"); return; }
  const data = await res.json();
  $("log").replaceChildren();
  let pending = false;
  for (const m of data.messages) {
    if (m.status === "pending") { pending = true; addMessage(m.role, "…", m.status); }
    else addMessage(m.role, m.text, m.status);
  }
  setBusy(pending, pending ? "Une réponse est en cours de préparation." : "");
  if (pending) setTimeout(loadConversation, 3000);
}

function setBusy(on, label) {
  busy = on;
  $("send").disabled = on;
  $("chat-status").textContent = label || "";
}

async function start() {
  const res = await fetch("/api/me");
  if (res.status !== 200) { show("login"); return; }
  const me = await res.json();
  $("who-name").textContent = me.name;
  show("app");
  await loadConversation();
  $("text").focus();
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
  $("log").replaceChildren();
  show("login");
});

$("chat-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const text = $("text").value.trim();
  if (!text || busy) return;
  setBusy(true, "Envoi…");
  let res;
  try {
    res = await fetch("/api/chat", { method: "POST", headers: HEADERS, body: JSON.stringify({ text }) });
  } catch (err) {
    setBusy(false, "Connexion perdue. Message non envoyé.");
    return;
  }
  if (res.status === 401) { show("login"); setBusy(false); return; }
  if (res.status !== 200) {
    const data = await res.json().catch(() => ({}));
    setBusy(false, data.error || "Envoi impossible.");
    if (res.status === 502) loadConversation();
    return;
  }
  $("text").value = "";
  addMessage("user", text);
  const bubble = addMessage("assistant", "");
  const body = document.createElement("span");
  bubble.appendChild(body);
  setBusy(true, "Votre collègue répond…");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "", ended = false;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let cut;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const line = buffer.slice(0, cut); buffer = buffer.slice(cut + 2);
        if (!line.startsWith("data: ")) continue;
        const ev = JSON.parse(line.slice(6));
        if (ev.type === "delta") { body.textContent += ev.text; }
        else if (ev.type === "tool" && ev.state === "started") { $("chat-status").textContent = "Outil en cours : " + ev.name; }
        else if (ev.type === "tool") { $("chat-status").textContent = "Votre collègue répond…"; }
        else if (ev.type === "end") {
          ended = true;
          body.textContent = ev.text || body.textContent;
          if (ev.status === "failed") bubble.classList.add("failed");
        }
        $("log").scrollTop = $("log").scrollHeight;
      }
    }
  } catch (err) { /* flux coupé : l'état réel est relu ci-dessous */ }
  if (ended) setBusy(false); else loadConversation();
});

$("text").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); $("chat-form").requestSubmit(); }
});

$("menu-btn").addEventListener("click", () => {
  const open = $("nav").classList.toggle("open");
  $("menu-btn").setAttribute("aria-expanded", String(open));
});

async function loadEngagements() {
  const res = await fetch("/api/engagements");
  if (res.status !== 200) return;
  const data = await res.json();
  const box = $("engagements-list");
  box.replaceChildren();
  if (!data.engagements.length) { box.textContent = "Aucun engagement enregistré."; return; }
  const nf = new Intl.DateTimeFormat("fr-FR", { dateStyle: "full", timeStyle: "short" });
  for (const e of data.engagements) {
    const card = document.createElement("article");
    card.className = "card";
    const h = document.createElement("h3");
    h.textContent = e.client + " — " + e.sujet;
    const meta = document.createElement("p");
    meta.className = "meta";
    meta.textContent = nf.format(new Date(e.echeance * 1000)) + " · " + e.statut + " · certitude : " + e.certitude;
    const p = document.createElement("p");
    p.textContent = e.decision;
    card.append(h, meta, p);
    box.append(card);
  }
}

async function loadDrafts() {
  const res = await fetch("/api/drafts");
  if (res.status !== 200) return;
  const data = await res.json();
  const box = $("drafts-list");
  box.replaceChildren();
  if (!data.drafts.length) { box.textContent = "Aucun brouillon en attente."; return; }
  for (const d of data.drafts) {
    const card = document.createElement("article");
    card.className = "card";
    const h = document.createElement("h3");
    h.textContent = "Pour : " + d.cible;
    const meta = document.createElement("p");
    meta.className = "meta";
    const tag = document.createElement("span");
    tag.className = "tag" + (d.statut === "en_attente" ? " wait" : (d.statut === "refuse" ? " bad" : ""));
    tag.textContent = d.statut;
    meta.append(tag);
    if (d.livraison) meta.append(" " + d.livraison);
    const body = document.createElement("pre");
    body.textContent = d.corps;
    card.append(h, meta, body);
    if (d.statut === "en_attente") {
      const actions = document.createElement("div");
      actions.className = "actions";
      const ok = document.createElement("button");
      ok.className = "btn"; ok.textContent = "Approuver";
      const no = document.createElement("button");
      no.className = "btn ghost"; no.textContent = "Refuser";
      const decide = async (approve) => {
        ok.disabled = no.disabled = true;
        const r = await fetch("/api/drafts/decide", { method: "POST", headers: HEADERS,
          body: JSON.stringify({ id: d.id, approve, empreinte: d.empreinte }) });
        if (r.status !== 200) {
          const err = await r.json().catch(() => ({}));
          $("chat-status").textContent = err.error || "Décision impossible.";
        }
        loadDrafts();
      };
      ok.addEventListener("click", () => decide(true));
      no.addEventListener("click", () => decide(false));
      actions.append(ok, no);
      card.append(actions);
    }
    box.append(card);
  }
}

for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t === tab));
    const view = tab.dataset.view;
    $("view-chat").hidden = view !== "chat";
    $("view-soon").hidden = view !== "soon";
    $("view-engagements").hidden = view !== "engagements";
    $("view-drafts").hidden = view !== "drafts";
    $("view-credits").hidden = view !== "credits";
    if (view === "soon") $("soon-title").textContent = tab.dataset.title;
    if (view === "engagements") loadEngagements();
    if (view === "drafts") loadDrafts();
    $("nav").classList.remove("open");
    $("menu-btn").setAttribute("aria-expanded", "false");
  });
}

start();
