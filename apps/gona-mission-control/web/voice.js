"use strict";
// Voix ARPAGONA Mission Control (alpha) — même fonctionnement que l'ancien tableau de bord :
// bouton 🎙 maintenu (ou Espace hors champ texte) → transcription locale (faster-whisper)
// → envoi dans la même conversation que Telegram → attente de LA réponse → lecture (voix fr-CA, Edge ; repli Piper).
// Haut-parleur 🔊/🔇 (mémorisé) : décide si GONA répond à voix haute, que la question soit dite ou tapée ici.
(() => {
  const $ = id => document.getElementById(id);
  const btn = $("voicebtn"), cancel = $("voicecancel"), status = $("chat-status");
  if (!btn) return;
  const spk = $("speakerbtn"), KEY = "mc_speaker";
  const enabled = () => localStorage.getItem(KEY) !== "off";
  function paintSpeaker() {
    if (!spk) return;
    spk.setAttribute("aria-label", enabled() ? "Couper la réponse vocale" : "Activer la réponse vocale");
    const on = enabled();
    spk.textContent = on ? "🔊" : "🔇";
    spk.classList.toggle("on", on);
    spk.setAttribute("aria-pressed", on ? "true" : "false");
    spk.title = on ? "Réponse à voix haute : activée (cliquer pour texte seul)" : "Réponse en texte seul (cliquer pour activer la voix)";
  }
  const H = { "X-Arpagona": "1", "X-Gona": "1" };
  const MIN_MS = 450, MAX_MS = 90000, POLL_MS = 2000, WAIT_MAX_MS = 15 * 60 * 1000;
  let state = "idle", recorder = null, stream = null, chunks = [], gen = 0, timer = null, startedAt = 0;
  let controller = null, pollTimer = null, waitStart = 0, pendingRelease = false;
  const player = new Audio(); player.preload = "auto";
  const SILENT = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
  let unlocked = false;
  // Lecture automatique fiable (25/11 soir) : une seule porte d'entrée « say », file d'attente
  // (une réponse arrivée pendant une lecture est lue ensuite, jamais perdue) et anti-doublon par texte.
  const said = new Set(), queue = [];
  const keyOf = t => (t || "").replace(/\s+/g, " ").trim().slice(0, 240);
  function remember(k) { said.add(k); if (said.size > 60) said.delete(said.values().next().value); }
  function say(text) {
    const k = keyOf(text);
    if (!k || said.has(k) || queue.some(t => keyOf(t) === k)) return false;
    if (state === "idle") { remember(k); speak(++gen, text); } else queue.push(text);
    return true;
  }
  function drain() {
    setTimeout(() => {
      if (state !== "idle" || !queue.length || !enabled()) return;
      const t = queue.shift(), k = keyOf(t);
      if (said.has(k)) return drain();
      remember(k); speak(++gen, t);
    }, 250);
  }
  function unlock() { if (unlocked) return; unlocked = true; try { player.src = SILENT; player.play().catch(() => {}); } catch (e) {} }

  function show(s, text) {
    state = s;
    if (text != null) status.textContent = text;
    const rec = s === "recording";
    btn.classList.toggle("rec", rec);
    btn.textContent = rec ? "● REC" : "🎙";
    btn.title = rec ? "Relâcher pour envoyer" : "Maintenir pour parler (ou Espace)";
    btn.disabled = ["transcribing", "sending", "stopping"].includes(s);   // jamais bloqué pendant que GONA travaille ou parle
    cancel.hidden = s === "idle";
    if (s === "idle" && queue.length) drain();
  }
  const capturing = () => ["starting", "recording"].includes(state);
  function stopTracks() { if (stream) stream.getTracks().forEach(t => t.stop()); stream = null; clearTimeout(timer); }
  function stopAll(msg) {
    gen++; pendingRelease = false; queue.length = 0;
    if (controller) controller.abort(); controller = null;
    clearTimeout(pollTimer); pollTimer = null;
    if (recorder && recorder.state !== "inactive") { try { recorder.stop(); } catch (e) {} }
    stopTracks(); chunks = []; recorder = null;
    try { player.pause(); } catch (e) {}
    show("idle", msg);
  }

  async function start() {
    if (state !== "idle") return;
    if (!window.MC || !MC.session()) { show("idle", "Conversation non chargée"); return; }
    // GONA occupée : le message vocal rejoint le tour en cours (comme un message tapé), plus de refus.
    const natif = !navigator.mediaDevices?.getUserMedia && window.AndroidMic;   // appli Android : micro natif (HTTP = pas de getUserMedia)
    if (!natif && (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)) { show("idle", "Micro indisponible dans ce navigateur"); return; }
    const id = ++gen; pendingRelease = false;
    if (natif) {
      if (!AndroidMic.start()) { show("idle", "Micro refusé : autorise-le dans les réglages Android de l’appli"); return; }
      chunks = []; startedAt = Date.now();
      recorder = { state: "recording", mimeType: "audio/mp4", stop() {
        this.state = "inactive";
        const b64 = AndroidMic.stop(), bin = atob(b64 || ""), u = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
        if (id === gen && u.length) chunks.push(new Blob([u], { type: "audio/mp4" }));
        this.onstop();
      } };
      recorder.onstop = () => onRecorded(id);
      show("recording", "Je t’écoute… relâche pour envoyer");
      timer = setTimeout(() => { if (state === "recording") finish(); }, MAX_MS);
      if (pendingRelease) { pendingRelease = false; finish(); }
      return;
    }
    show("starting", "Ouverture du micro…");
    try {
      const acquired = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      if (id !== gen) { acquired.getTracks().forEach(t => t.stop()); return; }
      stream = acquired; chunks = [];
      recorder = new MediaRecorder(stream);
      recorder.ondataavailable = e => { if (id === gen && e.data.size) chunks.push(e.data); };
      recorder.onstop = () => onRecorded(id);
      recorder.start(); startedAt = Date.now();
      show("recording", "Je t’écoute… relâche pour envoyer · Échap annule");
      timer = setTimeout(() => { if (state === "recording") finish(); }, MAX_MS);
      if (pendingRelease) { pendingRelease = false; finish(); }
    } catch (e) { stopTracks(); if (id === gen) show("idle", "Micro refusé ou indisponible · rien n’a été envoyé"); }
  }

  function finish() {
    if (state === "starting") { pendingRelease = true; return; }
    if (state !== "recording" || recorder?.state !== "recording") return;
    if (Date.now() - startedAt < MIN_MS) { stopAll("Appui trop court · rien n’a été envoyé"); return; }
    show("stopping", "Arrêt…"); recorder.stop();
  }

  async function onRecorded(id) {
    if (id !== gen) return; stopTracks();
    const blob = new Blob(chunks, { type: recorder?.mimeType || "audio/webm" }); chunks = []; recorder = null;
    if (!blob.size || blob.size > 8000000) { show("idle", "Enregistrement vide ou trop long · rien n’a été envoyé"); return; }
    show("transcribing", "Transcription locale…"); controller = new AbortController();
    let text;
    try {
      const r = await fetch("/api/voice/transcribe", { method: "POST", body: blob, signal: controller.signal,
        headers: { ...H, "Content-Type": (blob.type || "audio/webm").split(";")[0] } });
      const d = await r.json();
      if (id !== gen) return;
      if (!r.ok) throw new Error(d.error || "transcription impossible");
      text = (d.text || "").trim();
    } catch (e) { if (id === gen) show("idle", "Transcription impossible · rien n’a été envoyé"); return; }
    finally { if (id === gen) controller = null; }
    if (!text) { show("idle", "Aucune parole reconnue · rien n’a été envoyé"); return; }
    text = text.trim(); if (text.startsWith("/")) text = "(dicté) " + text;   // jamais une commande par la voix
    show("sending", "« " + text.slice(0, 120) + " » · envoi…");
    const session = MC.session(), submission = "imac-mc-v-" + crypto.randomUUID(), t0 = Date.now();
    try {
      const r = await fetch("/api/chat", { method: "POST", headers: { ...H, "Content-Type": "application/json" },
        body: JSON.stringify({ id: session, text, submission_id: submission }) });
      const d = await r.json();
      if (!r.ok || d.ok === false) throw new Error(d.error || "envoi refusé");
    } catch (e) {
      if (id !== gen) return;
      const ta = $("text"); ta.value = [ta.value.trim(), text.trim()].filter(Boolean).join("\n");
      show("idle", "Envoi non confirmé · texte remis dans la zone de saisie, à vérifier avant renvoi");
      return;
    }
    // Le micro est libéré tout de suite. La réponse est lue par la lecture automatique unique (app.js),
    // quel que soit le chemin d'arrivée : plus d'attente vocale qui bloquait le bouton 🎙.
    MC.refresh().catch(() => {});
    show("idle", enabled() ? "Envoyé ✓ · la réponse sera lue à voix haute" : "Envoyé ✓ · réponse en texte (🔇)");
  }

  // Si le gateway a mis le message en file (agent occupé), l'étiquette est perdue : on le retrouve par son texte.
  function byText(text, t0) {
    const msgs = MC.messages(), i = msgs.findIndex(m => m.role === "user" && (m.text || "").trim() === text && (!m.ts || m.ts >= t0 / 1000 - 30));
    if (i < 0) return { state: "waiting" };
    const after = msgs.slice(i + 1), a = after.find(m => m.role === "assistant");
    if (!a) return { state: "working" };
    if (after.slice(0, after.indexOf(a)).some(m => m.role === "user")) return { state: "ambiguous" };
    return { state: "ready", text: a.text || "" };
  }

  async function poll(id, session, submission, text, t0) {
    if (id !== gen) return;
    if (Date.now() - waitStart > WAIT_MAX_MS) { show("idle", "Réponse trop longue · elle restera dans le fil, sans lecture"); return; }
    let d;
    try {
      const r = await fetch("/api/channel/reply?id=" + encodeURIComponent(session) + "&submission=" + encodeURIComponent(submission), { headers: H });
      d = await r.json();
      if (d.state === "waiting") { await MC.refresh().catch(() => {}); d = byText(text, t0); }
    } catch (e) { d = { state: "retry" }; }
    if (id !== gen) return;
    if (d.state === "ready") {
      show("idle", enabled() ? null : "Réponse dans le fil · voix coupée (🔇)");
      if (enabled() && d.text) say(d.text);
      MC.refresh().catch(() => {});
      return;
    }
    if (d.state === "ambiguous") { show("idle", "Un autre message s’est intercalé : réponse dans le fil, non lue"); return; }
    const s = Math.round((Date.now() - waitStart) / 1000);
    show("waiting", "Envoyé · GONA " + (d.state === "waiting" ? "n’a pas encore pris le message" : "travaille") + "… " + s + " s · Échap pour ne pas lire");
    pollTimer = setTimeout(() => poll(id, session, submission, text, t0), POLL_MS);
  }

  async function speak(id, text) {
    window.__mcSpokenText = text; remember(keyOf(text));
    show("speaking", "Préparation de la voix…"); controller = new AbortController();
    try {
      let r = await fetch("/api/voice/speak", { method: "POST", signal: controller.signal,
        headers: { ...H, "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
      if (id !== gen) return;
      if (!r.ok) {   // une relance : la synthèse distante échoue parfois au premier appel
        await new Promise(ok => setTimeout(ok, 800));
        if (id !== gen) return;
        r = await fetch("/api/voice/speak", { method: "POST", signal: controller.signal,
          headers: { ...H, "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
        if (id !== gen) return;
        if (!r.ok) throw new Error("synthèse");
      }
      const url = URL.createObjectURL(await r.blob());
      if (id !== gen) { URL.revokeObjectURL(url); return; }
      player.src = url;
      player.preservesPitch = true;   // voix plus rapide sans la rendre aiguë
      player.playbackRate = parseFloat(localStorage.getItem("mc-voice-rate")) || 1.15;
      player.onended = () => { URL.revokeObjectURL(url); if (id === gen) show("idle", "Réponse lue · maintiens 🎙 pour reparler"); };
      player.onerror = () => { URL.revokeObjectURL(url); if (id === gen) show("idle", "Lecture audio impossible · réponse dans le fil"); };
      show("speaking", "🔊 Lecture de la réponse · Échap pour couper");
      try { await player.play(); }
      catch (err) {   // autoplay refusé : on garde le son prêt, il part au prochain toucher/clic
        if (err.name !== "NotAllowedError") throw err;
        show("speaking", "🔊 Touche l’écran pour entendre la réponse");
        const resume = () => { document.removeEventListener("pointerdown", resume, true); document.removeEventListener("keydown", resume, true);
          if (id === gen) player.play().then(() => show("speaking", "🔊 Lecture de la réponse · Échap pour couper")).catch(() => show("idle", "Lecture audio impossible · réponse dans le fil")); };
        document.addEventListener("pointerdown", resume, true); document.addEventListener("keydown", resume, true);
      }
    } catch (e) {
      if (id === gen) show("idle", e.name === "NotAllowedError" ? "Lecture automatique bloquée · réponse dans le fil" : "Voix indisponible · réponse dans le fil");
    } finally { if (id === gen) controller = null; }
  }

  if (spk) {
    paintSpeaker();
    spk.addEventListener("click", e => {
      e.preventDefault(); unlock();
      localStorage.setItem(KEY, enabled() ? "off" : "on"); paintSpeaker();
      if (!enabled() && state === "speaking") stopAll("Lecture coupée");
    });
  }
  window.MCVoice = {
    enabled, busy: () => state !== "idle", unlock, state: () => state,
    say: text => enabled() && say(text),
    seen: text => remember(keyOf(text)),          // historique déjà affiché : jamais relu
    speakText: text => enabled() && say(text)
  };

  btn.addEventListener("pointerdown", e => {
    e.preventDefault(); unlock();
    if (state === "speaking" || state === "waiting") stopAll();
    if (state === "idle") { try { btn.setPointerCapture(e.pointerId); } catch (_) {} start(); }
  });
  ["pointerup", "pointercancel"].forEach(ev => btn.addEventListener(ev, () => { if (capturing()) finish(); }));
  btn.addEventListener("contextmenu", e => e.preventDefault());
  btn.addEventListener("click", e => e.preventDefault());
  cancel.addEventListener("click", () => stopAll(state === "speaking" ? "Lecture coupée" : state === "waiting" ? "Réponse non lue · elle reste dans le fil" : "Annulé · rien n’a été envoyé"));

  let space = false;
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && state !== "idle") { e.preventDefault(); space = false; cancel.click(); return; }
    if (e.code !== "Space" || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target.closest("input,textarea,select,[contenteditable='true'],dialog")) return;
    e.preventDefault();
    if (e.repeat || space) return;
    if (state === "speaking") stopAll();
    if (state !== "idle") return;
    space = true; unlock(); start();
  });
  document.addEventListener("keyup", e => { if (e.code === "Space" && space) { e.preventDefault(); space = false; finish(); } });
  window.addEventListener("blur", () => { if (capturing()) { space = false; stopAll("Fenêtre quittée · enregistrement annulé"); } });
})();
