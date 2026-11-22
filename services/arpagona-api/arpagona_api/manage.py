"""Gestion des comptes. Le mot de passe est lu au clavier ou sur l'entrée standard, jamais en argument."""
from __future__ import annotations

import argparse
import getpass
import os
import sys

from .store import Store


def main() -> None:
    parser = argparse.ArgumentParser(prog="arpagona_api.manage")
    sub = parser.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add-user", help="créer un compte")
    add.add_argument("login")
    add.add_argument("--name", required=True, help="nom affiché")
    add.add_argument("--password-stdin", action="store_true")
    pwd = sub.add_parser("set-password", help="changer le mot de passe d'un compte")
    pwd.add_argument("login")
    pwd.add_argument("--password-stdin", action="store_true")
    rem = sub.add_parser("del-user", help="supprimer un compte et ses données")
    rem.add_argument("login")
    args = parser.parse_args()

    store = Store(os.environ.get("ARPAGONA_DB", "/var/lib/arpagona-api/arpagona.db"))
    if args.cmd == "del-user":
        found = store.delete_user(args.login)
        store.audit(None, "compte_supprimé" if found else "compte_introuvable", args.login)
        print(f"compte supprimé : {args.login}" if found else f"compte introuvable : {args.login}")
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
        user_id = store.add_user(args.login, args.name, password)
    except ValueError as exc:
        sys.exit(str(exc))
    store.audit(user_id, "compte_créé", args.login)
    print(f"compte créé : {args.login} (id {user_id})")


if __name__ == "__main__":
    main()
