import urllib.request,json,shlex,hashlib
from pathlib import Path
env={}
for line in Path('/etc/hindsight-arpagona/api.env').read_text().splitlines():
 if '=' in line and not line.lstrip().startswith('#'):
  k,v=line.split('=',1); parts=shlex.split(v);env[k]=parts[0] if parts else ''
req=urllib.request.Request('http://127.0.0.1:18897/v1/default/banks',headers={'Authorization':'Bearer '+env['HINDSIGHT_API_TENANT_API_KEY']})
with urllib.request.urlopen(req,timeout=10) as r:d=json.load(r)
payload=json.dumps(d,sort_keys=True,ensure_ascii=False).encode()
banks=d.get('banks',d.get('items',[])) if isinstance(d,dict) else d
out={'bank_count':len(banks),'metadata_sha256':hashlib.sha256(payload).hexdigest(),'banks':{}}
from urllib.parse import quote
for bank in banks:
 ident=bank.get('bank_id',bank.get('id'));assert isinstance(ident,str)
 state={}
 for kind in ('memories/list','documents'):
  items=[]; expected=None
  while True:
   url='http://127.0.0.1:18897/v1/default/banks/'+quote(ident,safe='')+'/'+kind+'?limit=200&offset='+str(len(items))
   req=urllib.request.Request(url,headers={'Authorization':'Bearer '+env['HINDSIGHT_API_TENANT_API_KEY']})
   with urllib.request.urlopen(req,timeout=20) as r:page=json.load(r)
   total=page['total'];assert not page.get('total_is_estimate',False)
   assert expected is None or total==expected, 'source modifiée pendant la lecture'
   expected=total; chunk=page['items'];items.extend(chunk)
   assert len(items)<=expected<=10000
   if len(items)==expected:break
   assert chunk, 'pagination incomplète'
  canonical=sorted(json.dumps(item,ensure_ascii=False,sort_keys=True) for item in items)
  assert len(canonical)==len(set(canonical)), 'doublon de pagination'
  digest=hashlib.sha256(('\n'.join(canonical)).encode()).hexdigest()
  state[kind]={'count':len(items),'sha256':digest}
 out['banks'][ident]=state
print(json.dumps(out,sort_keys=True))
