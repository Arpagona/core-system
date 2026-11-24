# Agents personnels et entreprise commune (banc Atlas) — deux zones

**Statut : banc de test, données fictives.** Mis en place le 24/11/2026 sur `agentcore-dev` (VMID 100). Corrigé le même jour : la première livraison isolait *tout* par utilisateur (mémoire, Kanban, dossiers). C'était une erreur de spécification ; ce document décrit le modèle voulu, conforme à l'ADR 0008 (une instance par entreprise cliente, **mémoire d'équipe commune** entre collègues).
Le Hermès personnel de Thibaud (poste, profil `gpt5`) n'est pas concerné : le « profil thibaud » du banc est un agent fictif du banc.

## Principe : deux zones

| | **Personnel (privé)** | **Entreprise (commun)** |
| --- | --- | --- |
| Agent | `agent-mael`, `agent-thibaud` (comptes système sans shell ni sudo), `HERMES_HOME=/srv/agents/<login>/.hermes` en `0700` : config, `SOUL.md`, sessions (`state.db`), cron, skills perso, préférences | Code Hermès v0.23.1 monté **en lecture seule** dans chaque service |
| Mémoire | banque Hindsight `arpagona-<login>` : mémoire automatique de l'agent (rappel et rétention) | banque Hindsight **`arpagona-equipe`** : faits métier (clients, projets, décisions), **auteur et source conservés** |
| Fichiers | boîte mail fictive `/srv/agents/<login>/mail` (`0700`), brouillons | **`/srv/arpagona/clients`** : dossiers clients, lisibles et modifiables par les deux agents et les humains habilités |
| Kanban | — (les anciens tableaux personnels sont conservés en lecture, plus utilisés) | **un seul Kanban d'entreprise**, un **responsable par carte**, filtre « Mes cartes / Toutes » |
| Secrets | `.env`, jetons, clés en `0600` | — |
| Décisions | — | visibles de tous, **approuvées par le seul responsable** de la carte |

Règles de partage :

1. **Destination explicite.** L'agent n'écrit dans le commun que par des outils dédiés (`arpagona_equipe_*`, `arpagona_clients_*`). Sa mémoire automatique va **toujours** dans sa banque personnelle. En cas de doute : privé.
2. **Aucun versement automatique.** Pas de copie de mail, de secret, ni de banque personnelle dans le commun. Le portier refuse un message électronique entier, un secret reconnaissable ou un fait de plus de 2 000 caractères.
3. **Visibilité ≠ droit de décider.** Tout le monde voit et commente une décision ; seul le responsable de la carte la débloque, la termine, l'archive ou la réaffecte (HTTP 403 sinon). Une carte **sans responsable** (cartes de démonstration) ne se décide pas : on la rattache d'abord (`assign` / bouton « Me l'affecter ») à un responsable.
4. **L'agent n'accède qu'à deux banques** : la sienne et celle de l'équipe.

```
Navigateur ──► API ARPAGONA (compte mael) ──► moteur agent-mael :8652 ──► portier :18911 ─┬─► banque arpagona-mael   (privée, tous droits)
                                          │                                              └─► banque arpagona-equipe (commune : lire, rappeler, déposer)
                                          └─► passerelle Kanban :8701 ──► Kanban d'entreprise (responsable par carte, règle appliquée par l'API)
agent-mael / agent-thibaud / humains habilités ──► /srv/arpagona/clients (groupe arpagona-equipe, setgid 2770)
```

## Ce qui garantit chaque zone

- **Mémoire d'équipe — portier** (`services/hindsight-gate`). Un jeton par agent. Sur `arpagona-equipe` : lecture, rappel et dépôt (`/memories`) seulement ; jamais de suppression, de configuration ni de synthèse. Le portier **impose** l'auteur (balise `auteur:<nom>`, métadonnée `auteur`) : un agent ne peut pas signer un fait au nom d'un autre. La source déclarée est conservée (`agent:<nom>` à défaut). Les banques personnelles de l'autre, la liste des banques, `..` et `%2f` restent refusés.
- **Outils d'équipe — plugin** `plugins/arpagona-equipe` : `arpagona_equipe_memoire_ecrire` (fait + source obligatoires), `arpagona_equipe_memoire_chercher` (faits d'origine, avec auteur et source ; les synthèses automatiques sans auteur sont écartées), `arpagona_clients_lister/lire/ecrire`.
- **Dossiers clients** : chemins relatifs, noms limités, aucun `..`, **aucun lien symbolique** sur le chemin ni sur la racine, ouverture sans suivre les liens. Les fichiers créés sont en `0660` (groupe `arpagona-equipe`), les dossiers en `2770`, ACL par défaut sur la racine pour que les fichiers créés par un humain restent partagés. Les agents n'ont **aucun autre** dossier en écriture hors de leur maison. Les maisons privées restent en `0700` : l'espace commun ne les rouvre pas.
- **Kanban d'entreprise — API** (`services/arpagona-api`) : un seul tableau (celui de l'instance commune, passerelle `:8701`). La carte porte `assignee` (responsable) et `created_by` (auteur, imposé par le compte connecté, jamais par le navigateur). Le responsable d'une création doit être un compte de l'équipe. `GET /api/kanban/list?scope=mine` filtre ; chaque carte porte `mine`. Le dispatcher de la passerelle est **désactivé** (`kanban.dispatch_in_gateway: false`) : affecter une carte à une personne ne lance aucun agent.
- **Privé — comptes Unix** : un compte par agent, `HERMES_HOME` distinct, moteur sur port propre avec clé propre, jeton d'outils limité aux sessions de son propriétaire, secrets en `0600`. Un compte MC sans entrée au registre n'a pas d'agent (503, jamais de repli sur un moteur commun).

## Fichiers

- `agents-perso.sh` — installation rejouable : `install [--seed]` (sauvegarde vérifiée, espace commun, comptes, portier, plugins, services, reprise Kanban), `backup`, `migrate-kanban`, `status`, `acl`.
- `migrate_kanban_equipe.py` — reprise non destructive des cartes des anciens Kanban personnels vers le Kanban d'entreprise.
- `arpagona-agent@.service`, `hindsight-gate.service` — unités systemd. `rollback-agents-perso.sh` — retour arrière.
- `../../services/hindsight-gate/`, `../../plugins/arpagona-mail/`, `../../plugins/arpagona-equipe/`.
- `../../tests/e2e/isolation_agents.py` — recette de la VM (les deux zones, dans les deux sens).

## Installer

```bash
git archive --format=tar.gz -o arp.tar.gz <commit> services apps deploy plugins tests
sudo bash deploy-arpagona.sh arp.tar.gz <commit>                    # code et API
sudo bash /opt/arpagona/current/deploy/atlas/agents-perso.sh install --seed
sudo python3 /opt/arpagona/current/tests/e2e/isolation_agents.py --live --json /tmp/recette.json
```

Ajouter un utilisateur : une ligne dans `AGENTS` (login, nom, port moteur, port inutilisé, port portier), un compte MC (`arpagona_api.manage add-user`), relancer `install`. Ajouter un humain à l'espace commun : l'ajouter à `HUMANS` (groupe `arpagona-equipe`).

## Preuves (24/11/2026, VM)

PREUVES_A_REMPLIR

Tests unitaires (CI) : `services/arpagona-api/tests/test_agents_isolation.py` (routage par compte, Kanban commun, responsable par carte, décision au seul responsable, compte sans agent refusé), `services/hindsight-gate/tests/test_gate.py` (deux banques, auteur imposé, refus mail/secret/suppression), `services/kanban-bridge/tests`, `tests/dev/test_equipe.py` (dossiers clients : droits, traversées, liens ; mémoire d'équipe), `tests/dev/test_migration_kanban.py`, `tests/dev/test_mail_perso.py`. La recette VM n'est pas rejouée par la CI : elle exige la VM.

## Migration (non destructive) et sauvegarde

`install` commence par `backup` : archive des maisons des agents (sans caches, journaux ni environnements Python reconstructibles), copie SQLite cohérente du Kanban d'entreprise, `gate.json` et `agents.json`, **somme SHA-256 vérifiée**, dans `/var/backups/arpagona-deux-zones/<horodatage>/` (root seul, `0700`). Ensuite :

- **Aucune fusion de banques personnelles.** `arpagona-mael` et `arpagona-thibaud` ne sont ni lues ni copiées vers l'équipe. La banque d'équipe démarre vide ; elle s'alimente par dépôt explicite.
- **Kanban** : les cartes des anciens tableaux personnels sont **copiées** (lecture seule SQLite) vers le Kanban d'entreprise avec responsable = leur propriétaire. Clé d'idempotence `deux-zones-<login>-<ancien id>` ; marqueur `/etc/arpagona-agents/<login>.kanban-repris` : une carte archivée depuis ne ressuscite pas. Les cartes de démonstration existantes ne sont pas touchées. Les anciennes bases `kanban.db` des agents restent en place.
- Fixtures de recette de la première livraison reprises par fidélité (5 cartes « carte de recette » et 2 doublons d'amorce de Maël) : **archivées** (non supprimées) le 24/11.

## Snapshot et restauration

- **Snapshot frais avant la correction** : Proxmox `avant-deux-zones-20261124` (24/11/2026 18:36, release alors active `1965eedde3ec`). Historique : `avant-agents-par-utilisateur-20261124`.

| Niveau | Commande | Effet |
| --- | --- | --- |
| Service | `sudo bash deploy/atlas/rollback-agents-perso.sh` | Arrête les agents et le portier, retire le registre ; l'API repasse au moteur commun. **Conserve** données personnelles, dossiers clients, banque d'équipe et Kanban d'entreprise |
| Purge des espaces perso | `... rollback-agents-perso.sh --purge` | Supprime comptes, maisons, ACL, portier, secrets. La zone commune est conservée |
| Données seules | `sha256sum -c SHA256SUMS` puis extraction de `agents.tar.gz` dans `/var/backups/arpagona-deux-zones/<horodatage>/` ; `kanban-entreprise.db` se restaure, service arrêté, vers `/srv/hermes-arpagona/.hermes/kanban.db` ; `config.yaml.avant-deux-zones` redonne la configuration de l'instance commune | Restauration fine sans toucher la VM |
| VM | Sur Atlas : `qm rollback 100 avant-deux-zones-20261124` (avant la correction) ou `avant-agents-par-utilisateur-20261124` (avant tout agent personnel) | Efface tout ce qui a été fait sur la VM depuis le snapshot |

## Limites connues

1. **Clé du modèle copiée** dans le `.env` de chaque agent (même clé que l'instance commune). Une clé par utilisateur et un plafond de dépense restent à faire.
2. **Hindsight reste un seul service et une seule base** : la séparation des banques est imposée par le portier (jeton par agent), pas par des processus distincts. Un administrateur root voit tout.
3. **Administrateur `agentcore`** (sudo) voit tout : prévu sur le banc.
4. **Humains** : le compte Unix `mael` est habilité à l'espace commun (aucun droit sur les dossiers privés des agents). Thibaud n'a pas de compte Unix sur la VM ; s'il en reçoit un, l'ajouter à `HUMANS`. Les humains passent sinon par Mission Control.
5. **Rappel d'équipe explicite** : la mémoire automatique de l'agent ne rappelle que sa banque personnelle ; le rappel métier d'équipe passe par l'outil `arpagona_equipe_memoire_chercher` (consigne dans `SOUL.md`). Un modèle qui n'appelle pas l'outil ne consultera pas l'équipe.
6. **Détection de secrets/mails du portier** : motifs simples (mots-clés, en-têtes de mail, taille) appliqués à tous les champs conservés (texte, contexte, balises, métadonnées) ; schéma strict des champs. Un secret déguisé passerait ; la barrière principale est la destination explicite.
7. **Droit de décision** : appliqué par l'API Mission Control, en deux appels (lecture du responsable puis action) : une réaffectation concurrente par le responsable lui-même dans cette fenêtre n'est pas exclue. La base du Kanban d'entreprise n'est lisible que par le compte de l'instance commune, mais la CLI Hermès ne connaît pas la règle.
8. **Reprise du Kanban** : toutes les cartes d'un ancien tableau personnel sont copiées dans le tableau commun (c'est l'objet de la correction). Sur le banc, ce sont des cartes fictives ; avec de vraies données, trier les cartes avant reprise.
9. **Observations Hindsight** : les synthèses automatiques de la banque d'équipe n'ont ni auteur ni source ; l'outil de rappel ne rend que les faits d'origine.
10. **Moteur commun `hermes-arpagona` conservé** (il porte le code partagé et le Kanban d'entreprise). Le compte `dupont` n'a pas d'agent.
11. **Outils des agents** : `web`, `todo`, `arpagona` (outils mail et équipe). Pas de terminal, pas de mémoire native.
12. **ACL** : Hermès remet `.hermes` à `0700` à chaque démarrage et à chaque appel de sa CLI ; les services agents n'en dépendent pas (montage en lecture seule). Les commandes d'administration hors service demandent d'abord `agents-perso.sh acl` ; la recette le rejoue.
13. **Boîtes fictives** : brancher de vraies boîtes demande des identifiants par utilisateur et un accord de Thibaud.
