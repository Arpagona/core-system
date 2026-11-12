# Schéma d'intégration ARPAGONA ↔ Hermès Agent

**Statut : PROPOSÉ** (ADR 0007, Issue #39). Les routes Hermès citées viennent de la documentation de la version 0.23.1 ; elles restent à essayer une par une sur le banc de test avant d'être retenues.

## Vue d'ensemble

```text
 Navigateur (ordinateur, mobile)                    Telegram
        |  HTTPS                                        |
        v                                               |
 +-------------------------------+                      |
 | Mission Control (web)         |                      |
 | chat, activité, missions,     |                      |
 | Kanban, approbations          |                      |
 +-------------------------------+                      |
        |  API ARPAGONA (seule surface exposée)         |
        v                                               |
 +-------------------------------------------+          |
 | API ARPAGONA                              |          |
 | - authentification, droits                |          |
 | - identité de conversation                |          |
 | - registre des engagements (base propre)  |          |
 | - approbations et journal d'audit         |          |
 | - exécuteur des actions externes          |          |
 +-------------------------------------------+          |
        |  boucle locale, clé de service                |
        v                                               v
 +-----------------------------------------------------------+
 | Hermès Agent officiel (version épinglée)                  |
 | gateway : serveur API 127.0.0.1:8642, Telegram            |
 | moteur, outils, sessions, mémoire, Kanban, planification  |
 | plugin arpagona-core : outils et hooks métier             |
 +-----------------------------------------------------------+
        |
        v
   modèles et outils
```

## Qui fait quoi

| Sujet | Hermès | ARPAGONA |
| --- | --- | --- |
| Boucle LLM, outils, sessions techniques | oui | non |
| Kanban | source de vérité | affichage et actions relayées |
| Planification | tâches natives | logique d'échéance des engagements |
| Telegram | gateway native | correspondance d'identité entre canaux |
| Utilisateurs, droits | non | oui |
| Engagements | non | source de vérité, base transactionnelle |
| Approbations, audit | non | oui |
| Envoi externe | **aucun outil d'envoi donné à l'agent** | exécuteur, après approbation |

## Flux

### Chat web

1. Le navigateur envoie le message à l'API ARPAGONA avec la session de l'utilisateur.
2. L'API retrouve la conversation métier de cet utilisateur et la session Hermès associée.
3. Elle appelle le serveur API d'Hermès en boucle locale, avec la clé de service et la clé de session.
4. Elle relaie le flux d'événements au navigateur, sans exposer d'identifiant technique.

Le navigateur ne reçoit jamais la clé Hermès et ne parle jamais au port 8642.

### Kanban

Les routes Kanban HTTP d'Hermès sont servies par le dashboard, qui donne aussi accès à la configuration et aux clés. L'API ARPAGONA n'en relaie que les routes de tâches, ou passe par la CLI `hermes kanban`. Le dashboard reste en boucle locale, jamais publié.

### Engagement et approbation

```text
à préparer -> brouillon prêt -> en attente de validation -> approuvé -> envoyé
                                                         |          -> échec
                                                         -> refusé
```

1. L'agent appelle un outil du plugin `arpagona-core` pour consigner un engagement. L'outil écrit dans le registre par l'API ARPAGONA.
2. À l'échéance, un déclencheur demande à l'agent de préparer un brouillon.
3. Le brouillon apparaît dans Approbations avec son contenu exact et sa cible.
4. L'utilisateur approuve ou refuse. La décision est liée à l'empreinte du contenu et de la cible : un brouillon modifié après coup doit être revalidé.
5. Seul l'exécuteur de l'API ARPAGONA peut envoyer, et seulement si un connecteur est autorisé. Sinon le brouillon est livré à copier, avec la mention « non envoyé ».

### Où se trouve le contrôle

| Mécanisme | Portée réelle | Rôle |
| --- | --- | --- |
| Hook `pre_tool_call` d'Hermès | Bloque un outil dans le processus de l'agent ; échoue fermé sur délai ou exception (documentation 0.23.1, à vérifier par essai) | Défense en profondeur : limiter les outils disponibles |
| Liste d'outils de l'instance | L'agent n'a ni outil d'envoi ni identifiants de messagerie | Barrière principale côté agent |
| Exécuteur de l'API ARPAGONA | Vérifie l'approbation au moment de l'action, hors de portée de l'agent | **Contrôle final** |

Un hook seul n'est pas présenté comme barrière de sécurité.

## Isolation

- Une instance Hermès par client : compte système, répertoire, secrets, mémoire et journaux séparés.
- Compte de service sans sudo.
- Serveur API et dashboard d'Hermès liés à la boucle locale.
- TLS et authentification portés par un reverse proxy devant l'API ARPAGONA seulement.

## À vérifier par essai avant de bâtir

1. Une exécution réelle par `/v1/runs`, avec flux d'événements et arrêt.
2. La reprise d'une conversation par clé de session après redémarrage de la gateway.
3. Le blocage effectif d'un outil par `pre_tool_call` depuis un plugin externe à l'arbre d'Hermès.
4. La lecture et la modification du Kanban sans exposer le dashboard.
5. Ce que partagent réellement une session web et une session Telegram du même utilisateur.
6. La création d'une tâche planifiée par `/api/jobs` et son déclenchement après redémarrage.
