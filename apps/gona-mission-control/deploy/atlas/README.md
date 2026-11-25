# Deploiement Atlas (banc de test) - GONA Mission Control, mode api

- `install-gona-mc.sh install archive.tar.gz` : release horodatee, bascule `current`, `previous` conserve pour `rollback`.
- Service `gona-mission-control` : 127.0.0.1:8711 (tunnel SSH), utilisateur dedie `gona-mc`, durci (ProtectSystem=strict).
- Secrets dans `/etc/gona-mission-control/` (jeton d'acces, cle Hermes), jamais dans l'archive.
- Acces : `ssh -L 8711:127.0.0.1:8711 agentcore` puis ouvrir http://127.0.0.1:8711/ (jeton : `sudo cat /etc/gona-mission-control/token`).
- Kanban/Decisions : necessitent le Hermes personnel ; vides sur Atlas tant que la passerelle kanban-bridge n'est pas branchee.
