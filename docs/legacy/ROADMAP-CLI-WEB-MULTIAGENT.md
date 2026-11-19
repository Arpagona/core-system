# Pistes après le spike CLI — proposition du 11 novembre 2026

Ce document prépare une discussion ; il n'approuve ni architecture ni contrat. Les contrats communs et leur migration exigent l'accord explicite de Thibaud, Maël et Stéphane avant développement dépendant. La préversion CLI n'est pas une plateforme multi-agents ni un produit réceptionné. Le plan historique M0–M6 décrit des étapes, non une garantie de leur livraison.

1. **Session CLI persistante.** Clarifier continuité de mission, reprise explicite, annulation et budget durable. Preuves attendues : redémarrage et reprise, non-rejeu d'effet incertain, isolation, contrôle des coûts, parcours complet réel. Exclusion : autonomie ou démon implicite.
2. **Interface Web.** Réutiliser le même noyau, sans en contourner les politiques ; proposer authentification, permissions et journalisation avant toute exposition. Preuves attendues : isolation de sessions, refus d'accès, validation des origines et effets, audit, arrêt/reprise. Choix de technologie et contrats à revoir à trois. Aucun serveur ou port réseau n'est ouvert par cette proposition.
3. **Multi-agents.** Proposer sous-missions bornées, budget global, isolation des contextes, propagation d'annulation et absence d'escalade de droits. Sélectionner un premier cas synthétique et justifier par comparaison avec un mono-agent à objectifs identiques : qualité vérifiable, coût, durée et surface de risque. Aucun orchestrateur n'est ajouté maintenant.

Avant chaque étape, distinguer scénarios synthétiques, preuves sur fournisseur réel et validation humaine. Pas de données client, déploiement en production ni autorisation supplémentaire par défaut.
