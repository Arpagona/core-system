#!/usr/bin/env bash
# Revient à la version précédente de l'API ARPAGONA (à lancer avec sudo). La base n'est pas modifiée.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "à lancer en root" >&2; exit 1; }
ROOT=/opt/arpagona
PREVIOUS="$(cat "$ROOT/previous" 2>/dev/null || true)"
[ -n "$PREVIOUS" ] && [ -d "$PREVIOUS" ] || { echo "aucune version précédente" >&2; exit 1; }
CURRENT="$(readlink "$ROOT/current")"
ln -sfn "$PREVIOUS" "$ROOT/current"
echo "$CURRENT" > "$ROOT/previous"
if [ -f "$PREVIOUS/deploy/atlas/kanban-bridge.service" ]; then
  install -m 644 "$PREVIOUS/deploy/atlas/kanban-bridge.service" /etc/systemd/system/kanban-bridge.service
  systemctl daemon-reload
  systemctl restart kanban-bridge.service
else
  systemctl disable --now kanban-bridge.service || true
fi
install -m 644 "$PREVIOUS/deploy/atlas/arpagona-api.service" /etc/systemd/system/arpagona-api.service
systemctl daemon-reload
systemctl restart arpagona-api.service
sleep 2
systemctl is-active arpagona-api.service
curl -fsS -m 5 http://127.0.0.1:8700/api/health; echo
echo "version active : $(readlink "$ROOT/current")"
