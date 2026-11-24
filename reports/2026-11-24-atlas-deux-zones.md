# Atlas / PR #59 — correction « deux zones » (24/11/2026)

**SHA déployé et poussé : `ad5014bf75460c747c9f79ef62756aad156c921f`** (branche `feat/agents-par-utilisateur`, PR #59 draft, base `main`, **non fusionnée**).
**CI exact-head** : « Validation produit » success sur ce SHA (runs 45455586107 et 45455566151).
**Snapshot frais avant correction** : Proxmox `avant-deux-zones-20261124` (VMID 100, 24/11 18:36). Historique : `avant-agents-par-utilisateur-20261124`.

## Ce qui change
La livraison t_bf13936e isolait tout par utilisateur (erreur de spécification). Maintenant :
- **Privé** : comptes Unix, `HERMES_HOME`, sessions, secrets, mail/brouillons, préférences, banque Hindsight perso.
- **Commun** : banque `arpagona-equipe` (auteur + source conservés, imposés par le portier), `/srv/arpagona/clients` (setgid 2770, ACL par défaut), **un seul Kanban** d'entreprise, responsable par carte, filtre « Mes cartes / Toutes ». Visibilité partagée ≠ droit d'approuver (403 pour un non-responsable ; carte sans responsable : affectation d'abord).
- Un agent n'atteint que sa banque et la banque d'équipe. Destination explicite par outils ; aucun versement automatique de mail/secret/banque perso.
Doc : `deploy/atlas/AGENTS-PERSO.md` (principe, preuves, migration, restauration, 13 limites).

## Preuves
- **Recette VM, rejouée sur le SHA final avec `--live` : 212/212 contrôles réussis** (dont 2 vrais tours de modèle, coût minime, 1 appel par session). Couvre : fait d'équipe Maël→Thibaud et inverse (auteur/source relus) ; fait perso et secret fictifs introuvables par l'autre (rappel d'équipe, API Hindsight, propre banque) ; refus de dépôt de secret et de mail entier ; fichiers clients créés/modifiés dans les deux sens, y compris par l'humain `mael` (0660, groupe d'équipe, umask 077 neutralisé), `..`, absolu, liens symboliques refusés ; même Kanban pour les deux, mes cartes/toutes, décisions visibles mais approuvées par le seul responsable, responsable inconnu refusé, tableau identique après nettoyage ; mail/brouillon/préférence/secret inaccessibles par API, outils et fichiers.
- Preuve de lecture après écriture : chaque fait/fichier/carte est relu par l'autre agent avant nettoyage ; les fixtures (documents par identifiant, dossiers `recette-*`, cartes `RECETTE-*` archivées) sont retirées, rien d'autre n'est supprimé (banque équipe : 0 document après la recette ; banque mael/thibaud : données utilisateur intactes).
- Migration Kanban (VM) : 4 cartes personnelles reprises avec leur responsable, 5 cartes `[DEMO]` intactes, aucun doublon au rejeu (`reprises: 0`). Vue finale : 9 cartes (5 DEMO, 2 mael, 2 thibaud). Fixtures de recette de la première livraison archivées (non supprimées).
- Sauvegarde : `/var/backups/arpagona-deux-zones/<horodatage>/` (agents.tar.gz 736 Mo, kanban-entreprise.db, agents.json, gate.json) ; `sha256sum -c` → 4 × OK. Plusieurs sauvegardes issues des déploiements intermédiaires existent (non supprimées).
- Tests unitaires locaux : hindsight-gate 14, arpagona-api 44, kanban-bridge 8, tests/dev 26 : OK. `security_checks.py` : aucun motif sensible ; relecture du diff : seuls des canaris de test fictifs.
- Services actifs après déploiement : hindsight-gate, arpagona-api, kanban-bridge, agents mael/thibaud, gateway commune.

## Revue indépendante (sous-agent Terra, lecture seule)
Elle a trouvé des défauts réels, **tous corrigés puis redéployés/retestés** : (1) dépôt d'équipe : schéma strict, secrets/mails cherchés aussi dans balises/métadonnées/contexte, usurpation d'auteur insensible à la casse ; (2) dossiers clients : résolution par descripteurs `openat`+`O_NOFOLLOW` (plus de fenêtre TOCTOU), refus des liens physiques, plus de `fchmod` sur un fichier existant ; (3) carte sans responsable ne se décide plus (bouton « Me l'affecter ») ; (4) reprise Kanban : échec de statut = pas de marqueur, rejouable ; sauvegarde de l'ancien SOUL.md. Tests ajoutés pour chacun.

## Limites / non fait
- Revue par sous-agent, pas par un humain : à valider par Thibaud/Maël.
- Une seule banque Hindsight/service : séparation par portier, pas par processus ; root et `agentcore` voient tout (banc).
- Rappel d'équipe seulement via l'outil explicite ; secrets déguisés non détectés par le portier (motifs simples).
- Règle de décision appliquée par l'API MC (deux appels, fenêtre de réaffectation concurrente théorique) ; la CLI Hermès ne la connaît pas.
- Clé modèle copiée dans chaque agent ; pas de plafond par utilisateur. Aucun appel payant hors recette ; budget préexistant respecté.
- Retour arrière : `rollback-agents-perso.sh` (conserve la zone commune), `--purge`, restauration des données par sauvegarde, `qm rollback 100 avant-deux-zones-20261124` (efface tout depuis le snapshot). Non exercé en réel (documenté, syntaxe vérifiée).
- Aucun merge dans `main`.
