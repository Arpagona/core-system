# Pistes après le spike CLI — proposition du 11 novembre 2026

Ce document prépare une discussion ; il n'approuve ni architecture ni contrat. Les contrats communs et leur migration exigent l'accord explicite de Thibaud, Maël et Stéphane avant développement dépendant. La préversion CLI n'est pas une plateforme multi-agents ni un produit réceptionné. Le plan historique M0–M6 décrit des étapes, non une garantie de leur livraison.

1. **Session CLI persistante.** Clarifier continuité de mission, reprise explicite, annulation et budget durable. Preuves attendues : redémarrage et reprise, non-rejeu d'effet incertain, isolation, contrôle des coûts, parcours complet réel. Exclusion : autonomie ou démon implicite.
2. **Interface Web.** Réutiliser le même noyau, sans en contourner les politiques ; proposer authentification, permissions et journalisation avant toute exposition. Preuves attendues : isolation de sessions, refus d'accès, validation des origines et effets, audit, arrêt/reprise. Choix de technologie et contrats à revoir à trois. Aucun serveur ou port réseau n'est ouvert par cette proposition.
3. **Multi-agents.** Proposer sous-missions bornées, budget global, isolation des contextes, propagation d'annulation et absence d'escalade de droits. Sélectionner un premier cas synthétique et justifier par comparaison avec un mono-agent à objectifs identiques : qualité vérifiable, coût, durée et surface de risque. Aucun orchestrateur n'est ajouté maintenant.

Avant chaque étape, distinguer scénarios synthétiques, preuves sur fournisseur réel et validation humaine. Pas de données client, déploiement en production ni autorisation supplémentaire par défaut.

## Console web pour le serveur de test

1. **Consulter.** La console liste les missions et affiche leur journal via la CLI Rust. Un indicateur vérifie si OpenCode est disponible dans l’environnement du processus. La console écoute uniquement en boucle locale. L’iMac s’y connecte avec un tunnel SSH.
2. **Piloter.** Ajouter un lancement sur des dossiers préautorisés et un suivi de la mission. Le serveur réutilise la politique et les budgets de la CLI. Vérifier dans le navigateur la réussite, un refus et un arrêt avant d’étendre les actions. Ajouter authentification et contrôle des requêtes d’écriture avant un accès direct sur le réseau.
3. **Brancher OpenCode.** Commencer par une tâche de développement sur un dépôt de test, dans une copie isolée et avec des permissions explicites. Afficher la sortie, les modifications proposées et les tests. Les opérations sur le noyau actif, le déploiement et la fusion restent soumis à leurs autorisations propres. [Permissions OpenCode](https://opencode.ai/docs/permissions)
4. **Distribuer.** Reprendre la piste de l’image Debian personnalisée après validation du parcours sur le serveur existant. [Version stable de Debian](https://www.debian.org/releases/stable/)

### Essayer la première tranche

Sur le serveur, depuis le dépôt, compiler le binaire et lancer la console sous le compte qui a accès aux journaux. La console nécessite Python 3 et la configuration Agent Core habituelle.

```sh
cargo build --locked -p agentcore
python3 web/console.py --agentcore ./target/debug/agentcore
```

Pour une configuration distincte, ajouter `--config /chemin/config.toml`. Depuis le terminal de l’iMac, ouvrir un tunnel avec le compte SSH déjà autorisé sur le serveur.

```sh
ssh -N -L 8765:127.0.0.1:8765 utilisateur@serveur
```

Ouvrir ensuite [la console locale](http://127.0.0.1:8765/) dans Safari. La liste utilise les journaux existants. Cliquer sur une mission affiche ses événements. Le serveur HTTP est destiné aux essais sous un compte de confiance via le tunnel SSH.
