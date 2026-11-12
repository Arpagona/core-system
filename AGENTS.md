# Règles communes aux agents

Avant toute action, lire `docs/ROADMAP-PRODUIT.md` (charte produit en cours de validation ; aucun agent ne la modifie), `docs/PROTOCOLE-JOURNAL-AGENTS.md` et le journal GitHub [#45](https://github.com/Arpagona/core-system/issues/45). Après chaque action significative et à chaque clôture de session, consigner résultat, preuve, problème et prochaine action dans le journal. Ne jamais annoncer une synchronisation non confirmée.

Lire README.md, docs/VISION.md, docs/ARCHITECTURE.md, docs/INTERFACES.md, CONTRIBUTING.md et les ADR pertinents avant toute modification.

- Trois co-concepteurs égaux : Thibaud, Maël, Stéphane. Un pilote temporaire par chantier, pas de chef permanent.
- Une Issue avec besoin, périmètre, exclusions et critères d'acceptation ; une branche et une PR par changement. Ne pas travailler directement sur main.
- Liberté interne aux modules ; modification de contrat commun soumise à revue collective à trois avant développement dépendant.
- Ne pas traiter une proposition d'architecture comme une décision approuvée.
- Mettre à jour code, contrats, tests et documentation dans la même PR. Dater et justifier les décisions dans les ADR, sans effacer l'historique.
- Ne jamais approuver ou fusionner seul son propre travail. Guardian est un auditeur indépendant, non un substitut aux tests ou à l'accord humain.
- Aucun secret ou donnée client dans Git, CI ou revue IA. Données synthétiques uniquement par défaut.
- Aucun déploiement production, changement des règles de contrôle, attribution de permissions ou engagement externe sans autorisation humaine appropriée.
- Ne pas importer de code de l'ancien Agent Core ou de GONA/Hermes sans demande et audit de provenance.

## Validation actuelle

`python3 scripts/build_docs.py`
`git diff --check`

Quand le workspace Rust sera introduit : `cargo fmt --check`, `cargo check --workspace`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo test --workspace` et tests de contrat. L'absence actuelle de Cargo.toml n'est pas une réussite de tests Rust.

Configurer explicitement la lecture de ce fichier si l'agent de codage ne le découvre pas automatiquement.
