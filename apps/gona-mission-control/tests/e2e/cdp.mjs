// Mini-pilote CDP (Node 22, WebSocket natif) pour les tests navigateur de Mission Control.
// Lance un Chrome headless dédié (profil jetable) et expose page.eval / page.shot / page.goto.
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const sleep = ms => new Promise(r => setTimeout(r, ms));

export async function launch(port = 9333) {
  const dir = mkdtempSync(join(process.env.TMPDIR || tmpdir(), "mc-e2e-"));
  const proc = spawn("google-chrome", ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${dir}`,
    "--no-first-run", "--no-default-browser-check", "--autoplay-policy=no-user-gesture-required",
    "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--mute-audio", "about:blank"],
    { stdio: "ignore" });
  for (let i = 0; i < 50; i++) {
    try { await (await fetch(`http://127.0.0.1:${port}/json/version`)).json(); break; } catch { await sleep(200); }
  }
  return { port, close: () => { proc.kill("SIGKILL"); try { rmSync(dir, { recursive: true, force: true }); } catch {} } };
}

export async function newPage(port, { width = 1280, height = 900, mobile = false } = {}) {
  const t = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((ok, ko) => { ws.onopen = ok; ws.onerror = ko; });
  let n = 0; const wait = new Map(); const events = []; const listeners = [];
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && wait.has(m.id)) { wait.get(m.id)(m); wait.delete(m.id); }
    else if (m.method) { events.push(m); listeners.forEach(f => f(m)); }
  };
  const cmd = (method, params = {}) => new Promise((ok, ko) => {
    const id = ++n; wait.set(id, m => m.error ? ko(new Error(method + ": " + m.error.message)) : ok(m.result));
    ws.send(JSON.stringify({ id, method, params }));
  });
  await cmd("Page.enable"); await cmd("Runtime.enable"); await cmd("Network.enable");
  await cmd("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: mobile ? 2 : 1, mobile });
  if (mobile) await cmd("Emulation.setUserAgentOverride", { userAgent: "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/158.0 Mobile Safari/537.36" });
  const page = {
    cmd, events, on: f => listeners.push(f),
    consoleErrors: () => events.filter(e => (e.method === "Runtime.exceptionThrown") ||
      (e.method === "Runtime.consoleAPICalled" && e.params.type === "error")).map(e =>
      e.params.exceptionDetails ? (e.params.exceptionDetails.exception?.description || e.params.exceptionDetails.text) :
      e.params.args.map(a => a.value ?? a.description).join(" ")),
    async goto(url, settle = 1500) { await cmd("Page.navigate", { url }); await sleep(settle); },
    async eval(expr) {
      const r = await cmd("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true, userGesture: true });
      if (r.exceptionDetails) throw new Error("eval: " + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
      return r.result.value;
    },
    async waitFor(expr, ms = 10000) {
      const t0 = Date.now();
      while (Date.now() - t0 < ms) { try { if (await page.eval(expr)) return true; } catch {} await sleep(200); }
      return false;
    },
    async shot(path, full = false) {
      const r = await cmd("Page.captureScreenshot", { format: "png", captureBeyondViewport: full });
      writeFileSync(path, Buffer.from(r.data, "base64")); return path;
    },
    async setCookie(name, value, url) { await cmd("Network.setCookie", { name, value, url, httpOnly: true, sameSite: "Strict" }); },
    async click(sel) { return page.eval(`(()=>{const e=document.querySelector(${JSON.stringify(sel)}); if(!e) return false; e.click(); return true;})()`); },
    close() { ws.close(); },
  };
  return page;
}
export { sleep };
