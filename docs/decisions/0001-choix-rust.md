# ADR 0001 — Rust pour le noyau

Date : 2026-11-10. Statut : orientation retenue dans le cadrage transmis, pas preuve d'une revue GitHub.

Décision : noyau Rust modulaire, adaptateurs Python isolés si nécessaire. Objectif : interfaces explicites et vérifications reproductibles. Conséquences : Cargo workspace à introduire après cadrage ; coût d'apprentissage et d'intégration à mesurer. Aucun découpage définitif en crates n'est approuvé ici.
