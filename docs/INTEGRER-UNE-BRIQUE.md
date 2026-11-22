# Intégrer une brique — points d'extension

But : permettre de vérifier vite si une brique existante (outil, connecteur, mémoire, interface) peut se brancher sur Core System, et à quel endroit. Document descriptif de l'existant au 22/11/2026, **pas un contrat approuvé** : toute interface commune reste à valider à trois.

## Principe

Core System ne contient pas de moteur d'agent. Le moteur est **Hermès Agent officiel v0.23.1**, sans fork (ADR 0007). Une brique se branche donc à l'un de ces cinq endroits :

| # | Point d'extension | Pour quoi | Où |
|---|---|---|---|
| 1 | Plugin Hermès (outils) | donner une capacité à l'agent | `plugins/arpagona-core/` |
| 2 | Routes internes de l'API | état métier persistant, rattaché à un utilisateur | `services/arpagona-api/arpagona_api/server.py` |
| 3 | Validation humaine | toute action vers l'extérieur | table `drafts`, route `/api/drafts/decide` |
| 4 | Kanban | missions et suivi, via la CLI officielle | `services/kanban-bridge/bridge.py` |
| 5 | Interface | affichage et décision | `apps/mission-control-web/` |

Règle transversale : **la brique prépare, l'humain décide**. Aucun outil n'envoie quoi que ce soit hors de l'instance.

## 1. Plugin Hermès : ajouter un outil

Mécanisme officiel d'Hermès : un dossier avec `plugin.yaml` et `__init__.py` exposant `register(ctx)`.

```python
ctx.register_tool(name="arpagona_xxx", toolset="arpagona", schema=SCHEMA,
                  handler=fonction, description="…")
```

- `SCHEMA` : JSON Schema des paramètres (format « function calling »). La description guide le modèle : dire quand appeler l'outil et quand demander d'abord à l'utilisateur.
- `handler(args: dict, session_id: str = "", **kw) -> str` : reçoit les arguments et l'identifiant de session Hermès ; renvoie **toujours** une chaîne JSON, jamais une exception (erreurs incluses : `{"error": "…"}`).
- Toolset `arpagona` : seul toolset métier autorisé par `deploy/atlas/politique-outils.sh` (liste permise : `web todo arpagona`). Un nouvel outil dans ce toolset est actif sans changer la politique ; un nouveau toolset exige de modifier la liste permise.
- Le plugin ne garde pas d'état : il appelle l'API (point 2). Il ne lit ni n'écrit de fichier.

Exemple complet : `plugins/arpagona-core/__init__.py` (3 outils, ~130 lignes).

## 2. Routes internes de l'API

Le plugin appelle l'API sur la boucle locale avec deux en-têtes :

- `X-Arpagona-Service` : jeton de service (fichier `ARPAGONA_SERVICE_TOKEN_FILE`), distinct de la clé Hermès.
- `X-Hermes-Session` : identifiant de session. L'API le relie à un compte : c'est ce qui rattache l'action à un utilisateur. Session inconnue → refus.

Routes existantes : `GET/POST /internal/engagements`, `POST /internal/drafts` (`server.py`, contrôle d'accès vers la ligne 369). Une nouvelle brique avec état ajoute ses routes `/internal/…` sur le même modèle, ses tables dans `store.py` et ses règles dans un module dédié (comme `engagements.py`).

Contraintes : Python bibliothèque standard seulement ; SQLite ; une base par instance client (ADR 0008).

## 3. Validation humaine

Toute sortie vers l'extérieur passe par un **brouillon** :

1. L'agent dépose le brouillon (`arpagona_draft_create`) → statut `en_attente`.
2. L'API calcule une empreinte SHA-256 de (cible + corps).
3. L'humain approuve ou refuse dans Mission Control ; l'empreinte transmise doit correspondre, sinon refus (409).
4. Une seule décision par brouillon.
5. Aujourd'hui : « approuvé · non envoyé ». **Aucun connecteur d'envoi n'existe.** Un connecteur (courriel, ERP…) se brancherait après l'étape 3, côté API, jamais côté outil.

## 4. Kanban

La passerelle n'autorise que : `list show create comment complete block unblock archive`, sur la CLI `hermes kanban`. Les cartes créées depuis l'interface n'ont pas d'affectation : aucun agent ne démarre seul. Une brique qui doit lancer du travail autonome demande une décision explicite (coût, droits).

## 5. Interface

HTML, CSS et JavaScript sans framework ni étape de build. Une vue = un onglet dans `index.html`, une fonction de chargement dans `app.js`, une route `/api/…` protégée par la session web et l'en-tête `X-Arpagona: 1`.

## Mémoire

Hindsight tourne en service séparé, une banque par instance client. Une brique mémoire alternative devrait respecter : isolation par instance, pas de fuite entre clients, reprise après redémarrage. État : contrôle M1 (mémoire d'équipe) encore en échec partiel au 22/11.

## Vérifier une brique sans Hermès

```sh
python3 dev/lancer.py
```

Le moteur simulé (`dev/moteur_simule.py`) charge le vrai plugin et appelle ses fonctions. Pour essayer un nouvel outil : l'ajouter au plugin, puis ajouter un cas dans `_repondre` du moteur simulé et un test dans `tests/dev/`. Validation finale : recette réelle sur le banc (`tests/e2e/recette_banc.py`).

## Grille de compatibilité rapide

Pour chaque brique, répondre :

1. Point d'extension : 1 à 5, ou autre (à discuter).
2. Langage et dépendances : Python stdlib ? sinon, service séparé appelé en HTTP local ?
3. État : où vit-il ? Rattaché à quel utilisateur ou client ?
4. Effets externes : lesquels ? Passent-ils par un brouillon validé ?
5. Secrets : lesquels, où stockés, qui les lit ?
6. Isolation : une instance par client possible sans changement ?
7. Test : peut-on la tester avec le moteur simulé ? Quel test de bout en bout sur le banc ?
