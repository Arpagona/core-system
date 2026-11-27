#!/usr/bin/env python3
"""Recette Proxmox locale : restaurer une copie neuve, sans réseau ni effet externe.

À lancer sur l'hyperviseur, jamais dans une VM. Ne programme aucune sauvegarde.
La source n'est jamais arrêtée ; la copie est arrêtée à la fin, succès ou échec.
"""
import argparse
import base64
import zlib
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time


def target_guard(source, target, existing):
    if source < 100 or target < 100 or target == source or target in existing:
        raise ValueError('cible existante ou protégée : aucun remplacement autorisé')


def network_keys(config):
    return sorted(k for k in config if re.fullmatch(r'net\d+', k))


def isolation_guard(config, vmid):
    unsafe = [k for k in config if re.fullmatch(r'(hostpci|usb|virtiofs)\d+',k) or k in {'args','hookscript','cicustom'}]
    if unsafe or network_keys(config) or config.get('onboot',0):
        raise ValueError('matériel ou réseau non isolé')
    for key,value in config.items():
        if re.fullmatch(r'(scsi|sata|ide|virtio|efidisk|tpmstate)\d+',key):
            vol=str(value).split(',')[0]
            if not vol.startswith('local-lvm:vm-'+str(vmid)+'-'):
                raise ValueError('volume non privé à la copie : '+key)


def archive_guard(path, expected, source=None):
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise ValueError('archive régulière absolue requise')
    match = re.fullmatch(r'vzdump-qemu-([1-9][0-9]*)-[0-9]{4}_[0-9]{2}_[0-9]{2}-[0-9]{2}_[0-9]{2}_[0-9]{2}\.vma\.zst', path.name)
    if not match or (source is not None and int(match.group(1)) != source):
        raise ValueError('nom Proxmox original requis, avec le VMID source exact')
    if not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('SHA-256 exact en minuscules requis')
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4*1024*1024), b''):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError('archive différente : restauration refusée')


def command(*args, timeout=600):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=timeout).stdout


def wire_program(program):
    # ASCII seul dans les arguments QGA : préserver exactement le programme UTF-8.
    payload = base64.b64encode(zlib.compress(program.encode('utf-8'))).decode('ascii')
    return "import base64,zlib;exec(zlib.decompress(base64.b64decode("+repr(payload)+")))"


class GuestError(RuntimeError):
    def __init__(self, message, details):
        super().__init__(message)
        self.details = details


def guest(vmid, program):
    # Un lancement unique. Un timeout de lancement est INCERTAIN, sans rejeu.
    try:
        launch = json.loads(command('qm', 'guest', 'exec', str(vmid), '--synchronous', '0',
                                   '--', '/usr/bin/python3', '-c', wire_program(program), timeout=30))
        pid = launch['pid']
        deadline = time.monotonic()+420
        while True:
            result = json.loads(command('qm', 'guest', 'exec-status', str(vmid), str(pid), timeout=20))
            if result.get('exited'):
                break
            if time.monotonic() >= deadline:
                raise GuestError('contrôle invité non terminé', {'pid':pid,'state':'uncertain'})
            time.sleep(2)
    except subprocess.CalledProcessError as exc:
        raise GuestError('transport QGA non confirmé, aucun rejeu',
                         {'state':'uncertain','stderr':exc.stderr,'stdout':exc.stdout}) from None
    if result.get('exitcode') != 0 or result.get('signal') or result.get('out-truncated'):
        raise GuestError('contrôle invité en échec ou sortie tronquée', result)
    return json.loads(result.get('out-data', 'null'))


SETUP = r'''
import subprocess,urllib.request,urllib.error,ssl,json,time
from pathlib import Path
run=lambda *a:subprocess.run(a,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
# Le matériel réseau a été RETIRÉ avant le premier boot. Adresses locales
# factices pour tester nginx/TLS ; pas de route vers le LAN ni Internet.
links=json.loads(subprocess.check_output(['ip','-j','link'],text=True))
if not any(link['ifname']=='proof0' for link in links):
 run('ip','link','add','proof0','type','dummy')
run('ip','addr','replace','192.168.68.240/32','dev','proof0')
run('ip','addr','replace','10.68.100.1/32','dev','proof0')
run('ip','link','set','proof0','up')
# Uniquement dans la copie isolée : utiliser les modèles déjà sauvegardés.
# Sans cela Hugging Face tente des HEAD réseau et retarde le démarrage.
p=Path('/run/systemd/system/hindsight-arpagona.service.d')
p.mkdir(parents=True,exist_ok=True)
(p/'90-recovery-offline.conf').write_text('[Service]\nEnvironment=HF_HUB_OFFLINE=1\nEnvironment=TRANSFORMERS_OFFLINE=1\nEnvironment=HF_DATASETS_OFFLINE=1\nEnvironment=HF_HUB_DISABLE_TELEMETRY=1\n')
run('systemctl','daemon-reload')
run('systemctl','restart','--no-block','hindsight-arpagona.service')
units=['arpagona-api.service','arpagona-tls.service','hindsight-arpagona.service','hindsight-gate.service','hermes-arpagona-gateway.service']
subprocess.run(['systemctl','reset-failed']+units,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
run('systemctl','start','--no-block',*units)
ctx=ssl.create_default_context(cafile='/etc/arpagona-tls/ca.crt')
urls={'api':('http://127.0.0.1:8700/api/health',200),
      'https':('https://192.168.68.240:8700/',200),
      'anonymous':('https://192.168.68.240:8700/api/me',401),
      'memory':('http://127.0.0.1:18897/version',200)}
def status(url):
 try:
  with urllib.request.urlopen(url,timeout=2,context=ctx) as r:return r.status
 except urllib.error.HTTPError as e:
  code=e.code;e.close();return code
 except Exception:return None
end=time.monotonic()+360
while True:
 seen={name:status(url) for name,(url,_) in urls.items()}
 if all(seen[name]==want for name,(_,want) in urls.items()):break
 if time.monotonic()>end:raise RuntimeError('services non prêts : '+json.dumps(seen))
 time.sleep(3)
active={u:subprocess.run(['systemctl','is-active',u],capture_output=True,text=True).stdout.strip() for u in units}
assert all(v=='active' for v in active.values()),'service non actif'
print(json.dumps({'http':seen,'units':active,'physical_network_present':False}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--source-vmid', type=int, default=100)
    parser.add_argument('--target-vmid', type=int, required=True)
    parser.add_argument('--postgres-helper', type=Path, default=Path(__file__).with_name('recovery_postgres.py'))
    parser.add_argument('--data-helper', type=Path, required=True)
    parser.add_argument('--memory-helper', type=Path, required=True)
    parser.add_argument('--expected-data', type=Path, required=True)
    parser.add_argument('--expected-memory', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({'dry_run':True,'source':args.source_vmid,'target':args.target_vmid,'network':'removed before first boot'}))
        return
    if os.geteuid() != 0:
        raise PermissionError('accès administrateur Proxmox requis')
    node = os.uname().nodename.split('.')[0]
    if not re.fullmatch(r'[A-Za-z0-9_-]+', node):
        raise ValueError('nom de nœud invalide')
    vmid, source = args.target_vmid, args.source_vmid
    existing = {r['vmid'] for r in json.loads(command('pvesh','get','/cluster/resources','--type','vm','--output-format','json'))}
    target_guard(source,vmid,existing)
    archive_guard(args.archive,args.sha256,source)
    expected_data = json.loads(args.expected_data.read_text())
    expected_memory = json.loads(args.expected_memory.read_text())
    helpers = [args.data_helper.read_text(), args.memory_helper.read_text()]
    import math
    cutoff = expected_data.get('audit_cutoff_utc')
    if cutoff is not None and (isinstance(cutoff,bool) or not isinstance(cutoff,(int,float)) or not math.isfinite(cutoff) or cutoff<0):
        raise ValueError('date de référence audit invalide')
    helpers[0] = 'AUDIT_CUTOFF='+repr(cutoff)+'\n'+helpers[0]
    postgres_helper = args.postgres_helper.read_text()
    # Le reçu ne peut pas écraser une preuve précédente.
    with args.receipt.open('x') as f: f.write('{}')
    args.receipt.chmod(0o600)
    started = time.monotonic()
    label = f'agentcore-restore-proof-{vmid}'
    receipt = {'source':source,'target':vmid,'archive_sha256':args.sha256,'passed':False,
               'source_status_before':command('qm','status',str(source)).strip()}
    booted = False
    def interrupted(signum, frame):
        raise InterruptedError('restauration interrompue')
    for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(signum, interrupted)
    def config():
        return json.loads(command('pvesh','get',f'/nodes/{node}/qemu/{vmid}/config','--output-format','json'))
    try:
        command('qmrestore',str(args.archive),str(vmid),'--storage','local-lvm','--unique','1','--start','0')
        nets = network_keys(config())
        options = ['--delete',','.join(nets)] if nets else []
        command('qm','set',str(vmid),'--name',label,'--onboot','0',*options)
        conf = config()
        if network_keys(conf) or conf.get('onboot',0) or conf.get('name') != label:
            raise RuntimeError('isolation avant boot non confirmée')
        isolation_guard(conf,vmid)
        receipt['network_devices_before_boot'] = []
        command('qm','start',str(vmid))
        booted = True
        until = time.monotonic()+240
        while True:
            try:command('qm','agent',str(vmid),'ping',timeout=15);break
            except subprocess.SubprocessError:
                if time.monotonic()>until:raise
                time.sleep(3)
        receipt['postgres_recovery'] = guest(vmid, postgres_helper)
        receipt['services'] = guest(vmid, SETUP)
        actual_data = guest(vmid,helpers[0])
        actual_memory = guest(vmid,helpers[1])
        receipt['data_match'] = actual_data == expected_data
        receipt['memory_match'] = actual_memory == expected_memory
        receipt['actual_data'] = actual_data
        receipt['actual_memory'] = actual_memory
        receipt['passed'] = receipt['data_match'] and receipt['memory_match']
        if not receipt['passed']:
            raise RuntimeError('données restaurées différentes : recette NON conforme')
    except Exception as exc:
        receipt['error'] = {'type':type(exc).__name__,'message':str(exc),
                            'details':getattr(exc,'details',None)}
        if isinstance(exc, subprocess.CalledProcessError):
            receipt['error']['stderr'] = exc.stderr
        raise
    finally:
        receipt['restore_seconds'] = round(time.monotonic()-started,3)
        cleanup_errors = []
        if booted:
            try:
                if config().get('name') != label:
                    raise RuntimeError('identité copie différente : arrêt automatique refusé')
                command('qm','stop',str(vmid),timeout=60)
            except Exception as exc:
                cleanup_errors.append(type(exc).__name__)
        for which, ident in (('target',vmid),('source',source)):
            try:
                receipt[which+'_status_after'] = command('qm','status',str(ident)).strip()
            except subprocess.SubprocessError as exc:
                receipt[which+'_status_after'] = 'unknown'
                cleanup_errors.append(type(exc).__name__)
        if receipt.get('target_status_after') != 'status: stopped' or receipt.get('source_status_after') != receipt['source_status_before']:
            cleanup_errors.append('etat_final_non_conforme')
        if cleanup_errors:
            receipt['cleanup_errors'] = cleanup_errors
            receipt['passed'] = False
        args.receipt.write_text(json.dumps(receipt,indent=2,sort_keys=True))
        args.receipt.chmod(0o600)
    if not receipt['passed']:
        raise RuntimeError('recette ou nettoyage non confirmé : consulter le reçu privé')
    print(json.dumps(receipt,sort_keys=True))


if __name__ == '__main__':
    main()
