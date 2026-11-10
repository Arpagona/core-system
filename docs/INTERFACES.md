# Contrats — propositions non approuvées

Aucune signature Rust publique n'est encore figée. Les noms ci-dessous expriment les besoins de la première discussion, pas une API à implémenter immédiatement.

| Port | Entrée proposée | Sortie proposée | Limites |
|---|---|---|---|
| Mémoire | contexte client autorisé, requête bornée | éléments sourcés ou erreur | pas de récupération inter-client |
| Modèle | contexte filtré, outils permis, budget | proposition typée ou réponse | la proposition n'autorise pas l'effet |
| Autorisation | identité, contexte client, action, contraintes | autorisé/refusé/validation humaine requise | refus par défaut ; pas d'auto-élévation |
| Exécution | action validée, contexte, identifiant | succès/échec/incertain | incertain ne signifie pas réessayer automatiquement |
| Mission | entrée bornée, état | nouvel état ou fin | budget, arrêt et annulation explicites |

À décider : représentation des identifiants, schémas des entrées/sorties, erreurs, délais, budgets, reprise et stratégie de versionnage.

## Tests de contrat à construire après accord

- Un refus ou une attente de validation produit zéro invocation.
- Un résultat correct est compris par le noyau et termine le scénario.
- Une erreur d'outil est distincte d'un résultat réussi.
- Une rupture de signature est détectée par compilation ; une rupture sémantique doit être détectée par un test de contrat, pas seulement par Clippy.
- Un contexte client non autorisé est rejeté ; ce test logique ne prouve pas à lui seul l'isolation réseau ou stockage.

Toute évolution commune doit expliciter consommateurs impactés, compatibilité, migration et accord des trois co-concepteurs.

## EXP-001 — contrat synthétique proposé

`atelier-demo` consomme `atelier-contrat` ; `etiquette(u32)` renvoie une chaîne. Le test `experiments/demo/tests/contrat.rs` vérifie des exemples. Ce contrat expérimental n'est ni un contrat produit ni une approbation collective.
