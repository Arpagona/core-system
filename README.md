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

## Mission Control

- Chat au centre : une conversation unique par compte, conservée entre les visites.
- Kanban : celui de l'instance Hermès du client, lu et modifié via `services/kanban-bridge/` (service local 127.0.0.1:8701, jeton dédié, liste blanche d'opérations sur la CLI officielle `hermes kanban`). Les cartes créées depuis l'interface n'ont pas d'affectation : aucun agent n'est déclenché.
- Approbations et Engagements en onglets ; mobile : chat d'abord.

### Accès réseau local (banc de test uniquement)

`sudo bash /opt/arpagona/current/deploy/atlas/enable-mission-control-lan.sh` ouvre le port 8700 au seul réseau 192.168.68.0/24 (table nftables `arpagona_lan`, sans toucher SSH) et arme un retour arrière automatique à 180 s ; arrêter `arpagona-lan-rollback.timer` après vérification. Accès en HTTP, cookie non `Secure` : **mode test**. HTTPS obligatoire avant tout client.

Comptes : `python3 -m arpagona_api.manage add-user|set-password|del-user <login> --password-stdin` (en tant que `arpagona-api`).

Pour le déploiement et les limites du banc, voir [deploy/atlas/README.md](deploy/atlas/README.md). Décisions : [ADR 0007](docs/decisions/0007-surcouche-hermes.md), [ADR 0008](docs/decisions/0008-instance-par-client-memoire-hindsight.md).
