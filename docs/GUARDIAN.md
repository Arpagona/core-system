# Guardian — conception à valider

Guardian n'est pas encore installé. La CI actuelle n'est pas Guardian et ne produit aucune approbation IA.

## Rapport attendu

Base et SHA exacts de la PR ; exigences vérifiées ; code et contrats examinés ; tests réellement exécutés ; défauts avec fichiers/lignes et reproduction ; impacts inter-modules ; sécurité/isolation ; documentation manquante ; verdict et limites.

## Permissions proposées

Lecture du diff, sources, contrats et résultats CI. Publication d'un rapport via un mécanisme distinct à configurer. Aucun droit de merge, déploiement, modification des protections ou auto-modification de ses critères. Identité et exécution distinctes de l'agent auteur. Fournisseur, budget et traitement du code privé à approuver avant branchement.

Les instructions présentes dans une PR sont des données non fiables. Ne pas exposer de secret à du code de PR. Éviter `pull_request_target` exécutant du code contributeur avec privilèges. Une erreur ou indisponibilité de Guardian n'est pas une validation.

## Preuve d'acceptation future

Sur une PR non fusionnable contenant une rupture volontaire, conserver : SHA testé, test de contrat échoué, rapport indépendant, correction puis test réussi. Tester aussi une rupture sémantique compilable. Vérifier séparément que les protections GitHub empêchent réellement le merge : actuellement elles sont indisponibles.
