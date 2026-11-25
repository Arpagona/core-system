// Test de la lecture automatique (aucun message réel envoyé à l'agent) :
// le fil et la synthèse sont simulés dans la page ; on compte ce que la voix lit.
import { launch, newPage, sleep } from "./cdp.mjs";
import { readFileSync } from "node:fs";
const BASE = process.env.GONA || "http://127.0.0.1:8719";   // banc isolé (sandbox.py)
const TOKEN = process.env.MC_TOKEN || "sandbox-token";
const HOOK = `(() => {
  window.__fake = []; window.__speak = [];
  const real = window.fetch.bind(window);
  const WAV = "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
  window.fetch = async (url, opt) => {
    const u = String(url);
    if (u.startsWith("/api/voice/speak")) {
      window.__speak.push(JSON.parse(opt.body).text);
      const bin = atob(WAV), a = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i);
      await new Promise(r => setTimeout(r, 300));
      return new Response(new Blob([a], { type: "audio/wav" }), { status: 200, headers: { "Content-Type": "audio/wav" } });
    }
    const r = await real(url, opt);
    if (u.startsWith("/api/channel/messages") && window.__fake.length) {
      const d = await r.clone().json(); d.messages = [...(d.messages || []), ...window.__fake];
      return new Response(JSON.stringify(d), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    return r;
  };
})();`;
const b = await launch(9334);
let fails = 0;
const check = (name, ok, extra = "") => { console.log((ok ? "PASS " : "FAIL ") + name + (extra ? " · " + extra : "")); if (!ok) fails++; };
try {
  const p = await newPage(b.port, { width: 1280, height: 900 });
  await p.cmd("Page.addScriptToEvaluateOnNewDocument", { source: HOOK });
  await p.goto(BASE + "/?t=" + TOKEN, 4000);
  await p.waitFor(`document.querySelectorAll("#log .msg").length>0`, 10000);
  await p.eval(`localStorage.setItem("mc_speaker","on")`);
  await sleep(6000);
  check("historique jamais relu au chargement", (await p.eval("window.__speak.length")) === 0, await p.eval("JSON.stringify(window.__speak)"));
  const push = t => p.eval(`window.__fake.push({role:"assistant",text:${JSON.stringify(t)},ts:Date.now()/1000});1`);
  await push("Réponse de test A.");
  await p.waitFor(`window.__speak.length>=1`, 12000);
  check("nouvelle réponse lue automatiquement", (await p.eval("window.__speak")).includes("Réponse de test A."));
  await push("Réponse de test B.");
  await p.waitFor(`window.__speak.length>=2`, 12000);
  await push("Réponse de test C.");
  await p.waitFor(`window.__speak.length>=3`, 12000);
  await sleep(9000);
  const s = await p.eval("window.__speak");
  check("réponses successives toutes lues, dans l'ordre", JSON.stringify(s) === JSON.stringify(["Réponse de test A.", "Réponse de test B.", "Réponse de test C."]), JSON.stringify(s));
  // File d'attente : une réponse arrive pendant une lecture en cours → lue après, pas perdue
  await p.eval(`window.MCVoice.say("Lecture longue en cours D.");1`);
  await p.eval(`window.MCVoice.say("Arrivée pendant la lecture E.");1`);
  await p.waitFor(`window.__speak.includes("Arrivée pendant la lecture E.")`, 12000);
  check("réponse arrivée pendant une lecture mise en file puis lue", (await p.eval("window.__speak")).includes("Arrivée pendant la lecture E."));
  await p.eval(`window.MCVoice.say("Arrivée pendant la lecture E.");1`); await sleep(1500);
  check("pas de doublon", (await p.eval(`window.__speak.filter(x=>x==="Arrivée pendant la lecture E.").length`)) === 1);
  // Chemin réel : message tapé → envoi → réponse en flux → lue une seule fois
  const before = await p.eval("window.__speak.length");
  await p.eval(`(()=>{const t=document.getElementById("text"); t.value="bonjour test tapé"; t.dispatchEvent(new Event("input",{bubbles:true})); document.getElementById("chat-form").requestSubmit(); return 1})()`);
  await p.waitFor(`window.__speak.some(x=>x.includes("bonjour test tapé"))`, 20000);
  await sleep(9000);
  const typed = await p.eval(`window.__speak.filter(x=>x.includes("bonjour test tapé")).length`);
  check("message tapé : réponse lue exactement une fois", typed === 1, "lectures=" + typed + " total=" + ((await p.eval("window.__speak.length")) - before));
  check("texte intermédiaire jamais affiché en bulle", (await p.eval(`[...document.querySelectorAll("#log .msg")].filter(e=>e.textContent.includes("Je vais chercher")).length`)) === 0);
  check("la voix ne lit pas le texte intermédiaire", (await p.eval(`window.__speak.filter(x=>x.includes("Je vais chercher")).length`)) === 0);
  await p.shot(process.env.SHOT_DIR ? process.env.SHOT_DIR + "/sandbox-chat-apres-envoi.png" : "/dev/null");
  check("bouton Envoyer revenu à l'état prêt", await p.eval(`!document.getElementById("stop").hidden===false`));
  // Haut-parleur coupé → rien n'est lu
  await p.eval(`(()=>{const b=document.getElementById("speakerbtn"); if(b.classList.contains("on")) b.click(); return 1})()`);
  const n = await p.eval("window.__speak.length");
  await push("Réponse de test F (voix coupée).");
  await sleep(9000);
  check("🔇 : aucune lecture", (await p.eval("window.__speak.length")) === n);
  await p.eval(`localStorage.setItem("mc_speaker","on")`);
  check("aucune erreur JavaScript", p.consoleErrors().length === 0, JSON.stringify(p.consoleErrors().slice(0, 3)));
  p.close();
} finally { b.close(); }
console.log(fails ? `ÉCHEC : ${fails}` : "TOUT OK");
process.exit(fails ? 1 : 0);
