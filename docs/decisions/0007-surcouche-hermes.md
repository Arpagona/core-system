# ADR 0007 — Agent Core devient une surcouche d'Hermès Agent

**Date :** 12 novembre 2026
**Statut :** ACCEPTÉ — validé par Thibaud le 19/11/2026 ; Maël et Stéphane informés

S'il est accepté, cet ADR remplace l'ADR 0001 (noyau Rust) et rend sans objet l'ADR 0005 (reprise de code Hermès dans le noyau). Les ADR 0002 (isolation des clients) et 0004 (modèle cloud) restent valables. Les ADR 0003 et 0006 deviennent historiques.

## Contexte

Du 10 au 11 novembre, l'atelier a produit une préversion d'un noyau agentique en Rust : 27 tests, 11 scénarios en VM, une console web locale. Ce travail n'a pas été reçu collectivement. La revue du 11/11 laisse trois défauts hauts ouverts (rejeu d'appel facturé, plafond de coût non garanti, confinement des fichiers) et constate que deux livrables réels étaient faux malgré une vérification « ok ».

Reconstruire une boucle agentique, un ordonnanceur, une mémoire, un Kanban et des connecteurs de messagerie demande des mois avant d'atteindre ce qu'Hermès Agent fournit déjà sous licence MIT. Le produit visé est un « collègue virtuel » sous marque ARPAGONA : sa valeur est dans l'expérience, la continuité métier et les validations humaines, pas dans le moteur.

L'état constaté du dépôt et du banc de test est dans [l'audit du 12/11/2026](../audits/AUDIT_INITIAL_2026-11-12.md).

## Proposition

1. **Hermès Agent officiel est le moteur.** Il fournit la boucle LLM, les outils, les sessions, la mémoire native, le Kanban, la planification et la gateway Telegram. Il est installé depuis une version officielle épinglée (tag et commit notés), sans application desktop.
2. **Ni fork ni modification du code amont.** Tout le code ARPAGONA vit dans ce dépôt, hors de l'arbre d'Hermès, et s'y branche par ses interfaces officielles : serveur API, plugins, hooks, CLI.
3. **ARPAGONA fournit la surcouche produit :**
   - Mission Control, interface web en marque blanche ;
   - une API ARPAGONA qui porte l'authentification, les droits, l'identité de conversation, le registre des engagements et les approbations ;
   - un plugin Hermès `arpagona-core` pour les outils et hooks métier.
4. **Le client n'atteint jamais Hermès directement** : ni shell, ni API brute, ni dashboard, ni clés.
5. **Une instance par client** pour le MVP : fichiers, secrets, mémoire, journaux et modèles séparés.
6. **Aucun effet externe sans validation humaine**, appliquée côté serveur par l'API ARPAGONA au moment de l'action et journalisée. L'agent prépare des brouillons ; il n'a pas d'outil d'envoi.
7. **Le noyau Rust est conservé comme historique**, pas supprimé (voir « Préservation »).

Le détail des flux est dans [le schéma d'intégration](../architecture/INTEGRATION-HERMES.md).

## Arborescence proposée

```text
core-system/
  apps/mission-control-web/     interface ARPAGONA
  services/arpagona-api/        passerelle, approbations, engagements
  plugins/arpagona-core/        outils et hooks Hermès
  deploy/atlas/                 déploiement de test, sauvegarde, retour arrière
  tests/e2e/                    scénarios de recette
  docs/architecture/            schémas et contrats
  docs/decisions/               ADR, anciens et nouveaux
  docs/legacy/                  documentation du noyau Rust
```

Ces dossiers sont créés au fil des PR qui les remplissent. Le déplacement des crates Rust et de leur documentation vers un emplacement d'archive fera l'objet d'une PR distincte, après accord.

## Options écartées

| Option | Raison |
| --- | --- |
| Poursuivre le noyau Rust | Délai trop long avant un produit montrable ; défauts de fiabilité ouverts sur des fonctions qu'Hermès couvre déjà |
| Forker Hermès | Charge de maintenance à chaque version amont ; interdit par le mandat |
| Reprendre des morceaux d'Hermès en Rust (ADR 0005) | Cumule le coût de la réécriture et la dérive par rapport à l'amont |
| Thème ou plugin du dashboard Hermès comme interface client | Le dashboard est une surface d'administration (configuration, clés, journaux). Son masquage complet n'est pas démontré. Reste ouvert, voir plus bas |

## Conséquences

- Le produit dépend d'un projet tiers. Chaque mise à niveau d'Hermès se fait d'abord en test, avec recette rejouée et retour arrière prévu.
- Le langage de la surcouche n'est plus imposé. Le plugin Hermès est en Python par nature. Le choix pour l'API et le web reste à faire.
- La CI, aujourd'hui centrée sur Rust, doit évoluer. Les règles de qualité (Issue, branche, PR, revue humaine, Guardian, pas de secret) sont maintenues.
- Les contrats M0 (PR #13) et le plan du noyau (PR #12) deviennent historiques. Les 19 PR ouvertes ou en brouillon sur le noyau Rust demandent une décision à trois : fermer sans fusion, ou garder en référence.
- Ce qu'Hermès ne garantit pas reste à la charge d'ARPAGONA : séparation des utilisateurs, plafonds de coût, traçabilité des approbations.

## Préservation et retour arrière

- Tags poussés le 12/11/2026 : `archive/atelier-rust-main-20261112` (`8fa7e64`), `archive/atelier-rust-integration-20261112` (`2ca3c27`), `archive/atelier-rust-spike-v0.1-20261112` (`cff972e`).
- Aucune branche ni PR fermée ou supprimée. Aucune réécriture d'historique.
- VM de test : snapshot Proxmox `pre-hermes-overlay-20261112` et archive vzdump vérifiée en lecture.
- Si l'ADR est refusé : fermer la branche `refactor/hermes-overlay-v1` sans fusion. `main` n'a pas bougé.
- Si l'orientation est abandonnée plus tard : le noyau Rust repart des tags ci-dessus.

## Décisions ouvertes

| Sujet | État |
| --- | --- |
| Accord de Maël et Stéphane sur cet ADR | À obtenir |
| Sort des PR Rust ouvertes et des ADR 0001, 0005, 0006 | À décider à trois |
| API Hermès retenue pour le chat (`/v1/runs`, `/v1/responses` ou `/api/sessions/.../chat/stream`) | À trancher après essai sur la version installée |
| Interface client : frontend indépendant ou extension du dashboard | Frontend indépendant recommandé ; extension du dashboard non évaluée |
| Langage et cadre de l'API ARPAGONA et du web | À décider |
| Fournisseur, modèle, clé et plafond de dépense pour le banc de test | À décider (déjà ouvert, ADR 0004) |
| Fournisseur de mémoire ; mémoire en graphe | À comparer par un banc d'essai, non requis pour le prototype |
| Voix : transcription puis synthèse | À décider selon coût et consentement |
| Reprise automatique d'une mission débloquée par Dream | À décider |
| Continuité web ↔ Telegram | `/handoff` ne la couvre pas d'après la documentation ; à confirmer par essai, adaptateur probable |
