#!/usr/bin/env bash
# Débranche la mémoire Hindsight du moteur et arrête son service (sudo). Ne supprime aucune donnée.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "à lancer en root" >&2; exit 1; }
sudo -u hermes-arpagona -H bash -lc 'export PATH=$HOME/.local/bin:$PATH; hermes config set memory.provider ""' >/dev/null
systemctl restart hermes-arpagona-gateway.service
systemctl disable --now hindsight-arpagona.service
echo "mémoire débranchée ; données conservées dans /srv/hindsight-arpagona"
