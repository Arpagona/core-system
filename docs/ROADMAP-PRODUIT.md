# ARPAGONA Agent Core — Les dix commandements du produit

> **Statut : PROPOSITION À VALIDER PAR LE PORTEUR DU PRODUIT — 12 novembre 2026.**
> Ce document décrit les capacités non négociables visées pour la **version aboutie** d'ARPAGONA Agent Core. Il n'affirme pas qu'elles existent aujourd'hui. Il est distinct du [journal opérationnel vivant](https://github.com/Arpagona/core-system/issues/45).
>
> **Règle de gouverne du document :** aucun agent ne peut réécrire, compléter, supprimer, reclasser ou déclarer accompli un commandement de sa propre initiative. Seul un changement explicitement demandé et validé par le porteur du produit peut modifier cette charte. Les agents peuvent proposer des amendements séparément et doivent les noter dans le journal sans toucher à ce fichier. La protection technique dépend de droits et de règles GitHub distincts, **non encore configurés** ; cette règle est pour l'instant une consigne et non une garantie cryptographique.

## Finalité

Créer une **équipe d'employés virtuels opérationnels** pour les entreprises, bureaux d'études, ateliers, usines et services : une intelligence collective persistante, capable d'agir sur des objectifs réels, de persévérer, d'apprendre et de rendre compte. **ARPAGONA n'est ni un simple chatbot ni un habillage d'Hermès.** Sa valeur ajoutée est le pilotage fiable et déterminé du travail dans la durée.

Ces dix commandements sont des **exigences produit**, organisées en grands jalons cohérents. Leur ordre propose une progression, pas une obligation de développement strictement séquentiel. Toute mention de « livré » exige des preuves reproduisibles.

### I — Exploiter Hermès sans réinventer son moteur
Hermès Agent officiel est la base de la boucle agentique, de ses outils et sessions. La surcouche ARPAGONA reste autonome dans son dépôt et s'intègre par API, plugins et hooks documentés : **ni fork permanent, ni copie opaque, ni deuxième moteur concurrent**. Un changement de version Hermès est testé avec possibilité de retour arrière.
**Critère observable :** une mission réelle fonctionne sur une version épinglée d'Hermès, à travers les interfaces ARPAGONA, avec test de compatibilité et rollback.

### II — Donner une existence durable à des employés virtuels
Chaque employé virtuel possède un rôle, un contexte, des compétences, des missions, des outils permis, une mémoire et un état de travail persistants. Un agent coordinateur peut déléguer à des spécialistes et reprendre leurs résultats, sans déployer une équipe de débatteurs qui gaspille les appels modèle.
**Critère observable :** plusieurs employés réalisent une mission commune, se répartissent les responsabilités et reprennent le travail après une interruption sans perdre leur objectif.

### III — Être incisif : détermination, initiative et persévérance méthodique
Un agent ARPAGONA **n'abandonne pas au premier obstacle**. Il diagnostique, recherche, explore plusieurs méthodes, décompose, mobilise un spécialiste, teste les alternatives et réorganise son plan ; s'il détecte un incident majeur, il peut ouvrir une sous-mission corrective prioritaire. Il n'interrompt pour une validation humaine que lorsqu'une autorisation, un risque, une information irremplaçable ou une limite le requiert. **Presque inarrêtable signifie difficile à décourager, jamais incontrôlable.**
**Critère observable :** face à des pannes et blocages injectés, le système mesure les tentatives utiles, les changements de stratégie, les reprises et le taux de résolution, sans dépassement de droits ni boucle infinie.

### IV — Piloter des objectifs et exécuter des missions jusqu'au résultat
Le système gère projets, objectifs, missions, sous-missions, tâches, dépendances, priorités, échéances, preuves et états. Il sait planifier, replanifier et reprendre de manière durable ; le Kanban reflète le travail réellement exécuté, pas une mise en scène. Toute tâche garde sa dernière action, son blocage et sa prochaine étape.
**Critère observable :** une mission longue traverse plusieurs sessions, incidents et redémarrages, avec un état cohérent et un livrable effectivement vérifié.

### V — Offrir un Mission Control au niveau d'un véritable poste de travail agentique
Une interface web sobre, rapide et disponible sur ordinateur comme sur mobile : **chat central, sessions, employés, projets, objectifs, missions, tâches, Kanban, activité, livrables, permissions et validations**. Une ergonomie comparable à celle d'un outil de travail moderne comme Codex ou Claude Code, sans tableaux décoratifs ni sur-ingénierie.
**Critère observable :** l'utilisateur crée un projet, dialogue dans une session, lance et suit une mission, inspecte preuves et fichiers, intervient au besoin et retrouve tout après reconnexion.

### VI — Construire une mémoire longue durée, structurée en graphe
Combiner mémoire épisodique, sémantique, procédurale et opérationnelle. Le **graphe mémoire** relie personnes, machines, clients, projets, événements, décisions, connaissances et causalités, avec sources, dates, niveaux de confiance, permissions et possibilités de correction ou d'oubli. La mémoire n'est pas un empilement de conversations.
**Critère observable :** un agent retrouve et justifie une relation utile entre faits de sessions différentes, sans fuite entre clients et avec rectification traçable d'une erreur.

### VII — Transformer les blocages en progrès avec le Garage et le Dreaming
Un **Garage persistant** conserve anomalies, limites, hypothèses, pistes abandonnées et opportunités. Le **Dreaming** exploite les périodes creuses pour sélectionner et examiner des problèmes, rechercher et tester des solutions, consolider des connaissances et préparer la reprise des missions. Il produit des résultats vérifiables, pas des déclarations d'auto-progrès.
**Critère observable :** un problème non résolu est repris lors d'un cycle Dream, une solution est testée et reliée à sa preuve, puis le chantier d'origine peut en bénéficier.

### VIII — S'améliorer récursivement sans dérive incontrôlée
ARPAGONA évalue ses propres échecs, méthodes, prompts, compétences, outils, workflows et code de surcouche. Il propose et expérimente des améliorations **dans un environnement isolé** ; les tests de régression, comparaisons avant/après et mécanismes de retour arrière décident de leur intérêt. Une modification de code ou de permissions en production exige une autorisation adaptée. **L'auto-amélioration doit augmenter une capacité mesurée, non seulement la complexité du système.**
**Critère observable :** une modification issue d'une analyse autonome surpasse une référence sur un banc pertinent, sans régression critique, et peut être annulée.

### IX — Agir réellement dans les ateliers, usines et services
Connecteurs modulaires vers bureautique, navigateur, messagerie, CRM, ERP, MES, CAO/PLM, fichiers, données d'atelier et applications métier. L'agent sait observer, préparer, exécuter et vérifier un travail autorisé ; il ne prétend jamais avoir envoyé, modifié, usiné ou livré ce qui n'a pas eu lieu. Les actes à impact physique, financier, irréversible ou externe passent par une politique de risque explicite et les validations nécessaires.
**Critère observable :** scénarios de bout en bout en bureau d'études, atelier et service administratif, avec résultats visibles dans les systèmes cibles et preuves d'exécution.

### X — Rester fiable, mesurable, explicable et maîtrisable
Fiabilité d'abord : séparation par client, moindre privilège, limites de coût et ressources, journal d'audit, Guardian, contrôle des effets, protection des secrets, arrêt/reprise et récupération d'incident. **Autonomie maximale à l'intérieur d'un périmètre consenti ; aucune escalade de privilèges ni dépense illimitée.** Mesurer réussite, erreurs, qualité des livrables, temps économisé, coût, taux de reprise et valeur métier.
**Critère observable :** essais réels reproductibles, attaques et pannes simulées, isolation démontrée, contrôle budgétaire testé, audit lisible et restauration vérifiée.

## Non-objectifs structurants

- Ne pas recréer dans ARPAGONA ce qu'Hermès fait correctement : privilégier l'intégration et le test.
- Ne pas empiler des sous-agents discutant entre eux sans bénéfice prouvé.
- Ne pas confondre apparence de Mission Control, simulation ou auto-évaluation avec capacités opérationnelles.
- Ne pas fabriquer une infrastructure abstraite sans cas d'usage industriel ou tertiaire vérifiable.
- Ne jamais confondre **incisivité** et contournement des permissions, des limites ou des refus humains.

## Relation avec le journal vivant

La **charte** définit la destination du produit. Le **journal opérationnel** ([issue #45](https://github.com/Arpagona/core-system/issues/45)) suit les faits, anomalies, versions, actions antérieures et prochaine action. Les agents modifient le journal après chaque action significative et au début/à la fin des sessions, mais **ne changent jamais eux-mêmes la destination**. Les propositions d'évolution de la charte restent des suggestions jusqu'à décision humaine explicite.

## État de départ connu au 12 novembre 2026

- ADR 0007 « surcouche Hermès » : proposé en PR #40, non fusionné.
- Hermès v0.23.1 : tests d'installation et de session rapportés dans la PR #42.
- API et chat web : prototype avec appel réel rapporté dans la PR #43, non fusionné.
- Le reste de cette charte (employés complets, détermination mesurée, Mission Control abouti, graphe mémoire, Dream, auto-amélioration, intégrations industrielles) représente **des objectifs**, non des fonctionnalités déjà livrées.
