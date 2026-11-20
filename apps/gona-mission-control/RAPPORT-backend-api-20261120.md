# Backend API — état partiel, 20 novembre 2026

**Non livrable en l’état : le chat sans Telegram n’est pas implémenté.** Le module ajouté est uniquement un transport HTTP ; il n’est pas branché à `server.py`. Le mode Telegram existant est inchangé. Ne pas configurer `GONA_MC_BACKEND=api` en pensant disposer de ce backend.

## Étape réalisée et vérifiée

- `backend_api.HermesClient` transmet une création de run avec `input`, `session_id` et `Idempotency-Key`, lit l’état et le SSE, et propose un appel de stop. Lecture optionnelle d’un fichier de clé, pas de clé journalisée. La capacité d’arrêt doit être vérifiée sur l’instance cible.
- Quatre tests avec faux serveur HTTP vérifient le protocole de transport, un identifiant de run invalide, un moteur injoignable et une clé inaccessible. Ils ne prouvent pas l’idempotence du backend MC ni un chat complet.
- `python3 -m unittest discover -s tests` : 32 tests réussis, dont les 28 préexistants ; `node --check web/app.js` : réussi.
- Aucun appel à un modèle ni écriture sur Atlas, aucun redémarrage de service ou opération sur la conversation Telegram.

## Vérification des références

- Client Atlas : `POST /v1/runs` avec clé d’idempotence, `GET /v1/runs/{id}`, SSE `GET /v1/runs/{id}/events`. Son serveur relaie `message.delta`, `tool.started`, `tool.completed` et récupère le résultat final via l’état du run. Le client Atlas lu n’implémente ni stop ni cancel ; cela ne prouve pas l’absence d’une route côté serveur Atlas.
- Store Atlas : une conversation par utilisateur, `hermes_session_id` aléatoire conservé en SQLite ; le client n’impose pas cet identifiant.
- Source Hermes locale, potentiellement plus récente : `gateway/platforms/api_server_runs.py` déclare `POST /v1/runs/{run_id}/stop` ; réponse possible `stopping`, ce qui signifie interruption demandée et non interruption déjà confirmée. Les événements ont les champs `event`, `run_id`, `timestamp`, notamment `message.delta`, `tool.started`, `tool.completed` et `run.<statut>`. Le code traite également la continuation de session. Ces observations ne démontrent pas les capacités de la version Atlas v0.23.1.

## À faire impérativement

- Implémenter le stockage SQLite configurable, l’idempotence atomique, les conversations et leur bascule `/new`, la gestion des reprises et des états incertains, et le flux SSE partagé entre clients sans perte lors des reconnexions.
- Brancher explicitement `server.py` et l’UI neutre selon `GONA_MC_BACKEND`, en conservant Telegram par défaut ; implémenter les commandes avec réponses honnêtes et éviter tout appel au gateway Telegram en mode API.
- Ajouter les tests demandés de bout en bout : chat, idempotence concurrente et après redémarrage, streaming navigateur, arrêt, `/new`, historique et indisponibilité sans blocage busy.
- Valider avec le vrai Hermes d’Atlas lorsque cela sera autorisé : version et événements effectifs, authentification, disponibilité de `/stop`, persistance et reprise des sessions ; la clé est lisible par root seulement. Aucun test réel n’a été réalisé ici.

## Fichiers créés

`backend_api.py`, `tests/test_backend_api_transport.py`, ce rapport. Les sauvegardes non suivies préexistantes ont été laissées intactes.
