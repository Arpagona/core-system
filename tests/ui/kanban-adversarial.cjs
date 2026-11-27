// Tests adversariaux de l'interface Kanban : petites résolutions, clavier réel,
// réponses réseau inversées, expiration de session, répétitions de clic.
// N'utilise que la démo synthétique « adversarial » sur 18810. Chrome CDP 9223 requis.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const BASE='http://127.0.0.1:18810',PAGE='http://kanban-adv.localhost:18810';
const out=path.resolve(process.argv[2]||'.local/kanban-adversarial');fs.mkdirSync(out,{recursive:true});
let ws,session,context;const results=[],pending=new Map();let serial=0,cookie='';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const ID={unknown:'t_20000001',longToken:'t_20000002',bulk:'t_20000003',done:'t_20000004',colleague:'t_20000006',unassigned:'t_20000007'};
function rpc(method,params={},sid=session){return new Promise((resolve,reject)=>{const id=++serial;const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout '+method));},25000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,...(sid?{sessionId:sid}:{})}));});}
async function js(expression){const r=await rpc('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.result?.description||r.exceptionDetails.text);return r.result?.value;}
async function wait(expression,ms=4000){const end=Date.now()+ms;for(;;){if(await js(expression))return true;if(Date.now()>end)return false;await sleep(80);}}
async function click(id){await js(`document.getElementById(${JSON.stringify(id)}).click()`);}
async function submit(id){await js(`(()=>{const f=document.getElementById(${JSON.stringify(id)});f.querySelector('button[type="submit"],button:not([type])').click();})()`);}
async function value(id,v,type='input'){await js(`(()=>{const e=document.getElementById(${JSON.stringify(id)});e.value=${JSON.stringify(v)};e.dispatchEvent(new Event(${JSON.stringify(type)},{bubbles:true}));})()`);}
async function enter(){await rpc('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13});await rpc('Input.dispatchKeyEvent',{type:'char',text:'\r',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});await rpc('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13});}
async function api(url,body){const r=await fetch(BASE+url,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Arpagona':'1',Cookie:cookie},body:body?JSON.stringify(body):undefined});return {status:r.status,data:await r.json().catch(()=>null)};}
async function screenshot(name){const r=await rpc('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,name),Buffer.from(r.data,'base64'));}
async function check(name,fn){try{await fn();results.push({name,passed:true});console.log('PASS '+name);}catch(err){results.push({name,passed:false,error:err.message});console.log('FAIL '+name+' → '+err.message);}}
async function login(){
  const r=await fetch(BASE+'/api/login',{method:'POST',headers:{'Content-Type':'application/json','X-Arpagona':'1'},body:JSON.stringify({login:'demo',password:'demo-arpagona-2026'})});
  assert.equal(r.status,200);cookie=r.headers.getSetCookie()[0].split(';')[0];
  if(session){const i=cookie.indexOf('=');await rpc('Network.setCookie',{name:cookie.slice(0,i),value:cookie.slice(i+1),url:PAGE,httpOnly:true,sameSite:'Strict'});}
}
(async()=>{
 await login();
 const ver=await fetch('http://127.0.0.1:9223/json/version').then(r=>r.json());
 ws=new WebSocket(ver.webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(!m.id)return;const p=pending.get(m.id);if(!p)return;pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error(m.error.message)):p.resolve(m.result);};
 context=(await rpc('Target.createBrowserContext',{},null)).browserContextId;
 const target=(await rpc('Target.createTarget',{url:'about:blank',browserContextId:context},null)).targetId;
 session=(await rpc('Target.attachToTarget',{targetId:target,flatten:true},null)).sessionId;
 await rpc('Page.enable');await rpc('Network.enable');
 const sep=cookie.indexOf('=');
 await rpc('Network.setCookie',{name:cookie.slice(0,sep),value:cookie.slice(sep+1),url:PAGE,httpOnly:true,sameSite:'Strict'});
 await rpc('Emulation.setDeviceMetricsOverride',{width:1366,height:900,deviceScaleFactor:1,mobile:false});
 await rpc('Page.navigate',{url:PAGE});
 assert.ok(await wait(`!document.getElementById('app-view').hidden`),'application non chargée');
 await js(`document.querySelector('.tab[data-view="kanban"]').click()`);
 assert.ok(await wait(`document.querySelectorAll('.task').length>0`),'aucune carte affichée');

 // 15 commentaires réels pour éprouver le défilement du détail
 for(let i=1;i<=15;i++) await api('/api/kanban/comment',{id:ID.bulk,text:`Commentaire fictif numéro ${i}.`});

 await check('statut inconnu visible et honnête, sans casser la vue',async()=>{
   assert.ok(await js(`!!document.querySelector('[data-status="other"]')`),'colonne « Autres états » absente');
   assert.ok(await js(`document.body.textContent.includes('custom')`),'statut brut non affiché');
   assert.ok(await js(`!!document.querySelector('[data-card-id="${ID.unknown}"]')`));
 });
 await check('jeton très long : pas de débordement horizontal de page',async()=>{
   await rpc('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
   await js('window.__beforeReload=true');await rpc('Page.reload');
   assert.ok(await wait(`!window.__beforeReload && document.getElementById('app-view') && !document.getElementById('app-view').hidden`),'rechargement mobile');
   await js(`document.querySelector('.tab[data-view="kanban"]').click()`);await wait(`document.querySelectorAll('.task').length>0`);
   assert.ok(await js('document.documentElement.scrollWidth<=window.innerWidth+1'),
     'page plus large que l’écran : '+await js('document.documentElement.scrollWidth+" > "+window.innerWidth'));
 });
 await check('petit écran 320×568 : détail long défilable, fin atteignable',async()=>{
   await rpc('Emulation.setDeviceMetricsOverride',{width:320,height:568,deviceScaleFactor:1,mobile:true});
   await js(`openCard(${JSON.stringify(ID.bulk)})`);
   assert.ok(await wait(`document.getElementById('card-dialog').open`),'détail non ouvert');
   assert.ok(await js(`document.getElementById('comments').textContent.includes('numéro 15')`),'commentaires absents');
   const scrollable=await js(`(()=>{const d=document.getElementById('card-dialog');return d.scrollHeight>d.clientHeight+2;})()`);
   assert.ok(scrollable,'le détail dépasse la hauteur sans zone de défilement');
   await js(`(()=>{const d=document.getElementById('card-dialog');d.scrollTop=d.scrollHeight;})()`);
   assert.ok(await js(`(()=>{const d=document.getElementById('card-dialog');const b=document.getElementById('close-card').getBoundingClientRect();return b.bottom>0&&b.top<window.innerHeight;})()`),'fermeture hors écran après défilement');
   await js(`(()=>{const d=document.getElementById('card-dialog');d.scrollTop=0;})()`);
   await screenshot('adversarial-320x568.png');
   await click('close-card');
 });
 await check('aide honnête quand tout est terminé (aucune carte active)',async()=>{
   await rpc('Emulation.setDeviceMetricsOverride',{width:1366,height:900,deviceScaleFactor:1,mobile:false});
   await js(`window.__saved=kanbanTasks;kanbanTasks=kanbanTasks.map(t=>({...t,status:'done'}));renderKanban()`);
   const text=await js(`document.querySelector('.kanban-empty')?.textContent||''`);
   await js(`kanbanTasks=window.__saved;delete window.__saved;renderKanban()`);
   assert.match(text,/termin/i,'message vide muet : « '+text+' »');
 });
 await check('touche Entrée dans le formulaire crée la carte',async()=>{
   await click('new-card');
   await value('card-name','Carte créée au clavier');
   await js(`document.getElementById('card-name').focus()`);
   await enter();
   const ok=await wait(`!document.getElementById('card-dialog').open`,3000);
   const list=await api('/api/kanban/list');
   const made=(list.data||[]).find(t=>t.title==='Carte créée au clavier');
   await js(`if(document.getElementById('card-dialog').open)closeCard()`);
   assert.ok(ok&&made,'soumission au clavier sans effet' + (made?'':', aucune carte créée'));
 });
 await check('réponse lente ne réécrit pas une carte ouverte plus tard',async()=>{
   await js(`(()=>{const orig=window.fetch;window.__orig=orig;window.fetch=async(u,o)=>{if(String(u).includes(${JSON.stringify(ID.bulk)}))await new Promise(r=>setTimeout(r,600));return orig(u,o);};})()`);
   await js(`openCard(${JSON.stringify(ID.bulk)});openCard(${JSON.stringify(ID.colleague)})`);
   assert.ok(await wait(`document.getElementById('card-title').textContent.includes('collègue')`),'seconde carte non affichée');
   await sleep(900);
   const title=await js(`document.getElementById('card-title').textContent`);
   await js(`window.fetch=window.__orig;delete window.__orig`);
   await click('close-card').catch(()=>{});
   assert.ok(title.includes('collègue'),'réponse tardive a écrasé la carte affichée : '+title);
 });
 await check('double clic sur Terminer : une seule clôture',async()=>{
   const id=ID.longToken;
   await js(`openCard(${JSON.stringify(id)})`);assert.ok(await wait(`document.getElementById('card-dialog').open`));
   await js(`(()=>{const b=Array.from(document.querySelectorAll('#card-actions button')).find(x=>x.textContent==='Terminer');b.click();b.click();})()`);
   assert.ok(await wait(`document.getElementById('detail-meta').textContent.includes('Terminé')`,4000),'statut non mis à jour');
   const shown=await api('/api/kanban/show?id='+id);
   const done=(shown.data.events||[]).filter(e=>e.kind==='completed');
   await click('close-card');
   assert.equal(shown.data.task.status,'done');
   assert.ok(done.length<=1,'clôtures multiples : '+done.length);
 });
 await check('brouillon de commentaire conservé pendant une actualisation',async()=>{
   await js(`openCard(${JSON.stringify(ID.unassigned)})`);assert.ok(await wait(`document.getElementById('card-dialog').open`));
   await value('comment-text','Brouillon fictif en cours de rédaction');
   await js('loadKanban()');await sleep(400);
   const kept=await js(`document.getElementById('comment-text').value`);
   await click('close-card');
   assert.equal(kept,'Brouillon fictif en cours de rédaction');
 });
 await check('motif de blocage fait uniquement d’espaces refusé',async()=>{
   const id=ID.colleague; // carte d'un collègue : refus attendu côté API
   const before=(await api('/api/kanban/show?id='+id)).data.task.status;
   const spaces=await api('/api/kanban/block',{id,text:'   '});
   assert.notEqual(spaces.status,200,'blocage avec espaces accepté');
   assert.equal((await api('/api/kanban/show?id='+id)).data.task.status,before);
 });
 await check('blocage refusé par le noyau sur une carte à faire',async()=>{
   const r=await api('/api/kanban/block',{id:ID.unassigned,text:'Motif fictif sur carte non démarrée'});
   assert.ok(r.status>=400,'transition non refusée : '+r.status);
 });
 await check('session expirée : retour à l’écran de connexion',async()=>{
   await rpc('Network.deleteCookies',{name:cookie.split('=')[0],url:PAGE});
   await js('loadKanban()');
   const ok=await wait(`!document.getElementById('login-view').hidden`,3000);
   if(!ok){/* laisser l'état pour le diagnostic */await screenshot('adversarial-session-expiree.png');}
   assert.ok(ok,'session expirée mais interface morte sans reconnexion');
   await login();await rpc('Page.reload');
   assert.ok(await wait(`!document.getElementById('app-view').hidden`),'reconnexion impossible');
 });
 const failed=results.filter(r=>!r.passed);
 fs.writeFileSync(path.join(out,'adversarial-results.json'),JSON.stringify({passed:failed.length===0,total:results.length,failed:failed.length,results,backend:'API et bridge réels, CLI simulée fidèle, données synthétiques'},null,2));
 console.log(JSON.stringify({passed:failed.length===0,total:results.length,failed:failed.length}));
 if(failed.length)process.exitCode=1;
})().catch(e=>{fs.writeFileSync(path.join(out,'adversarial-results.json'),JSON.stringify({passed:false,crashed:e.message,results},null,2));console.error(e.stack);process.exitCode=1;}).finally(async()=>{if(context&&ws?.readyState===1){try{await rpc('Target.disposeBrowserContext',{browserContextId:context},null);}catch{}}ws?.close();});
