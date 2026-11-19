# Architecture — proposition initiale à discuter à trois

Statut : proposition, non approuvée. Auteur de préparation : GONA pour revue par Thibaud, Maël et Stéphane. Date : 2026-11-10.

## Cinq responsabilités du noyau

1. Accepter une mission bornée et ses contraintes.
2. Construire le contexte de décision via le port mémoire.
3. Proposer une action ou une réponse via un port de modèle interchangeable.
4. Soumettre toute action à la politique d'autorisation, puis à l'exécuteur.
5. Interpréter le résultat et produire un nouvel état de mission ou un arrêt explicite.

## Exclusions du noyau

Ni stockage concret, ni gestion directe des secrets, ni implémentation des connecteurs, ni file distribuée, ni interface graphique, ni logique métier propre à un client. Le noyau ne s'accorde pas ses propres droits.

## Frontières pressenties (pas encore des crates imposées)

- `agent-core` : orchestration de haut niveau ; dépend de contrats, pas des adaptateurs.
- `memory` : récupération et persistance selon politique.
- `tools` : catalogue typé, adaptateurs, invocation.
- `runtime` : exécution, files, événements, annulation, reprise.
- `security` : décision d'autorisation et accès aux secrets côté exécution.
- `interface` : API et supervision.
- `skills` : compétences métier composables sans modification du noyau.

Flux proposé : interface → noyau → ports mémoire/modèle ; proposition d'action → sécurité → runtime → outil ; résultat → noyau. La liste de ports n'impose ni bus distribué ni protocole réseau.

## Scénario minimal proposé

Une mission synthétique demande une opération arithmétique sans effet externe. Le noyau propose l'outil, la sécurité autorise ou refuse, le runtime exécute uniquement si autorisé, puis renvoie un résultat typé. Arrêt après une action ; un refus ne produit aucun appel d'outil.

Après accord collectif, expérimenter avec deux crates (`agent-core` et `tool-demo`, noms provisoires) ; ne pas implémenter les sept modules avant d'avoir prouvé les frontières.

## Questions de revue

- Ces cinq responsabilités conviennent-elles ?
- Où résident les types partagés, sans créer de dépendances circulaires ?
- Quels états et erreurs sont requis pour la première expérience ?
- Quels contrôles d'autorisation doivent être refaits au moment de l'effet ?
- Quel scénario métier devra ensuite remplacer la démonstration synthétique ?
