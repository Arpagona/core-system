# ADR 0006 — Auto-amélioration du noyau par anneaux, sans auto-modification

**Date :** 11 novembre 2026
**Statut :** **PROPOSÉ** — demande de Thibaud du 11/11/2026 ; introduit le contrat **C-10** (`docs/contrats/C-10-BOUCLE-AMELIORATION.md`) ; **accord de Maël et Stéphane requis** avant tout développement dépendant. L'absence de réponse ne vaut pas accord.
**Référence Issue :** à créer lors de la revue (voir `GUIDE_NOUVELLE_TACHE.md`).

## Contexte

Thibaud souhaite que le noyau agentique devienne capable de **s'améliorer récursivement** : identifier ses faiblesses récurrentes, proposer des changements, les tester, mesurer avant/après, conserver ce qui marche et revenir en arrière sinon.

Deux faits s'opposent à une implémentation immédiate :

1. `PLAN-NOYAU.md` §« Explicitement exclu de la v0.1 » exclut l'**auto-modification**, leçon directe du programme GONA Core (lots 6–10) où la boucle d'auto-amélioration a été construite avant que le socle soit fiable.
2. La préversion v0.1 n'est **pas réceptionnée** et porte trois défauts hauts ouverts (revue du 11/11/2026 : appel modèle incertain potentiellement rejoué et facturé, plafond financier non garanti, fenêtre TOCTOU du confinement fichiers). Une boucle qui modifie un noyau capable de dépasser son plafond est un **amplificateur de défauts**.

En revanche, les deux livrables réels du 10 et 11/11 ont montré des défauts de **qualité** que la vérification structurelle (C-06) ne détecte pas : un calcul dérivé faux (réduction « 90 % » au lieu de 60 %), des contradictions affirmées sans preuve. Sans mesure de ces défauts, « améliorer » le noyau n'est que « changer » le noyau.

## Décision proposée

Structurer l'auto-amélioration en **trois anneaux**, activés dans l'ordre, chacun réceptionné séparément. Seul l'anneau 0 est proposé pour la période v0.1 → v0.2.

| Anneau | Ce que le noyau peut faire | Ce qu'il ne peut pas faire | Préalable |
|---|---|---|---|
| **0 — Observer** | émettre des signaux par mission (coût, itérations, refus, échecs de vérification, corrections humaines) ; être évalué par un **banc de régression figé** (`bench/`) rejouable hors ligne | rien changer | aucun (compatible v0.1) |
| **1 — Adapter sans code** | proposer une variante de *compétence* versionnée (consigne de vérification, stratégie de lecture, paramètres non sécuritaires) ; la tester en VM isolée sur le banc ; activer seulement si gain mesuré ; rollback automatique | toucher aux plafonds, permissions, politique, journal, contrats C-01…C-07 | v0.1 réceptionnée ; défauts hauts corrigés ; anneau 0 réceptionné |
| **2 — Faire évoluer le code** | ouvrir Issue + branche + PR avec preuve de banc avant/après ; passer CI + Guardian | **fusionner**, déployer, modifier ses propres règles de sûreté ou le banc de référence | anneau 1 réceptionné ; accord à trois sur le périmètre |

La **récursivité** est obtenue à l'anneau 2 : l'outil d'amélioration est lui-même un module soumis à la boucle (banc, PR, revue), mais **jamais à son propre merge**. La fusion reste humaine, conformément au cycle en 9 étapes de l'atelier.

## Invariants (non négociables, tous anneaux)

1. **Isolation** : toute expérimentation s'exécute sur une copie/VM jetable, jamais sur l'instance de référence ni sur des données client.
2. **Porte de mesure** : aucune activation sans comparaison avant/après sur le banc figé, avec résultat lisible par un humain.
3. **Réversibilité** : chaque activation a un retour arrière testé avant d'être proposée.
4. **Journal** : chaque cycle (hypothèse, variante, mesure, décision) est un enregistrement durable (C-10 §4).
5. **Interrupteur** : un opérateur peut arrêter la boucle immédiatement ; l'arrêt ne déclenche aucun rejeu.
6. **Auto-exclusion** : la boucle ne modifie jamais ses propres portes, le banc de référence, les plafonds, les permissions ni la politique d'autorisation.
7. **Pas de fausse réussite** : un gain non mesuré ou mesuré sur un banc modifié dans le même cycle est un résultat **invalide**, pas un succès.

## Alternatives écartées

- **Boucle complète dès maintenant** (proposition initiale) : refusée — viole l'exclusion v0.1 et construit sur un socle non reçu.
- **Attendre la v0.3 pour toute mesure** : refusée — sans banc, impossible de prouver qu'une correction des défauts hauts n'a pas dégradé la qualité des livrables.
- **Juge LLM pour la qualité** : différé — l'anneau 0 utilise des attendus **scellés par un humain** et des contrôles déterministes ; un juge modèle pourra s'ajouter à l'anneau 1 comme signal, jamais comme porte.

## Conséquences

- Nouveau contrat **C-10** (signaux, banc, enregistrement de cycle, portes). Les contrats C-01…C-07 ne changent pas.
- Nouveau répertoire `bench/` : cas, attendus scellés, vérificateur déterministe, syntheses historiques comme référence « avant ».
- Le rapport de mission (C-07) devra, en v0.2, inclure les signaux de l'anneau 0 ; proposition d'amendement à soumettre, non implémentée ici.
- La CI exécute le vérificateur du banc sur ses propres cas (tests négatifs : les livrables défectueux du 10–11/11 doivent échouer).

## État au 11/11/2026

Proposition documentaire + banc initial (2 cas, 2 livrables historiques défectueux, vérificateur hors ligne). Aucun code Rust modifié, aucun appel modèle, aucun déploiement.
