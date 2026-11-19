# ARPAGONA Core System

Surcouche produit du Hermès Agent officiel épinglé en v0.23.1 : Mission Control web, API ARPAGONA (comptes, approbations et engagements), plugin `arpagona-core` et mémoire Hindsight. Architecture retenue : une instance par client ; son isolation entre deux instances reste à démontrer.

**État : banc de test, pas de production client.** Ne pas utiliser de données réelles sans validation et garanties adaptées.

## Arborescence

- `apps/mission-control-web/` : interface web.
- `services/arpagona-api/` : API Python et tests.
- `plugins/arpagona-core/` : outils métier Hermès.
- `deploy/atlas/` : scripts et documentation du banc.
- `docs/decisions/` : décisions ; `docs/legacy/` : archives historiques.
- `tests/e2e/` : recette du banc ; `bench/` et `demo/` : matériel historique à réévaluer.

## Démarrage local

Python système et bibliothèque standard suffisent aux tests. Pour lancer l’API, utiliser une clé de banc locale (distincte de toute clé réelle) et un répertoire de données privé ; la passerelle Hermès est nécessaire au chat.

```sh
cd services/arpagona-api
mkdir -p .local && chmod 700 .local
umask 077
printf "%s\n" "cle-de-banc-fictive" > .local/hermes_key
export ARPAGONA_DB="$PWD/.local/arpagona.db"
export ARPAGONA_HERMES_KEY_FILE="$PWD/.local/hermes_key"
export ARPAGONA_STATIC_DIR="$PWD/../../apps/mission-control-web"
/usr/bin/python3 -m arpagona_api.manage add-user test --name "Test"
/usr/bin/python3 -m arpagona_api.server
```

Ouvrir http://127.0.0.1:8700 ; le mot de passe est demandé au clavier. Ne pas exposer ce serveur de test au réseau.

```sh
cd services/arpagona-api
/usr/bin/python3 -m unittest discover -s tests
```

Pour le déploiement et les limites du banc, voir [deploy/atlas/README.md](deploy/atlas/README.md). Décisions : [ADR 0007](docs/decisions/0007-surcouche-hermes.md), [ADR 0008](docs/decisions/0008-instance-par-client-memoire-hindsight.md).
