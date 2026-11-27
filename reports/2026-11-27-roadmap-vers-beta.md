# Agent Core — roadmap opérationnelle vers la beta

Date : 27 novembre 2026.
Responsable d'exécution : GONA, directement, sans sous-agent.
Statut : plan proposé à Thibaud. Ce document ne lance aucun chantier automatiquement.

## Objectif

Ouvrir une **beta interne utilisable par Thibaud et Maël**, simple, fiable et observable. Puis décider, après usage, si un pilote client est justifié. Ne pas confondre « ouverture de beta », « beta réussie » et « produit commercial prêt ».

Cette roadmap complète l'intention produit existante ; elle ne remplace ni ne réécrit la feuille de route produit protégée. Aucun nouvel écran, moteur, ordonnanceur ou connecteur n'est nécessaire par défaut.

## Point de départ : ce qui est acquis, ce qui reste ouvert

Référence du dernier déploiement vérifié dans cette session : `13045c624f6c` ; CI du commit canonique verte.

- Approbation propriétaire, empreinte du message complet, réservation SMTP persistante, traitement explicite des remises incertaines : correctifs intégrés et testés. Ne pas promettre une livraison SMTP « exactement une fois » : après coupure ambiguë, pas de réessai automatique.
- Courriel synthétique à notre propre boîte : reçu et contenu vérifié par IMAP. SMTP de recette limité à `contact@arpagona.com` ; aucun envoi client autorisé par ce plan.
- Mémoire : 67 contrôles réseau/équipe et 4 contrôles du parcours moteur ont réussi. Deux conversations web complètes et leur latence ne sont pas encore prouvées.
- HTTPS Atlas : actif, chaîne vérifiée depuis le PC et l'iMac ; API sur loopback ; ancien accès HTTP redirigé. L'écran connecté et les cookies de session restent à contrôler dans les navigateurs réels.
- Android 0.11 TLS : APK compilé, signé, installé et lancé sur émulateur. Cela ne prouve ni le parcours rendu, ni le téléphone physique, ni les téléchargements.
- **Ouverts** : protection financière stricte, recette visuelle et fonctionnelle multi-appareils, deux instances réellement isolées, restauration complète, exploitation et documentation.

Ces acquis sont les preuves de la session, pas une nouvelle mesure de disponibilité permanente. Rapport technique : `reports/2026-11-27-reprise-directe-beta.md`.

## Ordre d'exécution

### Lot 0 — Fixer le contrat de livraison et assainir les promesses

**Résultat :** une matrice unique « exigence → preuve → état → correctif », reliée au CDC et aux portes B-01 à B-12.

Travail :
- Réconcilier le CDC v2, la feuille de route technique et les preuves du 27/11. Les anciens états « fonctionne » ne valent pas recette en production.
- Signaler les contradictions : seuil de dépense après exécution versus plafond strict ; statut SMTP incertain versus échec certain ; ouverture de beta versus cinq jours nécessaires pour juger sa réussite.
- Préparer les corrections du CDC comme propositions explicites, sans supprimer d'objectif pour faire passer les tests.
- Revoir le comparatif Cognite Atlas AI, Microsoft Copilot Studio et Dust avec sources officielles datées. Comparer usages, approbations, isolation, intégration et coût publié. Une absence dans une documentation ne prouve pas une absence de fonction. Retirer les affirmations concurrentielles non étayées.
- Figer le parcours beta : demander une mission → suivre le travail → relire un livrable → approuver ou refuser → retrouver le résultat et sa preuve.

**Porte :** plus de promesse ambiguë dans le périmètre retenu ; liste des tests de réception écrite avant modification du code.

### Lot 1 — Fermer les risques qui interdisent la beta

**Priorité : protection financière et intégrité des exécutions.**

Travail :
- Réservation budgétaire atomique avant démarrage, commune aux chemins chat, missions et échéances ; tests de concurrence.
- Coût absent, invalide ou non fini : état inconnu explicite, jamais zéro par défaut. Refus prudent des nouveaux démarrages payants si le budget ne peut plus être garanti.
- Vérifier ce que le moteur permet réellement de borner : appels, jetons, durée et consommation. Ne pas annoncer de plafond financier strict sans borne supérieure effectivement appliquée. Si le moteur ne permet pas cette garantie, proposer un mode de beta borné réellement applicable ; ne pas abaisser le critère en silence.
- Arrêt réel sur le moteur du propriétaire ; statut honnête si l'arrêt n'est pas confirmé. Vérifier coupure réseau, crash et redémarrage sans rejeu d'un effet externe incertain.
- Vérifier le recalcul d'empreinte, la propriété, les refus et l'unicité de réservation sur le banc déployé, pas seulement avec des doublures de test.

**Porte :** tests adversariaux verts ; aucun chemin de travail ne contourne les contrôles ; coût inconnu et remise inconnue visibles et non automatiquement rejoués.

### Lot 2 — Rendre le parcours quotidien simple et complet

**Résultat :** une même expérience utilisable sur PC, iMac et Android.

Travail :
- Parcours réel : connexion HTTPS → conversation → mission → brouillon complet → refus/approbation → envoi de recette → journal → reprise après fermeture.
- Vérifier cookie Secure, confiance du certificat et absence d'avertissement sur chaque cible. Le téléphone physique reste une acceptation distincte de l'émulateur.
- Vérifier pièces jointes, téléchargement et installation APK : la confiance TLS du DownloadManager est distincte de celle du WebView. Aucun bypass de certificat.
- Rejouer la mémoire entre deux conversations web, dans les deux sens, avec auteur/source et mesure de latence ; vérifier aussi l'oubli.
- Vérifier Kanban et responsabilités, engagements et fuseaux, arrêt, reconnexion et absence de doublons.
- Simplifier la navigation existante autour de trois besoins : décider, suivre, retrouver les preuves. Supprimer les boutons inactifs et expliquer les erreurs en français. Tester clavier, zoom et petit écran.

**Porte :** matrice de parcours verts par appareil, captures réellement rendues et relues ; aucune action critique uniquement disponible sur ordinateur ; aucune promesse non tenue dans l'interface.

### Lot 3 — Prouver qu'on peut exploiter et récupérer le produit

**Résultat :** une panne ou une mise à jour ne fait pas perdre le travail et n'expose pas un autre client.

Travail :
- Créer une seconde instance fictive avec séparation des fichiers, bases, secrets, mémoires et journaux ; tests croisés négatifs.
- Sauvegarde chiffrée hors hôte, rétention vérifiée et restauration complète dans une instance neuve. Mesurer la durée et comparer les données métier.
- Exercer export/réimport, mise à jour, retour arrière et reprise après arrêt forcé.
- Vérifier les alertes de santé, les états dégradés et l'absence de secrets dans les journaux.
- Archiver puis retirer les comptes et données de recette non nécessaires ; vérifier leur absence et les rôles restants.

**Porte :** isolation négative complète, restauration réelle en moins de 30 minutes, rollback sans perte, reprise et alerte vérifiées. Une copie de fichier ou une sauvegarde sans restauration ne suffit pas.

### Lot 4 — Réception professionnelle et ouverture de la beta interne

**Résultat :** une version candidate figée, démontrable, documentée et vérifiable.

Travail :
- Rejouer les 20 scénarios de réception sur la même version : chat, missions, arrêt, approbations/refus, intégrité du message, responsabilités, engagements, mémoire, journal et portabilité.
- Réserver les données fictives au banc. Compléter le dossier d'information et de conservation des données ; toute déclaration juridique engageante reste soumise à validation humaine.
- Produire un guide utilisateur court et un guide administrateur : démarrage, approbation, limites, budget, sauvegarde et incident.
- Faire réaliser le parcours de démarrage par un utilisateur non accompagné : moins de 10 minutes. GONA prépare tout ; ce test humain ne peut pas être remplacé par un compte rendu automatique.
- Émettre un rapport GO/NO-GO : critères verts, preuves, défauts connus classés, commit, sauvegarde et retour arrière.

**Porte d'ouverture :** zéro défaut critique de sécurité, perte de données, effet externe non autorisé ou contournement financier ; parcours critiques verts ; décision explicite d'ouverture interne. Aucun pilote client ni publication commerciale automatique.

### Lot 5 — Cinq jours d'usage, puis décision pilote

**Résultat :** démontrer une utilité réelle, pas uniquement la réussite de tests.

- Thibaud et Maël utilisent la version interne pendant cinq jours ouvrés.
- Viser au moins dix missions utiles sur des cas d'entreprise fictifs représentatifs. Compter les livrables effectivement utilisables, le temps de reprise/correction, les coûts et les incidents.
- Corriger les blocages, sans ajouter de nouvelles fonctionnalités pendant l'essai.
- Faire un bilan : gain de temps observé, missions ratées, taux de correction et fiabilité. Ne pas inventer de gain théorique.

**Porte de réussite beta :** cinq jours observés, au moins dix missions utiles, zéro incident critique et décision écrite. Ensuite seulement : choix d'un pilote, cadre de données et autorisation d'engagement externe.

## Dépendances et estimation

Ordre : **0 → 1 → 2 → 3 → 4 → 5**. La rédaction documentaire peut avancer au fil des lots ; aucun sous-agent n'est prévu.

Enveloppe de planification : **5 à 8 jours de travail pour les lots 0 à 4**, puis **5 jours ouvrés d'usage**. C'est une estimation, pas une date de livraison garantie. Elle sera réévaluée après le lot 0 et la preuve de faisabilité du plafond financier. Les points les plus incertains sont cette garantie de budget, Android/téléchargements et la restauration complète.

Pas de délai artificiel de cinq jours avant de commencer la beta : l'essai de cinq jours sert à décider si elle est réussie.

## Discipline de livraison

Pour chaque lot : résultat observable, tests conservés, branche et PR ciblées, CI verte, revue selon les règles du dépôt, déploiement de la version canonique sur les cibles concernées, vérification de la cible après écriture et rapport daté. Le travail se fait directement par GONA, sans sous-agent. Toute validation humaine requise reste une validation réelle, jamais une auto-approbation déguisée.

## Hors chantier jusqu'à réussite de la beta

Pas de nouveaux connecteurs ERP/agenda/Drive, pas de nouvelle architecture agentique, pas d'autonomie supplémentaire, pas de multi-tenant libre-service, pas de nouvelle application ni de boucle d'amélioration. Cognite est un repère de comparaison, pas une liste de fonctions à recopier.

**Prochaine action précise :** lot 0, matrice de réception et clarification des promesses financières ; puis lot 1, tests rouges de réservation concurrente et de coûts inconnus avant correction.
