# Agents personnels par utilisateur (banc Atlas)

**Statut : banc de test, données fictives.** Mis en place le 24/11/2026 sur `agentcore-dev` (VMID 100).
Le Hermès personnel de Thibaud (poste, profil `gpt5`) n'est pas concerné : le « profil thibaud » du banc est un agent fictif du banc.

## Principe

Chaque utilisateur du banc (`mael`, `thibaud`) a **son** agent. L'isolation tient par les **comptes Unix et leurs droits**, pas par l'interface.

| Élément | Par utilisateur | Commun (lecture seule) |
| --- | --- | --- |
| Compte Unix | `agent-mael`, `agent-thibaud` (système, sans shell, sans sudo), maison `/srv/agents/<login>` en `0700` | — |
| Hermès | `HERMES_HOME=/srv/agents/<login>/.hermes` : config, `SOUL.md`, `state.db`, sessions, cron, **Kanban (`kanban.db`)**, skills personnels | Code, outils et dépendances de Hermès v0.23.1 : montés **en lecture seule** dans chaque service ; le reste de l'Hermès commun n'est pas visible |
| Moteur | `arpagona-agent@<login>.service`, API sur `127.0.0.1:8652` (mael) / `8653` (thibaud), **clé propre** | — |
| Mémoire | banque Hindsight `arpagona-<login>`, derrière le **portier** `hindsight-gate` (jeton propre, une banque par jeton) | Service Hindsight |
| Kanban | `arpagona-kanban-bridge@<login>.service`, port `8702` / `8703`, jeton propre, base propre | Code de la passerelle |
| Mail | boîte fictive Maildir `/srv/agents/<login>/mail` (`0700`), plugin `arpagona-mail` : lister, lire, **brouillonner ; aucun envoi** | Code du plugin |
| Secrets | `.env` et jetons en `0600`, propriétaire `agent-<login>` | — |
| Mission Control | le compte MC `<login>` est lié à son agent par `/etc/arpagona-api/agents.json` | API et interface |

Règles de l'API (`services/arpagona-api/arpagona_api/agents.py`) :

- Un compte **sans entrée** dans le registre n'a **pas** d'agent : refus net (HTTP 503), jamais de repli sur un moteur commun. Le compte démo `dupont` est dans ce cas.
- Le jeton d'outils d'un agent n'ouvre que **les sessions de son propriétaire**. L'ancien jeton commun est refusé quand le registre est actif.
- Chat, `/status`, déclencheur d'échéances et Kanban passent tous par l'agent du compte connecté.

```
Navigateur ──► API ARPAGONA (compte mael) ──► moteur agent-mael :8652 ──► portier :18911 ──► banque arpagona-mael
                                          └─► passerelle Kanban :8702 ──► kanban.db de agent-mael
                                          moteur agent-mael ──► boîte /srv/agents/mael/mail
```

## Fichiers

- `agents-perso.sh` — installation rejouable (`install [--seed]`, `status`). `--seed` crée les cartes Kanban fictives (une carte et une décision bloquée par utilisateur).
- `arpagona-agent@.service`, `arpagona-kanban-bridge@.service`, `hindsight-gate.service` — unités systemd.
- `rollback-agents-perso.sh` — retour arrière.
- `../../services/hindsight-gate/` — portier Hindsight. `../../plugins/arpagona-mail/` — agent mail personnel.
- `../../tests/e2e/isolation_agents.py` — recette d'isolation sur la VM.

## Installer

```bash
git archive --format=tar.gz -o arp.tar.gz <commit> services apps deploy plugins tests
sudo bash deploy-arpagona.sh arp.tar.gz <commit>                    # code et API
sudo bash /opt/arpagona/current/deploy/atlas/agents-perso.sh install --seed
sudo python3 /opt/arpagona/current/tests/e2e/isolation_agents.py --live --json /tmp/isolation.json
```

Ajouter un utilisateur : ajouter une ligne à `AGENTS` dans `agents-perso.sh` (login, nom, trois ports libres), créer son compte MC avec `arpagona_api.manage add-user`, relancer `install`.

## Preuves (24/11/2026, VM, release `fee0f0fa91e8`)

`isolation_agents.py --live` : 110 contrôles réels, 110 réussis. Ils couvrent :

1. **Fichiers** : `agent-mael` ne lit ni n'écrit rien chez `agent-thibaud` (`.env`, config, `kanban.db`, `state.db`, config Hindsight, jeton, skills, boîte mail) et inversement. Le compte humain `mael` (sans sudo) n'accède ni à l'un ni à l'autre.
2. **Socle** : chaque agent lit le code partagé de Hermès, ne peut ni l'écrire ni écrire les plugins partagés, ne lit pas l'Hermès commun, `/etc/arpagona-api`, `/etc/hindsight-gate`, la base de l'API.
3. **Réseau local** : la clé du moteur de l'un est refusée par le moteur de l'autre ; le jeton Kanban de l'un est refusé par la passerelle de l'autre ; le portier Hindsight refuse l'autre banque, la liste des banques, `..` et `%2f`, et le jeton de l'autre.
4. **Mail** : un brouillon créé pour `mael` (outil direct, puis vrai tour du modèle) n'existe que dans `/srv/agents/mael/mail/Drafts`. Une recherche sur tout `/srv/agents` et le Kanban commun ne le trouve nulle part ailleurs.
5. **Kanban et décisions** : la liste Kanban de `mael` ne contient que ses cartes, celle de `thibaud` que les siennes. La carte « décision » bloquée de chacun n'apparaît que chez lui. `mael` ne commente ni ne termine une carte de `thibaud`.
6. **Mémoire et état** : après un chat MC de `mael`, sa session est dans l'état de `mael` (3 sessions), 0 chez `thibaud` ; la banque `arpagona-mael` a été créée par son agent via le portier.

Les tests unitaires (CI) : `services/arpagona-api/tests/test_agents_isolation.py` (routage par compte, Kanban filtré, jeton limité à son propriétaire, compte sans agent refusé), `services/hindsight-gate/tests/test_gate.py`, `tests/dev/test_mail_perso.py`. La recette VM n'est pas rejouée par la CI : elle exige la VM.

## Snapshot et retour arrière

- **Avant changement** : snapshot Proxmox `avant-agents-par-utilisateur-20261124` (pris le 24/11/2026 à 18:11).
- **Niveau 1 — service** : `sudo bash deploy/atlas/rollback-agents-perso.sh`. Arrête les agents et le portier, retire le registre ; l'API repasse au moteur commun. Données conservées.
- **Niveau 2 — purge** : `... rollback-agents-perso.sh --purge`. Supprime comptes, données, ACL, portier, secrets des agents. Les banques `arpagona-mael` et `arpagona-thibaud` restent dans Hindsight.
- **Niveau 3 — VM** : sur Atlas, `qm rollback 100 avant-agents-par-utilisateur-20261124`. Efface tout ce qui a été fait sur la VM depuis le snapshot.

## Limites connues

1. **Clé du modèle copiée** dans le `.env` de chaque agent (même clé `opencode-go` que l'instance commune). Une clé par utilisateur et un plafond de dépense restent à faire.
2. **Hindsight reste un seul service et une seule base.** La séparation est imposée par le portier (jeton par banque), pas par des processus distincts. Un administrateur root voit tout.
3. **Administrateur `agentcore`** (sudo) voit tout : prévu sur le banc.
4. **Le compte humain `mael` n'a pas accès aux fichiers de son propre agent** : il passe par Mission Control. Un accès en lecture à sa propre maison reste possible plus tard (groupe), sans toucher à l'isolation.
5. **Moteur commun `hermes-arpagona` conservé** (il porte le code et l'environnement partagés) ; l'API ne l'utilise plus tant que le registre est actif. Le compte `dupont` n'a plus d'agent.
6. **Outils des agents** : liste permise `web`, `todo`, `arpagona` (dont les outils mail). Pas de terminal, pas de mémoire native ; la mémoire passe par Hindsight.
7. **Boîtes fictives** : le plugin lit et écrit un Maildir local. Brancher de vraies boîtes demande des identifiants par utilisateur et un accord de Thibaud.
8. **ACL** : le groupe `hermes-core` a une traversée sur `/srv/hermes-arpagona` et `.hermes`, et la lecture de `hermes-agent`, `tools`, `installs`. Hermès remet `.hermes` à `0700` à chaque démarrage de l'instance commune, ce qui annule la traversée (masque ACL). Les services agents n'en dépendent pas (montage en lecture seule, essai fait : masque cassé volontairement, agents et passerelles redémarrent et répondent). Les commandes d'administration hors service (`hermes kanban …` en `sudo -u agent-<login>`) demandent d'abord `agents-perso.sh acl`.
9. **Lancement à froid de la recette** : `isolation_agents.py` rejoue `agents-perso.sh acl` au début pour la même raison.
