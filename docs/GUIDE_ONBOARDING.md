# Nouveau poste (à vérifier en environnement vierge)

Prérequis : Git, Python 3 et rustup installés, accès personnel autorisé au dépôt privé. La PR [#1](https://github.com/Arpagona/core-system/pull/1) est ouverte, non fusionnée : **main ne contient pas encore le workspace**. Pour consulter la démonstration actuelle sans prétendre qu'elle est intégrée :

```sh
git clone --branch atelier/cadrage-v0-1 https://github.com/Arpagona/core-system.git
cd core-system
rustup show
cargo fmt --all -- --check
cargo check --workspace --all-targets --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo test --workspace --locked
python3 tests/rupture_contrat.py
python3 tests/architecture.py
python3 tests/guardian.py
python3 scripts/build_docs.py
```

Ouvrir localement `site/index.html` dans le navigateur ; ne pas publier cette page. Voir les [fichiers de la PR](https://github.com/Arpagona/core-system/pull/1/files) et ses [vérifications](https://github.com/Arpagona/core-system/pull/1/checks) ; les résultats doivent concerner le SHA courant. Ces liens nécessitent un accès au dépôt privé.

Une fois la PR fusionnée **par décision humaine**, le workflow normal démarre d'un clone de main à jour puis `git switch -c feat/mon-chantier`. Ne pas pousser sur main. Aucune fusion n'est autorisée ici.

Pour tout agent, donner explicitement ce point de départ : « Lis `AGENTS.md`, `README.md`, `docs/VISION.md`, `docs/ARCHITECTURE.md`, `docs/INTERFACES.md`, `CONTRIBUTING.md`, les ADR pertinents et l'Issue ; annonce le périmètre et les contrats touchés ; ne modifie pas main. » Les accès et ce scénario sur poste vierge ne sont pas encore validés.
