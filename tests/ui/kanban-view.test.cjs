const test=require('node:test'),assert=require('node:assert/strict');
const view=require('../../apps/mission-control-web/kanban-view.js');
const cards=[
 {id:'t_1',title:'Préparer la démonstration',assignee:'demo',status:'ready'},
 {id:'t_2',title:'Devis prototype',assignee:'lea',status:'running'},
 {id:'t_3',title:'Besoin à clarifier',assignee:null,status:'todo'},
 {id:'t_4',title:'Archive',assignee:'demo',status:'archived'},
 {id:'t_5',title:'Livré',assignee:'demo',status:'done'},
];
test('les cartes actives seulement par défaut',()=>assert.deepEqual(view.filter(cards).map(t=>t.id),['t_1','t_2','t_3']));
test('terminées visibles sur demande, archives toujours exclues',()=>assert.deepEqual(view.filter(cards,{showDone:true}).map(t=>t.id),['t_1','t_2','t_3','t_5']));
test('mes cartes selon le compte connecté',()=>assert.deepEqual(view.filter(cards,{scope:'mine',login:'demo'}).map(t=>t.id),['t_1']));
test('les cartes des collègues ne sont pas à moi',()=>assert.deepEqual(view.filter(cards,{scope:'mine',login:'inconnu'}),[]));
test('sans responsable',()=>assert.deepEqual(view.filter(cards,{scope:'unassigned'}).map(t=>t.id),['t_3']));
test('accents, casse, espaces et recherche multitermes',()=>assert.deepEqual(view.filter(cards,{query:'  PREPARER demonstration  '}).map(t=>t.id),['t_1']));
test('tous les termes sont requis',()=>assert.deepEqual(view.filter(cards,{query:'demo prototype'}),[]));
test('responsable et identifiant recherchables',()=>{assert.equal(view.filter(cards,{query:'LEA'})[0].id,'t_2');assert.equal(view.filter(cards,{query:'t_3'})[0].id,'t_3');});
test('filtre et recherche se combinent',()=>assert.deepEqual(view.filter(cards,{scope:'mine',login:'demo',query:'prototype'}),[]));
test('ne modifie pas les cartes reçues',()=>{const snapshot=JSON.stringify(cards);view.filter(cards,{showDone:true});view.order(cards);assert.equal(JSON.stringify(cards),snapshot);});
test('état inconnu conservé et étiqueté honnêtement',()=>{const tasks=[{status:'custom',title:'x'}];assert.equal(view.filter(tasks).length,1);assert.equal(view.label('custom'),'custom');});
test('liste ordonnée par priorité puis attention, tri stable',()=>{const tasks=[{id:'a',status:'ready'},{id:'b',status:'blocked'},{id:'c',status:'todo',priority:9},{id:'d',status:'review'},{id:'e',status:'ready'}];assert.deepEqual(view.order(tasks).map(t=>t.id),['c','b','d','a','e']);});
test('les planifiées ne sont pas étiquetées bloquées',()=>{assert.equal(view.label('scheduled'),'Planifiée');assert.equal(view.label('blocked'),'Bloquée');});

test("rechargement seulement quand la version déployée change",()=>{
  assert.equal(view.reloadNeeded(null,"abc"),false,"premier contact : ne pas recharger");
  assert.equal(view.reloadNeeded("abc","abc"),false,"même version : rester");
  assert.equal(view.reloadNeeded("abc","def"),true,"nouvelle version : recharger");
  assert.equal(view.reloadNeeded("abc",""),false,"réponse sans version : rester");
  assert.equal(view.reloadNeeded("","abc"),false,"version inconnue : ne pas boucler");
});
