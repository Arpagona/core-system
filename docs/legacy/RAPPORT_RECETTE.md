# Rapport de recette — atelier ARPAGONA — 10 novembre 2026

Périmètre : préparation de l'atelier `Arpagona/core-system` (P5/P6). Ce rapport **ne déclare pas** la réception finale : l'acceptation appartient aux trois co-concepteurs, le déploiement à une décision humaine distincte.

Référence de code : `main` = `92f47f0deba3fbaf80c19750c5c2a435689c80e6` (inchangé du début à la fin du lot), branche atelier `atelier/cadrage-v0-1` = `c8d764e893ef96033036ce9b7700ca373b655d81` (PR [#1](https://github.com/Arpagona/core-system/pull/1), non fusionnée).

## 1. Dérogation enregistrée

Thibaud a approuvé le 10/11/2026, dans Telegram, la **réception procédurale** des trois lots, en remplacement du contrat qui exigeait des required checks GitHub indisponibles sur cette formule privée. Cette dérogation ne dispense d'aucune preuve : PR publiées, CI verte vérifiée sur le SHA exact, tests rejoués, rapport et revue restent obligatoires. Elle ne vaut pas acceptation collective et n'autorise aucune fusion ni aucun déploiement.

## 2. Garanties : ce qui est imposé, suivi, ou impossible

| Garantie | Statut | Preuve / limite |
|---|---|---|
| Les jobs CI lisent seuls les sources, sans secret | **ENFORCÉ** | workflows `permissions: contents: read` ; `default_workflow_permissions = read` sur le dépôt ; aucune référence `secrets.*` dans `.github/` |
| Les contrôles portent sur le SHA de tête de la PR | **ENFORCÉ** | `actions/checkout` avec `ref: github.event.pull_request.head.sha` ; artefact nommé par SHA |
| Les artefacts Guardian et démonstration sont privés et éphémères | **ENFORCÉ** | dépôt privé ; artefacts Actions, rétention 7 jours |
| `site/index.html` n'est pas publié | **ENFORCÉ** | API GitHub Pages → 404 |
| Aucune fusion de `main` sans revue | **PROCÉDURAL** | aucune protection de branche possible (voir ci-dessous) ; discipline seule |
| CI verte exigée comme critère de réception | **PROCÉDURAL** | vérifiée à la main sur le SHA exact, non imposée par la plateforme |
| Revue indépendante et accord des trois | **PROCÉDURAL** | un seul compte GitHub dispose d'un accès ; non exerçable aujourd'hui |
| Guardian constitue un avis indépendant | **PROCÉDURAL, LIMITÉ** | script déterministe hébergé dans le dépôt examiné, sans LLM ; ne comprend pas le code |
| Protection obligatoire de `main` | **NON DISPONIBLE** | HTTP 403 « Upgrade to GitHub Pro… » vérifié les 10/11/2026 (formule Free, dépôt privé) |
| Serveur de test et déploiement | **NON DISPONIBLE / NON EXÉCUTÉ** | aucun hôte, aucun accès, aucun secret, aucune exécution distante |
| Comptes Maël / Stéphane, organisation | **NON DISPONIBLE** | API : un seul collaborateur `Arpagona` (admin), propriétaire de type `User` |

## 3. Rouge puis vert sur une PR réelle

PR de démonstration [#6](https://github.com/Arpagona/core-system/pull/6), titre « DÉMONSTRATION — NE PAS FUSIONNER », base `atelier/cadrage-v0-1` (branche non fusionnée, `main` intact).

### 3.1 État rouge — SHA `bf6482171acfa3c5360750718690adb07f9b09ea`

Deux défauts introduits ensemble, comme un vrai changement de contrat mal propagé :

1. `experiments/contrat/src/lib.rs` : `etiquette(nombre: u32)` → `etiquette(nombre: u32, prefixe: &str)`, **sans adapter** l'appel `atelier_contrat::etiquette(7)` dans `experiments/demo/src/lib.rs` ni le test de contrat.
2. `docs/modules.json` : dépendance déclarée `atelier-contrat → atelier-demo`, l'inverse de la réalité Cargo.

| Contrôle | Résultat | Run | Trace |
|---|---|---|---|
| `rust` | **échec** | [42868892561](https://github.com/Arpagona/core-system/actions/runs/42868892561) | `error[E0061]: this function takes 2 arguments but 1 argument was supplied` — `experiments/demo/src/lib.rs:3:5` |
| `docs` | **échec** | [42868892470](https://github.com/Arpagona/core-system/actions/runs/42868892470) | `"message": "atelier-contrat: chemin/dépendances déclarés experiments/contrat ['atelier-demo'] != réels experiments/contrat []"` |
| `documentation` | **échec** | [42868892477](https://github.com/Arpagona/core-system/actions/runs/42868892477) | `ValueError: [... dépendances déclarés … != réels …]`, la génération refuse de produire une page sur un registre divergent |
| `guardian` | **échec** | [42868892345](https://github.com/Arpagona/core-system/actions/runs/42868892345) | rapport `guardian-report.json`, verdict **« à corriger »**, 1 anomalie, SHA et base exacts ; artefact `sha256:d4997d3dfbeada8032ca7298bfe8be93348635350f0915bd70fe2bac294cce43` |

Le contrat n'est donc pas seulement « cassé » : la divergence documentaire est détectée par **deux** contrôles distincts, et Guardian refuse de conclure à l'accord.

### 3.2 État vert — SHA `73c5590cc0b1e5dccbbf95fb9a989253e3fc65db`

Correction dans la **même** PR :

- consommateur adapté : `atelier_contrat::etiquette(7, "atelier")` ;
- test de contrat complété, sans en retirer : `consommateur_respecte_le_contrat` + nouveau `prefixe_est_transmis_au_contrat` (2 tests verts) ;
- `docs/INTERFACES.md` : signature EXP-001 documentée, avec mention explicite que le changement reste **proposé** et exigerait l'accord des trois ;
- `docs/modules.json` : divergence retirée (retour à la dépendance réelle).

| Contrôle | Résultat | Run | Trace |
|---|---|---|---|
| `rust` | **succès** | [42869203103](https://github.com/Arpagona/core-system/actions/runs/42869203103) | fmt, check, clippy, tests, rupture de contrat, sécurité, artefact |
| `documentation` | **succès** | [42869202737](https://github.com/Arpagona/core-system/actions/runs/42869202737) | page générée, fichiers requis présents, `git diff --check` |
| `docs` | **succès** | [42869202875](https://github.com/Arpagona/core-system/actions/runs/42869202875) | architecture + tests architecture/Guardian + build |
| `guardian` | **succès** | [42869202814](https://github.com/Arpagona/core-system/actions/runs/42869202814) | nouveau rapport : verdict **« réserves »**, **0 anomalie**, 5 signaux (4 fichiers d'interface + « CI inconnue ») |

**Aucun test n'a été affaibli pour obtenir ce vert** : `tests/rupture_contrat.py` n'a pas été modifié, il continue de provoquer `E0308` puis de revenir à 0 ; le seul changement de test est l'ajout d'une assertion couvrant le nouveau paramètre.

La PR #6 est **laissée ouverte et non fusionnée**, comme demandé. Son contenu n'est pas destiné à `main` : il documente un exercice.

## 4. Matrice REC-01 → REC-08

| # | Exigence | Statut | Preuves exactes | Ce qui manque |
|---|---|---|---|---|
| REC-01 | Poste vierge (ou simulé) : clone, lecture, Rust, contrôles | **prouvé (environnement vierge simulé)** — partiel sur un OS réellement neuf | clone réel de `atelier/cadrage-v0-1` dans un répertoire isolé, `HEAD = c8d764e…`, `git status` vide, 9 commandes documentées → code 0 | installation OS nue, macOS/Windows, proxy |
| REC-02 | Deux branches indépendantes, PR sans toucher `main` | **prouvé techniquement, partiel humainement** | `sim/participant-a-etiquette` `b0af58f8…` → PR [#4](https://github.com/Arpagona/core-system/pull/4), 4 checks verts (runs 42868786409 / 42868786725 / 42868786493 / 42868786532) ; `sim/participant-b-workflow` `3832e9c9…` → PR [#5](https://github.com/Arpagona/core-system/pull/5), 4 checks verts (runs 42868789641 / 42868789619 / 42868789695 / 42868789633) ; `main` reste `92f47f0…`. PR de simulation fermées sans fusion, branches conservées. | **un seul auteur et une seule machine** : ces journaux ne prouvent pas deux participants réels |
| REC-03 | Signature modifiée sans adapter l'appel → échec visible | **prouvé** | PR #6 `bf64821…`, rust en échec `E0061`, run 42868892561 | — |
| REC-04 | Correction, test ajouté, contrats à jour, CI verte, nouveau Guardian | **prouvé** | PR #6 `73c5590…`, 4 checks verts, 2 tests, `INTERFACES.md` mis à jour, Guardian « réserves » sans anomalie | — |
| REC-05 | Divergence documentaire A→B détectée | **prouvé** | PR #6 `bf64821…` : `docs` (42868892470), `documentation` (42868892477), Guardian « à corriger » (42868892345) | — |
| REC-06 | Décision collective à trois sur une interface commune | **en attente (humain)** | la PR #6 est consultable et commentable ; Thibaud a approuvé la réception procédurale le 10/11/2026 | comptes Maël/Stéphane absents ; aucun accord des trois enregistré. L'accord serait **procédural**, non imposé par la plateforme |
| REC-07 | Artefact versionné construit, déployé seulement si autorisé | **partiel** | artefact du run 42868051788 (SHA `c8d764e…`) téléchargé : archive `sha256:2d74dfcf…`, binaire `503b86ab…`, `VERSION.txt` = commit, exécution `atelier-7` code 0 | **aucun déploiement** : pas de serveur, pas d'accès, pas d'autorisation (Issue [#9](https://github.com/Arpagona/core-system/issues/9)) |
| REC-08 | Aucun secret ; workflow sans accès silencieux aux secrets ; limites Guardian décrites | **prouvé sur le périmètre contrôlable** | `python3 scripts/security_checks.py` OK ; aucune référence `secrets.*` ; `default_workflow_permissions=read` ; aucune protection technique de `main` | absence exhaustive de secret non démontrable par motifs ; Guardian dans le dépôt examiné |

## 5. Matrice des objectifs

| # | Objectif | Statut | Preuve / limite |
|---|---|---|---|
| OBJ-01 | Trois personnes travaillent indépendamment | **partiel** | mécanique clone/branche/push/PR prouvée (REC-02) ; un seul compte réel |
| OBJ-02 | Même vérité de projet | **prouvé (procédural pour le chargement)** | `AGENTS.md`, `docs/` versionnés, référencés par PR et Issue ; le fait que chaque agent les lise au démarrage reste une consigne |
| OBJ-03 | Pas d'intégration sans revue | **partiel** | PR de démonstration soumise à 4 contrôles + Guardian ; revue humaine non exerçable, aucune barrière technique |
| OBJ-04 | Rupture d'interface visible avant intégration | **prouvé** | `E0061` sur PR #6 + `tests/rupture_contrat.py` (`E0308` → 0) |
| OBJ-05 | Architecture documentaire confrontée au code | **prouvé** | divergence déclarée détectée par `architecture.py` et par `build_docs.py` ; correction vérifiée |
| OBJ-06 | Architecture compréhensible visuellement | **prouvé** | `site/index.html` généré (20 documents), modules/dépendances/contrats/liens ; page locale privée (Pages 404) |
| OBJ-07 | Version testable livrable séparément | **partiel** | artefact CI identifié par SHA et empreinte, vérifié en isolation ; installation sur serveur de test non exécutée |
| OBJ-08 | Opérations sensibles contrôlées | **prouvé sur ce lot** | aucun secret, aucun merge, aucun déploiement, aucune création engageante ; `main` inchangé |

## 6. Matrice GH / MEM / GOV / GU / DOC / ENV

### GitHub (GH)

| # | Statut | Preuve / limite |
|---|---|---|
| GH-01 | **prouvé** | dépôt `Arpagona/core-system` privé, propriétaire `User`, `main = 92f47f0…`, aucun dépôt ancien modifié, aucun transfert |
| GH-02 | **non réalisé** | organisation non créée, un seul collaborateur (Issue [#7](https://github.com/Arpagona/core-system/issues/7)) |
| GH-03 | **prouvé** | dépôt privé avec `README`, `AGENTS.md`, `docs/`, `.github/`, `Cargo.toml`, `rust-toolchain.toml` — via la PR #1 non fusionnée, pas de duplication d'ancien projet |
| GH-04 | **prouvé (procédural pour l'interdiction)** | branches courtes `feat/`, `docs/`, `sim/`, `demo/` ; PR liées ; `main` jamais poussé ; interdiction non imposée par la plateforme |
| GH-05 | **partiel** | jetons à portée `repo`, `workflow`, `gist`, `read:org` (plus large que le minimum) ; 2FA non vérifiable ; aucun secret dans le dépôt ; jeton CI en lecture seule par défaut |
| GH-06 | **prouvé** | 403 sur `branches/main/protection`, message exact « Upgrade to GitHub Pro… », 10/11/2026 |

### Mémoire collective (MEM)

| # | Statut | Preuve / limite |
|---|---|---|
| MEM-01 | **prouvé** | `AGENTS.md` impose la lecture préalable et l'annonce du périmètre ; guide nouvelle tâche |
| MEM-02 | **partiel** | référentiel unique respecté ; un seul agent de codage réellement exercé, adaptateurs non testés à trois outils |
| MEM-03 | **prouvé (règle), non exercé** | règle Issue + PR + ADR ; la démonstration montre le coût d'un changement de contrat non propagé |
| MEM-04 | **partiel** | trois ADR (Rust, isolation, workspace) ; Guardian et la dérogation de réception ne sont pas encore en ADR |
| MEM-05 | **en attente** | documentation produit encore « proposition » ; commentaires de Maël et Stéphane non disponibles |

### Gouvernance (GOV)

| # | Statut | Preuve / limite |
|---|---|---|
| GOV-01 | **procédural** | pilote temporaire par chantier, aucun chef permanent ; un auteur ne peut être son unique relecteur — non imposé techniquement |
| GOV-02 | **partiel** | signaux automatiques de chemins sensibles produits par Guardian ; la revue élargie reste une décision |
| GOV-03 | **partiel** | `docs/WORKFLOW.md` décrit la suspension et l'arbitrage par options mesurables ; aucun cas réel de désaccord exercé |
| GOV-04 | **procédural** | modèle d'Issue avec pilote et modules ; deux PR simultanées sur une interface n'ont pas été exercées (les branches de simulation sont disjointes) |

### Guardian (GU)

| # | Statut | Preuve / limite |
|---|---|---|
| GU-01 | **partiel** | Guardian n'est pas l'auteur du contenu examiné, mais il est écrit et exécuté dans le même dépôt : indépendance organisationnelle absente |
| GU-02 | **partiel** | signaux sur `INTERFACES.md`, `.rs`, `.github/`, `scripts/`, modules affectés ; aucune analyse sémantique, aucune détection exhaustive d'API |
| GU-03 | **prouvé** | JSON structuré : synthèse, modules, exigences, anomalies avec fichier/ligne/test, signaux, recommandations, limites, verdict accord/réserves/à corriger |
| GU-04 | **prouvé** | `contents: read`, aucun droit de fusion/déploiement, rapport publié en artefact privé, Guardian ne modifie aucune règle |
| GU-05 | **prouvé** | aucun LLM, aucun transfert vers un modèle externe ; revue sémantique IA non activée |
| GU-06 | **prouvé par construction (partiel en intention)** | script déterministe : les fichiers sont lus comme données, aucune instruction exécutée ; non testé contre une PR hostile réelle |
| GU-07 | **prouvé** | PR rouge (`bf64821…`, 4 échecs) vs PR corrigée (`73c5590…`, 4 succès) ; les échecs déterministes restent visibles indépendamment du verdict Guardian |

### Documentation (DOC)

| # | Statut | Preuve / limite |
|---|---|---|
| DOC-01 | **prouvé** | HTML généré depuis Markdown + `cargo metadata` + registre `docs/modules.json` |
| DOC-02 | **prouvé** | modules, responsabilités, dépendances, contrats et statuts, ADR, liens vers sources |
| DOC-03 | **prouvé** | page locale ; Pages 404 ; aucun hébergement public |
| DOC-04 | **prouvé** | comparaison crates/chemins/dépendances/identifiants/fichiers de test ; limites écrites dans `MODULES.md` et `GUARDIAN.md` |
| DOC-05 | **prouvé** | génération à chaque CI et localement, reproductible, sans second diagramme manuel |

### Environnements (ENV)

| # | Statut | Preuve / limite |
|---|---|---|
| ENV-01 | **procédural** | séparation décrite (postes, CI, test, client) ; aucun isolement réseau vérifié |
| ENV-02 | **prouvé (document)** | `docs/DEPLOY_TEST.md` créé : préparation, promotion, retour arrière, aucun exemple exécuté |
| ENV-03 | **prouvé** | artefact de démonstration non productif, identifié commit + version, construit par CI, vérifié et hashé |
| ENV-04 | **prouvé (document)** | procédure de retour arrière et conditions de promotion écrites, non mises en œuvre |

## 7. Écarts, risques et décisions humaines restantes

1. **Organisation et accès** — organisation non créée, comptes Maël/Stéphane absents, propriétaire `User`. Bloque REC-06 et l'acceptation à trois. → Issue [#7](https://github.com/Arpagona/core-system/issues/7).
2. **Protection de `main`** — 403 vérifié ; aucune barrière technique. Risque : fusion sans revue par un administrateur. → Issue [#8](https://github.com/Arpagona/core-system/issues/8).
3. **Indépendance de Guardian et de la CI** — Guardian et les workflows sont dans le dépôt examiné, sans signature externe ; Guardian est déterministe, sans LLM. → Issue [#8](https://github.com/Arpagona/core-system/issues/8).
4. **Serveur de test et déploiement** — préparation seulement ; aucun hôte, accès ni secret. → Issue [#9](https://github.com/Arpagona/core-system/issues/9).
5. **Licence et propriété** — non décidées collectivement ; Apache-2.0 du commit initial retirée de l'arbre courant. → Issue [#10](https://github.com/Arpagona/core-system/issues/10).
6. **Preuve humaine de deux participants** — les journaux de branches prouvent la mécanique, pas deux personnes ni deux machines.
7. **Secrets et jetons** — le jeton du compte utilisé en local a des portées plus larges que nécessaire ; à réduire lors de la mise en place des accès à trois.
8. **Fusion de la PR #1** — non fusionnée ; `main` ne contient ni workspace ni documentation récente. Toute la démonstration repose sur une branche.

## 8. Backlog priorisé

| Priorité | Action | Dépend de |
|---|---|---|
| **P0** | Décider organisation + comptes Maël/Stéphane, inviter avec droits égaux | Thibaud, Maël, Stéphane (#7) |
| **P0** | Décider la formule GitHub ou accepter explicitement l'absence de protection de `main` | Thibaud (#8) |
| **P0** | Revue à trois de la PR #1 (architecture et contrats), puis décision de fusion | trois co-concepteurs |
| **P1** | Revue de la PR de démonstration #6 et clôture sans fusion après capture | trois co-concepteurs |
| **P1** | Choisir le serveur de test, les accès et la fenêtre ; exécuter DEPLOY_TEST | Thibaud (#9) |
| **P1** | Réduire la portée des jetons, activer la 2FA documentée sur les trois comptes | trois co-concepteurs |
| **P2** | Guardian hors dépôt ou signé ; jobs requis si formule payante | décision (#8) |
| **P2** | Revue sémantique par IA de Guardian (fournisseur et confidentialité à décider) | décision humaine (GU-05) |
| **P2** | ADR sur la dérogation de réception procédurale et sur Guardian | trois co-concepteurs |
| **P2** | Licence et propriété du code | décision humaine (#10) |
| **P3** | Intégration des agents à GitHub, télémétrie de développement, produit Agent Core | hors mandat |

## 9. Preuves locales rejouées par GONA (10/11/2026)

Sur le poste de travail, à `c8d764e…` : `cargo fmt --all -- --check`, `cargo check --workspace --all-targets --locked --offline`, `cargo clippy --workspace --all-targets --locked --offline -- -D warnings`, `cargo test --workspace --locked --offline`, `python3 tests/rupture_contrat.py`, `python3 tests/architecture.py`, `python3 tests/guardian.py`, `python3 scripts/architecture.py`, `python3 scripts/build_docs.py`, `python3 scripts/security_checks.py`, `git diff --check` → **tous code 0**.

Dans l'environnement vierge simulé, les 9 commandes du guide → **toutes code 0**. Ces exécutions ne remplacent pas la CI : elles la précèdent.

## 10. Ce que ce rapport ne prouve pas

- Il ne prouve pas que trois personnes peuvent travailler ensemble : un seul compte GitHub existe.
- Il ne prouve pas qu'une fusion non autorisée est impossible : aucune protection de branche n'est active.
- Il ne prouve pas l'indépendance de Guardian : même dépôt, même auteur, sans LLM.
- Il ne prouve pas l'isolation d'un serveur, d'un réseau ou de données client : rien n'a été déployé.
- Il ne prouve pas l'absence exhaustive de secrets : les contrôles sont des motifs, pas une analyse complète.
- Il ne vaut pas acceptation : celle-ci appartient à Thibaud, Maël et Stéphane.
