# Chantier : chat Mission Control au niveau de Telegram (parité)

Dépôt : /home/thibaud/projects/gona-mission-control (Python stdlib `server.py`, front `web/app.js`, `web/index.html`, `web/alpha.css`, `web/voice.js`).
Tu travailles dans le worktree /home/thibaud/projects/gona-mission-control-parity (branche `feat/telegram-parity`, déjà créée). NE MODIFIE JAMAIS /home/thibaud/projects/gona-mission-control (service en production). Commits locaux fréquents. Pour tester le serveur, lance-le sur un autre port (ex. 8719) en premier plan avec timeout, jamais 8710.

## Situation actuelle
- Le chat affiche la conversation Telegram vivante de GONA (profil Hermes gpt5). Envoi : `/api/chat` → ancien service 8790 → `~/.hermes/profiles/gpt5/mission-control/gateway_channel.py` (`prompt.submit` via `hermes_cli.gateway_client.connect_gateway`).
- Réception : polling de `/api/channel/messages` et `/api/channel/reply` toutes les quelques secondes. Pas de streaming.
- Commandes « / » : `server.py` fonction `command()` (`/status /model /reasoning /help /restart /new`), réponse affichée en texte brut dans un cadre.
- Sources Hermes (LECTURE SEULE) : /home/thibaud/.openclaw/workspace/hermes-agent (commit ae2a81ccc0). Le gateway expose des RPC `session.events`, `session.resume`, `session.info`, `model.options`, `session.interrupt`, etc. L'adaptateur Telegram : `gateway/platforms/` (rendu streaming par édition de message, claviers inline pour /model, clarify, approbations).

## Objectif : que l'expérience soit « vraiment pareille » que Telegram
Par ordre de priorité :
1. **Streaming** : la réponse s'affiche au fil de l'eau (tokens ou blocs), avec indicateur « GONA écrit… » et les lignes de progression d'outils comme Telegram les montre (même niveau de détail que le réglage Telegram du profil, pas plus). Mécanisme : abonnement aux événements du gateway (`session.events` ou équivalent — étudie le code et la doc dans le dépôt Hermes) relayé au navigateur en SSE (`text/event-stream`) par `server.py`. Repli propre sur le polling actuel si le flux tombe.
2. **Rendu** : Markdown comme Telegram (gras, italique, code, blocs, liens, listes, titres), images `MEDIA:/chemin` affichées, pas de bulles parasites pour les messages intermédiaires internes.
3. **Menu de commandes** : taper `/` ouvre une liste cliquable (comme le bouton menu Telegram) avec description ; Tab/Entrée/clic pour choisir. Liste = commandes réellement gérées.
4. **Boutons inline** :
   - `/model` → boutons fournisseur puis modèle (données : op `options` de gateway_channel.py) ; clic = change le modèle (op `model`), confirmation si le gateway la demande.
   - `/reasoning` → boutons low/medium/high/xhigh/reset.
   - **clarify** : quand l'agent pose une question à choix (outil clarify), afficher les choix en boutons et renvoyer la réponse par le même chemin natif que Telegram (trouve-le dans le code : réponse RPC dédiée, pas un message texte si un mécanisme natif existe).
   - **approbations** de commandes dangereuses : boutons Approuver/Refuser via le mécanisme natif.
5. **/stop** : interrompre le tour en cours (`session.interrupt` ou équivalent natif).

## Contraintes STRICTES
- Ne JAMAIS redémarrer/arrêter/signaler le gateway ni les services (`systemctl`, `kill`, `hermes gateway …` interdits).
- Interdits sur la VRAIE session : `prompt.submit`, `session.mutate`, interrupt, reset. Lecture seule autorisée (`session.resume`, `session.info`, lecture/abonnement aux événements) pour observer le format réel des événements.
- Ne pas modifier le dépôt hermes-agent ni ~/.hermes. Aucun `pip install`. Pas de dépendance JS externe (vanilla, pas de CDN) — un petit rendu Markdown maison sûr (échappement HTML obligatoire, aucun innerHTML non échappé).
- Garder la charte ARPAGONA (couleurs, polices) et la mise en page actuelle (chat à gauche réduit, Kanban + portail de décision à droite).
- Ne pas casser : voix (`voice.js` utilise `window.MC`), portail de décision, commandes existantes, les tests existants (`python3 -m unittest discover -s tests`).
- Aucun secret dans les fichiers ni les logs.

## Livrables
- Code sur `feat/telegram-parity`, tests ajoutés (rendu markdown, parsing des événements avec fixtures réelles capturées en lecture seule, routes SSE, boutons) et tous verts.
- `PARITE.md` : tableau fonction par fonction Telegram vs Mission Control (fait / partiel / non fait + pourquoi), format réel des événements observés, procédure de déploiement, retour arrière, sortie exacte des tests.
