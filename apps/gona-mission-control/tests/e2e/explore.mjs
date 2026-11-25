// Exploration : connexion Atlas, bascule GONA ⇄ Atlas, rendu desktop / mobile, erreurs console.
// Usage : node explore.mjs <dossier_captures>   (aucun message envoyé à l'agent)
import { launch, newPage, sleep } from "./cdp.mjs";
import { readFileSync } from "node:fs";
const OUT = process.argv[2];
const pw = readFileSync(process.env.HOME + "/.local/share/arpagona/acces-thibaud-banc.txt", "utf8")
  .split("\n").find(l => /^mot de passe/i.test(l)).split(":").slice(1).join(":").trim();
const GONA = process.env.GONA || "http://127.0.0.1:8710", ATLAS = process.env.ATLAS || "http://127.0.0.1:8700";
const b = await launch(9333);
const report = [];
const log = (k, v) => { report.push([k, v]); console.log(k, "→", typeof v === "string" ? v : JSON.stringify(v)); };
try {
  for (const [name, vp] of [["desktop", { width: 1440, height: 900 }], ["imac", { width: 2560, height: 1440 }], ["tablette", { width: 820, height: 1180, mobile: true }], ["mobile", { width: 390, height: 844, mobile: true }]]) {
    const p = await newPage(b.port, vp);
    // 1. Atlas : formulaire de connexion réel
    await p.goto(ATLAS + "/", 2000);
    log(name + " atlas login visible", await p.eval(`!document.getElementById("login-view")?.hidden`));
    await p.shot(`${OUT}/${name}-01-atlas-login.png`);
    await p.eval(`(()=>{document.getElementById("login").value="thibaud";document.getElementById("password").value=${JSON.stringify(pw)};
      document.getElementById("login-form").requestSubmit();return 1})()`);
    await sleep(2500);
    log(name + " atlas login error", await p.eval(`document.getElementById("login-error")?.textContent||""`));
    log(name + " atlas app visible", await p.eval(`!document.getElementById("app-view")?.hidden`));
    await p.shot(`${OUT}/${name}-02-atlas-app.png`);
    const toGona = await p.eval(`(()=>{const a=document.getElementById("switch-gona");return a?{href:a.href,target:a.target,hidden:a.hidden,vis:a.getBoundingClientRect().width>0}:null})()`);
    log(name + " atlas→gona link", toGona);
    // 2. Bascule vers GONA
    if (toGona) { await p.goto(toGona.href, 3000); }
    log(name + " gona url", await p.eval("location.href"));
    log(name + " gona app visible", await p.eval(`!document.getElementById("app-view")?.hidden`));
    log(name + " gona who", await p.eval(`document.getElementById("who-name")?.textContent||""`));
    await p.waitFor(`document.querySelectorAll("#log .msg").length>0`, 8000);
    log(name + " gona msgs", await p.eval(`document.querySelectorAll("#log .msg").length`));
    log(name + " gona status", await p.eval(`document.getElementById("chat-status")?.textContent||""`));
    await p.shot(`${OUT}/${name}-03-gona-chat.png`);
    const toAtlas = await p.eval(`(()=>{const a=document.getElementById("switch-atlas");return a?{href:a.href,hidden:a.hidden,vis:a.getBoundingClientRect().width>0}:null})()`);
    log(name + " gona→atlas link", toAtlas);
    // 3. Retour Atlas
    if (toAtlas) { await p.goto(toAtlas.href, 2500); log(name + " back atlas app", await p.eval(`!document.getElementById("app-view")?.hidden`)); await p.shot(`${OUT}/${name}-04-atlas-back.png`); }
    // 4. GONA : onglets
    await p.goto(GONA + "/", 3000);
    for (const tab of ["kanban", "drafts", "chat"]) {
      const ok = await p.click(`.tab[data-view=${tab}]`); await sleep(2500);
      log(name + " tab " + tab, ok); await p.shot(`${OUT}/${name}-05-gona-${tab}.png`);
    }
    // overflow horizontal (mise en page cassée)
    log(name + " horizontal overflow px", await p.eval(`document.documentElement.scrollWidth-innerWidth`));
    log(name + " console errors", p.consoleErrors().slice(0, 10));
    p.close();
  }
} finally { b.close(); }
