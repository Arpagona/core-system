import sqlite3,hashlib,json,os,stat
from pathlib import Path
audit_cutoff=globals().get('AUDIT_CUTOFF')
out={'audit_cutoff_utc':audit_cutoff,'release':str(Path('/opt/arpagona/current').resolve()),'databases':{},'files':{}}
for p in (Path('/var/lib/arpagona-api/arpagona.db'),Path('/srv/hermes-arpagona/.hermes/kanban.db')):
 if not p.exists():continue
 db=sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True);db.execute('BEGIN')
 tables=[x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if x[0] in {'users','sessions','conversations','messages','engagements','drafts','missions','audit','tasks','comments','dependencies','attachments','projects'}]
 d={}
 for table in tables:
  columns='*'  # empreinte agrégée, aucun champ d'authentification n'est imprimé
  where=' WHERE ts<=?' if table=='audit' and audit_cutoff is not None else ''
  args=(audit_cutoff,) if where else ()
  rows=db.execute('SELECT '+columns+' FROM "'+table+'"'+where+' ORDER BY rowid',args).fetchall()
  payload=json.dumps(rows,ensure_ascii=False,default=lambda x: x.hex() if isinstance(x,bytes) else str(x)).encode()
  d[table]={'count':len(rows),'sha256':hashlib.sha256(payload).hexdigest()}
 d['integrity']=db.execute('PRAGMA integrity_check').fetchone()[0]
 out['databases'][str(p)]=d;db.rollback();db.close()
for p in (Path('/opt/arpagona/current/apps/mission-control-web/app.js'),Path('/opt/arpagona/current/apps/mission-control-web/style.css'),Path('/etc/arpagona-tls/ca.crt')):
 if p.is_file():out['files'][str(p)]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mode':oct(stat.S_IMODE(p.stat().st_mode))}
print(json.dumps(out,sort_keys=True))
