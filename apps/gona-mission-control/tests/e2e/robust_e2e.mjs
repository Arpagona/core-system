// Robustesse du chat (banc isolé sandbox.py, faux moteur) — aucun message réel envoyé à GONA.
// Couvre : envoi pendant que GONA travaille, erreur réseau sans verrouillage, renvoi sans doublon,
// micro disponible pendant un tour, message long, mise en page mobile. Usage : node robust_e2e.mjs <dossier>
import { launch, newPage, sleep } from "./cdp.mjs";
const OUT = process.argv[2] || ".";
const BASE = process.env.GONA || "http://127.0.0.1:8719";
const b = await launch(9335);
let fails = 0;
const check = (k, ok, x = "") => { console.log((ok ? "PASS " : "FAIL ") + k + (x ? " · " + x : "")); if (!ok) fails++; };
try {
  for (const [name, vp] of [["desktop", { width: 1440, height: 900 }], ["mobile", { width: 390, height: 844, mobile: true }]]) {
    const p = await newPage(b.port, vp);
    await p.goto(BASE + "/?t=sandbox-token", 2500);
    check(name + " : appli chargée", await p.waitFor(`!document.getElementById("app-view").hidden`, 8000));
    const type = t => p.eval(`(()=>{const ta=document.getElementById("text");ta.value=${JSON.stringify(t)};ta.dispatchEvent(new Event("input"));return 1})()`);
    const send = () => p.eval(`document.getElementById("chat-form").requestSubmit()`);
    const nUser = () => p.eval(`[...document.querySelectorAll("#log .msg.user")].length`);
    // 1. un tour long, puis un second message pendant qu'il tourne
    const before = await nUser();
    await type("lent : tâche longue " + name); await send();
    await p.waitFor(`/travaille|écrit|utilise/.test(document.getElementById("chat-status").textContent)`, 6000);
    await sleep(800);
    await type("précision pendant le travail " + name);
    check(name + " : bouton Envoyer actif pendant que GONA travaille", await p.eval(`!document.getElementById("send").disabled`));
    check(name + " : micro actif pendant que GONA travaille", await p.eval(`!document.getElementById("voicebtn").disabled`));
    await send(); await sleep(1500);
    const st = await p.eval(`[...document.querySelectorAll("#log .msg.user")].pop()?.dataset.note||""`);
    check(name + " : message pendant le tour confirmé sous la bulle", /transmis|file/.test(st), st);
    check(name + " : zone de saisie vidée", await p.eval(`document.getElementById("text").value===""`));
    await p.shot(`${OUT}/${name}-01-envoi-pendant-travail.png`);
    // fin du tour : la réponse arrive, le chat se libère
    check(name + " : tour terminé, chat libéré", await p.waitFor(`!/travaille|écrit|utilise|Envoi/.test(document.getElementById("chat-status").textContent) && [...document.querySelectorAll("#log .msg.assistant")].some(e=>/Réponse à : lent/.test(e.textContent))`, 20000));
    await p.waitFor(`[...document.querySelectorAll("#log .msg.assistant")].some(e=>/précision pendant/.test(e.textContent))`, 15000);
    const users = await nUser();
    check(name + " : 2 messages utilisateur, aucun doublon", users - before === 2, `${users - before}`);
    await p.shot(`${OUT}/${name}-02-apres-tour.png`);
    // 2. panne réseau simulée : le chat ne doit pas rester verrouillé et le texte doit revenir
    await p.eval(`(()=>{window.__real=window.fetch;window.fetch=(u,o)=>String(u).startsWith("/api/chat")?Promise.reject(new TypeError("Failed to fetch")):window.__real(u,o);return 1})()`);
    await type("message pendant une coupure"); await send(); await sleep(800);
    check(name + " : après coupure, texte remis dans la zone", await p.eval(`document.getElementById("text").value==="message pendant une coupure"`));
    check(name + " : après coupure, Envoyer reste actif", await p.eval(`!document.getElementById("send").disabled`));
    const st2 = await p.eval(`document.getElementById("chat-status").textContent`);
    check(name + " : après coupure, erreur lisible", /injoignable|Hors ligne/.test(st2), st2);
    await p.shot(`${OUT}/${name}-03-coupure.png`);
    await p.eval(`(()=>{window.fetch=window.__real;return 1})()`);
    const u0 = await nUser(); await send();
    await p.waitFor(`[...document.querySelectorAll("#log .msg.assistant")].some(e=>/coupure/.test(e.textContent))`, 15000);
    check(name + " : renvoi après coupure, une seule bulle", (await nUser()) - u0 === 1);
    // 3. message long (12 000 caractères) accepté
    await type("long " + "x".repeat(12000)); await send();
    check(name + " : message de 12 000 caractères accepté", await p.waitFor(`document.getElementById("text").value===""`, 5000));
    await p.waitFor(`!/travaille|écrit|utilise|Envoi/.test(document.getElementById("chat-status").textContent)`, 20000);
    // 4. mise en page
    check(name + " : aucun débordement horizontal", (await p.eval(`document.documentElement.scrollWidth-innerWidth`)) <= 0);
    const comp = await p.eval(`(()=>{const r=document.querySelector(".composer").getBoundingClientRect();return r.bottom<=innerHeight+1 && r.right<=innerWidth+1})()`);
    check(name + " : composeur entièrement visible", comp);
    if (vp.mobile) {
      const small = await p.eval(`[...document.querySelectorAll(".composer-actions button")].filter(b=>!b.hidden && b.offsetParent && b.getBoundingClientRect().height<40).map(b=>b.id||b.textContent)`);
      check(name + " : cibles tactiles ≥ 40 px", !small.length, small.join(","));
    }
    check(name + " : aucune erreur JavaScript", !p.consoleErrors().filter(e => !/Failed to fetch|ERR_/.test(e)).length, p.consoleErrors().join(" | ").slice(0, 300));
    p.close();
  }
} finally { b.close(); }
console.log(fails ? `ÉCHECS : ${fails}` : "TOUT PASSE");
process.exit(fails ? 1 : 0);
