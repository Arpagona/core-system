# Guide « nouveau poste » — état vérifié au 10 novembre 2026

Ce guide décrit la mise en route d'un poste de travail pour l'atelier `Arpagona/core-system`. Il distingue ce qui a été **réellement exécuté** de ce qui reste **à confirmer sur un poste neuf**.

## 1. Ce qui a été vérifié, et dans quel cadre

- **Environnement vierge simulé** : clone réel depuis GitHub dans un répertoire isolé, puis exécution des commandes ci-dessous. Ce n'est **pas** une installation d'un système d'exploitation neuf : le poste utilisé disposait déjà de Git, Python 3.14, rustup et de la toolchain 1.95.0.
- **SHA contrôlé** : `c8d764e893ef96033036ce9b7700ca373b655d81` (tête de la branche `atelier/cadrage-v0-1`, PR [#1](https://github.com/Arpagona/core-system/pull/1), non fusionnée).
- **Résultat** : les neuf commandes de la section 3 se terminent avec le code 0. Le clone ressort propre (`git status --porcelain` vide) après génération de la page locale.
- **Non vérifié** : installation réelle sur un OS vierge, postes macOS et Windows, second participant humain, accès réseau d'entreprise, proxy. Ces points restent ouverts (voir la section 6).

## 2. Prérequis

| Élément | Version / état constaté | Remarque |
|---|---|---|
| Git | présent sur le poste de test | protocole HTTPS |
| Python | 3.14.9 | 3.10+ suffisant pour les scripts actuels |
| rustup + Rust | toolchain `1.95.0` imposée par `rust-toolchain.toml` (rustc 1.95.0, cargo 1.95.0) | rustup installe la toolchain exacte et les composants `rustfmt`, `clippy` |
| Accès GitHub | compte personnel invité sur le dépôt **privé** | aucun mot de passe ni code 2FA ne doit être transmis à un agent |

Le dépôt est privé : sans invitation, `git clone` échoue. C'est le comportement attendu.

## 3. Commandes vérifiées

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

Puis ouvrir localement `site/index.html` dans un navigateur. Cette page reste **locale et privée** : aucun hébergement public n'est configuré (l'API GitHub Pages du dépôt répond 404). Ne pas la publier.

Les commandes sont aussi rejouées par la CI avec les mêmes options ; la CI ajoute `--offline` et `python3 scripts/security_checks.py`. Voir les [vérifications de la PR #1](https://github.com/Arpagona/core-system/pull/1/checks) : les résultats doivent correspondre au SHA courant affiché en tête de PR. Ces liens exigent un accès au dépôt privé.

## 4. Ce que l'on doit voir

- `cargo test --workspace` : 1 test d'intégration vert sur la branche atelier (`consommateur_respecte_le_contrat`). Sur la branche de démonstration du lot 3, 2 tests verts.
- `python3 tests/rupture_contrat.py` : affiche `RUPTURE exit: 101` avec `E0308`, puis `CORRECTION exit: 0`. Il travaille sur une copie temporaire et ne modifie aucune source.
- `python3 tests/architecture.py` : scénarios sain, divergence, identifiant manquant, échappement HTML ; code 0.
- `python3 tests/guardian.py` : état sain, CI inconnue, CI en échec, divergence ; code 0.
- `python3 scripts/architecture.py` : `[]` et code 0.
- `python3 scripts/build_docs.py` : `20 documents → .../site/index.html`.
- `python3 scripts/security_checks.py` : `Aucune dépendance externe et aucun des motifs sensibles ciblés détectés (couverture limitée).`

Un écart sur l'un de ces points est un incident à signaler, pas une étape à contourner.

## 5. Après la fusion humaine de la PR #1

La PR #1 n'est pas fusionnée : `main` ne contient pas encore le workspace. Une fois la fusion décidée **par un humain** :

```sh
git switch main && git pull
git switch -c feat/mon-chantier
```

Ne jamais pousser directement sur `main`. La protection technique de `main` est **non disponible** sur la formule actuelle (403 vérifié le 10/11/2026) : l'interdiction est **procédurale**.

## 6. Limites et points à confirmer sur un vrai poste neuf

1. Installation réelle de Git, Python et rustup sur un OS nu, y compris droits administrateur et proxy.
2. Comportement sur macOS et Windows (chemins, fins de ligne) ; `.gitattributes` est présent mais non validé sur ces plateformes.
3. Accès effectif des comptes de Maël et Stéphane : au 10/11/2026, l'API ne liste que le compte `Arpagona` comme collaborateur.
4. Téléchargement de la toolchain 1.95.0 derrière un pare-feu d'entreprise.
5. Ouverture de la page HTML dans un navigateur autre que celui du poste de test.

## 7. Consigne à donner à un agent de codage

> Lis `AGENTS.md`, `README.md`, `docs/VISION.md`, `docs/ARCHITECTURE.md`, `docs/INTERFACES.md`, `CONTRIBUTING.md`, les ADR pertinents et l'Issue. Annonce le périmètre, les modules et les contrats touchés. Ne modifie jamais `main`, ne fusionne pas, n'ajoute aucun secret. Signale toute divergence entre la documentation et le code au lieu de la contourner.

La suite du parcours est décrite dans le [guide « nouvelle tâche »](GUIDE_NOUVELLE_TACHE.md) et l'état vérifié de la recette dans le [rapport de recette](RAPPORT_RECETTE.md).
