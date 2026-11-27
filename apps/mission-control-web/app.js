"use strict";
const $ = (id) => document.getElementById(id);
const HEADERS = { "Content-Type": "application/json", "X-Arpagona": "1" };
let busy = false;
const LIBELLES = { planifie: "Planifié", en_preparation: "Brouillon en préparation", pret: "Prêt",
  en_attente: "À valider", approuve: "Approuvé · prêt à envoyer", refuse: "Refusé", envoye: "Envoyé",
  echec: "Échec", annule: "Annulé" };
const MISSION = { en_cours: "En cours", terminee: "Terminée", echouee: "Échouée", arretee: "Arrêtée" };
const ARRET = { demande: "arrêt demandé", depassement_plafond: "plafond dépassé", arret_moteur: "arrêté par le moteur" };
const CERTITUDES = { certain: "certaine", probable: "probable", a_confirmer: "à confirmer" };
const libelle = (code) => LIBELLES[code] || code;

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
  let pending = false, previous = null;
  for (const m of data.messages) {
    if (previous !== null && previous !== m.conversation) {
      const separator = document.createElement("div");
      separator.className = "session-break";
      separator.textContent = "nouvelle session · contexte repris";
      $("log").appendChild(separator);
    }
    previous = m.conversation;
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
  meUser = await res.json();
  $("who-name").textContent = meUser.name;
  if (meUser.gona) {
    // Même hôte, port voisin : 8700 → 8710 (ou 18700 → 18710 sur l'iMac). La session de 90 jours est partagée.
    const sw = $("switch-gona");
    sw.href = location.protocol + "//" + location.hostname + ":" + (parseInt(location.port || "80", 10) + 10) + "/";
    sw.hidden = false;
  }
  show("app");
  await loadConversation();
  loadKanban();
  refreshBadge();
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
  setBusy(true, "L’agent prépare…");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
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
        else if (ev.type === "tool" && ev.state === "started") { $("chat-status").textContent = "L’agent prépare…"; }
        else if (ev.type === "tool") { $("chat-status").textContent = "L’agent prépare…"; }
        else if (ev.type === "end") {
          body.textContent = ev.text || body.textContent;
          if (ev.status === "failed") bubble.classList.add("failed");
        }
        $("log").scrollTop = $("log").scrollHeight;
      }
    }
  } catch (err) { /* flux coupé : l'état réel est relu ci-dessous */ }
  await loadConversation();
});

$("text").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); $("chat-form").requestSubmit(); }
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
    meta.textContent = nf.format(new Date(e.echeance * 1000)) + " · " + libelle(e.statut) + " · certitude " + (CERTITUDES[e.certitude] || e.certitude);
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
  updateBadge(data.drafts);
  if (!data.drafts.length) { box.textContent = "Aucun brouillon pour l’instant. À l’échéance d’un engagement, l’agent en prépare un ici."; return; }
  const df = new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" });
  for (const d of data.drafts) {
    const card = document.createElement("article");
    card.className = "card";
    const h = document.createElement("h3");
    h.textContent = "Pour : " + d.cible;
    const meta = document.createElement("p");
    meta.className = "meta";
    const tag = document.createElement("span");
    tag.className = "tag" + (d.statut === "en_attente" ? " wait" : (d.statut === "refuse" ? " bad" : ""));
    tag.textContent = libelle(d.statut);
    meta.append(tag, " préparé le " + df.format(new Date(d.cree * 1000)));
    if (d.livraison) meta.append(" · " + d.livraison);
    const body = document.createElement("pre");
    body.textContent = d.corps;
    const envelope = document.createElement('p');
    envelope.className = 'meta';
    envelope.textContent = 'De : ' + (d.expediteur || 'non validé') + ' · Objet : ' + (d.sujet || 'non validé');
    card.append(h, envelope, meta, body);
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
    } else if (d.statut === "approuve") {
      const actions = document.createElement("div");
      actions.className = "actions";
      const copy = document.createElement("button");
      copy.className = "btn ghost"; copy.textContent = "Copier le texte";
      copy.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(d.corps); copy.textContent = "Copié ✓"; }
        catch (err) { const r = document.createRange(); r.selectNodeContents(body);
          const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); copy.textContent = "Texte sélectionné : Ctrl+C"; }
      });
      actions.append(copy);
      if (meUser && meUser.mail && !d.message_id && d.sujet && d.expediteur) {
        const mail = document.createElement("button");
        mail.className = "btn"; mail.textContent = "Envoyer par courriel";
        mail.addEventListener("click", async () => {
          if (!confirm('De : ' + d.expediteur + '\nÀ : ' + d.cible + '\nObjet : ' + d.sujet +
            '\n\nEnvoyer le message affiché ? L’envoi est définitif.')) return;
          mail.disabled = true;
          const r = await fetch("/api/drafts/send", { method: "POST", headers: HEADERS,
            body: JSON.stringify({ id: d.id, empreinte: d.empreinte }) }).catch(() => null);
          if (!r || r.status !== 200) {
            const err = r ? await r.json().catch(() => ({})) : {};
            $("chat-status").textContent = err.error || "Envoi impossible.";
          }
          loadDrafts();
        });
        actions.append(mail);
      } else {
        actions.append(node('span', d.message_id ? 'Tentative enregistrée : vérifier la livraison, aucun nouvel envoi.' :
          (!d.sujet || !d.expediteur ? 'Ancien brouillon : recréez-le pour valider objet et expéditeur.' :
          'Envoi non configuré sur cette instance.'), 'hint'));
      }
      card.append(actions);
    }
    box.append(card);
  }
}

function updateBadge(drafts) {
  const n = drafts.filter(d => d.statut === "en_attente").length;
  const tab = document.querySelector('.tab[data-view="drafts"]');
  tab.textContent = "Approbations";
  if (n) { const b = document.createElement("span"); b.className = "badge"; b.textContent = String(n);
    b.setAttribute("aria-label", n + " à valider"); tab.append(b); }
}
async function refreshBadge() {
  if ($("app-view").hidden) return;
  const res = await fetch("/api/drafts").catch(() => null);
  if (!res || res.status !== 200) return;
  const data = await res.json();
  updateBadge(data.drafts);
  if (!$("view-drafts").hidden) loadDrafts();
}
setInterval(refreshBadge, 10000);

function duree(a, b) {
  if (!b) return "";
  const s = Math.max(0, Math.round(b - a));
  return s < 60 ? s + " s" : Math.round(s / 60) + " min";
}
async function loadMissions() {
  const res = await fetch("/api/missions");
  if (res.status !== 200) return;
  const data = await res.json();
  $("budget").textContent = "Dépensé sur 24 h : " + Number(data.depense_24h || 0).toFixed(3) +
    " $ · plafond jour " + data.plafond_jour + " $ · plafond mission " + data.plafond_mission + " $.";
  const box = $("missions-list");
  box.replaceChildren();
  if (!data.missions.length) {
    box.textContent = "Aucune mission pour l'instant. Chaque demande envoyée dans Conversation devient une mission suivie ici.";
    return;
  }
  const df = new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" });
  for (const m of data.missions) {
    const card = document.createElement("article"); card.className = "card";
    const h = document.createElement("h3"); h.textContent = m.titre;
    const meta = document.createElement("p"); meta.className = "meta";
    const tag = document.createElement("span");
    tag.className = "tag" + (m.statut === "en_cours" ? " wait" : (m.statut === "echouee" ? " bad" : ""));
    tag.textContent = MISSION[m.statut] || m.statut;
    meta.append(tag, " " + df.format(new Date(m.debut * 1000)));
    const d = duree(m.debut, m.fin); if (d) meta.append(" · " + d);
    if (m.cout !== null && m.cout !== undefined) meta.append(" · " + Number(m.cout).toFixed(4) + " $");
    if (m.arret && ARRET[m.arret]) meta.append(" · " + ARRET[m.arret]);
    card.append(h, meta);
    if (m.resultat) { const pre = document.createElement("pre"); pre.textContent = m.resultat; card.append(pre); }
    if (m.statut === "en_cours") {
      const actions = document.createElement("div"); actions.className = "actions";
      const stop = document.createElement("button"); stop.className = "btn ghost"; stop.textContent = "Arrêter";
      stop.addEventListener("click", async () => {
        stop.disabled = true;
        const r = await fetch("/api/missions/stop", { method: "POST", headers: HEADERS,
          body: JSON.stringify({ id: m.id }) }).catch(() => null);
        if (!r || r.status !== 200) {
          const err = r ? await r.json().catch(() => ({})) : {};
          $("budget").textContent = err.error || "Arrêt impossible.";
        }
        loadMissions();
      });
      actions.append(stop); card.append(actions);
    }
    box.append(card);
  }
}
setInterval(() => { if (!$("view-missions").hidden) loadMissions(); }, 5000);

async function loadAudit() {
  const res = await fetch("/api/audit?limit=200");
  if (res.status !== 200) return;
  const data = await res.json();
  const box = $("audit-list");
  box.replaceChildren();
  if (!data.evenements.length) { box.textContent = "Journal vide."; return; }
  const df = new Intl.DateTimeFormat("fr-FR", { dateStyle: "short", timeStyle: "medium" });
  const list = document.createElement("div"); list.className = "cards";
  for (const e of [...data.evenements].reverse()) {
    const row = document.createElement("p"); row.className = "meta";
    row.textContent = df.format(new Date(e.quand * 1000)) + " · " + e.action.replaceAll("_", " ") +
      (e.detail ? " · " + e.detail : "");
    list.append(row);
  }
  box.append(list);
}

// Voix : dictée par le navigateur (Chrome peut traiter l'audio sur son service), lecture locale.
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SR) {
  const mic = $("mic"); mic.hidden = false;
  let rec = null;
  mic.addEventListener("click", () => {
    if (rec) { rec.stop(); return; }
    rec = new SR(); rec.lang = "fr-FR"; rec.interimResults = true; rec.continuous = false;
    const base = $("text").value;
    rec.onresult = (ev) => {
      let t = "";
      for (const r of ev.results) t += r[0].transcript;
      $("text").value = (base ? base + " " : "") + t;
    };
    rec.onend = () => { mic.setAttribute("aria-pressed", "false"); rec = null; };
    mic.setAttribute("aria-pressed", "true");
    try { rec.start(); } catch (err) { mic.hidden = true; }
  });
}
if ("speechSynthesis" in window) {
  const sp = $("speak"); sp.hidden = false;
  sp.addEventListener("click", () => {
    const msgs = document.querySelectorAll("#log .msg.assistant");
    const last = msgs[msgs.length - 1];
    if (!last) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(last.textContent);
    u.lang = "fr-FR";
    speechSynthesis.speak(u);
  });
}

for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.toggle("on", t === tab));
    const view = tab.dataset.view;
    $("app-view").dataset.view = view;
    $("view-chat").hidden = !["chat", "kanban"].includes(view);
    $("view-engagements").hidden = view !== "engagements";
    $("view-drafts").hidden = view !== "drafts";
    $("view-missions").hidden = view !== "missions";
    $("view-audit").hidden = view !== "audit";
    if (view === "engagements") loadEngagements();
    if (view === "drafts") loadDrafts();
    if (view === "kanban") loadKanban();
    if (view === "missions") loadMissions();
    if (view === "audit") loadAudit();
  });
}

const COLUMNS = [["todo", "À trier / À faire", ["triage", "todo"]], ["ready", "Prêt", ["ready"]], ["running", "En cours", ["running"]], ["blocked", "Bloqué / Planifié", ["blocked", "scheduled"]], ["review", "En revue", ["review"]], ["done", "Terminé", ["done"]]];
let selectedCard = null;
let kanbanScope = "all";
let meUser = null;
async function kanban(op, data) {
  const res = await fetch("/api/kanban/" + op, data ? {method:"POST", headers:HEADERS, body:JSON.stringify(data)} : {});
  const result = await res.json();
  if (!res.ok) throw new Error(result.error || "Kanban indisponible");
  return result;
}
function node(tag, text, cls) {
  const el = document.createElement(tag); el.textContent = text; if(cls) el.className = cls; return el;
}
async function loadKanban() {
  if ($("app-view").hidden) return;
  try {
    const result = await kanban("list" + (kanbanScope === "mine" ? "?scope=mine" : ""));
    const tasks = Array.isArray(result) ? result : (result.tasks || []);
    $("board").replaceChildren();
    for(const [key, title, states] of COLUMNS) {
      const cards = tasks.filter(t => states.includes(t.status));
      const col = node("section", "", "column"); col.dataset.status = key;
      const h = node("h3", title); h.append(node("span", String(cards.length))); col.append(h);
      for(const card of cards) {
        const b = node("button", card.title, "task");
        b.append(node("small", card.assignee || "Non affectée"));
        b.addEventListener("click", () => openCard(card.id)); col.append(b);
      }
      $("board").append(col);
    }
    const owners = [...new Set(tasks.map(t => t.assignee).filter(Boolean))];
    const select = $("card-assignee");
    if (select && !select.dataset.ready) { fillAssignees(select, owners); }
    $("kanban-status").textContent = "À jour · actualisation toutes les 10 s";
  } catch(err) { $("kanban-status").textContent = "Kanban indisponible"; }
}
function fillAssignees(select, owners) {
  select.dataset.ready = "1";
  for (const login of [...new Set([meUser && meUser.login, ...owners].filter(Boolean))]) {
    const o = node("option", login === (meUser && meUser.login) ? login + " (moi)" : login); o.value = login; select.append(o);
  }
}
for (const [id, scope] of [["scope-all", "all"], ["scope-mine", "mine"]]) {
  $(id).addEventListener("click", () => {
    kanbanScope = scope;
    $("scope-all").className = "btn " + (scope === "all" ? "on" : "ghost");
    $("scope-mine").className = "btn " + (scope === "mine" ? "on" : "ghost");
    loadKanban();
  });
}
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
    const canDecide = task.can_decide !== false;
    if (!canDecide) $("detail-meta").textContent += task.assignee ? " · décision réservée à " + task.assignee : " · sans responsable : affectez-la avant toute décision";
    if (!task.assignee) {
      const claim = node("button", "Me l'affecter", "btn");
      claim.addEventListener("click", async () => {
        claim.disabled = true;
        try { await kanban("assign", {id, assignee: meUser.login}); await openCard(id); await loadKanban(); }
        catch(err) { $("card-error").textContent = err.message; }
        finally { claim.disabled = false; }
      });
      $("card-actions").append(claim);
    }
    for(const [op, label] of canDecide ? [["complete","Terminer"],[task.status === "blocked" ? "unblock" : "block",task.status === "blocked" ? "Débloquer" : "Bloquer"],["archive","Archiver"]] : []) {
      const b = node("button", label, "btn ghost");
      b.addEventListener("click", async () => {
        b.disabled = true;
        try { await kanban(op, {id, ...(op === "block" ? {text:"Bloquée depuis Agent Core"} : {})});
          if(op === "archive") $("card-dialog").close(); else await openCard(id);
          await loadKanban();
        } catch(err) { $("card-error").textContent = err.message; }
        finally { b.disabled = false; }
      }); $("card-actions").append(b);
    }
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
  try { await kanban("create", {title:$("card-name").value,body:$("card-body").value,assignee:$("card-assignee").value || undefined}); $("card-dialog").close(); await loadKanban(); }
  catch(err) { $("card-error").textContent = err.message; }
  finally { btn.disabled = false; }
});
$("comment-form").addEventListener("submit", async ev => {
  ev.preventDefault(); const btn = ev.submitter; btn.disabled = true;
  try { await kanban("comment", {id:selectedCard,text:$("comment-text").value}); $("comment-text").value = ""; await openCard(selectedCard); }
  catch(err) { $("card-error").textContent = err.message; }
  finally { btn.disabled = false; }
});
setInterval(loadKanban,10000);
start();

// Application installable (Android) : le service worker n'existe qu'en contexte sécurisé (HTTPS ou origine autorisée).
if ("serviceWorker" in navigator && window.isSecureContext) {
  navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
}
