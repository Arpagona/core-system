# Matrice de réception beta — Agent Core

27 novembre 2026. Référence : `docs/CDC-PRODUIT-v2.0.md` et roadmap acceptée du 27/11.
Exécution directe GONA ; aucune délégation. Cette matrice ne remplace pas la roadmap produit protégée.

## Règles de lecture

- « Partiel » signifie preuves limitées, jamais conformité globale.
- Les preuves runtime précédentes concernent la release `13045c624f6c`. La branche `fix/beta-budget-admission` n'est pas déployée.
- Les tests locaux du candidat ne prouvent pas le moteur payant ni le téléphone physique.
- Le CDC reste inchangé : ses contradictions sont exposées, pas effacées pour faire passer les tests.

## Contradictions de contrat à fermer

1. **N-03/B-04** : le CDC appelle « plafond » un seuil après exécution qui ne coupe pas la facturation. La roadmap acceptée vise une garantie stricte. La réservation atomique est nécessaire mais insuffisante. La conformité financière stricte reste ouverte tant qu'une borne moteur/fournisseur n'est pas prouvée.
2. **B-12** : cinq jours d'usage ne peuvent pas être un résultat antérieur au début de cette période. La roadmap distingue ouverture interne sécurisée et réussite de la beta ; les exigences de sécurité ne sont pas différées.
3. **N-08** : « 99 % » nécessite une fenêtre de mesure définie, pas un simple endpoint sain. Garder l'objectif et mesurer pendant l'essai.
4. **F-14** : exporter ne prouve pas réimporter. Ajouter les réservations à l'export ne suffit pas à valider la portabilité.

## Exigences et preuves

| ID | Exigence source | État | Preuve ou manque précis | Lot |
|---|---|---|---|---|
| F-01 | Conversation persistante. | partiel | tests API/rotation ; parcours web repris après fermeture à refaire | 2 |
| F-02 | Missions visibles. | partiel | missions testées ; échéances maintenant suivies dans le candidat, pas encore déployé | 1–2 |
| F-03 | Arrêt d'une mission. | partiel | propriétaire/moteur testés ; arrêt réel chronométré et confirmation encore ouverts | 1–2 |
| F-04 | Voix. | à recetter | dictée/lecture et erreurs de permission sur PC/iMac/téléphone | 2 |
| F-05 | Brouillon et empreinte. | partiel | empreinte complète et message affiché testés ; rendu à contrôler | 2 |
| F-06 | Approbation liée au contenu. | partiel | propriétaire/empreinte/mutation testés ; parcours complet à rejouer | 2 |
| F-07 | Envoi courriel après approbation. | partiel | auto-envoi reçu et contenu IMAP vérifié ; SMTP encore limité à notre boîte | 2 |
| F-08 | Aucun autre canal. | à recetter | pas de test exhaustif de l’absence de tous les autres canaux | 1–3 |
| F-09 | Engagements datés. | partiel | tests de parsing et échéance ; contrôles budgétaires ajoutés dans le candidat | 1–2 |
| F-10 | Mémoire d'équipe. | partiel | 67 contrôles équipe/réseau + 4 moteur précédents ; deux conversations web et latence non prouvées | 2 |
| F-11 | Oubli. | à recetter | effacement et absence dans les réponses ultérieures à mesurer | 2–3 |
| F-12 | Kanban avec responsabilité. | à recetter | passerelle verte ; responsabilité, filtre et déplacement mobile à exercer | 2 |
| F-13 | Journal d'audit lisible par le client. | partiel | rôles et audit testés ; lecture métier et recherche de secrets dans les vrais événements à faire | 2–3 |
| F-14 | Portabilité. | partiel | export inclut désormais les réserves ; réimport complet non implémenté/prouvé | 3 |
| F-15 | Comptes et rôles. | partiel | rôles, décisions et non-réutilisation des IDs testés ; inventaire runtime à actualiser | 2–3 |
| F-16 | Multi-appareils. | partiel | HTTPS vérifié via curl PC/iMac ; APK installé sur émulateur, pas de preuve écran complet | 2 |
| N-01 | TLS obligatoire. | partiel | TLS/redirection/loopback observés ; cookies et navigateurs réels à vérifier | 2 |
| N-02 | Isolation par instance. | ouvert | isolation entre comptes ne prouve pas deux instances client | 3 |
| N-03 | Plafond de dépense. | non conforme à la cible stricte | admission réservée en candidat ; aucune borne fournisseur garantie, ambiguïté CDC explicitée ci-dessous | 1 |
| N-04 | Sauvegarde et restauration. | ouvert | pas de restauration complète chronométrée ni preuve complète de rétention hors hôte | 3 |
| N-05 | Conformité RGPD. | ouvert | documentation/procédures à préparer ; pas de validation juridique inventée | 3–4 |
| N-06 | Journalisation sans secret. | partiel | scan code ciblé vert ; 1 000 lignes runtime non vérifiées | 3 |
| N-07 | Performance. | ouvert | 10 mesures, médiane et p95 non réalisées | 2–4 |
| N-08 | Disponibilité beta. | ouvert | reprise forcée/alerte et mesure sur fenêtre définie non faites | 3–5 |
| N-09 | Mise à jour et retour arrière. | partiel | bascule TLS ratée revenue en HTTP ; rollback de version et données complet à exercer | 3 |
| N-10 | Restriction des outils de l'agent. | ouvert | politique effective et refus d’outil interdit à recetter | 3 |
| N-11 | Accessibilité de base. | ouvert | clavier, zoom 200 %, contraste et libellés à contrôler | 2 |
| N-12 | Documentation client. | ouvert | guides et essai sans assistance non terminés | 4 |
| B-01 | 20 parcours scénarisés verts sur le banc (chat, mission, approbation, refus, Kanban, engagement, mémoire, arrêt) | ouvert | les 20 scénarios utilisateur doivent être exécutés sur une seule version | 4 |
| B-02 | Deux instances fictives, zéro fuite croisée | ouvert | tests croisés entre deux instances à faire | 3 |
| B-03 | Envoi courriel réel après approbation, refus sans approbation | partiel | preuve réelle à soi-même et refus unitaires ; recette négative sur candidat déployé à compléter | 2 |
| B-04 | Plafond de dépense actif | partiel | critère historique dépassé/refus testé ; strict plafond de facture non garanti | 1 |
| B-05 | Restauration complète < 30 min | ouvert | restauration réelle neuve <30 min non faite | 3 |
| B-06 | TLS valide sur l'accès équipe, cookie `Secure` | partiel | certificat/HTTPS vrais ; cookie et capture navigateur à obtenir | 2 |
| B-07 | Mémoire d'équipe restituée entre deux comptes | partiel | partage via outils prouvé ; deux conversations web encore à exercer | 2 |
| B-08 | Journal d'audit complet et sans secret | ouvert | 200 événements réels relus et scan non faits | 3–4 |
| B-09 | Aucun bouton mort, aucune promesse fausse dans l'interface | ouvert | revue écran par écran à faire ; vocabulaire budget corrigé dans le candidat | 2–4 |
| B-10 | Guide client testé par un utilisateur nouveau | ouvert | nouvel utilisateur <10 min à observer, pas à simuler par un compte rendu | 4 |
| B-11 | Aucune donnée réelle sur le banc | à vérifier | inventaire runtime complet fictif/sensible à refaire avant ouverture | 3–4 |
| B-12 | 5 jours d'usage réel par Thibaud et Maël, ≥ 10 missions utiles, 0 incident critique | non commencé | cinq jours et dix missions utiles : mesure après ouverture, pas un résultat instantané | 5 |

## Scénarios de réception utilisateur à figer pour le lot 4

Le jeu doit couvrir connexion TLS, session persistante, mission aboutie, erreur moteur, arrêt confirmé, brouillon complet, refus, approbation et envoi, mutation refusée, anti-doublon, échéance/fuseau, budget avant démarrage, coût inconnu, mémoire dans les deux sens, oubli, responsabilité Kanban, export/réimport, reprise après coupure, incident/restauration et parcours mobile. Chaque scénario devra nommer données, étapes, résultat attendu, version et preuve, pas simplement compter une suite de tests unitaires.

## Décision actuelle

**NO-GO beta professionnelle.** Les lots peuvent avancer sans attendre une réécriture architecturale. Le candidat de garde budgétaire doit passer revue humaine avant merge et déploiement selon AGENTS.md/CONTRIBUTING.md ; aucune auto-approbation.
