"""Lance Mission Control en local, en une commande, sans clé ni modèle payant.

    python3 dev/lancer.py            # moteur et Kanban simulés, compte « demo »
    python3 dev/lancer.py --reset    # repart d'un état vierge
    python3 dev/lancer.py --hermes-url http://127.0.0.1:8642 --hermes-key-file ~/.secret/cle
                                     # vrai Hermès (le plugin arpagona-core doit y être installé)

Données et secrets générés dans `.local/dev/` (ignoré par Git, droits 0600/0700).
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
API = RACINE / "services/arpagona-api"
LOGIN, MOT_DE_PASSE = "demo", "demo-arpagona-2026"


def secret(fichier: Path) -> Path:
    if not fichier.exists():
        fichier.write_text(secrets.token_urlsafe(32) + "\n", encoding="ascii")
        fichier.chmod(0o600)
    return fichier


def attendre(url: str, delai: float = 15.0) -> bool:
    fin = time.time() + delai
    while time.time() < fin:
        try:
            with urllib.request.urlopen(url, timeout=1) as rep:
                if rep.status == 200:
                    return True
        except OSError:
            time.sleep(0.2)
    return False


def preparer_compte(base: Path) -> None:
    sys.path.insert(0, str(API))
    from arpagona_api.store import Store  # noqa: E402

    store = Store(str(base / "arpagona.db"))
    if not store.check_password(LOGIN, MOT_DE_PASSE):
        try:
            store.add_user(LOGIN, "Démo ARPAGONA", MOT_DE_PASSE)
        except Exception:  # compte existant avec un autre mot de passe
            store.set_password(LOGIN, MOT_DE_PASSE)


def main() -> int:
    p = argparse.ArgumentParser(description="Mission Control ARPAGONA en local (mode développement).")
    p.add_argument("--port", type=int, default=8700, help="port de Mission Control (défaut 8700)")
    p.add_argument("--moteur-port", type=int, default=18642)
    p.add_argument("--kanban-port", type=int, default=18701)
    p.add_argument("--data", type=Path, default=RACINE / ".local/dev", help="répertoire des données locales")
    p.add_argument("--reset", action="store_true", help="efface les données locales avant de démarrer")
    p.add_argument("--hermes-url", help="URL d'un vrai serveur API Hermès (sinon moteur simulé)")
    p.add_argument("--hermes-key-file", type=Path, help="clé API du vrai Hermès")
    p.add_argument("--kanban-cli", help="chemin de la CLI `hermes` pour un vrai Kanban (sinon simulé)")
    p.add_argument("--echeances", type=float, default=5.0, help="intervalle du déclencheur d'échéances (s)")
    a = p.parse_args()

    if a.reset and a.data.exists():
        shutil.rmtree(a.data)
    a.data.mkdir(parents=True, exist_ok=True)
    a.data.chmod(0o700)
    os.umask(0o077)
    service = secret(a.data / "service_token")
    jeton_kanban = secret(a.data / "kanban_token")
    if a.hermes_url:
        if not a.hermes_key_file:
            p.error("--hermes-key-file est requis avec --hermes-url")
        cle, url_moteur = a.hermes_key_file.expanduser(), a.hermes_url
    else:
        cle, url_moteur = secret(a.data / "hermes_key"), f"http://127.0.0.1:{a.moteur_port}"
    preparer_compte(a.data)

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    procs: list[subprocess.Popen] = []

    def lancer(args: list[str], extra: dict, cwd: Path = RACINE) -> None:
        procs.append(subprocess.Popen([sys.executable, *args], cwd=cwd, env={**env, **extra}))

    if not a.hermes_url:
        lancer(["dev/moteur_simule.py", "--port", str(a.moteur_port), "--cle-fichier", str(cle)],
               {"ARPAGONA_API_URL": f"http://127.0.0.1:{a.port}", "ARPAGONA_SERVICE_TOKEN_FILE": str(service)})
    lancer(["services/kanban-bridge/bridge.py"],
           {"KANBAN_TOKEN_FILE": str(jeton_kanban), "KANBAN_BRIDGE_PORT": str(a.kanban_port),
            "KANBAN_CLI": a.kanban_cli or str(RACINE / "dev/kanban_simule.py"),
            "KANBAN_SIMULE_FICHIER": str(a.data / "kanban.json")})
    lancer(["-m", "arpagona_api.server"], {
        "ARPAGONA_DB": str(a.data / "arpagona.db"), "ARPAGONA_HERMES_KEY_FILE": str(cle),
        "ARPAGONA_HERMES_URL": url_moteur, "ARPAGONA_STATIC_DIR": str(RACINE / "apps/mission-control-web"),
        "ARPAGONA_PORT": str(a.port), "ARPAGONA_BIND": "127.0.0.1",
        "ARPAGONA_SERVICE_TOKEN_FILE": str(service), "ARPAGONA_KANBAN_TOKEN_FILE": str(jeton_kanban),
        "ARPAGONA_KANBAN_URL": f"http://127.0.0.1:{a.kanban_port}",
        "ARPAGONA_TRIGGER_INTERVAL": str(a.echeances)}, cwd=API)

    def arreter(*_):
        for proc in procs:
            proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    signal.signal(signal.SIGTERM, lambda *_: (arreter(), sys.exit(0)))
    if not attendre(f"http://127.0.0.1:{a.port}/api/health"):
        arreter()
        print("Échec : Mission Control ne répond pas (port occupé ?).", file=sys.stderr)
        return 1
    print(json.dumps({"url": f"http://127.0.0.1:{a.port}", "login": LOGIN, "mot_de_passe": MOT_DE_PASSE,
                      "moteur": "réel" if a.hermes_url else "simulé",
                      "kanban": "réel" if a.kanban_cli else "simulé", "donnees": str(a.data)},
                     ensure_ascii=False), flush=True)
    print("Mission Control prêt. Ctrl+C pour arrêter.", flush=True)
    try:
        while all(proc.poll() is None for proc in procs):
            time.sleep(0.5)
        print("Un service s'est arrêté : arrêt de l'ensemble.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        arreter()


if __name__ == "__main__":
    sys.exit(main())
