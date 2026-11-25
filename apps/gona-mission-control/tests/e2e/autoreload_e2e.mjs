// Vérifie le rechargement automatique après déploiement (aucun message envoyé).
import { launch, newPage, sleep } from "./cdp.mjs";
import { appendFileSync } from "node:fs";
const BASE = process.env.GONA || "http://127.0.0.1:8710", TOKEN = process.env.MC_TOKEN;
const b = await launch(9336);
try {
  const p = await newPage(b.port, { width: 1280, height: 900 });
  await p.goto(BASE + "/?t=" + encodeURIComponent(TOKEN), 3000);
  await p.eval(`window.__avant = 1`);
  await sleep(32000);                    // première lecture de version
  appendFileSync(process.argv[2], "\n/* déploiement " + new Date().toISOString() + " */\n");
  const ok = await p.waitFor(`window.__avant === undefined && !document.getElementById("app-view").hidden`, 45000);
  console.log((ok ? "PASS" : "FAIL") + " écran rechargé seul après déploiement");
  process.exit(ok ? 0 : 1);
} finally { b.close(); }
