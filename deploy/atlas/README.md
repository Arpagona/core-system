# Banc de test Atlas — Hermès Agent officiel

**Statut : environnement de test, proposition (ADR 0007, Issue #39).** Aucune production, aucune donnée réelle.

## Ce qui est installé

| Élément | Valeur |
| --- | --- |
| Machine | VM `agentcore-dev` (VMID 100) sur l'hôte Proxmox Atlas |
| Hermès | v0.23.1, commit `3b421578588243f920886e6fe79a6faa87ea026e`, installé par le script officiel `scripts/install.sh --commit`, arbre Git sans modification |
| Composants | CLI et gateway. Ni navigateur, ni computer-use, ni application desktop |
| Compte | `hermes-arpagona`, compte système sans sudo, mot de passe verrouillé, répertoire `/srv/hermes-arpagona` en `0750` |
| Service | `hermes-arpagona-gateway.service` (systemd), démarrage automatique |
| Écoute | Serveur API sur `127.0.0.1:8642` uniquement, clé porteur obligatoire |
| Modèle | `deepseek-v4.1-flash` par `opencode-go` (ADR 0004) |
| Limites | 3 Gio de RAM, 2 cœurs, 512 tâches ; pas d'accès aux répertoires de l'ancien Agent Core |
| Secrets | `/srv/hermes-arpagona/.hermes/.env` en `0600`, hors dépôt |
| Télémétrie | Désactivée (valeur par défaut, vérifiée dans `config.yaml`) |

L'ancienne console Agent Core (`agentcore-console.service`, port 8765) n'a pas été touchée.

## Fichiers

- `hermes-arpagona-gateway.service` — l'unité systemd installée, à l'identique.
- `install-hermes.sh` — transcription des commandes exécutées à la main le 12/11/2026. **Le script lui-même n'a pas encore été rejoué de bout en bout** sur une VM vierge.
- `rollback-hermes.sh` — arrêt et désactivation du service, sans suppression. Même réserve : les commandes ont été exécutées à la main, pas par ce script.

## Preuves du 12/11/2026

Essais faits sur la VM, par l'API en boucle locale, avec des données fictives.

| Essai | Résultat |
| --- | --- |
| Version exécutée | `hermes --version` : v0.23.1 ; `git rev-parse HEAD` : `3b42157…` ; `git status` : 0 fichier modifié |
| API sans clé | `/v1/health` 200 ; `POST /v1/runs` 401 |
| Exécution réelle | `POST /v1/runs` puis `GET /v1/runs/{id}` : statut `completed`, réponse du modèle, 12 800 jetons |
| Rejeu idempotent | Même `Idempotency-Key` : 202 avec `Idempotency-Replayed: true`, pas de nouvelle exécution |
| Redémarrage | `systemctl restart` : nouveau PID, `/v1/health` 200 après 12 s |
| Reprise de session | Un fait donné dans la session `c` avant redémarrage est restitué après redémarrage |
| Séparation des sessions | La session `d` ne connaît pas ce fait (« inconnu ») |
| Retour arrière | `systemctl disable --now` : port 8642 fermé, console Agent Core toujours active (HTTP 200) ; réactivation : `/v1/health` 200 |
| Journal | Aucune erreur ni trace d'exception sur la période |

## Limites connues

1. **Aucun plafond de dépense n'est appliqué.** Les plafonds de l'ADR 0004 (0,50 $ par mission, 20 $ par 24 h) étaient appliqués par le noyau Rust. Hermès n'en impose pas ici. Chaque exécution coûte environ 12 500 jetons d'entrée, même pour une question d'un mot.
2. **Clé du modèle partagée.** L'instance utilise la clé `opencode-go` déjà présente sur la VM, la même que l'ancien Agent Core. Elle n'a pas été changée (décision du 12/11/2026).
3. **Outils non restreints.** L'agent dispose de la liste d'outils par défaut d'Hermès, dont le terminal, dans les limites du compte de service et du confinement systemd. La restriction des outils de la plateforme API reste à faire.
4. **Arrêt signalé en échec.** À l'arrêt, le processus sort avec le code 1 et systemd note `failed`. Sans effet constaté sur le redémarrage.
5. **Retour arrière complet non exécuté.** Le retour à l'état d'avant l'installation passe par le snapshot Proxmox ; il n'a pas été déclenché.
6. **Pas de reverse proxy, pas de TLS, pas de Telegram** à ce stade. L'API n'est joignable que depuis la VM.
7. La séparation des sessions observée est celle d'identifiants de session différents sous une même clé. Ce n'est pas une séparation entre utilisateurs : celle-ci relève de l'API ARPAGONA.

## Retour arrière

| Niveau | Commande | Effet |
| --- | --- | --- |
| Service | `sudo deploy/atlas/rollback-hermes.sh` | Hermès arrêté et désactivé, données conservées |
| VM | Sur Atlas : `qm rollback 100 pre-hermes-overlay-20261112` | Retour à l'état du 12/11 à 09:03, avant toute installation. **Efface tout ce qui a été fait depuis sur la VM** |
| Reconstruction | Sur Atlas : `qmrestore /var/lib/vz/dump/vzdump-qemu-100-2026_11_12-09_04_01.vma.zst <nouveau VMID>` | Nouvelle VM à partir de l'archive (non testé) |

## Mise à niveau d'Hermès

Non encore exercée. Procédure prévue : snapshot Proxmox, relance de `install-hermes.sh` avec `HERMES_COMMIT=<nouveau commit>`, recette rejouée, retour au snapshot en cas de régression.

## Déploiement reproductible et recette du banc

Tout l'état du banc lié à ARPAGONA est posé par `deploy-arpagona.sh` ; aucun geste manuel n'est requis après lui.

```bash
git archive --format=tar.gz -o arp.tar.gz <commit> services apps deploy plugins tests
sudo bash deploy-arpagona.sh arp.tar.gz <commit>
sudo python3 /opt/arpagona/current/tests/e2e/recette_banc.py --json /tmp/recette.json
```

Le script, rejouable :

- tire une seule fois un **jeton de service** propre aux outils du plugin, distinct de la clé de l'API Hermès, et en remet une copie lisible par le seul compte du moteur ;
- installe le plugin `arpagona-core` hors de l'arbre d'Hermès et l'active ;
- applique `politique-outils.sh` : **liste permise** d'outils par canal (`web`, `todo`, `arpagona`), tout le reste désactivé, mémoire native coupée ;
- redémarre les deux services et attend qu'ils répondent.

### Pourquoi `memory` et `session_search` sont coupés

Ces deux outils d'Hermès sont communs à toute l'instance. La recette l'a prouvé le 12/11/2026 : un second compte a retrouvé, par `session_search`, une information confiée par le premier. Tant qu'une instance sert plus d'un utilisateur, ils restent coupés. Conséquence assumée : l'agent ne garde pour l'instant que le fil de la conversation de chaque compte et le registre d'engagements ; la mémoire durable par utilisateur reste à construire côté ARPAGONA.

### Recette `tests/e2e/recette_banc.py`

Contrôles contre les vrais services et le vrai modèle, avec deux comptes fictifs créés puis supprimés : surface exposée, routes internes, politique d'outils, chat en flux, isolation entre comptes, engagement daté, persistance après redémarrage des deux services, et — sauf `--sans-echeance` — le cycle complet d'une relance : échéance forcée, brouillon produit par l'agent, refus d'une empreinte modifiée, approbation explicite, non-envoi, aucune seconde décision.

Options utiles :

- `--memoire-equipe N` : l'instance a une mémoire commune ; après N secondes, un second compte doit retrouver ce que le premier a confié. C'est le contrôle M1.
- `--sans-echeance` : saute le déclencheur d'échéance, pour une passe rapide.
- `--json chemin` : conserve le détail des contrôles. Les contrôles marqués « modèle » dépendent d'une réponse du modèle : un échec isolé se relit avant de conclure. Les sessions de recette restent dans l'historique interne d'Hermès ; seules les données côté ARPAGONA sont supprimées.

C'est aussi le test de compatibilité à rejouer après toute mise à niveau d'Hermès.

## Mémoire en graphe : Hindsight, en service séparé

Décision de Thibaud du 12/11/2026 (à confirmer par Maël et Stéphane) : **une instance Hermès par client**, avec Hindsight comme mémoire en graphe.

```bash
sudo bash /opt/arpagona/current/deploy/atlas/install-hindsight.sh    # installe, démarre, branche le moteur
sudo python3 /opt/arpagona/current/tests/e2e/recette_banc.py --memoire-equipe 90
sudo bash /opt/arpagona/current/deploy/atlas/rollback-hindsight.sh   # débranche, sans rien supprimer
```

| Élément | Valeur |
|---|---|
| Serveur | `hindsight-api` 1.2.1, service `hindsight-arpagona`, `127.0.0.1:18897`, clé d'accès obligatoire |
| Compte | `hindsight-arpagona`, sans accès aux dossiers d'Hermès ni de l'API ARPAGONA |
| Environnement | Python à part dans `/srv/hindsight-arpagona/venv`, PyTorch CPU |
| Limites | `MemoryMax=3G`, `CPUQuota=200%` |
| Plugin Hermès | `hindsight` 1.2.4, catalogue officiel, mode « serveur externe », hors de l'arbre d'Hermès |
| Extraction | modèle du fournisseur déjà configuré pour l'instance |

### Ce qu'il faut savoir

- **Mémoire d'équipe.** Tous les comptes d'une instance partagent la même banque de mémoire. L'isolation se joue entre instances, donc entre clients ; elle reste à prouver avec une seconde instance.
- **Les engagements, eux, restent par compte.** Un collègue peut donc se souvenir d'une relance décidée par un autre sans la voir dans son registre. Incohérence à trancher.
- **Le démarrage automatique du plugin est à éviter** : il télécharge PyTorch avec CUDA (plus de 9 Go) et tourne dans le service du moteur.
- **`recall_sync` est nécessaire** : sans lui, le rappel n'arrive qu'au tour suivant.
- **Aucun outil de mémoire n'est donné à l'agent** (`memory_mode: context`) : la liste permise d'outils ne change pas.
- **Coût** : chaque échange retenu déclenche des appels au modèle pour l'extraction puis la consolidation, en plus de la réponse.
- **Si la mémoire tombe, le chat continue** ; il ne rappelle simplement rien.
