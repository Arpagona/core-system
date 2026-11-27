# Réparation de la recette de restauration — 27 novembre 2026

## Résultat vérifié

**PASS sur une nouvelle VM 103 restaurée depuis l'archive réellement récupérée hors Atlas.**

Le reçu distant a été relu après exécution. `passed`, `data_match` et `memory_match` valent `true`. La copie a ensuite été arrêtée. Une lecture séparée de Proxmox confirme : VM 100 active ; VM 101, 102 et 103 arrêtées. L'API de la source répond toujours HTTP 200.

Preuve publique expurgée : [proofs/2026-11-27-recovery-summary.json](proofs/2026-11-27-recovery-summary.json). Le reçu complet sans textes mémoire est conservé hors Git sur Atlas : `/var/lib/vz/dump/agent-core-beta-20261127T111520Z/restore-receipt-103.json`.

## Réception réelle

- Archive déchiffrée contrôlée : SHA-256 `423d618c0112509473aca507a4c19987fe7f1e63eb75eb9a3b01e92e020f934d`.
- Nouvelle VM, jamais de restauration forcée sur une VM existante.
- Interfaces réseau retirées avant premier démarrage. Contrôle supplémentaire : pas de passthrough, argument QEMU libre ou volume appartenant à une autre VM.
- API : HTTP 200 ; interface HTTPS avec validation du certificat : HTTP 200 ; utilisateur non connecté : HTTP 401 ; Hindsight : HTTP 200.
- Cinq services contrôlés actifs : API, TLS, moteur Hermès, Hindsight et passerelle mémoire.
- Empreintes des données métier et fichiers contrôlés identiques à la référence indépendante : 4 comptes, 3 conversations, 29 messages, 2 brouillons, 1 engagement, 26 cartes Kanban. Intégrité SQLite `ok`.
- Journal : les **1 496 événements présents au point de sauvegarde** correspondent, contenu et ordre inclus, à la source historique.
- Mémoire : **4 banques, 69 unités mémoire, 22 documents**, toutes les empreintes comparées identiques ; vérification de la pagination et des totaux. Aucun texte mémoire ni secret exporté dans Git.
- Durée de restauration et de contrôle, archive déjà rapatriée : **220,106 secondes**. Ce n'est pas un nouveau chronométrage monolithique du rapatriement hors hôte : celui-ci avait été mesuré séparément à 639,766 secondes. Ne pas annoncer un nouveau RTO complet garanti.

## Défauts corrigés

### Transport QGA

L'exécution brute du script provoquait `guest-exec failed - got timeout`, alors que des sondes simples fonctionnaient. Le programme est désormais transmis en ASCII compressé/base64, avec conservation exacte de ses octets UTF-8. Son lancement est asynchrone ; le PID retourné est conservé pendant la lecture de l'état. Un lancement incertain n'est jamais rejoué automatiquement. Un code invité non nul ou une sortie tronquée refuse le succès. Les erreurs sont conservées dans le reçu privé.

Le défaut interne précis du transport initial n'est pas attribué au démon invité sans preuve supplémentaire. Le contournement a été exercé sur les vrais scripts, puis dans la nouvelle restauration complète.

### Démarrage hors ligne de Hindsight

Sans réseau, Hugging Face retentait des requêtes de métadonnées malgré les modèles présents. Un drop-in **dans `/run` de la copie seulement** impose le mode hors ligne. Les modèles sauvegardés ont réellement été chargés.

Dans la copie diagnostiquée, `pg0` ne redémarrait pas : métadonnées `instance.json` et `postmaster.pid` vides observées, puis erreur JSON EOF reproduite directement. L'origine exacte de ces fichiers vides n'est pas établie ; cela ne démontre pas une corruption des données PostgreSQL.

La recette contourne ce wrapper avec les exécutables PostgreSQL déjà sauvegardés et le cluster existant, sans `initdb`, sans effacement et sans réinitialisation des mots de passe. Les bibliothèques natives viennent du répertoire `lib` de l'installation restaurée. La connexion passe par un socket Unix privé, une règle `peer` limitée à l'utilisateur système Hindsight et une correspondance explicite vers son rôle SQL. TCP est désactivé. Les paramètres temporaires sont dans la copie, pas dans l'instance active. Les données mémoire ont ensuite été intégralement comparées.

Ce mécanisme est un outil de récupération de la copie isolée, **pas un déploiement silencieux d'un nouveau PostgreSQL sur l'instance active**. Le cycle de vie de `pg0` sur l'instance active reste un sujet distinct à durcir avant une bêta professionnelle.

### Référence du journal d'audit

La première référence avait été capturée après la sauvegarde et incluait des événements ultérieurs. La comparaison de tous ces événements à une sauvegarde antérieure ne pouvait pas réussir.

La correction n'ignore pas le journal et ne fabrique pas une référence depuis la copie. La référence est recalculée sur la **source**, bornée au point de sauvegarde : `2026-11-27 12:15:21 Europe/Paris`, soit `1795778121.0`. Le fuseau de l'hyperviseur a été vérifié. La source et la copie contiennent exactement les mêmes 1 496 événements jusqu'à ce point et la même empreinte. Le dernier événement restauré est antérieur à cette borne. Les autres données et les fichiers sont comparés sans exclusion supplémentaire.

## Validation du code

- `python3 -m unittest discover -s tests/dev -v` : **39 tests OK**, dont 10 tests du contrôleur et de ses garde-fous.
- `python3 scripts/security_checks.py` : aucun motif sensible ciblé détecté ; contrôle limité, pas un audit de sécurité.
- `git diff --check` : OK.
- La preuve Proxmox réelle est distincte des tests simulés de transport.

## Périmètre et limites

- Ni sous-agent ni appel d'inférence lancé pour la recette. La copie n'avait pas de sortie réseau physique.
- Aucune modification du code applicatif ni redémarrage de l'instance active. La release restaurée et la source restent `13045c624f6c`.
- Les VM de test sont conservées arrêtées ; aucune suppression de leurs disques n'est annoncée.
- Pas d'activation de sauvegarde quotidienne ni de rétention automatique dans ce chantier.
- Pas de validation de deux clients indépendants, de parcours Android complet ou de livraison SMTP par cet exercice.
- La réparation ferme le blocage de cette recette de restauration ; elle ne déclare pas la totalité des critères bêta conformes.
