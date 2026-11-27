# Agent Core — reprise directe et corrections de sécurité

Date : 27 novembre 2026. Travail repris et vérifié personnellement par GONA. À la demande de Thibaud, les deux délégations encore actives ont reçu un ordre d'arrêt ; aucune nouvelle délégation.

## État réellement vérifié
- HEAD de départ 6ddb25b, PR67. Le lot précédent avait survendu ses garanties : tests faux moteur, seuils a posteriori (pas plafonds stricts), objet/expéditeur hors empreinte, décision sans contrôle propriétaire.
- Sauvegarde SQLite du banc avant modification : `/var/backups/arpagona-beta/20261127-093333-before-review.db` (0600).
- Rôles effectifs corrigés et relus : thibaud admin ; mael, dupont, recette-beta membres. Le compte démo avait été promu par erreur par la migration.
- SMTP Hostinger 587 STARTTLS : authentification contact@arpagona.com réussie (235), aucun envoi lors du contrôle. Secret lu depuis l'intégration existante sans affichage. Pas besoin de redemander le token.

## Correctifs de la branche fix/beta-approval-ownership
- Décider d'un brouillon d'autrui : test d'abord rouge (200 au lieu de 403), puis vert. Booléen strict obligatoire.
- Migration : ne promeut plus le plus ancien compte au redémarrage. Test rouge puis vert. L'admin des bases existantes est nommé explicitement par CLI.
- Empreinte v2 canonique : destinataire, objet, corps exact, expéditeur. Les anciens brouillons sans objet/expéditeur validés restent conservés, mais ne sont pas envoyables.
- Réservation SMTP conditionnelle SQLite, inter-connexions, avec Message-ID persistant avant tentative. Une seule connexion gagne. Une réouverture après réservation ne relance pas l'envoi. Suppression de l'écriture tardive qui pouvait effacer la réservation.
- SMTP : TLS obligatoire hors capture loopback sans identifiants ; destinataire unique et enveloppe explicite ; coupure après soumission marquée incertaine, pas non-remise certaine ; QUIT raté après acceptation ne transforme pas l'envoi en échec.
- Arrêt : sélection du moteur du propriétaire de la mission (pas celui de l'admin demandeur), erreur si la demande n'est pas acceptée, pas de fallback au moteur commun.
- UI : affiche objet et expéditeur, empêche une seconde tentative et expose les anciens brouillons non envoyables.

## Tests exécutés localement
`python3 -m unittest discover -s tests` dans services/arpagona-api : **96 tests OK**, 74,413 s. ResourceWarnings résiduels (HTTPError/SQLite) : ne pas masquer, à traiter séparément.
Neuf nouveaux contrôles adversariaux mail : enveloppe canonique, mutation d'objet, deux connexions SQLite en concurrence, réouverture après réservation, brouillon ancien, SMTP réel sur socket loopback (sans tiers), TLS obligatoire, injection/listes refusées, remise incertaine. Tous verts.

## Mémoire d'équipe — recette réelle sur Atlas
Recette existante `/opt/arpagona/current/tests/e2e/isolation_agents.py`, fonctions `network_isolation()` et `team_memory()`, invoquées personnellement via SSH root sur le banc : **67 contrôles, aucun échec**.
- Traceurs fictifs RUN 1795772514 (ZORBA/QUILLON).
- Écriture Maël puis rappel par Thibaud et sens inverse, auteur/source conservés.
- Secrets et préférences privés absents de l'équipe ; accès direct aux banques de l'autre refusé (403), mauvais jeton refusé (401).
- Six documents de fixture supprimés par identifiant en fin de test. Pas de purge générale.
Recette `live_zones()` : **4 contrôles, aucun échec**, RUN 1795772584.
- Moteur réel Maël completed, écrit un fait via outils d'équipe et un fichier client.
- Outil équipe de Thibaud retrouve le fait avec auteur mael ; fichier lisible par son compte.
- Nettoyage du document et du dossier de fixture vérifié.
Limite : cette dernière recette comporte un tour de modèle Maël et un rappel outillé Thibaud ; elle ne prouve pas deux conversations web complètes ni la cible de latence <10 s. L'échec historique M1 n'est pas reproduit sur l'architecture actuelle, déjà corrigée depuis novembre. Aucun nouveau système de mémoire n'a été construit.

## Restant — beta non déclarée
TLS local à finir et déployer (certificats des appareils à installer) ; SMTP authentifié mais remise réelle après approbation pas encore prouvée ; plafonds stricts et comptabilisation des échéances encore insuffisants ; export/restauration à tester ; revue UI réelle desktop/mobile ; cinq jours d'usage = critère d'évaluation beta, pas prérequis artificiel à son ouverture.
Les critères ne doivent pas être affaiblis pour faire passer du code. Un seuil informatif n'est pas un plafond financier strict.
