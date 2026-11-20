# Backend « api » (sans Telegram) — 20 novembre 2026

**État : implémenté, testé avec un faux Hermes ET validé sur le vrai Hermes d'Atlas (20/11/2026, 3 tours, quelques centimes).**

## Fonctionnement (`GONA_MC_BACKEND=api`)
- Conversation persistante en SQLite (`GONA_MC_DATA_DIR/chat.db`), session Hermes stable par conversation.
- Envoi idempotent (`submission_id`) : un doublon ne relance pas de tour, y compris après redémarrage.
- Streaming SSE identique au mode Telegram (writing, delta, tool, tool_done, complete), reprise du texte en cours à la reconnexion.
- `/new` (nouvelle conversation), `/stop` (route `/v1/runs/{id}/stop`), `/status`, `/help`. `/model`, `/reasoning`, `/restart` : refus explicite « pas pris en charge par cette instance ».
- Moteur indisponible : message lisible, pas de blocage « busy ». Tour interrompu par un redémarrage : jamais rejoué.
- Mode Telegram (défaut) inchangé.

## Variables
`GONA_MC_BACKEND` (telegram|api), `GONA_MC_HERMES_URL` (défaut http://127.0.0.1:8642), `GONA_MC_HERMES_KEY_FILE`, `GONA_MC_DATA_DIR`.

## Preuves
46 tests unittest OK (Ryzen et VM agentcore-dev), `node --check web/app.js` OK. Faux serveur Hermes : envoi, idempotence, flux SSE via le vrai serveur HTTP, /new, /stop, panne moteur, redémarrage.

## Essai réel sur Atlas (Hermes v0.23.1, VM agentcore-dev, port 8711 temporaire, arrêté ensuite)
- Tour 1 « réponds : bleu » -> `bleu` ; événements writing, delta, complete.
- Tour 2 « quel mot ? » -> `bleu` : la session Hermes est bien conservée entre les tours.
- Doublon (même submission_id) -> `duplicate`, aucun nouveau tour. Historique et /status corrects.
- /stop pendant un tour long -> état `cancelled`, route /stop présente sur Atlas.
- /new -> nouvelle conversation vide.
- Clé API lue via sudo dans /dev/shm, jamais affichée, détruite après l'essai ; console 8700 et services intacts.

## Limites connues
- Pas d'événements `tool` observés (aucun outil utilisé pendant l'essai) ; texte partiel perdu si /stop avant le premier delta.
- Pièces jointes, approbations/clarifications : non pris en charge en mode api. /model, /reasoning, /restart : refus explicite.
- Installation en service permanent sur Atlas non faite (copie dans ~agentcore/gona-mission-control-alpha.new).
