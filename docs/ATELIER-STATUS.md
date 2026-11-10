# État de l'atelier — 10 novembre 2026

## Vérifié lors de l'adaptation

- Dépôt existant : `Arpagona/core-system`, main, initialement README et licence Apache-2.0 seulement.
- Dépôt passé en privé et relu via l'API GitHub.
- Propriétaire `Arpagona` de type `User` : organisation cible non créée. Ne pas convertir ce compte personnel sans décision explicite.
- API protections de branche : HTTP 403, demande GitHub de passer à Pro ou de rendre public. Conserver le privé ; ne pas prétendre que les règles sont imposées.
- Liste des collaborateurs retournée : `Arpagona` admin uniquement. Identifiants Maël/Stéphane à fournir.

## Livré dans cette proposition

Cadrage source, consignes agents, vision, proposition d'architecture et contrats, règles de revue, conception Guardian, modèles Issue/PR et génération HTML locale avec CI. Pas de code métier ni reprise d'ancien code.

## Expérience restant à réaliser

1. Décider de la création/transfert vers une organisation et de sa formule ; configurer les accès des trois participants.
2. Revoir à trois architecture et contrats ; enregistrer les accords explicites.
3. Introduire deux crates Rust simples et les contrôles Rust, puis contribuer depuis plusieurs PC.
4. Configurer Guardian indépendant et tester une incompatibilité volontaire, sans la fusionner.
5. Corriger, intégrer après revue, déployer sur un serveur de test désigné et vérifier le retour arrière.

## Déploiement et isolation

Aucun serveur choisi, aucun secret de déploiement, aucune production modifiée. Prévoir par client : droits, réseau, stockage, modèles, journaux, sauvegardes, rétention et administrateurs. Tester restauration et séparation réelle avant toute donnée client. La vue HTML doit rester privée ; pas de GitHub Pages public.
