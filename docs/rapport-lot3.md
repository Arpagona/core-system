# Lot 3 — preuves rouge/vert et dossier de recette — 2026-11-10

**PHASE / DATE** : P5/P6 — exercice complet et transfert — 10 novembre 2026.
**OBJECTIF** : prouver sur des PR réelles qu'une rupture de contrat et une divergence documentaire échouent visiblement, qu'une correction ne nécessite aucun affaiblissement de test, et livrer le dossier de recette, les guides et la procédure de test.

**TRAVAUX EFFECTUÉS**
Vérification indépendante de l'état Git et de la PR #1 (`c8d764e…`, 4 checks verts, runs 42868051783/42868051802/42868051798/42868051788), rejeu local des 11 commandes, clone isolé et exécution des 9 commandes du guide, simulation de deux branches indépendantes (`sim/participant-a-etiquette` `b0af58f8…` PR #4, `sim/participant-b-workflow` `3832e9c9…` PR #5, toutes deux fermées sans fusion), création de la PR de démonstration #6 volontairement incompatible (`bf64821…` rouge → `73c5590…` vert), téléchargement et vérification de l'artefact CI, rédaction de `docs/RAPPORT_RECETTE.md`, `docs/DEPLOY_TEST.md`, `docs/GUIDE_NOUVELLE_TACHE.md`, mise à jour de `docs/GUIDE_ONBOARDING.md`, création des Issues #7 à #10. `main` reste `92f47f0deba3fbaf80c19750c5c2a435689c80e6`.

**FICHIERS / PR / URL**
PR de démonstration, **non fusionnée** : https://github.com/Arpagona/core-system/pull/6
PR du présent dossier : voir la PR liée à la branche `lot3/recette-dossier`.
Issues : #7 (accès et organisation), #8 (protection de main et indépendance Guardian/CI), #9 (serveur de test), #10 (licence).
Artefact : run 42868051788, archive `sha256:2d74dfcf83b6772eca60a3267879a1ee7cdf5c40e0001f3f227b463147dbfcb4`, binaire `503b86ab6c23242dd3e0c3b60556d95c298801c3aaa30a3ed6c4c3e6c538ca9f`.

**TESTS EXÉCUTÉS ET RÉSULTATS**
Localement à `c8d764e…` : fmt, check, clippy `-D warnings`, tests, rupture de contrat, tests architecture, tests Guardian, architecture, build_docs, security_checks, `git diff --check` → tous code 0. Environnement vierge simulé : 9 commandes, code 0. En CI sur la PR #6 : `bf64821…` → 4 échecs (`E0061`, divergence `docs/modules.json` détectée deux fois, Guardian « à corriger ») ; `73c5590…` → 4 succès, Guardian « réserves » sans anomalie.

**RÈGLES ENFORCÉES / PROCÉDURALES / ABSENTES**
ENFORCÉ : `permissions: contents: read`, défaut de jeton CI en lecture seule, contrôles sur le SHA de tête, artefacts privés, aucune référence `secrets.*`, page HTML non publiée (Pages 404). PROCÉDURAL : interdiction de pousser sur `main`, revue indépendante, accord des trois, vérification manuelle du SHA, dérogation de réception approuvée par Thibaud le 10/11/2026. NON DISPONIBLE : protection obligatoire de `main` (403), comptes Maël/Stéphane, serveur de test, déploiement. Indépendance de Guardian limitée : même dépôt, sans LLM.

**RISQUES ET RÉGRESSIONS POTENTIELLES**
Aucune régression constatée sur la branche atelier. Risque principal : la totalité de l'atelier vit sur une branche non fusionnée, sans barrière technique sur `main`. Risque secondaire : Guardian peut être modifié par la PR qu'il examine. Le jeton local du compte utilisé possède des portées plus larges que nécessaire.

**BLOCAGES / ACCORD HUMAIN NÉCESSAIRE**
Décision sur l'organisation et les comptes (#7) ; formule GitHub ou acceptation explicite de l'absence de protection (#8) ; serveur de test et accès (#9) ; licence (#10) ; revue et fusion de la PR #1 ; revue de la PR #6 puis clôture sans fusion. Aucune fusion, aucun déploiement, aucune invitation n'a été effectuée.

**PROCHAINE ACTION RECOMMANDÉE**
Faire relire la PR #1 par Maël et Stéphane dès que leurs accès existent, puis décider humainement de sa fusion ; en parallèle, trancher #8 pour savoir si l'absence de protection de `main` est acceptée comme risque résiduel documenté.
