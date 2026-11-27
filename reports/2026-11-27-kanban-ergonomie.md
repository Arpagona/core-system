# Kanban quotidien — premier lot ergonomique

Date : 27 novembre 2026. Issue : [#78](https://github.com/Arpagona/core-system/issues/78). Branche : `feat/kanban-ergonomie`. Travail réalisé directement, sans sous-agent.

## Livrable et statut

Prototype fonctionnel de l’interface existante, avec guide d’utilisation et recette reproductible. **Testé localement ; pas fusionné, pas déployé sur Atlas, l’iMac ou l’application Android.** Il ne clôt pas à lui seul le jalon du parcours bêta complet. Aucune carte métier réelle n’a été modifiée et aucun autre tableau personnel n’a été restructuré.

La revue humaine reste obligatoire. L’interface et l’ajout API proposés ne sont pas une décision commune acquise : accord explicite de Thibaud, Maël et Stéphane requis avant adoption, conformément à `CONTRIBUTING.md`.

## Réception de ce lot

- [x] Tableau dédié en pleine largeur sur ordinateur ; onglet accessible aussi sur grand écran. Preuve navigateur : panneau supérieur à 1 100 px dans le viewport 1 440 × 1 000.
- [x] Recherche sans accents et multi-termes ; filtres Équipe / Mes cartes / Sans responsable ; état vide récupérable en un geste ; terminées visibles sur demande. Preuves : recette navigateur et tests JavaScript.
- [x] Liste par défaut à 390 × 844, cartes non comprimées, cibles tactiles agrandies, absence de débordement horizontal de page. Capture réellement ouverte et contrôlée après correction. La barre d’onglets reste défilante horizontalement, comme avant.
- [x] Responsable disponible même sans carte existante : ajout proposé `team` dans `/api/me`, limité aux membres configurés ; session anonyme refusée. Preuve : test API avec tableau vidé et compte non configuré.
- [x] Parcours création → responsable → commentaire → blocage motivé → déblocage → fin, avec relecture des états par API. Preuve : navigateur, vraie API et vraie passerelle, CLI simulée.
- [x] Décision interdite sur une carte de collègue : boutons absents et POST direct refusé `403` dans la recette. Les règles serveur existantes restent inchangées.
- [x] Focus et filtres conservés pendant une actualisation ; erreur réseau explicite avec conservation des dernières cartes ; déconnexion effaçant filtres et brouillons. Preuve : recette navigateur, interruption réseau ciblée dans le contexte de test.
- [x] Injection HTML affichée comme texte dans un commentaire : aucun élément image créé et aucun script exécuté dans la recette.

## Résultats exécutés

- API : **99 tests OK**, 78,669 s.
- Développement : **31 tests OK**, 4,247 s.
- Présentation JavaScript : **13 tests OK** ; ils sont également appelés par l’un des tests de développement. Ne pas additionner les deux comptes comme deux couvertures indépendantes.
- Navigateur : **21 scénarios OK** sur le dernier rejeu de la version livrée.
- Syntaxe Node, contrôles de motifs sensibles ciblés et `git diff --check` exécutés avec succès. La détection de motifs n’est pas un audit de sécurité.
- Des `ResourceWarning` préexistants subsistent dans les suites API/développement (connexion SQLite, nettoyage de réponses HTTP d’erreur). Ils ne sont pas masqués et restent dans les logs.

Preuves :

- [`proofs/2026-11-27-kanban-browser.json`](proofs/2026-11-27-kanban-browser.json) : résultats détaillés, périmètre réel et empreintes SHA-256 des sources de la recette.
- [`proofs/2026-11-27-kanban-desktop.png`](proofs/2026-11-27-kanban-desktop.png).
- [`proofs/2026-11-27-kanban-mobile.png`](proofs/2026-11-27-kanban-mobile.png).
- Logs `proofs/2026-11-27-kanban-api.log`, `...-dev.log`, `...-checks.log`.

## Chasse aux bugs (après la première revue)

Onze scénarios adversariaux ont été exécutés sur un jeu de données séparé. Trois défauts réels ont été trouvés puis corrigés, avec le test qui échoue avant correction et passe après.

| Défaut trouvé | Effet utilisateur | Correction |
| --- | --- | --- |
| Détail long en 320×568 | La croix de fermeture défilait hors écran : impossible de fermer sans remonter | Croix rendue fixe en haut du détail ; mesure : 49–101 px sur 568, largeur 49 px |
| Message d’état vide | « Effacez les filtres » alors que tout était simplement terminé | Trois consignes distinctes : tableau vide, tout terminé, filtres trop étroits |
| Session expirée | Tableau affiché mais toute action refusée, sans retour à la connexion | `401` → écran de connexion avec message explicite |

Défauts vérifiés comme **non** présents : recherche multi-termes et sans accents, débordement horizontal sur un jeton de 250 caractères, réponse réseau lente écrasant une carte ouverte plus tard, double clic sur « Terminer », brouillon de commentaire pendant l’actualisation, motif de blocage fait d’espaces, blocage d’une carte non démarrée, statut inconnu, création au clavier (touche Entrée).

Preuve de détection : huit mutations volontaires (recherche, accents, archives, filtre « mes cartes », tri, réponse tardive, session expirée, message d’état vide) sont **toutes détectées** ; chaque fichier muté est restauré à l’octet près, empreinte SHA-256 vérifiée. Voir `tests/ui/mutation-check.py` et `reports/proofs/2026-11-27-kanban-browser.json`.

Fidélité renforcée de la CLI simulée, alignée sur le noyau natif : blocage refusé hors `ready`/`running`, motif vide refusé, motif recopié en commentaire `BLOCKED: …`, clôture refusée sur `done`/`archived`/`triage`.

Résultats cumulés : API **99 OK**, développement **31 OK**, JavaScript **13 OK**, navigateur **21 + 11 scénarios OK**, mutations **8/8 détectées**.

## État du chantier

Travail commité sur la branche, PR en brouillon, CI verte sur le commit exact. **Aucune fusion ni déploiement au moment de cette rédaction** : la suite de ce document couvre la mise en service.

## Corrections obtenues pendant la recette

- L’événement asynchrone `close` d’un ancien dialogue pouvait annuler l’ouverture suivante. Invalidation déplacée au geste de fermeture/annulation ; protection contre les réponses périmées conservée.
- La liste flexible comprimait les cartes au lieu de défiler : hauteur minimale et absence de compression des cartes.
- La soumission automatisée doit cliquer le véritable bouton, y compris sans attribut `type` ; une soumission sans submitter ne représente pas ce clic.
- Après rechargement, la recette attend le nouveau document et ne valide plus l’ancien écran encore présent.
- Le texte d’introduction est retiré sur petit écran pour libérer de la place ; les instructions restent dans le guide et le formulaire de création.

## Cadre et exclusions

API et passerelle réelles, moteur et CLI Kanban **simulés**, comptes et données synthétiques. Contexte navigateur isolé, hôte `.localhost` distinct et aucun cookie de session habituelle remplacé. Ce n’est ni une preuve d’isolation entre clients réels, ni une recette sur téléphone/iMac physiques, ni un test du moteur Hermès réel.

Pas de changement de base, de permission, de mémoire, de budget ou de déclenchement des agents. Pas de glisser-déposer arbitraire des états, d’édition d’une description existante, de nouvelle boucle autonome ni de second gestionnaire de tâches. Les critères « preuve avant de terminer » et « au plus trois priorités » sont des recommandations de travail, pas des validations automatiques ajoutées au serveur.

Le guide [`docs/KANBAN-USAGE.md`](../docs/KANBAN-USAGE.md) documente le contrat proposé et les commandes exactes de reproduction. L’adoption sur les appareils réels attend revue, accord collectif, intégration et recette sur une même version. Les PR budgétaire et restauration ne sont pas fusionnées par ce chantier.
