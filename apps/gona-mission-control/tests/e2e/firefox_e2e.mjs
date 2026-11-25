// Test Firefox réel (WebDriver BiDi, sans dépendance) : le kiosque iMac tourne sous Firefox, pas Chrome.
// Usage : node firefox_e2e.mjs <dossier> [url_gona] [url_atlas]   — jeton lu dans MC_TOKEN (jamais affiché).
// Aucun message envoyé à l'agent.
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
const OUT = process.argv[2] || ".";
const GONA = process.argv[3] || "http://127.0.0.1:8710";
const ATLAS = process.argv[4] || "";
const TOKEN = process.env.MC_TOKEN || "";
const FF = process.env.FIREFOX || "firefox";
const sleep = ms => new Promise(r => setTimeout(r, ms));
// Firefox Snap : le profil doit vivre sous ~/snap/firefox/common (sinon refus silencieux).
import { existsSync, mkdirSync } from "node:fs";
const base = existsSync(process.env.HOME + "/snap/firefox/common") ? process.env.HOME + "/snap/firefox/common" : (process.env.TMPDIR || "/tmp");
const prof = mkdtempSync(join(base, "mc-ff-"));
writeFileSync(join(prof, "user.js"), 'user_pref("media.autoplay.default", 0);\nuser_pref("browser.shell.checkDefaultBrowser", false);\n');
const port = 9500 + Math.floor(Math.random() * 300);
const ff = spawn(FF, ["--headless", "--no-remote", "--profile", prof, `--remote-debugging-port=${port}`, "--width=2560", "--height=1440"], { stdio: "ignore", env: { ...process.env, MOZ_REMOTE_ALLOW_SYSTEM_ACCESS: "1" } });
let ws;
for (let i = 0; i < 60; i++) { try { ws = new WebSocket(`ws://127.0.0.1:${port}/session`); await new Promise((ok, ko) => { ws.onopen = ok; ws.onerror = ko; }); break; } catch { ws = null; await sleep(500); } }
if (!ws) { console.log("FAIL Firefox BiDi injoignable"); ff.kill(); process.exit(2); }
let n = 0; const wait = new Map(); const logs = [];
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && wait.has(m.id)) { wait.get(m.id)(m); wait.delete(m.id); }
  else if (m.method === "log.entryAdded" && m.params.level === "error") logs.push(m.params.text); };
const cmd = (method, params = {}) => new Promise((ok, ko) => { const id = ++n; wait.set(id, m => m.type === "error" ? ko(new Error(method + ": " + m.message)) : ok(m.result)); ws.send(JSON.stringify({ id, method, params })); });
let fails = 0; const check = (k, ok, x = "") => { console.log((ok ? "PASS " : "FAIL ") + k + (x !== "" ? " · " + x : "")); if (!ok) fails++; };
try {
  await cmd("session.new", { capabilities: {} });
  await cmd("session.subscribe", { events: ["log.entryAdded"] });
  const ctx = (await cmd("browsingContext.create", { type: "tab" })).context;
  const ev = async expr => { const r = await cmd("script.evaluate", { expression: expr, target: { context: ctx }, awaitPromise: true, resultOwnership: "none" }); return r.result?.value; };
  const until = async (expr, ms = 10000) => { const t = Date.now(); while (Date.now() - t < ms) { try { if (await ev(expr)) return true; } catch {} await sleep(250); } return false; };
  const shot = async name => { const r = await cmd("browsingContext.captureScreenshot", { context: ctx }); writeFileSync(`${OUT}/${name}.png`, Buffer.from(r.data, "base64")); };
  for (const [label, w, h] of [["imac", 2560, 1440], ["portable", 1366, 768], ["mobile", 390, 844]]) {
    await cmd("browsingContext.setViewport", { context: ctx, viewport: { width: w, height: h } });
    await cmd("browsingContext.navigate", { context: ctx, url: GONA + (TOKEN ? "/?t=" + encodeURIComponent(TOKEN) : "/"), wait: "complete" });
    check(`firefox ${label} : appli GONA ouverte`, await until(`!document.getElementById("app-view").hidden`, 10000));
    check(`firefox ${label} : fil chargé`, await until(`document.querySelectorAll("#log .msg").length > 0`, 10000), await ev(`document.querySelectorAll("#log .msg").length`));
    check(`firefox ${label} : Kanban chargé`, await until(`document.querySelectorAll("#board .column").length >= 3 && /cartes au total/.test(document.getElementById("kanban-status").textContent)`, 15000));
    check(`firefox ${label} : flux direct ouvert`, await until(`document.getElementById("chat-status").textContent === "" || /travaille|écrit/.test(document.getElementById("chat-status").textContent)`, 5000), await ev(`document.getElementById("chat-status").textContent`));
    check(`firefox ${label} : boutons du composeur visibles`, await ev(`["attachbtn","modelbtn","speakerbtn","voicebtn","send"].every(id=>{const r=document.getElementById(id).getBoundingClientRect();return r.width>0&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1})`));
    check(`firefox ${label} : aucun débordement horizontal`, (await ev(`document.documentElement.scrollWidth - innerWidth`)) <= 0);
    const sw = await ev(`(()=>{const a=document.getElementById("switch-atlas");return a&&!a.hidden?a.href:""})()`);
    check(`firefox ${label} : lien ⇄ Atlas présent`, !!sw, sw);
    await shot(`firefox-${label}-gona`);
    if (label === "mobile") { await ev(`document.querySelector('.tab[data-view=kanban]').click()`); await sleep(1500); await shot(`firefox-${label}-kanban`); }
  }
  if (ATLAS) {
    await cmd("browsingContext.setViewport", { context: ctx, viewport: { width: 2560, height: 1440 } });
    await cmd("browsingContext.navigate", { context: ctx, url: ATLAS + "/", wait: "complete" });
    const shown = await until(`!document.getElementById("login-view")?.hidden || !document.getElementById("app-view")?.hidden`, 10000);
    check("firefox Atlas : page rendue (connexion ou appli)", shown);
    await shot("firefox-imac-atlas");
  }
  check("firefox : aucune erreur JavaScript", !logs.length, logs.slice(0, 5).join(" | "));
} catch (e) { console.log("FAIL exception " + e.message); fails++; }
finally { try { await cmd("session.end"); } catch {} ff.kill("SIGKILL"); await sleep(500); rmSync(prof, { recursive: true, force: true }); }
console.log(fails ? `ÉCHECS : ${fails}` : "TOUT PASSE"); process.exit(fails ? 1 : 0);
