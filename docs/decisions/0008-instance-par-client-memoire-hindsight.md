# ADR 0008 — Une instance Hermès par client, mémoire en graphe Hindsight

**Date :** 12 novembre 2026
**Statut :** **PROPOSÉ** — orientation de Thibaud du 12/11/2026. **Accord de Maël et Stéphane requis.**
Complète l'ADR 0007 (surcouche Hermès) et précise l'ADR 0002 (isolation des clients) sur le point de la mémoire.

## Contexte

Le 12/11/2026, la recette de bout en bout du banc a prouvé une fuite entre comptes : un compte a retrouvé, par l'outil `session_search` d'Hermès, une information confiée par un autre. La mémoire native et l'historique de sessions sont **communs à toute l'instance**. Tant qu'une instance sert plusieurs utilisateurs, ils ne peuvent pas être gardés.

Deux façons de corriger :

1. **Mémoire par utilisateur construite côté ARPAGONA** : l'API tient un registre par compte, l'agent ne voit qu'un extrait filtré. Beaucoup de code, une garantie qui repose sur du filtrage applicatif, et aucun bénéfice de graphe.
2. **Une instance Hermès par client** : l'isolation devient structurelle (fichiers, secrets, mémoire, journaux, modèles) ; la mémoire commune à l'intérieur d'une instance devient un avantage (mémoire d'équipe).

Thibaud a retenu la seconde le 12/11/2026, avec une mémoire en graphe de type **Hindsight**, déjà en service sur son Hermès principal.

## Décision

1. **Une instance Hermès par client.** Chaque instance a son propre compte système, son dossier, ses secrets, sa base, ses journaux, sa banque de mémoire et ses limites de ressources. Aucune mutualisation multiclient.
2. **La mémoire est une mémoire d'équipe** : tous les comptes d'une même instance partagent la même banque. C'est voulu — un collègue virtuel au service d'une entreprise connaît ce que savent ses collègues.
3. **Le fournisseur de mémoire est Hindsight**, en mode « serveur externe », servi par un processus séparé du moteur (voir « Mise en œuvre »).
4. **Aucun outil de mémoire n'est donné à l'agent** : rappel et rétention sont automatiques (`memory_mode: context`). La liste permise d'outils reste `web`, `todo`, `arpagona`.
5. **La mémoire n'est pas une source de vérité métier.** Les engagements datés et leur état vivent dans le registre transactionnel de l'API ARPAGONA ; la mémoire sert à retrouver le contexte et la justification.

## Alternatives écartées

- **Mémoire par utilisateur dans une instance partagée** : garantie par filtrage applicatif, coût de développement élevé, et l'historique de sessions d'Hermès resterait hors de portée du filtre.
- **Hindsight en mode « local embarqué »** : le démarrage automatique télécharge PyTorch avec CUDA (plus de 9 Go) et sature le plafond mémoire du moteur. Essayé, échoué, abandonné.
- **Mémoire mutualisée entre clients** : exclue par l'ADR 0002.

## Conséquences

### Bénéfices

- Isolation réelle et vérifiable entre clients, sans filtrage applicatif à maintenir.
- Mémoire d'équipe utile : décisions, personnes, projets, préférences partagés dans l'entreprise.
- Un client = une instance = une sauvegarde, une version, un retour arrière.

### Coûts et risques

- **Ce qui n'est pas démontré** : l'isolation entre deux instances réelles. Il n'existe qu'une instance à ce jour. C'est la prochaine preuve à produire, et elle est bloquante pour toute promesse au client.
- **Incohérence à trancher** : la mémoire est d'équipe, le registre d'engagements est par compte. Un collègue se souvient d'une relance décidée par un autre sans la voir dans son registre. Deux issues : porter les engagements à l'échelle de l'instance, ou assumer la séparation (mémoire = contexte, registre = responsabilité individuelle).
- **Ressources** : chaque instance porte son moteur, son service de mémoire et sa base. Sur le banc, la mémoire consomme 1,7 à 2,4 Go et 2,7 Go de disque, en plus du moteur.
- **Coût** : la rétention automatique ajoute des appels au modèle à chaque échange, pour l'extraction puis la consolidation. Non chiffré à ce jour.
- **Exploitation** : une instance par client multiplie les mises à jour et les sauvegardes à piloter.

## Mise en œuvre sur le banc (vérifiée le 12/11/2026)

- Serveur `hindsight-api` 1.2.1, service `hindsight-arpagona`, `127.0.0.1:18897`, clé d'accès obligatoire, compte système dédié, PyTorch CPU, `MemoryMax=3G`.
- Plugin `hindsight` 1.2.4 du catalogue officiel d'Hermès, mode `local_external`, `recall_sync` actif, banque `arpagona-banc`.
- Tout est posé par `deploy/atlas/install-hindsight.sh` ; `rollback-hindsight.sh` débranche sans supprimer de données.
- Preuve : recette du banc 24/24 avec mémoire branchée ; un compte confie trois faits, un second les retrouve 90 s plus tard ; aucun message du premier n'apparaît dans le fil du second.

## Retour arrière

`rollback-hindsight.sh` débranche le fournisseur et arrête le service ; les données restent. Le banc se ramène aussi au snapshot Proxmox `pre-hindsight-20261112`. Le retour arrière ne supprime aucune mémoire.

## Questions ouvertes

1. Isolation entre deux instances : quelle preuve, et quel contrôle automatique ?
2. Engagements : par compte ou par instance ?
3. Sauvegarde, restauration et purge de la banque de mémoire : rythme et preuve de restauration.
4. Coût et latence par échange : mesure sérieuse avant toute mise en production.
5. Définition de l'« oubli » : un client peut-il demander la suppression d'un fait, et comment le prouver ?
