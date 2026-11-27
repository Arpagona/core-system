#!/usr/bin/env python3
"""Préparer/réinitialiser une démo synthétique d'ergonomie Kanban, jamais Atlas.

Chaque jeu porte un marqueur : un répertoire non reconnu est refusé sans écriture.
"""
import argparse
import json
from pathlib import Path
from kanban_simule import tache

ROOT=Path(__file__).resolve().parents[1]
MARKER='kanban-ergonomie-synthetic-v1'

MAIN=[
    ('Préparer la démonstration atelier','Un exemple fictif, un résultat clair et les points à valider.','ready','demo'),
    ('Vérifier le devis prototype','Comparer matière, temps machine et délai.','running','demo'),
    ('Attendre le retour fournisseur','Obtenir la confirmation du délai.','blocked','demo'),
    ('Valider le dossier de fabrication','Vérifier les hypothèses avant validation.','review','lea'),
    ('Clarifier le besoin client','Définir le résultat et choisir un responsable.','todo',None),
    ('Synthèse d’essai terminée','Résultat fictif livré et contrôlé.','done','demo'),
    ('Relance atelier planifiée','Action fictive en attente de sa date.','scheduled','lea'),
]

ADVERSARIAL=[
    ('État non prévu par l’interface','Statut inconnu, doit rester visible et honnête.','custom','demo'),
    ('https://exemple.invalide/'+'segment-sans-espace-'*12,'Jeton long sans séparation pour éprouver le débordement.','ready','demo'),
    ('Dossier volumineux','Contenu long pour éprouver le défilement du détail.\n'+('Ligne de contexte fictive. '*260),'ready','demo'),
    ('Travail déjà livré','Terminé, reste masqué par défaut.','done','demo'),
    ('Second travail livré','Terminé, reste masqué par défaut.','done','lea'),
    ('À confier à un collègue','Carte d’un collègue, en lecture seule pour demo.','ready','lea'),
    ('Besoin sans responsable','Sans responsable, prise en charge explicite.','todo',None),
]

SETS={'main':MAIN,'adversarial':ADVERSARIAL}


def prepare(data_dir,choice='main',reset=False):
    data=Path(data_dir)
    if data.is_symlink():raise SystemExit('Répertoire symbolique refusé')
    marker=data/'.fixture-kind';expected=f'{MARKER}:{choice}'
    # Compatibilité : une démo principale créée avant le découpage des jeux porte le marqueur nu.
    reconnu=marker.exists() and marker.read_text() in ({expected,MARKER} if choice=='main' else {expected})
    if data.exists() and not reconnu:
        raise SystemExit('Répertoire existant non reconnu : aucune écriture')
    if marker.exists() and not reset:
        raise SystemExit('Démo existante : --reset requis (cartes fictives uniquement)')
    data.mkdir(parents=True,exist_ok=True);data.chmod(0o700)
    def save(name,value):
        p=data/name
        if p.is_symlink():raise SystemExit('Lien symbolique refusé')
        p.write_text(value);p.chmod(0o600)
    save('.fixture-kind',expected)
    moteur='http://127.0.0.1:18842' if choice=='main' else 'http://127.0.0.1:18852'
    agents={}
    for login in ('demo','lea'):
        save(login+'-token','synthetic-'+login)
        agents[login]={'hermes_url':moteur,'hermes_key_file':str(data/'hermes_key'),'service_token_file':str(data/(login+'-token'))}
    save('agents.json',json.dumps({'agents':agents}))
    base=0x10000000 if choice=='main' else 0x20000000
    rows=[]
    for i,(title,body,status,owner) in enumerate(SETS[choice],1):
        task=tache(title,body,status);task.update(id=f't_{base+i:08x}',assignee=owner)
        if status=='blocked':task['events']=[{'kind':'blocked','payload':{'reason':'Attente de la confirmation du délai par le fournisseur.'}}]
        rows.append(task)
    save('kanban.json',json.dumps(rows,ensure_ascii=False))
    print(f'Démo synthétique « {choice} » prête : {len(rows)} cartes. Aucun compte réel ni agent exécutant.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reset',action='store_true',help='Réinitialiser les seules cartes de cette démo reconnue')
    parser.add_argument('--data',default=str(ROOT/'.local/kanban-ergonomie'),help='Répertoire de données isolé')
    parser.add_argument('--set',dest='choice',default='main',choices=sorted(SETS),help='Jeu de cartes synthétiques')
    args=parser.parse_args()
    prepare(args.data,args.choice,args.reset)
