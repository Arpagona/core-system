#!/usr/bin/env bash
# Retour arrière de l'instance Hermès de test (à lancer avec sudo).
# Sans argument : arrête et désactive le service, ne supprime rien.
# Pour revenir à l'état d'avant l'installation : snapshot Proxmox, voir README.md.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "à lancer en root" >&2; exit 1; }
systemctl disable --now hermes-arpagona-gateway.service || true
systemctl reset-failed hermes-arpagona-gateway.service || true
echo "gateway : $(systemctl is-active hermes-arpagona-gateway.service || true), $(systemctl is-enabled hermes-arpagona-gateway.service || true)"
if ss -tln | grep -q ':8642 '; then echo "ATTENTION : le port 8642 écoute encore" >&2; exit 1; fi
echo "port 8642 fermé ; données conservées dans /srv/hermes-arpagona"
