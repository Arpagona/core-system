# Audit initial — 12 novembre 2026

Audit préalable à la proposition « Agent Core devient une surcouche d'Hermès Agent » (Issue #39, ADR 0007).
Relevés faits le 12/11/2026 entre 09:00 et 09:30 (Europe/Paris) par l'agent GONA, pour Thibaud.
Aucune valeur de secret n'a été lue ni affichée.

Chaque constat est marqué **vérifié** (commande exécutée ce jour), **documenté** (lu dans un document, non revérifié) ou **non vérifié**.

## 1. GitHub

### Dépôt cible

| Élément | Constat | Statut |
| --- | --- | --- |
| Dépôt | `Arpagona/core-system`, privé, branche par défaut `main` | vérifié |
| Commit de base | `main` = `8fa7e649bbdef98b47a836580858c08372eda9fc` (fusion de la PR #19, 11/11/2026) | vérifié |
| Contenu de `main` | 99 fichiers : 3 crates Rust (`agentcore`, `agentcore-core`, `agentcore-types`), `deploy/`, `bench/`, `scripts/`, `web/`, 6 ADR, 4 workflows CI | vérifié |
| Branches | 25 branches distantes, dont `main` | vérifié |
| PR | 2 fusionnées (#1, #19), 2 fermées sans fusion (#4, #5), 9 ouvertes (#6, #11, #12, #13, #14, #16, #17, #18, #38), 10 en brouillon (#21, #23, #25, #27, #29, #30, #31, #32, #34, #36) | vérifié |
| Issues | 15 ouvertes avant cet audit (#2, #3, #7 à #10, #15, #20, #22, #24, #26, #28, #33, #35, #37), plus #39 créée ce jour | vérifié |
| Protection de `main` | L'API répond 403 : indisponible sur la formule du compte. La discipline Issue, branche, PR reste une convention | vérifié |
| Propriétaire | `Arpagona` est un compte personnel, pas une organisation ; seul collaborateur connu | documenté (`docs/ATELIER-STATUS.md`) |

### Dépôts liés (lus, non modifiés)

| Dépôt | Visibilité | Dernier push | Remarque |
| --- | --- | --- | --- |
| `Arpagona/hermes-agent-backup` | privé | 24/09/2026 | Sauvegarde ancienne de configuration Hermès. À préserver ; pas une source de l'état actuel |
| `Arpagona/arpagona-core-one` | privé | 19/06/2026 | Application Android Kotlin |
| `Arpagona/Agent-core` | **public** | 01/06/2026 | Ancien Agent Core. Hors périmètre |
| `Arpagona/openclaw-squeezer-hybrid` | public | 05/05/2026 | Hors périmètre |
| `Arpagona/lab` | public | 05/05/2026 | Hors périmètre |

### Préservation réalisée ce jour

Trois tags annotés ont été poussés. Ils n'ajoutent aucun commit et ne modifient aucune branche.

| Tag | Commit | Contenu |
| --- | --- | --- |
| `archive/atelier-rust-main-20261112` | `8fa7e64` | `main` après la PR #19 |
| `archive/atelier-rust-integration-20261112` | `2ca3c27` | Branche `test/integration-20261111-console`, celle qui tourne sur la VM |
| `archive/atelier-rust-spike-v0.1-20261112` | `cff972e` | Préversion v0.1 du noyau (PR #14) |

Les branches des PR ouvertes ne sont pas toutes couvertes par ces tags. Elles restent intactes sur GitHub ; aucune n'a été fermée ni supprimée.

## 2. Atlas

### Hôte

| Élément | Constat | Statut |
| --- | --- | --- |
| Nature | Atlas est un **hôte Proxmox VE 9.2.25** (noyau 7.0.14-28-pve), adresse 192.168.68.20 | vérifié |
| Ressources | 31 Gio de RAM dont 27 libres ; racine 94 Go, 8 % utilisés ; `local-lvm` 348 Gio, 0,83 % utilisés | vérifié |
| Charges | Une seule VM (VMID 100), aucun conteneur LXC | vérifié |
| Sauvegardes Proxmox | `/var/lib/vz/dump` était vide avant cet audit | vérifié |

Le banc de test est donc la **VM**, pas l'hôte. Rien n'a été modifié sur l'hôte hormis le snapshot et l'archive décrits au § 3.

### VM `agentcore-dev` (VMID 100)

| Élément | Constat | Statut |
| --- | --- | --- |
| Système | Debian 13 (trixie), noyau 6.12.115 cloud, 4 vCPU, 8 Gio de RAM, disque 40 Go dont 1,2 Go utilisés | vérifié |
| Réseau | 192.168.68.240/24 sur `vmbr0`, démarrage automatique | vérifié |
| Service applicatif | `agentcore-console.service` : console Python sur `127.0.0.1:8765`, répond HTTP 200, unité systemd durcie | vérifié |
| Ports en écoute | 22 (SSH), 5355 (LLMNR), 53 en boucle locale, 8765 en boucle locale. Aucun autre | vérifié |
| Version active | `/opt/agentcore/current` → `releases/0.1.0-2ca3c27d57c5` ; 9 releases conservées (41 Mo) | vérifié |
| État | `/var/lib/agentcore/missions` : 68 entrées, 2,7 Mo | vérifié |
| Outils | Python 3.13.5, git 2.47.3. **Absents : Rust, Node, uv, Docker, Podman, Hermès** | vérifié |
| Compte | `agentcore` appartient au groupe `sudo` et obtient root sans mot de passe | vérifié |
| Configuration | `/etc/agentcore/config.toml` et `/etc/agentcore/api_key`, `root:agentcore 0640` | vérifié (présence et droits, pas le contenu) |

Les binaires Rust sont compilés ailleurs et livrés en archive : la VM n'a pas de chaîne Rust. Aucun composant Hermès n'y est installé.

### Secrets et sauvegardes de la VM

- `/var/backups/agentcore` : répertoire `root:root 0700`, 9 archives `avant-*.tar.gz` et 9 fichiers `previous-*` en `0600`. **vérifié**
- Huit de ces archives contiennent une entrée `etc/agentcore/api_key`. **documenté** (rapport du 11/11, PR #38) ; non réouvert ce jour.
- La clé n'a été ni changée ni révoquée. Selon le rapport du 11/11, elle est partagée avec une installation Hermès. **documenté**
- Le compte `agentcore` peut devenir root : la restriction en `0600` ne protège pas contre lui. **vérifié**
- Le snapshot et l'archive créés ce jour contiennent le disque entier, donc aussi cette clé (voir § 3).

**Décision humaine requise :** rotation de cette clé, avec inventaire des consommateurs. Non faite.

## 3. Sauvegarde restaurable réalisée

| Élément | Détail |
| --- | --- |
| Snapshot Proxmox | `pre-hermes-overlay-20261112`, pris à 09:03:59, VM en marche, système de fichiers gelé par l'agent invité |
| Archive | `/var/lib/vz/dump/vzdump-qemu-100-2026_11_12-09_04_01.vma.zst`, 804 Mo, mode snapshot, sans arrêt de la VM |
| Empreinte SHA-256 | `14fce381791893a799a55ab7a5426dd1b5e5664e731845eb4696dd4112447bf5` |
| Lisibilité | `zstd -t` réussi ; `vma verify` a relu les 42 949 672 960 octets sans erreur |
| Droits | Archive passée en `root:root 0600` (elle contient la clé API) |
| État après | VM `running`, snapshot précédent `baseline-post-install` conservé |

Retour arrière :

- revenir à l'état de ce matin : `qm rollback 100 pre-hermes-overlay-20261112` sur Atlas ;
- reconstruire la VM depuis l'archive : `qmrestore <archive> <nouveau VMID>`.

**Limites.** La relecture de l'archive prouve qu'elle est lisible, pas qu'une VM restaurée démarre : aucune restauration réelle n'a été faite. L'archive et le snapshot sont sur le même hôte que la VM : une panne d'Atlas les emporte. Aucune copie hors hôte n'existe.

## 4. Hermès Agent : interfaces disponibles

Version examinée : **v0.23.1 (2026.9.24)**, documentation fournie avec cette version. Le tag amont `v2026.9.24` pointe sur `e3dd27ee2d8b011737a4eea8e3eb3d711ab78690`. Licence MIT (documenté, ADR 0005).

| Besoin | Interface officielle | Statut |
| --- | --- | --- |
| Fonctionnement sans desktop | CLI et `hermes gateway` suffisent | documenté |
| Chat et exécutions | Serveur API de la gateway, `127.0.0.1:8642` : `POST /v1/runs`, `GET /v1/runs/{id}`, `POST /v1/runs/{id}/stop`, `POST /v1/responses`, `POST /v1/chat/completions`, `POST /api/sessions/{id}/chat/stream` | documenté |
| Continuité de conversation | En-tête `X-Hermes-Session-Key` sur `/v1/runs` et `/v1/responses` | documenté |
| Authentification | Clé `API_SERVER_KEY` en porteur. Sur une installation v0.23.1 existante : `/v1/health` répond 200, `/v1/capabilities` et `/v1/runs` répondent 401 sans clé | **vérifié** |
| Tâches planifiées | `GET/POST/PATCH/DELETE /api/jobs`, `POST /api/jobs/{id}/run` sur le même serveur API | documenté |
| Kanban | `/api/plugins/kanban/tasks`, `/tasks/:id`, `/runs/{id}`, `/workers/active`, servis par le **dashboard** (port 9119), plus la CLI `hermes kanban` | documenté |
| Plugins et hooks | `pre_tool_call` peut bloquer un outil ou exiger une approbation ; il échoue fermé en cas de délai dépassé ou d'exception | documenté |
| Telegram | Plateforme native de la gateway | documenté |
| Passage web vers Telegram | `/handoff <plateforme>` part d'une session **CLI** vers le canal principal d'une messagerie. La documentation indique qu'il n'est pas disponible depuis une session gateway | documenté |

Conséquences pour la conception :

1. Le Kanban HTTP vit sur le dashboard, qui est une surface d'administration complète (configuration, clés, journaux). Il ne doit jamais être atteignable par un client. L'API ARPAGONA n'en relaie que les routes Kanban, ou passe par la CLI.
2. `/handoff` ne couvre pas la continuité web ↔ Telegram. Un adaptateur ARPAGONA sera nécessaire ; à confirmer par essai.
3. `pre_tool_call` applique réellement un refus dans le processus de l'agent. Pour un envoi externe, le contrôle final doit quand même résider dans l'API ARPAGONA : l'agent n'a pas d'outil d'envoi, il ne peut que déposer un brouillon.

**Non fait :** aucune exécution réelle n'a été lancée par l'API, et rien n'a été testé sur la VM. La possibilité d'un white label par extension du dashboard n'a pas été évaluée.

## 5. État des lieux

| Catégorie | Éléments |
| --- | --- |
| **Conservé** | Tout l'historique Git, les 25 branches, les PR et Issues ; les 6 ADR ; rapports et recettes ; règles de collaboration (`AGENTS.md`, `CONTRIBUTING.md`, modèles d'Issue et de PR) ; la VM et ses deux snapshots ; `Arpagona/hermes-agent-backup` |
| **À migrer** | README, vision et architecture vers le produit ARPAGONA ; CI (aujourd'hui centrée sur Rust) ; scripts `deploy/` ; idées de la console web (PR #29, #31, #36) vers Mission Control ; `docs/GUARDIAN.md` vers la politique d'approbation |
| **À désactiver** | Rien pour l'instant. La console actuelle écoute en boucle locale sur 8765 et n'entre en conflit avec aucun port d'Hermès (8642, 9119) |
| **À supprimer après accord** | Rien n'est proposé à la suppression. Candidats futurs, sur décision à trois : crates Rust dans l'arbre courant, anciennes releases sous `/opt/agentcore/releases`, archives contenant la clé une fois celle-ci changée |
| **Bloqueurs** | Voir ci-dessous |
| **Risques** | Voir ci-dessous |

### Bloqueurs

1. **Modèle et clé pour Hermès sur la VM.** Fournisseur, modèle, clé dédiée et plafond de dépense ne sont pas décidés. Sans eux, Hermès s'installe mais n'exécute rien.
2. **Telegram.** Il faut un bot de test dédié et l'identifiant du ou des comptes autorisés.
3. **Accord de Maël et Stéphane** sur l'ADR 0007. Sans lui, tout reste proposition et rien ne va sur `main`.

### Risques

1. Clé API historique non changée, présente dans huit archives, dans le snapshot et dans l'archive de ce jour.
2. Compte `agentcore` avec sudo sans mot de passe : inadapté comme compte de service. Hermès doit tourner sous un compte distinct sans sudo.
3. Sauvegardes sur le même hôte que la VM.
4. Dix-neuf PR ouvertes ou en brouillon portent sur le noyau Rust. Leur sort est à décider à trois ; les laisser ouvertes sans décision entretient deux directions concurrentes.
5. L'ADR 0005 autorisait la reprise de code Hermès dans le noyau Rust. L'ADR 0007 propose l'inverse (utiliser Hermès tel quel) : les deux ne peuvent pas rester « proposés » ensemble.
6. Dépendance à un projet tiers dont les interfaces évoluent : version épinglée et recette à rejouer à chaque mise à niveau.
