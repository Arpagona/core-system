# Agent Core — ARPAGONA

Atelier de développement collaboratif de Thibaud, Maël et Stéphane, trois co-concepteurs à responsabilité égale.

Socle agentique réutilisable en Rust, organisé par responsabilités fonctionnelles. Adaptateurs Python isolés si nécessaire. Le nom du dépôt `core-system` est conservé ; aucun ancien code n'a été importé.

## Références

- [Cadrage transmis, v0.1](docs/ATELIER-v0.1.md) : décisions retenues et propositions ouvertes.
- [Vision](docs/VISION.md)
- [Proposition d'architecture](docs/ARCHITECTURE.md) et [contrats proposés](docs/INTERFACES.md)
- [Gouvernance et contributions](CONTRIBUTING.md)
- [Consignes aux agents](AGENTS.md)
- [Guardian](docs/GUARDIAN.md)
- [État réel de l'atelier et expérience initiale](docs/ATELIER-STATUS.md)
- [Décisions](docs/decisions/)

## État

Cadrage initial, pas de moteur fonctionnel. L'architecture doit être relue à trois avant les développements qui en dépendent. Aucun déploiement de production autorisé par ce dépôt.

Le dépôt est privé. La publication open source n'est pas décidée. La licence Apache-2.0 du commit initial reste présente dans l'historique ; son retrait de l'arbre courant ne révoque aucun droit déjà accordé. Toute future politique de licence nécessite une décision collective.

## Vue HTML locale

`python3 scripts/build_docs.py` génère `site/index.html` à partir des Markdown versionnés. Ouvrir ce fichier localement. Cette vue n'est pas une seconde source de vérité ; aucun hébergement public n'est configuré.

## Limites actuelles

Le propriétaire GitHub `Arpagona` est encore un compte personnel, pas une organisation. Les protections obligatoires de branche ne sont pas disponibles sur sa formule actuelle. Voir l'état détaillé avant de considérer l'atelier opérationnel.

## Expérience Rust jetable

Deux crates synthétiques sous `experiments/` vérifient un contrat ; aucun code produit. Voir [guide poste neuf](docs/GUIDE_ONBOARDING.md), [workflow](docs/WORKFLOW.md), [sécurité](docs/SECURITY.md) et [plan](docs/PLAN-P0-P1.md).
