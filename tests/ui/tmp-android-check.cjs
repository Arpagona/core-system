
const fs=require('node:fs');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));let ws=null,serial=0;const pending=new Map();
function rpc(m,p={}){return new Promise((res,rej)=>{const id=++serial;const t=setTimeout(()=>rej(Error('timeout '+m)),15000);pending.set(id,{res,rej,t});ws.send(JSON.stringify({id,method:m,params:p}));});}
async function js(e){const r=await rpc('Runtime.evaluate',{expression:e,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.result?.description||'js');return r.result?.value;}
(async()=>{
 const list=await fetch('http://127.0.0.1:9334/json').then(r=>r.json());
 const page=list.find(t=>t.type==='page')||list[0];
 console.log('cible:',page.url);
 ws=new WebSocket(page.webSocketDebuggerUrl);
 await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(!m.id)return;const p=pending.get(m.id);if(!p)return;pending.delete(m.id);clearTimeout(p.t);m.error?p.rej(Error(m.error.message)):p.res(m.result);};
 const info=await js(`(()=>{const q=s=>!!document.querySelector(s);return{
   url:location.href, protocole:location.protocol, titre:document.title,
   largeur:window.innerWidth, hauteur:window.innerHeight,
   connexion:q('#login-view')? !document.getElementById('login-view').hidden : null,
   application:q('#app-view')? !document.getElementById('app-view').hidden : null,
   formulaire:q('#login')&&q('#password'),
   nouveauKanban:{recherche:q('#kanban-search'),equipe:q('#scope-mine'),sansResponsable:q('#scope-unassigned'),mode:q('#kanban-mode')},
   moduleVue:(()=>{try{return KanbanView.filter([{id:'t_1',title:'x',status:'ready',assignee:'mael'}],{scope:'mine',login:'mael'}).length}catch(e){return 'erreur:'+e.message}})(),
   erreursSSL:(document.body.innerText||'').slice(0,160)
 };})()`);
 console.log(JSON.stringify(info,null,1));
 const shot=await rpc('Page.captureScreenshot',{format:'png'});
 fs.writeFileSync('/home/thibaud/projects/core-system-kanban/reports/proofs/2026-11-27-kanban-android.png',Buffer.from(shot.data,'base64'));
})().catch(e=>{console.error('ÉCHEC '+e.message);process.exitCode=1;}).finally(()=>{try{ws&&ws.close()}catch{}});
