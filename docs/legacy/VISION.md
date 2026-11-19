# Vision

Construire un socle agentique réutilisable, fiable et adaptable aux besoins métier d'ARPAGONA. Permettre à trois co-concepteurs et leurs agents de travailler en parallèle avec des contrats explicites, des tests reproductibles et des décisions traçables.

## Principes retenus dans le cadrage du 10 novembre 2026

Rust modulaire ; adaptateurs Python isolés si nécessaires. GitHub Cloud, dépôt privé, organisation cible ARPAGONA. Markdown versionné comme référence ; HTML généré comme vue. Guardian indépendant et validation humaine de production. Isolation stricte des environnements et données par client.

## Hors périmètre initial

Pas de moteur complet, pas de sept modules implémentés par anticipation, pas de données clients, pas de production, pas de publication open source décidée, pas de reprise implicite d'un ancien projet.

## Première preuve recherchée

Après revue des contrats : deux crates simples, contributions depuis plusieurs postes, PR rompant volontairement un contrat, détection avant intégration, correction, version commune testée et déploiement de test. La rupture volontaire ne doit jamais être fusionnée. Les preuves multi-PC et déploiement ne peuvent pas être simulées par un simple test local.
