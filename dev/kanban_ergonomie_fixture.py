#!/usr/bin/env python3
"""Préparer/réinitialiser uniquement la démo synthétique d'ergonomie, jamais Atlas."""
import argparse
import json
from pathlib import Path
from kanban_simule import tache

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'.local/kanban-ergonomie'
MARKER='kanban-ergonomie-synthetic-v1'


def prepare(reset=False):
    if DATA.is_symlink():
        raise SystemExit('Répertoire symbolique refusé')
    marker=DATA/'.fixture-kind'
    if DATA.exists() and not (marker.exists() and marker.read_text()==MARKER):
        raise SystemExit('Répertoire existant non reconnu : aucune écriture')
    if marker.exists() and not reset:
        raise SystemExit('Démo existante : --reset requis (cartes fictives uniquement)')
    DATA.mkdir(parents=True,exist_ok=True);DATA.chmod(0o700)
    def save(name,value):
        p=DATA/name
        if p.is_symlink():raise SystemExit('Lien symbolique refusé')
        p.write_text(value);p.chmod(0o600)
    save('.fixture-kind',MARKER)
    agents={}
    for login in ('demo','lea'):
        save(login+'-token','synthetic-'+login)
        agents[login]={'hermes_url':'http://127.0.0.1:18842','hermes_key_file':str(DATA/'hermes_key'),'service_token_file':str(DATA/(login+'-token'))}
    save('agents.json',json.dumps({'agents':agents}))
    specs=[
        ('Préparer la démonstration atelier','Un exemple fictif, un résultat clair et les points à valider.','ready','demo'),
        ('Vérifier le devis prototype','Comparer matière, temps machine et délai.','running','demo'),
        ('Attendre le retour fournisseur','Obtenir la confirmation du délai.','blocked','demo'),
        ('Valider le dossier de fabrication','Vérifier les hypothèses avant validation.','review','lea'),
        ('Clarifier le besoin client','Définir le résultat et choisir un responsable.','todo',None),
        ('Synthèse d’essai terminée','Résultat fictif livré et contrôlé.','done','demo'),
        ('Relance atelier planifiée','Action fictive en attente de sa date.','scheduled','lea'),
    ]
    rows=[]
    for i,(title,body,status,owner) in enumerate(specs,1):
        task=tache(title,body,status);task.update(id=f't_{0x10000000+i:08x}',assignee=owner)
        if status=='blocked':task['events']=[{'kind':'blocked','payload':{'reason':'Attente de la confirmation du délai par le fournisseur.'}}]
        rows.append(task)
    save('kanban.json',json.dumps(rows,ensure_ascii=False))
    print(f'Démo synthétique prête : {len(rows)} cartes. Aucun compte réel ni agent exécutant.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reset',action='store_true',help='Réinitialiser les seules cartes de cette démo reconnue')
    prepare(parser.parse_args().reset)
