"""Réparation réservée à la COPIE offline, après contrôle d'identité par l'hôte.

Ne réinitialise jamais PostgreSQL. Utilise les exécutables et les données restaurés.
Contourne uniquement les métadonnées pg0 inutilisables ; secrets jamais imprimés.
"""
import ast
import os
from pathlib import Path
import shlex
import subprocess
import time
from urllib.parse import urlsplit, unquote, quote


def recover():
    base = Path('/srv/hindsight-arpagona')
    data = base/'.pg0/instances/hindsight/data'
    if not (data/'PG_VERSION').is_file() or not (data/'base').is_dir():
        raise RuntimeError('cluster PostgreSQL existant obligatoire ; aucun initdb autorisé')
    env = {}
    for line in Path('/etc/hindsight-arpagona/api.env').read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k,v=line.split('=',1); parts=shlex.split(v);env[k]=parts[0] if parts else ''
    original = env.get('HINDSIGHT_API_DATABASE_URL','pg0')
    if original != 'pg0' and not original.startswith('pg0://'):
        raise RuntimeError('cette recette ne doit pas remplacer une base externe')
    parsed = urlsplit(original if original != 'pg0' else 'pg0://hindsight')
    if parsed.hostname != 'hindsight':
        raise RuntimeError('instance pg0 différente : réparation refusée')
    defaults = {}
    source = next((base/'venv/lib').glob('python*/site-packages/hindsight_api/pg0.py'))
    for node in ast.parse(source.read_text()).body:
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id in ('DEFAULT_USERNAME','DEFAULT_DATABASE'):
                    defaults[target.id]=ast.literal_eval(node.value)
    username=unquote(parsed.username) if parsed.username else defaults['DEFAULT_USERNAME']
    database=defaults['DEFAULT_DATABASE']
    uid=data.stat().st_uid
    run=lambda *a:subprocess.run(a,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=40)
    # Éviter une course entre le wrapper pg0 et le démarrage natif.
    run('systemctl','stop','hindsight-arpagona.service')
    if subprocess.run(['systemctl','is-active','--quiet','hindsight-arpagona.service']).returncode==0:
        raise RuntimeError('service Hindsight encore actif')
    ctls=list((base/'.pg0/installation').glob('*/bin/pg_ctl'))
    matching=[p for p in ctls if p.parent.parent.name.split('.')[0]==(data/'PG_VERSION').read_text().strip()]
    if len(matching)!=1:
        raise RuntimeError('exécutable PostgreSQL de même version introuvable ou ambigu')
    ctl=matching[0]
    # Ne pas retirer un verrou d'un serveur existant. pg_ctl status n'affiche pas de secret.
    status=subprocess.run(['runuser','-u','hindsight-arpagona','--','env','LD_LIBRARY_PATH='+str(ctl.parent.parent/'lib'),str(ctl),'-D',str(data),'status'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if status.returncode==0:
        raise RuntimeError('PostgreSQL est déjà démarré : aucune deuxième instance autorisée')
    pidfile=data/'postmaster.pid'
    if pidfile.exists() and not pidfile.read_text().strip():
        pidfile.rename(data/('postmaster.pid.empty-preserved-'+str(time.time_ns())))
    # Socket privé + authentification OS : aucun secret deviné ou réinitialisé.
    import re
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]*',username):
        raise RuntimeError('rôle PostgreSQL non pris en charge par la recette peer')
    sock=base/'.pg0/recovery-socket'
    sock.mkdir(mode=0o700,exist_ok=True);os.chown(sock,uid,data.stat().st_gid);sock.chmod(0o700)
    hba=sock/'pg_hba.conf';ident=sock/'pg_ident.conf'
    hba.write_text('local all '+username+' peer map=recovery\n')
    ident.write_text('recovery hindsight-arpagona '+username+'\n')
    for f in (hba,ident):f.chmod(0o600);os.chown(f,uid,data.stat().st_gid)
    options=shlex.join(['-h','','-p','5432','-k',str(sock),'-c','hba_file='+str(hba),'-c','ident_file='+str(ident)])
    # -l utilise un vrai fichier, sans pipe hérité. TCP est désactivé.
    run('runuser','-u','hindsight-arpagona','--','env','LD_LIBRARY_PATH='+str(ctl.parent.parent/'lib'),str(ctl),'-D',str(data),'-l',str(data/'log/recovery-native.log'),'-o',options,'-w','-t','25','start')
    url='postgresql://'+quote(username,safe='')+'@/'+quote(database,safe='')+'?host='+quote(str(sock),safe='')
    runtime=Path('/run/hindsight-recovery.env')
    # systemd lit le fichier en root, avant de changer d'utilisateur.
    fd=os.open(runtime,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:f.write('HINDSIGHT_API_DATABASE_URL='+shlex.quote(url)+'\n')
    runtime.chmod(0o600)
    drop=Path('/run/systemd/system/hindsight-arpagona.service.d')
    drop.mkdir(parents=True,exist_ok=True)
    (drop/'95-recovery-database.conf').write_text('[Service]\nEnvironmentFile=/run/hindsight-recovery.env\n')
    run('systemctl','daemon-reload')
    return {'native_postgres_existing_data':True,'metadata_reinitialized':False}


if __name__=='__main__':
    import json
    print(json.dumps(recover()))
