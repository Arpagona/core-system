#!/usr/bin/env bash
# Retour à l'état HTTP précédent : uniquement les fichiers créés par la procédure.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo 'root requis' >&2; exit 1; }
[ "$#" = 1 ] && [ -f "$1/relay-enabled" ] && [ -f "$1/relay-active" ] || { echo "usage: $0 SAUVEGARDE" >&2; exit 2; }
b=$1
systemctl disable --now arpagona-tls.service || true
rm -f /etc/systemd/system/arpagona-tls.service /etc/systemd/system/arpagona-api.service.d/90-tls-local.conf
systemctl daemon-reload
systemctl restart arpagona-api.service
case "$(<"$b/relay-enabled")" in enabled) systemctl enable arpagona-gona-relay.service ;; disabled) systemctl disable arpagona-gona-relay.service ;; *) echo 'État enable du relais non standard : restauration manuelle nécessaire' >&2; exit 1 ;; esac
case "$(<"$b/relay-active")" in active) systemctl start arpagona-gona-relay.service ;; inactive|failed) systemctl stop arpagona-gona-relay.service ;; *) echo 'État actif du relais non standard : restauration manuelle nécessaire' >&2; exit 1 ;; esac
printf '%s\n' 'Retour HTTP effectué ; vérifier écoute, accès et relais. La CA et les sauvegardes restent en place.'
