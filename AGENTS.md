# Règles communes aux agents

Lire README.md, docs/VISION.md, docs/ARCHITECTURE.md, docs/INTERFACES.md, CONTRIBUTING.md et les ADR pertinents avant toute modification.

- Trois co-concepteurs égaux : Thibaud, Maël, Stéphane. Un pilote temporaire par chantier, pas de chef permanent.
- Une Issue avec besoin, périmètre, exclusions et critères d'acceptation ; une branche et une PR par changement. Ne pas travailler directement sur main.
- Liberté interne aux modules ; modification de contrat commun soumise à revue collective à trois avant développement dépendant.
- Ne pas traiter une proposition d'architecture comme une décision approuvée.
- Mettre à jour code, contrats, tests et documentation dans la même PR. Dater et justifier les décisions dans les ADR, sans effacer l'historique.
- Ne jamais approuver ou fusionner seul son propre travail. Guardian est un auditeur indépendant, non un substitut aux tests ou à l'accord humain.
- Aucun secret ou donnée client dans Git, CI ou revue IA. Données synthétiques uniquement par défaut.
- Aucun déploiement production, changement des règles de contrôle, attribution de permissions ou engagement externe sans autorisation humaine appropriée.
- Pour le chantier actuel de fiabilisation du noyau, Thibaud pilote et arbitre seul.
- Pour un choix technique courant, vérifier les sources officielles ou le code actuel de Hermes Agent et d’OpenClaw. Comparer leurs pratiques aux contraintes de Core System, choisir une approche, puis l’implémenter et la tester. Solliciter Thibaud pour les arbitrages stratégiques ou les changements qui dépassent le périmètre autorisé.
- Ne pas importer de code de l'ancien Agent Core ou de GONA/Hermes sans demande et audit de provenance.

## Validation actuelle

`python3 scripts/build_docs.py`
`git diff --check`

Quand le workspace Rust sera introduit : `cargo fmt --check`, `cargo check --workspace`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo test --workspace` et tests de contrat. L'absence actuelle de Cargo.toml n'est pas une réussite de tests Rust.

Configurer explicitement la lecture de ce fichier si l'agent de codage ne le découvre pas automatiquement.
