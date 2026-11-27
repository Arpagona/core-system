
const sleep=ms=>new Promise(r=>setTimeout(r,ms));let ws=null,serial=0;const pending=new Map();
function rpc(m,p={}){return new Promise((res,rej)=>{const id=++serial;const t=setTimeout(()=>rej(Error('timeout '+m)),20000);pending.set(id,{res,rej,t});ws.send(JSON.stringify({id,method:m,params:p}));});}
async function js(e){const r=await rpc('Runtime.evaluate',{expression:e,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.result?.description||'js');return r.result?.value;}
(async()=>{
 const list=await fetch('http://127.0.0.1:9334/json').then(r=>r.json());
 const page=list.find(t=>t.type==='page')||list[0];
 ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(!m.id)return;const p=pending.get(m.id);if(!p)return;pending.delete(m.id);clearTimeout(p.t);m.error?p.rej(Error(m.error.message)):p.res(m.result);};
 await rpc('Page.enable');
 const before=await js(`(()=>({cache:!!document.getElementById('kanban-search'),sw:'serviceWorker' in navigator?!!navigator.serviceWorker.controller:false,scripts:[...document.scripts].map(s=>s.getAttribute('src'))}))()`);
 console.log('avant rechargement:',JSON.stringify(before));
 await rpc('Page.reload',{ignoreCache:true});
 await sleep(4000);
 const after=await js(`(()=>{const q=s=>!!document.querySelector(s);return{
   rechargementComplete:document.readyState,
   url:location.href,
   recherche:q('#kanban-search'),equipe:q('#scope-mine'),sansResponsable:q('#scope-unassigned'),mode:q('#kanban-mode'),
   moduleVue:(()=>{try{return KanbanView.filter([{id:'t_1',status:'ready',assignee:'mael'}],{scope:'mine',login:'mael'}).length}catch(e){return 'erreur'}})(),
   sw:(()=>{try{return !!navigator.serviceWorker.controller}catch(e){return 'non'}})()
 };})()`);
 console.log('après rechargement:',JSON.stringify(after,null,1));
})().catch(e=>{console.error('ÉCHEC '+e.message);process.exitCode=1;}).finally(()=>{try{ws&&ws.close()}catch{}});
