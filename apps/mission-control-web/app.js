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

for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t === tab));
    const view = tab.dataset.view;
    $("view-chat").hidden = view !== "chat";
    $("view-soon").hidden = view !== "soon";
    $("view-credits").hidden = view !== "credits";
    if (view === "soon") $("soon-title").textContent = tab.dataset.title;
    $("nav").classList.remove("open");
    $("menu-btn").setAttribute("aria-expanded", "false");
  });
}

start();
