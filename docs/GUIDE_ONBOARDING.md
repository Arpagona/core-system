# Nouveau poste (à vérifier en environnement vierge)

Prérequis : Git, Python 3 et rustup installés selon les instructions officielles, accès personnel autorisé au dépôt privé. Depuis un clone :

```sh
git clone https://github.com/Arpagona/core-system.git
cd core-system
git switch -c feat/mon-chantier
rustup show
cargo fmt --all -- --check
cargo check --workspace --all-targets --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo test --workspace --locked
python3 tests/rupture_contrat.py
python3 scripts/build_docs.py
```

rustup installe la toolchain exacte spécifiée si nécessaire. Lire README, AGENTS, l'Issue, les contrats et ADR avant modification. Les accès et ce scénario sur poste vierge ne sont pas encore validés.
