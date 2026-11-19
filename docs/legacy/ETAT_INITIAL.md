# P0 — État initial de l'atelier ARPAGONA

PHASE / DATE : P0, 2026-11-10.
OBJECTIF : compléter l'inventaire non destructif selon ARP-DEV-CDC-001 v1.0, après la première adaptation autorisée du dépôt.

## Source du mandat

Copie durable exacte : `/home/thibaud/arpagona-agent-core/documents/ARP-DEV-CDC-001-v1.0.md`.
SHA-256 : `5642cd3ba2a97c90b2b0d6badf5221f211814975e77f9d1199f3003ffd3aa798`.
Le document v1.0 remplace les suppositions de préparation ; il ne valide pas l'architecture produit proposée dans PR 1.

## Travaux et preuves

Inventaire API GitHub en lecture seule avec la connexion Arpagona déjà présente dans gh ; aucun secret affiché ni changement du compte actif global. Liste `user/orgs` vide pour cette connexion : aucune organisation accessible retournée. Cela ne prouve pas l'absence d'organisations accessibles par d'autres comptes.

- https://github.com/Arpagona/core-system : privé, propriétaire de type User, main `92f47f0deba3fbaf80c19750c5c2a435689c80e6`, droits admin disponibles via compte Arpagona. Cible existante désignée par Thibaud dans l'instruction précédente.
- https://github.com/Arpagona/Agent-core : public, main, dernier push retourné `2026-06-01T10:26:48Z`. Ancien travail : exclu des mutations.
- https://github.com/Arpagona/arpagona-core-one : privé, main, dernier push retourné `2026-06-19T16:16:31Z`. Ancien travail : exclu des mutations.
- Autres dépôts retournés par l'inventaire : Arpagona/hermes-agent-backup (privé), Arpagona/openclaw-squeezer-hybrid (public), Arpagona/lab (public). Hors périmètre, aucun contenu inspecté.

Clone de travail : `/home/thibaud/projects/arpagona-core-system`, propre au moment de l'audit. Branche `atelier/cadrage-v0-1`, commit `c879be48cb1c1c95377bd80c9130a342b4ea7fab`.
PR ouverte : https://github.com/Arpagona/core-system/pull/1 . Aucun merge.
Workflow existant retourné actif : `.github/workflows/validation.yml`, Validation atelier. Première CI documentaire verte vérifiée au tour précédent : https://github.com/Arpagona/core-system/actions/runs/42864359595 . Ce n'est pas une preuve de CI Rust.
GitHub Actions : enabled=true, allowed_actions=all, sha_pinning_required=false. Les actions du workflow existant sont épinglées ; ce n'est pas une règle imposée à tous les futurs workflows.
Collaborateurs retournés : Arpagona admin uniquement. Accès réels de Maël et Stéphane non établis. État 2FA non vérifié.

## Outils vérifiés

- rustc 1.95.0 (59807616e 2026-04-14)
- cargo 1.95.0 (f2d3ce0bd 2026-03-21)
- Python 3.14.9
- gh 2.46.0

## Règles ENFORCÉES / PROCÉDURALES / NON DISPONIBLES

- Visibilité privée : ENFORCÉ par GitHub pour l'état actuel du dépôt ; n'efface pas son historique précédemment public.
- Permissions CI en lecture seule : déclarées dans le workflow existant ; règles procédurales de maintenance à préserver, pas verrou contre un administrateur.
- Interdiction de push direct, revue humaine, accord à trois, Guardian : PROCÉDURAL ; Guardian pas encore implémenté.
- Protection obligatoire de main : NON DISPONIBLE dans la formule actuelle, API HTTP 403 « Upgrade to GitHub Pro or make this repository public ». Ne pas rendre public pour contourner.

## Risques et écarts

Organisation cible absente de cet inventaire ; ne pas transformer le compte personnel, transférer ou renommer un dépôt sans accord. Préserver Agent-core et arpagona-core-one. Ne pas confondre l'accès admin disponible avec l'approbation de distribuer des droits.
La PR 1 contient une proposition d'architecture, non une architecture produit approuvée. Aucun code du produit ne doit être commencé. Seules deux crates jetables sous experiments/ sont autorisées par le nouveau mandat.
La CI documentaire existante n'est pas la recette demandée. Manquent : CI Rust, tests négatifs, contrôle metadata/documentation, Guardian déterministe, artefact, guides et preuves de réception.

## Décisions humaines nécessaires, sans bloquer la préparation locale

Organisation et éventuel transfert ; formule GitHub ; identifiants et droits Maël/Stéphane ; licence ; destination et accès du serveur de test. Guardian initial sans LLM externe, explicitement permis par le mandat. Aucun fournisseur externe ajouté.

## Prochaine action

Lots séquentiels et bornés : (1) workspace expérimental et CI Rust ; (2) Guardian déterministe et vue HTML liée à cargo metadata ; (3) exercice négatif/correction, simulation poste neuf, guides et rapport de recette avec statut réel REC-01 à REC-08. Branches/PR autorisées, aucun merge autonome, aucune installation client ou production. Les points nécessitant les trois humains et un serveur autorisé resteront explicitement non reçus.
