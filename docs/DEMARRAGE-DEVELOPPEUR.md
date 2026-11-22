# Démarrage développeur

Objectif : cloner le dépôt et voir Mission Control fonctionner en moins de 5 minutes, sans clé, sans modèle payant, sans Hermès installé.

## Prérequis

- Git et Python 3.10 ou plus récent (bibliothèque standard seulement, aucune dépendance à installer). Testé avec 3.10, 3.11 et 3.14.
- Node.js : facultatif, seulement pour `node --check` sur le JavaScript.
- Linux ou macOS conseillé. Windows : le mode local doit fonctionner, mais il n'est pas testé.

## Lancer

```sh
git clone git@github.com:Arpagona/core-system.git
cd core-system
python3 dev/lancer.py
```

Le lanceur affiche l'URL et les identifiants :

- URL : http://127.0.0.1:8700
- Identifiant : `demo`
- Mot de passe : `demo-arpagona-2026`

Options utiles :

- `--port 8710` : autre port si 8700 est occupé.
- `--reset` : efface les données locales (`.local/dev/`) et repart de zéro.
- `--echeances 5` : intervalle du déclencheur d'échéances, en secondes.

`Ctrl+C` arrête les trois services.

## Ce qui tourne en mode local

| Service | Rôle | Mode local |
|---|---|---|
| `services/arpagona-api` | API et Mission Control (seule surface navigateur) | **réel** |
| `services/kanban-bridge` | passerelle vers `hermes kanban` | **réelle**, branchée sur `dev/kanban_simule.py` |
| `plugins/arpagona-core` | outils métier de l'agent (engagements, brouillons) | **réel**, appelé par le moteur simulé |
| Hermès Agent | moteur de l'agent | **simulé** : `dev/moteur_simule.py` |
| Hindsight | mémoire en graphe | absent |

Le moteur simulé imite les routes `/v1/runs` d'Hermès. Il ne comprend que des phrases simples. Les données et secrets locaux sont dans `.local/dev/` (ignoré par Git, droits 0700/0600).

## Parcours de démonstration (2 minutes)

1. Se connecter avec `demo`.
2. Dans la conversation, écrire : `Relance le client Dupont dans 30 secondes au sujet du devis de 200 supports`.
3. Onglet **Engagements** : l'engagement est planifié, avec son échéance.
4. Attendre l'échéance. La pastille de l'onglet **Approbations** passe à 1.
5. Ouvrir **Approbations** : relire le brouillon, puis **Approuver**. Le statut devient « Approuvé · non envoyé » : aucun connecteur d'envoi n'existe.
6. **Kanban** : créer une carte, la commenter, l'archiver. Le commentaire est signé par le compte connecté.

## Tester

Les mêmes commandes que la CI (`.github/workflows/ci.yml`) :

```sh
(cd services/arpagona-api && python3 -m unittest discover -s tests)
python3 -m unittest discover -s services/kanban-bridge/tests
python3 -m unittest discover -s tests/dev -v      # parcours complet, ~2 s
python3 scripts/security_checks.py
node --check apps/mission-control-web/app.js
```

`tests/dev` démarre la pile complète sur des ports libres et rejoue : refus sans session, engagement, échéance, brouillon, empreinte falsifiée refusée, approbation « non envoyé », double décision refusée, Kanban, droits des secrets.

## Brancher un vrai Hermès

Sur un poste où Hermès Agent tourne avec son serveur API et le plugin `arpagona-core` installé :

```sh
python3 dev/lancer.py --hermes-url http://127.0.0.1:8642 --hermes-key-file ~/chemin/vers/cle \
                      --kanban-cli "$(command -v hermes)"
```

Attention : `--kanban-cli` pointe sur le Kanban réel de ce Hermès. Les cartes créées depuis Mission Control n'ont pas d'affectation : aucun agent n'est déclenché. Le plugin doit connaître l'URL de l'API et le jeton de service (`ARPAGONA_API_URL`, `ARPAGONA_SERVICE_TOKEN_FILE` = `.local/dev/service_token`). Installation complète du banc : [deploy/atlas/README.md](../deploy/atlas/README.md).

## Où modifier quoi

- Interface : `apps/mission-control-web/` (HTML, CSS, JavaScript sans framework ni build). Rechargement du navigateur suffit.
- API : `services/arpagona-api/arpagona_api/server.py` (routes), `store.py` (SQLite), `engagements.py` (règles métier). Redémarrer le lanceur.
- Outils de l'agent : `plugins/arpagona-core/__init__.py`. Le moteur simulé les appelle aussi : un test local suffit pour une première vérification.
- Banc Atlas : `deploy/atlas/`. Recette réelle : `tests/e2e/recette_banc.py` (consomme le modèle, écrit sur le banc).

## Règles

Lire [AGENTS.md](../AGENTS.md) et [CONTRIBUTING.md](../CONTRIBUTING.md). En bref : une branche et une PR par chantier ; données fictives uniquement ; aucun secret dans Git ; aucun envoi externe sans validation humaine.
