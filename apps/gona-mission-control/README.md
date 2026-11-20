# GONA Mission Control (alpha)

Interface web locale pour piloter un Hermes personnel : chat branché sur la vraie conversation Telegram, Kanban, décisions, voix.
Alpha : HTTP local uniquement (127.0.0.1), authentification par jeton, pas d'exposition réseau.

- `server.py` : serveur (port 8710), relais vers le gateway Hermes ; jeton lu dans `~/.hermes/profiles/<profil>/gona-mission-control/token` (jamais versionné).
- `web/` : interface (chat avec streaming SSE, commandes `/status` `/model` `/reasoning` `/help` `/new` `/stop` `/restart`, Kanban, voix).
- `gateway_live.py`, `gateway_new.py`, `bridge.py`, `gate.py` : liaison avec le gateway Hermes.
- `new-command/` : plugin Hermes `mc-new` (commande `/new` depuis Mission Control).
- `tests/` : `python3 -m unittest discover -s tests`.
- `arpagona-mission-control-alpha.service` : unité systemd `--user`.

Différent de `apps/mission-control-web` (variante Agent Core / Atlas, comptes multiples). Pas de secret dans ce dossier ; chemins et noms de profil à adapter.
