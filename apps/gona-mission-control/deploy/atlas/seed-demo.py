#!/usr/bin/env python3
"""Donnees FICTIVES de demonstration pour le banc Atlas (Kanban + une decision en attente).
Usage (en tant que gona-mc) : seed-demo.py [--reset]. Ne touche qu'a /var/lib/gona-mission-control."""
import json, os, sqlite3, sys, time
VAR = os.environ.get('GONA_MC_VAR', '/var/lib/gona-mission-control')
DB = VAR + '/kanban.db'
LOOP = VAR + '/profile/refonte/loop'
SCHEMA = """
create table if not exists tasks(id text primary key,title text not null,body text,assignee text,status text not null,priority integer default 0,
 created_by text,created_at integer not null,started_at integer,completed_at integer,workspace_kind text not null default 'scratch',workspace_path text,
 claim_lock text,claim_expires integer,tenant text,result text,idempotency_key text,consecutive_failures integer not null default 0,worker_pid integer,
 last_failure_error text,max_runtime_seconds integer,last_heartbeat_at integer,current_run_id integer,workflow_template_id text,current_step_key text,
 skills text,max_retries integer,branch_name text,model_override text,session_id text,goal_mode integer not null default 0,goal_max_turns integer,
 project_id text,block_kind text,block_recurrences integer not null default 0,provider_override text,reasoning_effort text,completion_contract text,worker_started_at integer);
create table if not exists task_comments(id integer primary key autoincrement,task_id text not null,author text not null,body text not null,created_at integer not null);
create table if not exists task_events(id integer primary key autoincrement,task_id text not null,run_id integer,kind text not null,payload text,created_at integer not null);
create table if not exists task_links(parent_id text not null,child_id text not null,primary key(parent_id,child_id));
"""
H = 3600; now = int(time.time())
CARDS = [  # id, titre, statut, tenant, assignee, age(h), block_kind, corps
 ('t_dede0001', '[DEMO] Ombrelle - Pilote Dupont Mecanique', 'ready', 'arpagona', None, 72, None, 'Projet fictif : pilote sur 3 pieces CNC. Donnees de demonstration.'),
 ('t_dede0002', '[DEMO] Relancer Dupont sur le devis 2026-041', 'blocked', 'arpagona', 'gpt5', 30, 'needs_input', 'Brouillon de relance pret. Besoin de ton accord avant envoi.'),
 ('t_dede0003', '[DEMO] Analyser le plan P-1042 (rev B vs rev C)', 'done', 'arpagona', 'gpt5', 50, None, 'Comparaison terminee : 2 cotes modifiees, tolerance resserree sur le percage A.'),
 ('t_dede0004', '[DEMO] Rediger la note de cadrage client', 'running', 'arpagona', 'gpt5', 5, None, 'Redaction en cours (donnee fictive).'),
 ('t_dede0005', '[DEMO] Preparer la serie de 100 supports', 'ready', 'arpagona', 'gpt5', 20, None, 'Chiffrage CNC/FDM a produire apres validation du devis.'),
 ('t_dede0006', '[DEMO] Verifier la facture fournisseur Acier-Ouest', 'todo', 'admin', None, 8, None, 'Controle des montants. Donnee fictive.'),
 ('t_dede0007', '[DEMO] Mettre a jour le catalogue de pieces', 'done', 'veille', 'gpt5', 90, None, 'Catalogue synchronise (12 references).'),
]
GATE = {'t_dede0002': {'question': 'Veux-tu que j\'envoie la relance a Dupont Mecanique sur le devis 2026-041 ?',
   'oui': {'effect': 'close', 'note': 'La relance est marquee a envoyer (demo : aucun envoi reel).'},
   'non': {'effect': 'reopen', 'note': 'La relance est reportee (demo).'}}}
def main():
    os.makedirs(LOOP, exist_ok=True)
    if '--reset' in sys.argv and os.path.exists(DB): os.remove(DB)
    c = sqlite3.connect(DB); c.executescript(SCHEMA)
    for i, t, st, tn, asg, age, bk, body in CARDS:
        ts = now - age * H
        c.execute('insert or ignore into tasks(id,title,body,assignee,status,created_by,created_at,started_at,completed_at,tenant,block_kind,result) values(?,?,?,?,?,?,?,?,?,?,?,?)',
                  (i, t, body, asg, st, 'demo', ts, ts + 600 if st in ('running', 'done', 'blocked') else None,
                   ts + 4 * H if st == 'done' else None, tn, bk, 'Termine (demo).' if st == 'done' else None))
    c.execute("insert or ignore into task_links values('t_dede0001','t_dede0002')")
    if not c.execute("select 1 from task_comments where task_id='t_dede0002'").fetchone():
        c.execute("insert into task_comments(task_id,author,body,created_at) values('t_dede0002','gpt5','BLOCKED: Brouillon de relance redige pour Dupont Mecanique (devis 2026-041). Envoi apres accord. [donnee fictive]',?)", (now - 6 * H,))
    c.commit(); c.close()
    m = LOOP + '/kanban_map.json'
    if not os.path.exists(m):
        open(m, 'w').write(json.dumps({'version': 1, 'umbrellas': {'arpagona': 't_dede0001'},
            'projects': {'dupont': {'card': 't_dede0001', 'mission': '01-arpagona.md', 'actions': [], 'tenant': 'arpagona'}}}, indent=1))
    p = LOOP + '/gate.json'
    if not os.path.exists(p): open(p, 'w').write(json.dumps(GATE, ensure_ascii=False, indent=1))
    print('ok', len(CARDS), 'cartes fictives,', len(GATE), 'decision en attente')
main()
