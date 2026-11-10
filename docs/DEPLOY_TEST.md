# Procédure de test et de retour arrière (préparation seulement)

**Statut : document de préparation. Aucune exécution distante n'a eu lieu.** Aucun serveur de test n'est choisi, aucun accès n'est autorisé, aucun secret de déploiement n'existe dans le dépôt ni dans la CI. Ce document décrit ce qu'il faudra faire **après** autorisation humaine, pour que la décision soit examinable à l'avance.

Périmètre : environnement d'intégration/test ARPAGONA uniquement (ENV-01). Aucune connexion de production, aucune donnée client.

## 1. Ce qui existe aujourd'hui

- Un artefact de démonstration **sans fonctionnalité produit**, construit par la CI à chaque PR : binaire `atelier-demo`, `VERSION.txt` (commit + version) et `SHA256SUMS`, publié comme artefact privé de l'exécution GitHub Actions.
- Une identification reproductible : le nom de l'artefact contient le SHA du commit testé.
- Aucun script de déploiement, aucun accès serveur, aucun secret. C'est volontaire : rien ne peut être déployé par accident depuis ce dépôt.

### Vérification de l'artefact (déjà exécutée, locale, isolée)

Le 10/11/2026, l'artefact du run `42868051788` (SHA `c8d764e893ef96033036ce9b7700ca373b655d81`) a été téléchargé, vérifié et exécuté dans un répertoire isolé, sans installation système :

- empreinte de l'archive fournie par l'API GitHub : `sha256:2d74dfcf83b6772eca60a3267879a1ee7cdf5c40e0001f3f227b463147dbfcb4` (identique après téléchargement) ;
- `VERSION.txt` : `commit=c8d764e893ef96033036ce9b7700ca373b655d81`, `version=0.1.0` ;
- `sha256sum -c SHA256SUMS` : OK ; binaire `atelier-demo` = `503b86ab6c23242dd3e0c3b60556d95c298801c3aaa30a3ed6c4c3e6c538ca9f` ;
- exécution : sortie `atelier-7`, code 0.

Ce contrôle prouve que l'artefact est **identifié, intègre et exécutable**. Il ne prouve ni une installation serveur, ni un déploiement, ni une isolation réseau.

## 2. Prérequis à obtenir avant toute exécution distante

À décider et fournir par un humain (aucun de ces éléments n'est acquis) :

| Élément | Décision attendue | Pourquoi |
|---|---|---|
| Hôte de test | nom/adresse, fournisseur, système, architecture | destination explicite, pas de « serveur par défaut » |
| Accès | compte, clé ou jeton, réseau autorisé, plage d'IP | sans accès, aucune action ; jamais de secret dans Git |
| Comptes | qui administre, qui déploie, qui peut revenir en arrière | séparation des rôles |
| Données | aucune donnée client au premier essai | preuve d'isolation avant toute donnée réelle |
| Fenêtre | date, durée, personne responsable | un test sans responsable n'est pas un test |
| Journal | où sont conservés les journaux et pendant combien de temps | traçabilité |

Tant que ces éléments manquent, la seule action légitime est de **compléter ce document**, pas de « tester vite fait ».

## 3. Préparation de l'hôte (à exécuter après autorisation, non exécutée)

1. Créer un compte de service dédié, sans privilège d'administration générale, avec un répertoire de travail dédié.
2. Installer uniquement les paquets nécessaires au binaire et au diagnostic (aucun compilateur en production de test n'est requis).
3. Restreindre l'accès entrant au strict nécessaire ; documenter les ports ouverts et leur justification.
4. Placer l'artefact hors du dépôt Git, dans un chemin versionné par SHA de commit.
5. Vérifier l'empreinte de l'artefact sur l'hôte **avant** exécution : `sha256sum atelier-demo` doit égaler la valeur publiée dans `SHA256SUMS` de la même exécution CI.
6. Refuser l'exécution si l'empreinte, le SHA du commit ou la version ne concordent pas.
7. Prévoir la rotation des journaux et la purge des données de test.

## 4. Déploiement de l'artefact (non exécuté)

Étapes prévues, à ne réaliser qu'avec l'autorisation écrite de la destination :

1. Copier `atelier-demo`, `VERSION.txt` et `SHA256SUMS` dans le répertoire de version (`/srv/arpagona-test/<sha>/` par exemple — chemin à valider, non choisi ici).
2. Vérifier l'empreinte sur place.
3. Exécuter `./atelier-demo` et vérifier la sortie attendue (`atelier-7` pour la version 0.1.0) et le code 0.
4. Consigner : SHA du commit, empreinte, date, exécutant, sortie, code de retour.
5. Ne conserver qu'un seul lien actif « courant » vers la version testée ; les versions restent côte à côte pour le retour arrière.

Aucune de ces étapes n'a été exécutée.

## 5. Retour arrière

Le retour arrière doit rester possible sans reconstruire ni recompiler :

1. Identifier la version précédente conservée sur l'hôte (répertoire par SHA).
2. Rebasculer le lien « courant » vers cette version ; ne rien supprimer avant validation.
3. Vérifier l'empreinte de la version restaurée.
4. Relancer le test de fumée (sortie attendue + code 0) et consigner le résultat.
5. Si l'échec vient de l'hôte et non de l'artefact, revenir à l'état documenté de l'hôte avant de conclure.

Condition de déclenchement : empreinte non conforme, code de retour non nul, sortie inattendue, ou doute sur la version réellement exécutée. Le retour arrière est **immédiat et non négocié** ; l'analyse vient après.

## 6. Conditions de promotion

Une version ne peut être déclarée « promue » vers un environnement de test que si :

1. la CI est verte sur le **SHA exact** de l'artefact, tous contrôles terminés ;
2. le rapport Guardian de ce SHA a été examiné par un humain (son verdict est un signal, pas une autorisation) ;
3. l'empreinte de l'artefact déployé est identique à celle publiée par la CI ;
4. l'Issue du chantier porte l'accord explicite du pilote et, pour un changement de contrat ou d'architecture, des trois co-concepteurs ;
5. le test de fumée et le retour arrière ont été **répétés sur l'hôte** avant d'annoncer un résultat.

Une promotion vers la production est **hors mandat** et exige une décision humaine distincte, un environnement séparé et des données autorisées.

## 7. Sécurité et limites

- Aucun secret dans le dépôt, les workflows, les artefacts ou les journaux. Les workflows déclarent `permissions: contents: read` et n'utilisent aucune référence `secrets.*` (vérifié le 10/11/2026) : un changement de workflow ne peut donc pas lire silencieusement un secret de déploiement inexistant.
- Les artefacts GitHub Actions du dépôt privé ne sont pas publics ; ils expirent après 7 jours. Une version à conserver durablement doit être copiée vers un stockage autorisé, avec son empreinte.
- Aucune protection technique de `main` n'est active (403 sur la formule actuelle) : la séparation dépôt/CI/test/production est **procédurale**.
- Ce document ne prouve pas l'isolation réseau, le durcissement de l'hôte, la sauvegarde ni la restauration. Ces preuves exigent un serveur autorisé et restent à produire.

## 8. Attestation d'état

Au 10/11/2026 : aucun serveur contacté, aucun déploiement, aucun test distant, aucun secret créé. Seule la vérification locale et isolée de l'artefact décrite en section 1 a été réalisée.
