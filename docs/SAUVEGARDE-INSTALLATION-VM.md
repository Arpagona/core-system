# Sauvegarde et retour arrière — VM de test

Date : 2026-11-11. Portée : prototype CLI, pas de production ni de modification des contrats communs.

## Choix et références

Les [consignes de sécurité Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/security) recommandent des secrets en 0600 et des clés distinctes par service. [OpenClaw](https://docs.openclaw.ai/cli/backup) traite les sauvegardes comme sensibles, vérifie avant restauration et restaure d'abord vers un répertoire vierge sans remplacer l'état actif. Ici les chemins sont fixes et la sauvegarde tar est volontairement plus simple : elle ne propose ni manifeste authentifié ni snapshot transactionnel. Aucun code de ces projets n'est repris.

## Installation

L'installateur exige une archive de bundle vérifiée, une nouvelle version valide et une sauvegarde préalable réussie, lisible et comparée aux sources. La sauvegarde privée (umask 077, répertoire root 0700, fichiers 0600) capture `/etc/agentcore`, `/var/lib/agentcore`, le lien `current` et la release effectivement ciblée, si présents. Une première installation génère une archive vide. Si création ou vérification échoue, aucun changement de release ni de lien actif n'est entrepris. Le répertoire de sauvegarde ne peut pas être un lien et doit appartenir à root.

**Limites :** arrêter au préalable toute mission et empêcher de nouveaux lancements ; tar et sa comparaison ne constituent pas un snapshot transactionnel. Il n'y a pas de verrou contre une installation ou une écriture concurrente, et un échec après la sauvegarde peut laisser une installation partielle. L'archive ne contient ni toutes les anciennes releases ni `/usr/local/bin/agentcore`, ni les composants système extérieurs aux chemins ci-dessus. Les sauvegardes ne sont ni chiffrées, ni authentifiées, ni répliquées. Protéger également ACL, supports et copies ; root et tout compte capable de sudo restent privilégiés.

## Retour arrière

`sudo rollback.sh [VERSION]` ne fait que rebasculer le lien de la release active vers une release locale existante ; il ne restaure pas la configuration ou l'état des missions. Vérifier ensuite la version et l'intégrité. Ne pas supposer que cela annule les effets externes.

Pour une récupération des données, arrêter les exécutions, faire une sauvegarde fiable de l'état courant, choisir une archive dont la provenance est vérifiée, et l'inspecter et l'extraire dans un répertoire vide privé, jamais directement sur `/`. Les liens absolus présents dans l'archive, notamment `current`, doivent être inspectés sans les suivre ; l'extraction automatisée ne doit pas leur permettre d'écrire hors du répertoire isolé. Comparer les fichiers, propriétaires et permissions avant toute remise en place manuelle autorisée. L'archive seule ne prouve pas une restauration complète ni cohérente à chaud. La gestion des absences initiales, de l'état postérieur et des services doit être décidée explicitement par l'opérateur.

## Test local

`python3 -m unittest discover -s tests -p test_install_safety.py -v` utilise exclusivement des chemins synthétiques et simule l'identité root ; ce n'est pas une preuve de permissions système. Les tests couvrent sauvegarde, refus des erreurs tar et d'un lien de sauvegarde, première installation, restauration isolée de fichiers synthétiques, retour arrière et cible invalide. Les droits réels et la concurrence exigent une validation distincte sur la VM autorisée.
