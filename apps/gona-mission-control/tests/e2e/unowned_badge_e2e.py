"""E2E navigateur : badge « Sans responsable ». Instance isolée (fixture) + Chrome headless dédié.
Usage: python3 unowned_badge_e2e.py <base_url> <token> <dossier_captures>   (Chrome déjà lancé sur --remote-debugging-port=9333)"""
import asyncio, json, sys, urllib.request, websockets
BASE, TOK, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
async def run(vp, name):
    tabs = json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:9333/json/new?about:blank', method='PUT')))
    async with websockets.connect(tabs['webSocketDebuggerUrl'], max_size=None) as ws:
        n = 0
        async def cmd(m, **p):
            nonlocal n; n += 1; await ws.send(json.dumps({'id': n, 'method': m, 'params': p}))
            while True:
                r = json.loads(await ws.recv())
                if r.get('id') == n: return r.get('result', r)
        ev = lambda e: cmd('Runtime.evaluate', expression=e, returnByValue=True, awaitPromise=True)
        await cmd('Emulation.setDeviceMetricsOverride', width=vp[0], height=vp[1], deviceScaleFactor=1, mobile=vp[0] < 700)
        await cmd('Page.navigate', url=BASE + '/?t=' + TOK); await asyncio.sleep(2)
        await ev('document.querySelector(\'[data-view=kanban]\').click()'); await asyncio.sleep(2)
        js = '''JSON.stringify([...document.querySelectorAll("#board .task")].map(b=>({t:[...b.childNodes].find(n=>n.nodeType===3).textContent,
          badge:[...b.querySelectorAll(".badge-unowned")].map(x=>x.textContent),cls:b.className,vis:[...b.querySelectorAll(".badge-unowned")].every(x=>x.getBoundingClientRect().width>0),
          col:b.closest(".column").dataset.status})))'''
        cards = json.loads((await ev(js))['result']['value'])
        shot = await cmd('Page.captureScreenshot', format='png', captureBeyondViewport=True)
        import base64; open(f'{OUT}/kanban-{name}.png', 'wb').write(base64.b64decode(shot['data']))
        return cards
res = {}
for name, vp in (('desktop', (1280, 900)), ('mobile', (390, 844))):
    res[name] = asyncio.run(run(vp, name))
exp = {'Carte non assignée': True, 'Carte assignée': False, 'Attente de déploiement (bloquée, assignée)': False,
       'Attente humaine (non assignée)': False, 'Ombrelle volontairement sans responsable': False,
       'Terminée sans responsable': False, 'Bloquée non assignée (déploiement)': True}
ok = True
for name, cards in res.items():
    seen = {}
    for c in cards: seen[c['t']] = c
    for t, want in exp.items():
        c = seen.get(t); got = bool(c and c['badge'] == ['Sans responsable'] and c['vis'])
        st = 'OK' if c and got == want and (want or not c['badge']) else 'ECHEC'
        ok &= st == 'OK'; print(name, st, t, '→ badge' if got else '→ pas de badge', '| needs-input' if c and 'needs-input' in c['cls'] else '')
sys.exit(0 if ok else 1)
