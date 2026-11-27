"""Gestion des comptes. Le mot de passe est lu au clavier ou sur l'entrée standard, jamais en argument."""
from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
import json

from .store import Store


def main() -> None:
    parser = argparse.ArgumentParser(prog="arpagona_api.manage")
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add-user", help="créer un compte")
    add.add_argument("login")
    add.add_argument("--name", required=True, help="nom affiché")
    add.add_argument("--role", choices=("admin", "membre"), default="membre",
                     help="admin ou membre (le premier compte est toujours admin)")
    add.add_argument("--password-stdin", action="store_true")
    role = sub.add_parser("set-role", help="changer le rôle d'un compte")
    role.add_argument("login")
    role.add_argument("role", choices=("admin", "membre"))
    pwd = sub.add_parser("set-password", help="changer le mot de passe d'un compte")
    pwd.add_argument("login")
    pwd.add_argument("--password-stdin", action="store_true")
    rem = sub.add_parser("del-user", help="supprimer un compte et ses données")
    rem.add_argument("login")
    status = sub.add_parser('budget-status', help='réserves et coûts inconnus (opérateur local)')
    status.add_argument('--operator', required=True, help='compte administrateur responsable')
    rec = sub.add_parser('budget-reconcile', help='rapprocher un coût inconnu avec justificatif')
    rec.add_argument('key')
    rec.add_argument('--operator', required=True)
    rec.add_argument('--cost-usd', required=True)
    rec.add_argument('--evidence', required=True, help='référence du justificatif, jamais un secret')
    rec.add_argument('--confirm', action='store_true', help='confirmer le rapprochement explicite')
    args = parser.parse_args()

    store = Store(os.environ.get("ARPAGONA_DB", "/var/lib/arpagona-api/arpagona.db"))
    try:
        _dispatch(store, args)
    finally:
        store.close()


def _dispatch(store, args):
    if args.cmd in ('budget-status', 'budget-reconcile'):
        try:
            operator = store._one('SELECT id,role FROM users WHERE login=?', (args.operator,))
            if not operator or operator['role'] != 'admin':
                sys.exit('opérateur administrateur requis')
            if args.cmd == 'budget-reconcile':
                if not args.confirm:
                    sys.exit('aucun changement : --confirm requis après vérification du justificatif')
                store.budget.reconcile_unknown(args.key, args.cost_usd, args.evidence,
                                                operator['id'], time.time())
                row = store._one('SELECT key,state,actual_micros FROM budget_entries WHERE key=?', (args.key,))
                print(json.dumps(dict(row)))
            else:
                out = store.budget.snapshot(time.time())
                out['historiques_inconnus'] = store.budget.legacy_unknown()
                out['attentes'] = [dict(r) for r in store._all(
                    "SELECT key,state,user_id,run_id FROM budget_entries WHERE state!='settled' ORDER BY created_at")]
                print(json.dumps(out, ensure_ascii=False))
        except (ValueError, PermissionError) as exc:
            sys.exit(str(exc))
        return
    if args.cmd == "del-user":
        found = store.delete_user(args.login)
        store.audit(None, "compte_supprimé" if found else "compte_introuvable", args.login)
        print(f"compte supprimé : {args.login}" if found else f"compte introuvable : {args.login}")
        sys.exit(0 if found else 1)
    if args.cmd == "set-role":
        try:
            found = store.set_role(args.login, args.role)
        except ValueError as exc:
            sys.exit(str(exc))
        store.audit(None, "role_changé" if found else "compte_introuvable", f"{args.login} {args.role}")
        print(f"rôle changé : {args.login} → {args.role}" if found else f"compte introuvable : {args.login}")
        sys.exit(0 if found else 1)
    if args.cmd == "set-password":
        password = sys.stdin.readline().rstrip("\n") if args.password_stdin else getpass.getpass("Mot de passe : ")
        try:
            found = store.set_password(args.login, password)
        except ValueError as exc:
            sys.exit(str(exc))
        store.audit(None, "mot_de_passe_changé" if found else "compte_introuvable", args.login)
        print(f"mot de passe changé : {args.login}" if found else f"compte introuvable : {args.login}")
        sys.exit(0 if found else 1)
    password = sys.stdin.readline().rstrip("\n") if args.password_stdin else getpass.getpass("Mot de passe : ")
    try:
        user_id = store.add_user(args.login, args.name, password, getattr(args, "role", "membre"))
    except ValueError as exc:
        sys.exit(str(exc))
    store.audit(user_id, "compte_créé", args.login)
    print(f"compte créé : {args.login} (id {user_id})")


if __name__ == "__main__":
    main()
