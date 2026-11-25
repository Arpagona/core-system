// Test sur l'appli Android réelle (WebView de l'émulateur, débogage via adb forward tcp:9444).
// Connexion Atlas avec le compte de test, bascule GONA, onglets ; captures par adb screencap (rendu réel).
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
const OUT = process.argv[2];
const ADB = process.env.HOME + "/Android/Sdk/platform-tools/adb";
const pw = readFileSync(process.env.HOME + "/.local/share/arpagona/acces-thibaud-banc.txt", "utf8")
  .split("\n").find(l => /^mot de passe/i.test(l)).split(":").slice(1).join(":").trim();
const sleep = ms => new Promise(r => setTimeout(r, ms));
const shot = name => { const png = execFileSync(ADB, ["exec-out", "screencap", "-p"], { maxBuffer: 64e6 }); require_write(OUT + "/" + name + ".png", png); console.log("capture", name); };
import { writeFileSync } from "node:fs"; function require_write(p, b) { writeFileSync(p, b); }
async function attach() {
  const list = await (await fetch("http://127.0.0.1:9444/json/list")).json();
  const t = list.find(x => x.type === "page");
  const ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
  let n = 0; const w = new Map(); const errs = [];
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && w.has(m.id)) { w.get(m.id)(m); w.delete(m.id); }
    if (m.method === "Runtime.exceptionThrown") errs.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text); };
  const cmd = (method, params = {}) => new Promise(r => { const id = ++n; w.set(id, r); ws.send(JSON.stringify({ id, method, params })); });
  await cmd("Runtime.enable");
  const ev = async x => { const r = await cmd("Runtime.evaluate", { expression: x, awaitPromise: true, returnByValue: true, userGesture: true }); return r.result?.result?.value ?? r.result?.exceptionDetails?.text; };
  return { ev, ws, errs, url: t.url };
}
let fails = 0; const check = (k, ok, x = "") => { console.log((ok ? "PASS " : "FAIL ") + k + (x ? " · " + x : "")); if (!ok) fails++; };
let p = await attach();
console.log("page", p.url);
// Connexion Atlas (même formulaire que l'utilisateur) puis retour GONA
await p.ev(`location.href="http://10.68.100.1:8700/"`); p.ws.close(); await sleep(4000); p = await attach();
if (await p.ev(`!document.getElementById("login-view").hidden`)) {
  shot("02-atlas-login");
  await p.ev(`(()=>{login.value="thibaud";password.value=${JSON.stringify(pw)};document.getElementById("login-form").requestSubmit();return 1})()`);
  await sleep(3500);
}
check("Atlas : connecté", await p.ev(`!document.getElementById("app-view").hidden`));
shot("03-atlas-app");
check("Atlas : bouton ⇄ GONA visible", await p.ev(`(()=>{const a=document.getElementById("switch-gona");return !!a && a.getBoundingClientRect().width>0})()`));
await p.ev(`document.getElementById("switch-gona").click()`); p.ws.close(); await sleep(5000); p = await attach();
check("GONA : page chargée", /:8710/.test(p.url), p.url);
check("GONA : connecté par le pont Atlas", await p.ev(`!document.getElementById("app-view").hidden`));
await sleep(3000);
check("GONA : fil affiché", (await p.ev(`document.querySelectorAll("#log .msg").length`)) > 0);
const geo = await p.ev(`(()=>{const f=document.getElementById("chat-form").getBoundingClientRect();return [...document.querySelectorAll(".composer-actions .btn")].filter(b=>!b.hidden&&getComputedStyle(b).display!=="none").map(b=>{const r=b.getBoundingClientRect();return {id:b.id,inside:r.left>=f.left-1&&r.right<=f.right+1,w:Math.round(r.width),h:Math.round(r.height)}})})()`);
check("composeur : tous les boutons dans le cadre", geo.every(g => g.inside), JSON.stringify(geo));
check("composeur : cibles tactiles ≥ 44 px", geo.every(g => g.h >= 44));
check("pas de débordement horizontal", (await p.ev(`document.documentElement.scrollWidth-innerWidth`)) <= 0);
shot("04-gona-chat");
await p.ev(`document.querySelector('.tab[data-view=kanban]').click()`); await sleep(3500);
check("Kanban : colonnes en défilement horizontal", await p.ev(`getComputedStyle(document.getElementById("board")).display==="flex"`));
const ov = await p.ev(`(()=>{const c=[...document.querySelectorAll("#board>.column")].map(c=>c.getBoundingClientRect());for(let i=1;i<c.length;i++) if(c[i].left<c[i-1].right-1 && c[i].top<c[i-1].bottom-1) return true; return false})()`);
check("Kanban : aucune colonne superposée", !ov);
shot("05-gona-kanban");
await p.ev(`document.querySelector('.tab[data-view=drafts]').click()`); await sleep(2500);
shot("06-gona-decisions");
await p.ev(`document.querySelector('.tab[data-view=chat]').click()`); await sleep(1000);
// Clavier Android ouvert : le composeur doit rester visible et l'envoi possible (rien n'est envoyé).
await p.ev(`(()=>{const t=document.getElementById("text");t.focus();t.click();return 1})()`);
execFileSync(ADB, ["shell", "input", "tap", "540", "2000"]); await sleep(1500);
execFileSync(ADB, ["shell", "input", "text", "test%sclavier"]); await sleep(1500);
const kb = await p.ev(`(()=>{const f=document.getElementById("chat-form").getBoundingClientRect();const s=document.getElementById("send");return {bottom:Math.round(f.bottom),h:innerHeight,val:document.getElementById("text").value,send:!s.disabled,mic:!document.getElementById("voicebtn").disabled}})()`);
check("clavier ouvert : composeur visible au-dessus du clavier", kb.bottom <= kb.h + 1, JSON.stringify(kb));
check("clavier ouvert : texte saisi et Envoyer actif", /clavier/.test(kb.val) && kb.send, JSON.stringify(kb));
shot("07-gona-clavier");
await p.ev(`(()=>{const t=document.getElementById("text");t.value="";t.dispatchEvent(new Event("input"));t.blur();return 1})()`);
execFileSync(ADB, ["shell", "input", "keyevent", "111"]);
check("aucune erreur JavaScript", p.errs.length === 0, JSON.stringify(p.errs.slice(0, 3)));
p.ws.close();
console.log(fails ? "ÉCHEC : " + fails : "TOUT OK"); process.exit(fails ? 1 : 0);
