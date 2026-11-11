# État de l'atelier — 11 novembre 2026

## Vérifié le 11 novembre 2026

- **Préversion v0.1** (PR [#14](https://github.com/Arpagona/core-system/pull/14), branche `spike/v0.1-noyau`) installée dans la VM `agentcore-dev` ; recette 11 PASS, 27 tests Rust verts ; **réception non prononcée** (accord Maël/Stéphane manquant sur les contrats M0).
- **Deux livrables réels défectueux** malgré une vérification structurelle « ok » : réduction « 90 % » au lieu de 60 % (mission du 10/11) ; contradictions affirmées sans preuve (mission du 11/11). La vérification C-06 ne juge pas la qualité.
- **Trois défauts hauts ouverts** (revue indépendante du 11/11) : appel modèle incertain potentiellement rejoué et facturé ; plafond financier « strict » et quotidien non garantis ; fenêtre TOCTOU du confinement fichiers. PR [#17](https://github.com/Arpagona/core-system/pull/17) corrige partiellement le parsing d'usage, pas le plafond.
- **Sécurité opérationnelle VM** : archives `/var/backups/agentcore/avant-*.tar.gz` lisibles localement et contenant la clé API ; décision humaine requise (restriction + rotation). Aucune permission modifiée.
- PR ouvertes, aucune fusionnée : #1 cadrage, #6 démonstration rupture, #11 recette lot 3, #12 plan noyau, #13 contrats M0, #14 préversion v0.1, #16 documentation CLI, #17 usage modèle, **#18 C-10 / banc**. Issues ouvertes : #2, #3, #7, #8, #9, #10, #15.

## Décision du 11 novembre 2026 — amélioration continue par anneaux

Thibaud demande une capacité d'auto-amélioration récursive du noyau. Décision retenue : **ADR 0006** (`docs/decisions/0006-boucle-amelioration-anneaux.md`), contrat **C-10** (`docs/contrats/C-10-BOUCLE-AMELIORATION.md`), cahier des charges **v1.1** (`docs/ARP-DEV-CDC-001-v1.1.md`, §16).

- **Anneau 0 — observer** (livré en proposition, PR [#18](https://github.com/Arpagona/core-system/pull/18)) : `bench/` avec 2 cas issus des livrables défectueux, attendus scellés par empreinte, vérificateur hors ligne, historiques en FAIL, oracles en PASS, tests négatifs dans le workflow `docs-architecture`.
- **Anneau 1 — adapter sans code** et **anneau 2 — faire évoluer le code par PR** : non commencés ; préalables en CDC v1.1 §16.3.
- Suivi Kanban : ombrelle `t_c27d3c84` (tenant arpagona) pour décisions et jalons.

## Prochaines décisions humaines (ordre proposé)

1. Revue à trois de #13 (contrats M0) et #18 (ADR 0006, C-10, attendus du banc à confirmer).
2. Ordre de correction des trois défauts hauts, avant tout anneau 1.
3. Points ouverts inchangés : organisation/accès (#7), protection de `main` (#8), serveur de test (#9), licence (#10), restriction des archives VM.

---

# État de l'atelier — 10 novembre 2026 (historique)

## Vérifié lors de l'adaptation

- Dépôt existant : `Arpagona/core-system`, main, initialement README et licence Apache-2.0 seulement.
- Dépôt passé en privé et relu via l'API GitHub.
- Propriétaire `Arpagona` de type `User` : organisation cible non créée. Ne pas convertir ce compte personnel sans décision explicite.
- API protections de branche : HTTP 403, demande GitHub de passer à Pro ou de rendre public. Conserver le privé ; ne pas prétendre que les règles sont imposées.
- Liste des collaborateurs retournée : `Arpagona` admin uniquement. Identifiants Maël/Stéphane à fournir.

## Livré dans cette proposition

Cadrage source, consignes agents, vision, proposition d'architecture et contrats, règles de revue, conception Guardian, modèles Issue/PR et génération HTML locale avec CI. Pas de code métier ni reprise d'ancien code.

## Expérience restant à réaliser

1. Décider de la création/transfert vers une organisation et de sa formule ; configurer les accès des trois participants.
2. Revoir à trois architecture et contrats ; enregistrer les accords explicites.
3. Contribuer réellement depuis plusieurs PC (la mécanique Git est prouvée, pas la pluralité des participants).
4. Déployer l'artefact sur un serveur de test désigné et vérifier le retour arrière.

## Lot 3 — exercice complet (10 novembre 2026, vérifié)

- PR de démonstration [#6](https://github.com/Arpagona/core-system/pull/6), volontairement non fusionnée : `bf6482171acf…` échoue sur `E0061` et sur la divergence `docs/modules.json` (4 checks rouges, Guardian « à corriger ») ; `73c5590cc0b1…` repasse les 4 checks au vert, Guardian « réserves » sans anomalie, sans affaiblir aucun test.
- Deux branches de simulation poussées et deux PR ouvertes sans toucher `main` (`92f47f0…`), puis fermées sans fusion : preuve de la mécanique, pas de deux participants réels.
- Clone isolé : 9 commandes du guide au vert. Artefact CI téléchargé, hashé et exécuté en isolation.
- Dossier de recette, guides et procédure de test : [RAPPORT_RECETTE.md](RAPPORT_RECETTE.md), [GUIDE_ONBOARDING.md](GUIDE_ONBOARDING.md), [GUIDE_NOUVELLE_TACHE.md](GUIDE_NOUVELLE_TACHE.md), [DEPLOY_TEST.md](DEPLOY_TEST.md).
- Écarts suivis : Issues [#7](https://github.com/Arpagona/core-system/issues/7) accès et organisation, [#8](https://github.com/Arpagona/core-system/issues/8) protection de `main` et indépendance Guardian/CI, [#9](https://github.com/Arpagona/core-system/issues/9) serveur de test, [#10](https://github.com/Arpagona/core-system/issues/10) licence.

## Déploiement et isolation

Aucun serveur choisi, aucun secret de déploiement, aucune production modifiée. Prévoir par client : droits, réseau, stockage, modèles, journaux, sauvegardes, rétention et administrateurs. Tester restauration et séparation réelle avant toute donnée client. La vue HTML doit rester privée ; pas de GitHub Pages public.
