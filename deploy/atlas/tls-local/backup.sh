#!/usr/bin/env bash
# Avant la bascule, sauvegarde privée et horodatée des éléments concernés.
set -euo pipefail
umask 077
[ "$(id -u)" = 0 ] || { echo 'root requis' >&2; exit 1; }
[ "$#" = 1 ] || { echo "usage: $0 REPERTOIRE_INEXISTANT" >&2; exit 2; }
b=$1
mkdir -m 700 -- "$b"
for f in /etc/arpagona-api/lan.env /etc/arpagona-lan.nft /etc/arpagona-wg.nft; do
  if [ -f "$f" ]; then mkdir -p "$b$(dirname "$f")"; cp -p -- "$f" "$b$f"; fi
done
systemctl is-enabled arpagona-gona-relay.service > "$b/relay-enabled" || :
systemctl is-active arpagona-gona-relay.service > "$b/relay-active" || :
nft list table inet arpagona_lan > "$b/arpagona-lan.runtime.nft"
nft list table inet arpagona_wg > "$b/arpagona-wg.runtime.nft"
printf 'Sauvegarde : %s\n' "$b"
