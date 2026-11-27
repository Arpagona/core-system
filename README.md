# ARPAGONA Core System

Surcouche produit du Hermès Agent officiel épinglé en v0.23.1 : Mission Control web, API ARPAGONA (comptes, approbations et engagements), plugin `arpagona-core` et mémoire Hindsight. Architecture retenue : une instance par client ; son isolation entre deux instances reste à démontrer.

**État : banc de test, pas de production client.** Ne pas utiliser de données réelles sans validation et garanties adaptées. Le cahier des charges produit de référence est [`docs/CDC-PRODUIT-v2.0.md`](docs/CDC-PRODUIT-v2.0.md) (ARP-PROD-CDC-002).

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
- **Missions** : chaque demande devient une mission suivie (statut, durée, coût, résultat), arrêtable. Consommation et réservations persistantes avant démarrage, appliquées côté API. Ce contrôle d’admission ne garantit pas le plafond de facturation d’un moteur déjà lancé.
- **Approbations** : un brouillon porte une empreinte SHA-256 du destinataire, de l’objet, du corps exact et de l’expéditeur approuvés ; l'envoi courriel est un second geste explicite, refusé si le contenu a changé. Un seul canal sortant : le courriel (SMTP).
- **Journal** : les 200 derniers événements (connexion, décision, envoi, refus), sans secret. Visible en entier par l'admin, limité à ses propres événements pour un membre.
- **Rôles** : `admin` (comptes, export, journal complet) et `membre`. Le premier compte d'une instance est toujours admin.
- **Export** : JSON complet des données métier, réservé à l'admin.
- Kanban : celui de l'instance Hermès du client, lu et modifié via `services/kanban-bridge/` (service local 127.0.0.1:8701, jeton dédié, liste blanche d'opérations sur la CLI officielle `hermes kanban`). Les cartes créées depuis l'interface n'ont pas d'affectation : aucun agent n'est déclenché.
- Engagements en onglet ; mobile : chat d'abord. Dictée et lecture via le navigateur (aucun audio conservé).

Configuration de l'envoi : `deploy/atlas/mail.env.example`. Sans SMTP configuré, l'API démarre et l'interface indique que l'envoi est indisponible.

### Accès réseau local (banc de test uniquement)

Le banc existant utilise HTTPS sur `https://192.168.68.240:8700/` et, via WireGuard, `https://10.68.100.1:8700/`. API interne sur loopback ; certificat signé par la CA locale ARPAGONA à installer dans les appareils autorisés. Installation, vérifications et rollback : [TLS local](deploy/atlas/tls-local/README.md). Le script historique `enable-mission-control-lan.sh` concerne un banc HTTP de test ; ne pas l’appliquer comme procédure normale à une instance HTTPS.

Garde budgétaire et rapprochement des coûts inconnus : [contrat opérateur](docs/BUDGET-ADMISSION.md).

Comptes : `python3 -m arpagona_api.manage add-user|set-password|del-user <login> --password-stdin` (en tant que `arpagona-api`).

Pour le déploiement et les limites du banc, voir [deploy/atlas/README.md](deploy/atlas/README.md). Accès distant des contributeurs : [deploy/atlas/ACCES-DISTANT.md](deploy/atlas/ACCES-DISTANT.md). Décisions : [ADR 0007](docs/decisions/0007-surcouche-hermes.md), [ADR 0008](docs/decisions/0008-instance-par-client-memoire-hindsight.md).
