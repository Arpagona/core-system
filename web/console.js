// Console Mission Control — toutes les données viennent de l'API locale (journaux Agent Core réels).
"use strict";

const TOKEN = document.querySelector('meta[name="console-token"]').content;
const $ = (sel) => document.querySelector(sel);
const STATE_LABEL = {
  queued: "En attente", running: "En cours", completed: "Terminée", failed: "En échec",
  uncertain: "À valider", cancelled: "Annulée", unreadable: "Illisible",
};
const VIEW_TITLE = {
  control: "Mission Control", sessions: "Sessions", missions: "Missions", garage: "Garage",
  dream: "Dream", guardian: "Guardian", validations: "Validations", ressources: "Ressources",
  configuration: "Configuration", opencode: "OpenCode",
};
const TOOL_VERB = { list_dir: "Lister", read_file: "Lire", write_file: "Écrire", finish: "Terminer" };

const app = {
  overview: null, selected: null, detail: null, detailKey: "", view: "control",
  input: null, filter: "all", busy: false, timers: {},
  showTests: localStorage.getItem("ac-show-tests") === "1",
};
const isTest = (m) => Boolean(m && m.origin);
const shown = (ms) => (app.showTests ? ms : ms.filter((m) => !isTest(m)));

// ---------- utilitaires ----------
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "px") { el.dataset.px = v; }
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) el.append(c.nodeType ? c : String(c));
  return el;
}
const sprite = (name, scale) => h("span", { px: name, "data-scale": scale || 2, class: "ico" });
const paint = (root) => window.Pixels.paintSprites(root);
const base = (p) => String(p || "").split("/").filter(Boolean).pop() || p;
const two = (n) => String(n).padStart(2, "0");
function hhmm(ms) { const d = new Date(ms); return `${two(d.getHours())}:${two(d.getMinutes())}`; }
function idDate(id) {
  const m = /^m-(\d{4})(\d\d)(\d\d)-(\d\d)(\d\d)(\d\d)/.exec(id || "");
  return m ? new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6])) : null;
}
function fmtDate(d) { return d ? `${two(d.getDate())}/${two(d.getMonth() + 1)} ${hhmm(d)}` : "—"; }
function shortId(id) {
  const m = /^m-\d{8}-\d{6}-([0-9a-f]{6})(?:-(.+))?$/.exec(id || "");
  if (!m) return id || "";
  return `#AC-${m[1].toUpperCase()}${m[2] ? "·" + m[2].slice(0, 3).toUpperCase() : ""}`;
}
const money = (usd) => (usd === undefined || usd === null ? "—" : `${Number(usd).toFixed(4).replace(".", ",")} $`);
const stateTag = (s) => h("span", { class: `state s-${s}` }, STATE_LABEL[s] || s);

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST", body: JSON.stringify(body),
    headers: { "Content-Type": "application/json", "X-Console-Token": TOKEN },
  };
  const r = await fetch(path, opts);
  let data = {};
  try { data = await r.json(); } catch { /* corps vide */ }
  if (!r.ok) throw new Error(data.error || data.message || `HTTP ${r.status}`);
  return data;
}

function toast(text, err) {
  const t = $("#toast");
  t.textContent = text;
  t.className = "toast px" + (err ? " err" : "");
  t.hidden = false;
  clearTimeout(app.timers.toast);
  app.timers.toast = setTimeout(() => { t.hidden = true; }, 6000);
}

function reasonText(reason) {
  if (!reason) return "";
  const t = reason.type;
  if (t === "limit_exceeded") return { cost: "plafond de coût atteint", iterations: "plafond d'itérations atteint", wall_time: "durée maximale atteinte", tokens: "plafond de jetons atteint", tool_calls: "plafond d'appels d'outils atteint" }[reason.limit] || `plafond atteint (${reason.limit})`;
  if (t === "model") {
    const e = reason.error || {};
    if (e.type === "auth") return "clé du fournisseur refusée";
    return `erreur du modèle (${e.type || "?"})${e.message ? " : " + e.message : ""}`;
  }
  if (t === "deliverable") return "livrable non conforme";
  return t + (reason.message ? ` : ${reason.message}` : "");
}

// ---------- vue d'ensemble ----------
async function refreshOverview() {
  try {
    app.overview = await api("/api/overview");
  } catch (e) {
    app.overview = null;
    renderTop(e.message);
    return;
  }
  const ms = app.overview.missions;
  if (!app.selected || !ms.some((m) => m.id === app.selected)) {
    const real = shown(ms);
    const pick = ms.find((m) => m.state === "running") || ms.find((m) => m.state === "uncertain") || real[0] || ms[0];
    app.selected = pick ? pick.id : null;
  }
  renderTop();
  renderCards();
  renderSelect();
  renderValidations();
  renderPage();
  refreshDetail();
}

function renderTop(error) {
  const o = app.overview;
  const ok = o && o.version.ok;
  $("#agent-pill").classList.toggle("off", !ok);
  $("#agent-state").textContent = ok ? "Agent Core : Actif" : "Agent Core : Indisponible";
  $("#agent-pill").title = error || (o ? `${o.version.version || ""} · ${o.version["modèle"] || ""}` : "");
  $("#online").classList.toggle("off", !ok);
  $("#online").lastChild.textContent = ok ? "En ligne" : "Hors ligne";
  const n = o ? o.validations.length : 0;
  for (const id of ["#bell-badge", "#nav-badge", "#val-badge"]) { $(id).textContent = n; $(id).hidden = !n; }
  $("#who").title = o ? `Opérateur · ${o.resources.hostname}` : "Opérateur";
}

function renderCards() {
  const o = app.overview;
  const ms = shown(o.missions);
  const active = ms.filter((m) => m.state === "running" || m.state === "queued").length;
  const dayAgo = Date.now() - 86400000;
  const today = ms.filter((m) => (idDate(m.id) || 0) >= dayAgo);
  const done = today.filter((m) => m.state === "completed").length;
  $("#c-missions").textContent = `${active} active${active > 1 ? "s" : ""}`;
  $("#c-missions-bar").style.width = today.length ? `${Math.round((100 * done) / today.length)}%` : "0%";
  $("#c-missions-bar").parentElement.title = `${done} terminée(s) sur ${today.length} mission(s) en 24 h`;
  const problems = today.filter((m) => m.state === "failed").length + o.validations.length;
  $("#c-garage").textContent = `${problems} problème${problems > 1 ? "s" : ""}`;
  $("#c-garage").title = `missions en échec sur 24 h + validations en attente${app.showTests ? "" : " (missions de recette exclues)"}`;
  $("#c-dream").textContent = o.dream.configured ? `Prochaine : ${o.dream.next}` : "Non configuré";
  $("#c-dream").className = o.dream.configured ? "purple" : "muted";
  const g = o.guardian;
  $("#c-guardian").textContent = g.status === "sain" ? "Système sain" : "À vérifier";
  $("#c-guardian").className = g.status === "sain" ? "green" : "orange";
  const r = o.resources;
  $("#c-res").textContent = `${r.cpu} % CPU · ${r.ram.percent} % RAM`;
  $("#c-res-bar").style.width = `${r.ram.percent}%`;
}

function renderSelect() {
  const sel = $("#session-select");
  const ms = app.overview.missions.filter((m) => !isTest(m) || app.showTests || m.id === app.selected);
  const key = ms.map((m) => m.id + m.state).join("|");
  if (sel.dataset.key !== key) {
    sel.replaceChildren(...ms.map((m) => h("option", { value: m.id }, `Session ${shortId(m.id)} · ${STATE_LABEL[m.state] || m.state}${isTest(m) ? " · recette" : ""}`)));
    sel.dataset.key = key;
  }
  if (app.selected) sel.value = app.selected;
}

function valCard(v) {
  const title = v.tool ? `Confirmer : ${TOOL_VERB[v.tool] || v.tool} ${base(v.path)}` : "Vérifier la mission";
  return h("button", { class: "val px", type: "button", onclick: () => select(v.mission, "control") },
    sprite("checkO", 3),
    h("span", {}, h("b", {}, title), h("small", {}, `Impact : mission ${shortId(v.mission)}`)),
    sprite("arrow", 2));
}

function renderValidations() {
  const list = $("#val-list");
  const vs = app.overview.validations;
  list.replaceChildren(...(vs.length ? vs.map(valCard)
    : [h("p", { class: "empty" }, sprite("ok", 2), "Aucune demande en attente.")]));
  paint(list);
}

// ---------- détail d'une mission ----------
async function refreshDetail() {
  if (!app.selected) { renderChat(null); return; }
  const id = app.selected;
  try {
    const d = await api(`/api/missions/${encodeURIComponent(id)}`);
    if (id !== app.selected) return;
    const key = `${id}:${d.events.length}:${d.report.state}`;
    app.detail = d;
    if (key !== app.detailKey) { app.detailKey = key; renderChat(d); renderSteps(d); }
  } catch (e) {
    if (id === app.selected) toast(e.message, true);
  }
  clearTimeout(app.timers.detail);
  const live = app.detail && ["running", "queued"].includes(app.detail.report.state);
  app.timers.detail = setTimeout(refreshDetail, live ? 2000 : 15000);
}

function callIndex(events) {
  const calls = {};
  for (const e of events) {
    const k = e.kind;
    if (k.type === "model_replied") for (const c of k.tool_calls || []) calls[c.id] = { ...c };
    if (k.type === "policy_decided" && calls[k.call_id]) calls[k.call_id].decision = k.decision;
    if (k.type === "tool_finished" && calls[k.call_id]) calls[k.call_id].outcome = k.outcome;
    if (k.type === "resolved" && calls[k.call_id]) calls[k.call_id].resolved = k;
  }
  return calls;
}

function planItem(c, i) {
  let icon = sprite("ring", 2);
  let extra = "";
  let cls = "what";
  if (c.decision && c.decision.decision === "deny") {
    icon = sprite("ko", 2); cls += " deny"; extra = ` — refusé (${c.decision.rule})`;
  } else if (c.outcome && c.outcome.status === "ok") icon = sprite("ok", 2);
  else if (c.outcome) { icon = sprite("ko", 2); cls += " deny"; extra = ` — ${c.outcome.message || "erreur"}`; }
  else if (c.resolved) icon = sprite(c.resolved.resolution === "done" ? "ok" : "ko", 2);
  const arg = c.arguments && typeof c.arguments === "object" ? base(c.arguments.path) : "";
  return h("li", {}, h("span", { class: "num" }, i + 1), icon,
    h("span", { class: cls, title: (c.arguments && c.arguments.path) || "" }, `${TOOL_VERB[c.name] || c.name} ${arg}${extra}`));
}

function agentMsg(time, meta, ...body) {
  return h("div", { class: "msg agent" }, h("div", { class: "avatar" }, sprite("robot", 3)),
    h("div", {}, h("div", { class: "msg-meta" }, h("b", {}, "Agent Core"), h("time", {}, time), h("small", {}, meta || "")),
      h("div", { class: "bubble px" }, ...body)));
}

function foldThoughts(ul) {
  const items = [...ul.children].filter((li) => !li.classList.contains("fold"));
  ul.querySelectorAll(".fold").forEach((x) => x.remove());
  items.forEach((li, i) => { li.hidden = ul.dataset.open !== "1" && items.length > 3 && i < items.length - 2; });
  if (items.length > 3) {
    const open = ul.dataset.open === "1";
    ul.prepend(h("li", { class: "fold" }, h("button", { class: "more", type: "button", onclick: () => { ul.dataset.open = open ? "0" : "1"; foldThoughts(ul); } },
      open ? "Masquer les étapes précédentes" : `${items.length - 2} étapes précédentes…`)));
  }
}

function foldPlan(ol) {
  const items = [...ol.children].filter((li) => !li.classList.contains("fold"));
  ol.querySelectorAll(".fold").forEach((x) => x.remove());
  items.forEach((li, i) => { li.hidden = ol.dataset.open !== "1" && items.length > 7 && i >= 5; });
  if (items.length > 7) {
    const open = ol.dataset.open === "1";
    ol.append(h("li", { class: "fold" }, h("button", { class: "more", type: "button", onclick: () => { ol.dataset.open = open ? "0" : "1"; foldPlan(ol); } },
      open ? "Réduire le plan" : `… et ${items.length - 5} autres actions`)));
  }
}

function clampText(text) {
  const p = h("p", { class: "summary" }, text);
  if (text.length < 420) return p;
  p.classList.add("clamp");
  const more = h("button", { class: "more", type: "button", onclick: () => { const c = p.classList.toggle("clamp"); more.textContent = c ? "Afficher tout" : "Réduire"; } }, "Afficher tout");
  return h("div", {}, p, more);
}

function renderChat(d) {
  const box = $("#messages");
  const nearBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  box.replaceChildren();
  if (!d) {
    box.append(h("p", { class: "empty" }, "Aucune mission enregistrée. Écris une consigne ci-dessous pour lancer la première."));
    return;
  }
  const calls = callIndex(d.events);
  const rep = d.report;
  let input = [];
  let group = null;
  for (const e of d.events) {
    const k = e.kind;
    const t = hhmm(e.at_ms);
    if (["mission_created", "model_failed", "deliverable_checked", "resolved", "mission_ended"].includes(k.type)
      || (k.type === "mission_started" && k.attempt > 1)) group = null;
    if (k.type === "mission_created") {
      input = k.spec.input_dirs || [];
      box.append(h("div", { class: "msg user" }, h("div", { class: "avatar" }, sprite("person", 3)),
        h("div", {}, h("div", { class: "msg-meta" }, h("b", {}, "Vous"), h("time", {}, t), h("small", {}, `dossier : ${input.map(base).join(", ")}`)),
          h("div", { class: "bubble px" }, h("p", {}, k.spec.goal)))));
    } else if (k.type === "mission_started" && k.attempt > 1) {
      box.append(agentMsg(t, `tentative ${k.attempt}`, h("p", { class: "muted" }, "Reprise de la mission après interruption.")));
    } else if (k.type === "model_replied") {
      if (!group) {
        group = { thoughts: h("ul", { class: "thoughts" }), plan: h("ol", { class: "plan" }), n: 0, first: k.iteration };
        group.msg = agentMsg(t, "", group.thoughts, h("p", { class: "muted plan-title" }, "Voici mon plan :"), group.plan);
        box.append(group.msg);
      }
      if (k.text) {
        const li = h("li", {}, k.text.length > 260 ? k.text.slice(0, 260) + "…" : k.text);
        li.title = k.text;
        group.thoughts.append(li);
        foldThoughts(group.thoughts);
      }
      for (const c of k.tool_calls || []) { group.plan.append(planItem(calls[c.id] || c, group.n)); group.n += 1; }
      group.msg.querySelector(".msg-meta small").textContent = k.iteration > group.first ? `étapes ${group.first} à ${k.iteration}` : `étape ${k.iteration}`;
      if (!group.n) group.msg.querySelector(".plan-title").hidden = true;
      else group.msg.querySelector(".plan-title").hidden = false;
      foldPlan(group.plan);
      continue;
    } else if (k.type === "model_failed") {
      const m = agentMsg(t, `étape ${k.iteration}`, h("p", {}, `Échec de l'appel au modèle : ${(k.error && (k.error.message || k.error.type)) || "erreur"}`));
      m.classList.add("err");
      box.append(m);
    } else if (k.type === "deliverable_checked") {
      const r = k.report || {};
      box.append(agentMsg(t, "vérification", h("p", {}, r.ok ? `Livrable vérifié : ${r.path} (${(r.bytes || 0).toLocaleString("fr-FR")} octets) ✓`
        : `Livrable non conforme : ${(r.problems || []).join(" ; ") || r.path}`)));
    } else if (k.type === "resolved") {
      box.append(agentMsg(t, "validation", h("p", {}, `Appel ${k.call_id} marqué ${k.resolution === "done" ? "effectué" : "non effectué"} par ${k.by}.`)));
    } else if (k.type === "mission_ended") {
      const m = agentMsg(t, STATE_LABEL[k.state] || k.state,
        k.summary ? clampText(k.summary) : h("p", {}, k.state === "cancelled" ? "Mission annulée." : `Mission arrêtée : ${reasonText(k.reason)}.`),
        h("p", { class: "facts" }, `${rep.iterations} étape(s) · ${rep.tool_calls} appel(s) d'outil · ${(rep.usage ? rep.usage.input_tokens + rep.usage.output_tokens : 0).toLocaleString("fr-FR")} jetons · coût estimé ${money(rep.estimated_cost_usd)} · ${Math.round(rep.elapsed_s || 0)} s`));
      if (k.state !== "completed") m.classList.add("err");
      box.append(m);
    }
  }
  if (["running", "queued"].includes(rep.state)) {
    const last = d.events[d.events.length - 1];
    box.append(agentMsg(hhmm(Date.now()), "en cours", h("p", { class: "typing" }, "Analyse en cours...")));
    box.lastChild.querySelector(".bubble").append(actionBar(d, last));
  } else {
    const agents = box.querySelectorAll(".msg.agent .bubble");
    if (agents.length) agents[agents.length - 1].append(actionBar(d));
  }
  paint(box);
  $("#raw").textContent = d.events.map((e) => `[${String(e.seq).padStart(3)}] ${hhmm(e.at_ms)} ${JSON.stringify(e.kind)}`).join("\n");
  if (nearBottom || box.dataset.mission !== d.mission) box.scrollTop = box.scrollHeight;
  box.dataset.mission = d.mission;
}

function actionBar(d, last) {
  const rep = d.report;
  const id = d.mission;
  const bar = h("div", { class: "actions" });
  const spec = (d.events.find((e) => e.kind.type === "mission_created") || {}).kind;
  const goal = spec ? spec.spec.goal : "";
  const inputs = spec ? spec.spec.input_dirs || [] : [];
  if (["running", "queued"].includes(rep.state)) {
    const stale = last && Date.now() - last.at_ms > 90000 && !app.overview.running_children;
    if (stale) bar.append(h("button", { class: "btn primary", type: "button", onclick: () => act(id, "resume", {}, "Reprendre cette mission interrompue ?") }, sprite("play", 2), "Reprendre la mission"));
    bar.append(h("button", { class: "btn warn", type: "button", onclick: () => act(id, "cancel", {}, "Annuler cette mission ?") }, sprite("cross", 2), "Annuler"));
  } else if (rep.state === "uncertain") {
    for (const call of rep.uncertain || []) {
      bar.append(h("button", { class: "btn good", type: "button", onclick: () => act(id, "resolve", { call, as: "done" }, `Confirmer que l'appel ${call} a bien été effectué, puis reprendre ?`) }, sprite("ok", 2), "Confirmer : effectué"),
        h("button", { class: "btn warn", type: "button", onclick: () => act(id, "resolve", { call, as: "not-done" }, `Confirmer que l'appel ${call} n'a PAS été effectué, puis reprendre ?`) }, sprite("ko", 2), "Confirmer : non effectué"));
    }
    bar.append(h("button", { class: "btn", type: "button", onclick: () => act(id, "cancel", {}, "Annuler cette mission ?") }, sprite("cross", 2), "Annuler"));
  } else {
    const allowed = inputs.length === 1 && (app.overview.inputs || []).includes(inputs[0]);
    bar.append(h("button", { class: "btn primary", type: "button", disabled: !allowed || !goal, title: allowed ? "" : "dossier non autorisé pour la console", onclick: () => launch(goal, inputs[0]) }, sprite("play", 2), "Relancer la mission"),
      h("button", { class: "btn", type: "button", onclick: () => { $("#goal").value = goal; if (allowed) app.input = inputs[0]; autosize(); $("#goal").focus(); } }, sprite("pencil", 2), "Ajuster la consigne"),
      h("button", { class: "btn", type: "button", disabled: true, title: "mission déjà terminée" }, sprite("cross", 2), "Annuler"));
  }
  return bar;
}

function renderSteps(d) {
  const ol = $("#steps");
  const ev = d.events.map((e) => ({ ...e.kind, at: e.at_ms }));
  const state = d.report.state;
  const tools = (names) => ev.filter((k) => k.type === "tool_started" && names.includes(k.tool));
  const lastAt = (arr) => (arr.length ? arr[arr.length - 1].at : null);
  const created = ev.find((k) => k.type === "mission_created");
  const explore = tools(["list_dir", "read_file"]);
  const write = tools(["write_file"]);
  const check = ev.filter((k) => k.type === "deliverable_checked");
  const end = ev.find((k) => k.type === "mission_ended");
  const reached = end ? 4 : check.length ? 3 : write.length ? 2 : explore.length || ev.some((k) => k.type === "model_called") ? 1 : 0;
  const finalLabel = { completed: "Mission terminée", failed: "Mission en échec", cancelled: "Mission annulée", uncertain: "Attente de validation" }[state] || "Clôture (à venir)";
  const steps = [
    ["Mission créée", created && created.at],
    ["Exploration du dossier", lastAt(explore)],
    ["Rédaction du livrable", lastAt(write)],
    ["Vérification du livrable", lastAt(check)],
    [finalLabel, end && end.at],
  ];
  const live = ["running", "queued"].includes(state);
  $("#act-title").textContent = live ? "Activité en cours" : state === "uncertain" ? "Activité · en attente" : "Dernière activité";
  ol.replaceChildren(...steps.map(([label, at], i) => {
    let cls = "done";
    let icon = sprite("ok", 2);
    let right = at ? h("time", {}, hhmm(at)) : h("small", {}, "—");
    if (live && i === reached) { cls = "active"; icon = sprite("playG", 2); right = h("small", {}, "..."); }
    else if (live && i > reached) { cls = "pending"; icon = sprite("ring", 2); right = h("small", {}, ""); }
    else if (!live && i > reached && i < 4) { cls = "pending"; icon = sprite("ring", 2); right = h("small", {}, "non atteinte"); }
    if (i === 4 && !live) {
      if (state === "uncertain") { cls = "active"; icon = sprite("checkO", 2); }
      else if (state !== "completed") { cls = "failed"; icon = sprite("ko", 2); }
    }
    return h("li", { class: cls }, icon, h("span", {}, label), right);
  }));
  paint(ol);
}

// ---------- actions ----------
async function act(id, action, body, question) {
  if (question && !window.confirm(question)) return;
  try {
    const r = await api(`/api/missions/${encodeURIComponent(id)}/${action}`, body);
    toast({ cancel: "Mission annulée.", resume: "Mission relancée.", resolve: "Décision enregistrée : la mission reprend." }[action] || r.message || "Action effectuée.");
  } catch (e) { toast(e.message, true); }
  app.detailKey = "";
  refreshOverview();
}

async function launch(goal, input) {
  goal = (goal || "").trim();
  if (goal.length < 3) { toast("La consigne est trop courte.", true); return; }
  const where = input || app.input || (app.overview && app.overview.inputs[0]);
  if (!where) { toast("Aucun dossier d'entrée n'est autorisé pour cette console.", true); return; }
  if (!window.confirm(`Lancer une mission sur « ${base(where)} » ?\nLe vrai modèle sera appelé (plafond par mission appliqué).`)) return;
  const send = $("#composer .send");
  send.disabled = true;
  try {
    const r = await api("/api/missions", { goal, input: where });
    $("#goal").value = ""; autosize();
    app.selected = r.mission; app.detailKey = "";
    toast(`Mission ${shortId(r.mission)} lancée.`);
    setView("control");
  } catch (e) { toast(e.message, true); }
  send.disabled = false;
  refreshOverview();
}

function autosize() { const t = $("#goal"); t.style.height = "auto"; t.style.height = `${Math.min(t.scrollHeight, 140)}px`; }

function renderInputPicker() {
  const pop = $("#input-pop");
  const inputs = (app.overview && app.overview.inputs) || [];
  if (!app.input && inputs.length) app.input = inputs[0];
  pop.replaceChildren(h("p", { class: "muted" }, "Dossier d'entrée autorisé :"),
    ...(inputs.length ? inputs.map((p) => h("button", { type: "button", "aria-pressed": String(p === app.input), onclick: () => { app.input = p; pop.hidden = true; noteInput(); } }, p))
      : [h("p", {}, "Aucun dossier autorisé (option --input-autorise).")]));
}
function noteInput() {
  $("#composer-note").textContent = app.input ? `Dossier : ${base(app.input)} · Entrée : lancer · Maj+Entrée : nouvelle ligne` : "";
}

// ---------- pages secondaires ----------
function select(id, view) { app.selected = id; app.detailKey = ""; setView(view || "control"); refreshDetail(); renderSelect(); }

function missionTable(ms) {
  return h("table", { class: "table" },
    h("thead", {}, h("tr", {}, h("th", {}, "Session"), h("th", {}, "Date"), h("th", {}, "État"), h("th", {}, "Consigne"))),
    h("tbody", {}, ms.map((m) => h("tr", { class: "clickable", onclick: () => select(m.id) },
      h("td", {}, shortId(m.id), isTest(m) ? h("span", { class: "tag-test" }, m.origin) : null), h("td", {}, fmtDate(idDate(m.id))), h("td", {}, stateTag(m.state)),
      h("td", {}, (m.goal || "").slice(0, 140) + ((m.goal || "").length > 140 ? "…" : ""))))));
}

function testToggle() {
  const n = app.overview.missions.filter(isTest).length;
  return h("button", { class: "btn", type: "button", "aria-pressed": String(app.showTests),
    onclick: () => { app.showTests = !app.showTests; localStorage.setItem("ac-show-tests", app.showTests ? "1" : "0"); renderCards(); renderSelect(); renderPage(); } },
  `${app.showTests ? "Masquer" : "Afficher"} les missions de recette (${n})`);
}

const PAGES = {
  sessions(o) {
    return [h("p", { class: "lead" }, "Chaque session est une mission et sa conversation avec Agent Core. Cliquer pour l'ouvrir dans Mission Control."),
      h("div", { class: "filters" }, testToggle()), missionTable(shown(o.missions))];
  },
  missions(o) {
    const filters = [["all", "Toutes"], ["running", "En cours"], ["completed", "Terminées"], ["failed", "En échec"], ["uncertain", "À valider"], ["cancelled", "Annulées"]];
    const base = shown(o.missions);
    const ms = base.filter((m) => app.filter === "all" || m.state === app.filter);
    return [h("div", { class: "filters" }, filters.map(([k, label]) => h("button", { class: "btn", type: "button", "aria-pressed": String(app.filter === k), onclick: () => { app.filter = k; renderPage(); } },
      `${label} (${k === "all" ? base.length : base.filter((m) => m.state === k).length})`)), testToggle()), missionTable(ms)];
  },
  garage(o) {
    const failed = shown(o.missions).filter((m) => m.state === "failed").slice(0, 30);
    const tbody = h("tbody", {});
    const wrap = [h("p", { class: "lead" }, "Missions en échec (30 plus récentes) et validations en attente. Les causes viennent du journal de chaque mission."),
      h("div", { class: "filters" }, testToggle()),
      o.validations.length ? h("div", { class: "val-list" }, o.validations.map(valCard)) : null,
      h("table", { class: "table" }, h("thead", {}, h("tr", {}, h("th", {}, "Session"), h("th", {}, "Date"), h("th", {}, "Cause"), h("th", {}, "Consigne"))), tbody)];
    failed.forEach((m) => {
      const cause = h("td", {}, "…");
      tbody.append(h("tr", { class: "clickable", onclick: () => select(m.id) }, h("td", {}, shortId(m.id)), h("td", {}, fmtDate(idDate(m.id))), cause, h("td", {}, (m.goal || "").slice(0, 90))));
      api(`/api/missions/${encodeURIComponent(m.id)}`).then((d) => {
        const end = d.events.find((e) => e.kind.type === "mission_ended");
        cause.textContent = end ? reasonText(end.kind.reason) || "—" : "—";
      }).catch(() => { cause.textContent = "journal illisible"; });
    });
    return wrap;
  },
  dream() {
    return [h("div", { class: "dream-art" }, sprite("moon", 12)),
      h("p", { class: "lead" }, "Dream n'est pas encore configuré sur ce serveur : aucune exécution nocturne n'est planifiée, et aucune heure n'est affichée tant qu'elle n'existe pas réellement."),
      h("p", { class: "lead" }, "Piste prévue (CDC v1.1 §16, amélioration par anneaux) : rejouer le banc de régression la nuit et proposer des ajustements, toujours soumis à validation humaine.")];
  },
  guardian(o) {
    const g = o.guardian;
    const r = g.recette;
    return [h("div", { class: "grid2" },
      h("div", { class: "meter px" }, h("b", {}, "État"), h("span", { class: `big ${g.status === "sain" ? "green" : "orange"}` }, g.status === "sain" ? "Système sain" : "À vérifier")),
      h("div", { class: "meter px" }, h("b", {}, "Intégrité du binaire"), h("span", { class: `big ${g.integrity === "ok" ? "green" : "orange"}` }, g.integrity === "ok" ? "SHA-256 conforme" : g.integrity), h("p", { class: "muted" }, o.version.version || "")),
      h("div", { class: "meter px" }, h("b", {}, "Dernière recette"), r ? h("span", { class: `big ${r.fail ? "orange" : "green"}` }, `${r.pass} PASS · ${r.fail} FAIL · ${r.nc} NC`) : h("span", { class: "big muted" }, "aucune"), r ? h("p", { class: "muted" }, r.run) : null)),
      r ? h("table", { class: "table verdict-table" },
        h("thead", {}, h("tr", {}, h("th", {}, "Exigence"), h("th", {}, "Verdict"), h("th", {}, "Détail"))),
        h("tbody", {}, r.lines.map((l) => /^(\S+)\s+(\S+)\s+(.*)$/.exec(l)).filter(Boolean).map(([, name, verdict, detail]) =>
          h("tr", {}, h("td", {}, name), h("td", {}, h("span", { class: `state ${verdict === "PASS" ? "s-completed" : verdict === "FAIL" ? "s-failed" : "s-uncertain"}` }, verdict)), h("td", {}, detail))))) : null];
  },
  validations(o) {
    if (!o.validations.length) return [h("p", { class: "empty" }, sprite("ok", 2), "Aucune demande de validation en attente.")];
    return [h("p", { class: "lead" }, "Une écriture a commencé sans résultat journalisé (coupure). Vérifie le fichier, puis confirme si l'écriture a eu lieu ; la mission reprend ensuite."),
      h("div", { class: "val-list" }, o.validations.map((v) => h("div", { class: "meter px" },
        h("b", {}, v.tool ? `${TOOL_VERB[v.tool] || v.tool} ${v.path}` : v.mission),
        h("p", { class: "muted" }, `Mission ${shortId(v.mission)} · appel ${v.call_id}`),
        h("p", {}, v.goal || ""),
        h("div", { class: "actions" },
          h("button", { class: "btn good", type: "button", onclick: () => act(v.mission, "resolve", { call: v.call_id, as: "done" }, "Confirmer : écriture effectuée, puis reprendre ?") }, sprite("ok", 2), "Confirmer : effectué"),
          h("button", { class: "btn warn", type: "button", onclick: () => act(v.mission, "resolve", { call: v.call_id, as: "not-done" }, "Confirmer : écriture NON effectuée, puis reprendre ?") }, sprite("ko", 2), "Confirmer : non effectué"),
          h("button", { class: "btn", type: "button", onclick: () => select(v.mission) }, "Ouvrir la session")))))];
  },
  ressources(o) {
    const r = o.resources;
    const meter = (label, pct, text, cls) => h("div", { class: "meter px" }, h("b", {}, label), h("span", { class: "big" }, text), h("i", { class: `bar ${cls || ""}` }, (() => { const i = h("i"); i.style.width = `${pct}%`; return i; })()));
    return [h("p", { class: "lead" }, `Mesures en direct sur ${r.hostname} (/proc). Plafonds de dépenses : ${o.version.plafonds || "—"}.`),
      h("div", { class: "grid2" }, meter("Processeur", r.cpu, `${r.cpu} %`), meter("Mémoire", r.ram.percent, `${r.ram.percent} % · ${r.ram.used_gib} / ${r.ram.total_gib} Gio`, "mauve"),
        r.disk ? meter("Disque (état)", r.disk.percent, `${r.disk.percent} % · ${r.disk.free_gib} Gio libres`, "orange") : null,
        h("div", { class: "meter px" }, h("b", {}, "Charge (1 min)"), h("span", { class: "big" }, String(r.load).replace(".", ","))))];
  },
  configuration(o) {
    const v = o.version;
    return [h("dl", { class: "kv" },
      h("dt", {}, "Version"), h("dd", {}, v.version || "—"),
      ...["configuration", "état", "modèle", "plafonds", "clé"].flatMap((k) => [h("dt", {}, k), h("dd", {}, v[k] || "—")]),
      h("dt", {}, "Dossiers autorisés"), h("dd", {}, (o.inputs || []).join(", ") || "aucun"),
      h("dt", {}, "OpenCode"), h("dd", {}, o.opencode ? "détecté" : "non détecté"),
      h("dt", {}, "Console"), h("dd", {}, "boucle locale, jeton de session pour les actions, tunnel SSH requis depuis l'iMac"))];
  },
};

async function refreshOpenCode() {
  const button = $("#opencode-start");
  const status = $("#opencode-status");
  try {
    const result = await api("/api/opencode-lab");
    button.disabled = !result.configured || result.state === "running";
    const states = {
      idle: "Prêt à lancer.", running: "OpenCode travaille…",
      passed: "Les trois vérifications passent.", failed: "L’essai a échoué.",
    };
    status.textContent = !result.configured ? "OpenCode doit être configuré sur le serveur."
      : result.error || states[result.state];
    $("#opencode-diff").textContent = result.diff || "—";
    $("#opencode-tests").replaceChildren(...(result.tests || []).map((test) =>
      h("li", {}, `${test.quantity} × ${test.price} · attendu ${test.expected} · obtenu ${test.actual} · ${test.passed ? "réussi" : "échec"}`)
    ));
  } catch (error) {
    button.disabled = true;
    status.textContent = error.message;
  }
}

$("#opencode-start").addEventListener("click", async (event) => {
  if (!window.confirm("Lancer un appel OpenCode avec le modèle de test ?")) return;
  event.currentTarget.disabled = true;
  try {
    await api("/api/opencode-lab", {});
    await refreshOpenCode();
  } catch (error) {
    await refreshOpenCode();
    toast(error.message, true);
  }
});

function renderPage() {
  if (app.view === "opencode") return;
  if (app.view === "control" || !app.overview) return;
  const sec = $(`#view-${app.view}`);
  sec.replaceChildren(h("header", { class: "panel-head" }, sprite({ sessions: "chat", missions: "target", garage: "cubes", dream: "moon", guardian: "shield", validations: "check", ressources: "bars", configuration: "gear" }[app.view], 3), h("h2", {}, VIEW_TITLE[app.view])),
    h("div", { class: "inner" }, ...PAGES[app.view](app.overview)));
  paint(sec);
}

function setView(view) {
  if (!VIEW_TITLE[view]) view = "control";
  app.view = view;
  if (location.hash !== `#${view}`) history.replaceState(null, "", `#${view}`);
  for (const sec of document.querySelectorAll(".view")) sec.hidden = sec.id !== `view-${view}`;
  for (const a of document.querySelectorAll(".side a")) a.toggleAttribute("aria-current", a.dataset.view === view);
  for (const a of document.querySelectorAll(".side a[aria-current]")) a.setAttribute("aria-current", "page");
  $("#view-title").textContent = VIEW_TITLE[view];
  if (view === "opencode") refreshOpenCode();
  else renderPage();
}

// ---------- câblage ----------
document.addEventListener("click", (e) => {
  const a = e.target.closest("[data-view]");
  if (a) { e.preventDefault(); setView(a.dataset.view); }
  if (!e.target.closest("#input-pop, #input-pick")) $("#input-pop").hidden = true;
  if (!e.target.closest("#help-pop, #help")) { $("#help-pop").hidden = true; $("#help").setAttribute("aria-expanded", "false"); }
});
$("#bell").addEventListener("click", () => setView("validations"));
$("#help").addEventListener("click", () => { const p = $("#help-pop"); p.hidden = !p.hidden; $("#help").setAttribute("aria-expanded", String(!p.hidden)); });
$("#session-select").addEventListener("change", (e) => select(e.target.value));
$("#raw-toggle").addEventListener("click", (e) => {
  const raw = $("#raw"); raw.hidden = !raw.hidden; $("#messages").hidden = !raw.hidden;
  e.currentTarget.setAttribute("aria-pressed", String(!raw.hidden));
});
$("#input-pick").addEventListener("click", () => { renderInputPicker(); $("#input-pop").hidden = !$("#input-pop").hidden; });
$("#goal").addEventListener("input", autosize);
$("#goal").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); launch($("#goal").value); } });
$("#composer").addEventListener("submit", (e) => { e.preventDefault(); launch($("#goal").value); });
window.addEventListener("hashchange", () => setView(location.hash.slice(1)));

paint(document);
setView(location.hash.slice(1) || "control");
refreshOverview().then(() => { renderInputPicker(); noteInput(); });
setInterval(refreshOverview, 5000);
setInterval(() => { if (app.view === "opencode") refreshOpenCode(); }, 2000);
