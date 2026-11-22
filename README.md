# ARPAGONA Core System

Surcouche produit du Hermès Agent officiel épinglé en v0.23.1 : Mission Control web, API ARPAGONA (comptes, approbations et engagements), plugin `arpagona-core` et mémoire Hindsight. Architecture retenue : une instance par client ; son isolation entre deux instances reste à démontrer.

**État : banc de test, pas de production client.** Ne pas utiliser de données réelles sans validation et garanties adaptées.

## Essayer en 2 minutes

Python 3.10+ suffit. Aucune dépendance, aucune clé, aucun modèle payant :

```sh
python3 dev/lancer.py
```

Ouvrir http://127.0.0.1:8700, identifiant `demo`, mot de passe `demo-arpagona-2026`. Le moteur Hermès et le Kanban sont simulés ; l'API, la passerelle et le plugin sont les vrais. Puis écrire : « Relance le client Dupont dans 30 secondes au sujet du devis de 200 supports ».

Guide complet : [docs/DEMARRAGE-DEVELOPPEUR.md](docs/DEMARRAGE-DEVELOPPEUR.md). Brancher une brique : [docs/INTEGRER-UNE-BRIQUE.md](docs/INTEGRER-UNE-BRIQUE.md). État et lots proposés : [docs/FEUILLE-DE-ROUTE.md](docs/FEUILLE-DE-ROUTE.md).

## Arborescence

- `apps/mission-control-web/` : interface web (sans framework ni build).
- `services/arpagona-api/` : API Python et tests.
- `services/kanban-bridge/` : passerelle vers le Kanban officiel d'Hermès.
- `plugins/arpagona-core/` : outils métier Hermès (engagements, brouillons ; aucun envoi).
- `dev/` : lanceur local, moteur et Kanban simulés. `tests/dev/` : parcours complet.
- `deploy/atlas/` : scripts et documentation du banc.
- `docs/decisions/` : décisions ; `docs/legacy/` : archives historiques.
- `tests/e2e/` : recette du banc réel ; `bench/` et `demo/` : matériel historique à réévaluer.

## Tests

Les commandes de la CI sont listées dans [docs/DEMARRAGE-DEVELOPPEUR.md](docs/DEMARRAGE-DEVELOPPEUR.md#tester). Le parcours complet local prend environ 2 secondes :

```sh
python3 -m unittest discover -s tests/dev -v
```

## Mission Control

- Chat au centre : une conversation unique par compte, conservée entre les visites.
- Kanban : celui de l'instance Hermès du client, lu et modifié via `services/kanban-bridge/` (service local 127.0.0.1:8701, jeton dédié, liste blanche d'opérations sur la CLI officielle `hermes kanban`). Les cartes créées depuis l'interface n'ont pas d'affectation : aucun agent n'est déclenché.
- Approbations et Engagements en onglets ; mobile : chat d'abord.

### Accès réseau local (banc de test uniquement)

`sudo bash /opt/arpagona/current/deploy/atlas/enable-mission-control-lan.sh` ouvre le port 8700 au seul réseau 192.168.68.0/24 (table nftables `arpagona_lan`, sans toucher SSH) et arme un retour arrière automatique à 180 s ; arrêter `arpagona-lan-rollback.timer` après vérification. Accès en HTTP, cookie non `Secure` : **mode test**. HTTPS obligatoire avant tout client.

Comptes : `python3 -m arpagona_api.manage add-user|set-password|del-user <login> --password-stdin` (en tant que `arpagona-api`).

Pour le déploiement et les limites du banc, voir [deploy/atlas/README.md](deploy/atlas/README.md). Décisions : [ADR 0007](docs/decisions/0007-surcouche-hermes.md), [ADR 0008](docs/decisions/0008-instance-par-client-memoire-hindsight.md).
