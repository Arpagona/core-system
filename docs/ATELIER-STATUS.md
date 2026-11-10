# État de l'atelier — 10 novembre 2026

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
