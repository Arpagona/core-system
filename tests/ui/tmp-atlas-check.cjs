
const assert=require('node:assert/strict');const fs=require('node:fs');
const URL_='https://192.168.68.240:8700/';let ws=null,session,serial=0,ctx=null;const pending=new Map();
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function rpc(m,p={},sid=session){return new Promise((res,rej)=>{const id=++serial;const t=setTimeout(()=>rej(Error('timeout '+m)),20000);pending.set(id,{res,rej,t});ws.send(JSON.stringify({id,method:m,params:p,...(sid?{sessionId:sid}:{})}));});}
async function js(e){const r=await rpc('Runtime.evaluate',{expression:e,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.result?.description||'js');return r.result?.value;}
(async()=>{
 const ver=await fetch('http://127.0.0.1:9223/json/version').then(r=>r.json());
 ws=new WebSocket(ver.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(!m.id)return;const p=pending.get(m.id);if(!p)return;pending.delete(m.id);clearTimeout(p.t);m.error?p.rej(Error(m.error.message)):p.res(m.result);};
 ctx=(await rpc('Target.createBrowserContext',{},null)).browserContextId;
 const tg=(await rpc('Target.createTarget',{url:'about:blank',browserContextId:ctx},null)).targetId;
 session=(await rpc('Target.attachToTarget',{targetId:tg,flatten:true},null)).sessionId;
 await rpc('Page.enable');await rpc('Security.setIgnoreCertificateErrors',{ignore:true},null);
 await rpc('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 await rpc('Page.navigate',{url:URL_});
 for(let n=0;n<80;n++){if(await js(`document.readyState==='complete' && !!document.getElementById('login-view')`))break;await sleep(150);}
 const st=await js(`(()=>{let ok=null;try{ok=KanbanView.filter([{id:'t_1',title:'Préparer',status:'ready',assignee:'thibaud'}],{scope:'mine',login:'thibaud'}).length;}catch(e){ok='erreur:'+e.message;}
 return {titre:document.title,protocole:location.protocol,loginVisible:!document.getElementById('login-view').hidden,
  scripts:[...document.scripts].map(s=>s.getAttribute('src')).filter(Boolean),
  filtreExecutable:ok,sessionExpireePresente:typeof sessionExpired==='function',
  recherche:!!document.getElementById('kanban-search'),equipe:['scope-all','scope-mine','scope-unassigned'].every(i=>!!document.getElementById(i)),
  mode:!!document.getElementById('kanban-mode'),blocage:!!document.getElementById('block-reason')};})()`);
 console.log(JSON.stringify(st,null,1));
 assert.equal(st.titre,'ARPAGONA · Agent Core');
 assert.equal(st.protocole,'https:');
 assert.ok(st.loginVisible,'écran de connexion absent');
 assert.equal(st.filtreExecutable,1,'module de vue Kanban non exécuté dans la page déployée');
 assert.ok(st.sessionExpireePresente,'correctif de session absente du déploiement');
 assert.ok(st.recherche&&st.equipe&&st.mode&&st.blocage,'interface Kanban incomplète sur Atlas');
 const shot=await rpc('Page.captureScreenshot',{format:'png'});
 fs.writeFileSync('/home/thibaud/projects/core-system-kanban/reports/proofs/2026-11-27-kanban-atlas.png',Buffer.from(shot.data,'base64'));
 console.log('OK: page déployée servie et interface Kanban exécutée');
})().catch(e=>{console.error('ÉCHEC '+e.message);process.exitCode=1;}).finally(async()=>{try{if(ctx)await rpc('Target.disposeBrowserContext',{browserContextId:ctx},null);}catch{}try{ws&&ws.close();}catch{}});
