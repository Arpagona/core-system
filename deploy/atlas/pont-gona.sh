#!/usr/bin/env bash
# Pont Atlas <-> GONA : une seule connexion (cookie de 90 jours émis par Atlas) ouvre aussi GONA.
# Usage (depuis le poste GONA, le Ryzen) :
#   pont-gona.sh cle      crée la clé partagée (hors dépôt) si absente, l'installe sur Atlas et sur GONA
#   pont-gona.sh atlas    (root sur Atlas) installe relais 8710, pare-feu, variables de l'API ; à lancer après un déploiement
#   pont-gona.sh retour   (root sur Atlas) retire le relais et la variable
# Aucun secret n'est écrit dans ce dépôt : la clé vit dans deux fichiers 0600/0640.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
GONA_KEY="${GONA_MC_BRIDGE_KEY_FILE:-$HOME/.hermes/profiles/gpt5/gona-mission-control/bridge.key}"
ATLAS_KEY=/etc/arpagona-api/bridge_key
DROPIN=/etc/systemd/system/arpagona-api.service.d/pont-gona.conf

case "${1:-}" in
  cle)
    umask 077
    # Clé existante réutilisée telle quelle : en régénérer une casserait l'authentification des deux côtés.
    if [ ! -s "$GONA_KEY" ]; then mkdir -p "$(dirname "$GONA_KEY")"; head -c 48 /dev/urandom | base64 -w0 | tr '+/' '-_' | tr -d '=' > "$GONA_KEY"; fi
    chmod 600 "$GONA_KEY"
    ssh agentcore "sudo install -m 640 -o root -g arpagona-api /dev/stdin $ATLAS_KEY" < "$GONA_KEY"
    echo "clé installée (Atlas : $ATLAS_KEY ; GONA : $GONA_KEY) — valeur non affichée"
    ;;
  atlas)
    [ "$(id -u)" -eq 0 ] || { echo "à lancer en root sur Atlas" >&2; exit 1; }
    [ -s "$ATLAS_KEY" ] || { echo "clé absente : lancer 'pont-gona.sh cle' depuis le Ryzen" >&2; exit 1; }
    install -m 644 "$HERE/arpagona-wg.nft" /etc/nftables.d/arpagona-wg.nft
    nft delete table inet arpagona_wg 2>/dev/null || true
    nft -f /etc/nftables.d/arpagona-wg.nft
    install -m 644 "$HERE/arpagona-gona-relay.service" /etc/systemd/system/arpagona-gona-relay.service
    install -d -m 755 "$(dirname "$DROPIN")"
    printf '[Service]\nEnvironment=ARPAGONA_BRIDGE_KEY_FILE=%s\nEnvironment=ARPAGONA_BRIDGE_LOGINS=thibaud\n' "$ATLAS_KEY" > "$DROPIN"
    systemctl daemon-reload
    systemctl enable --now arpagona-gona-relay.service
    systemctl restart arpagona-api.service
    echo "pont installé"
    ;;
  retour)
    [ "$(id -u)" -eq 0 ] || { echo "à lancer en root sur Atlas" >&2; exit 1; }
    systemctl disable --now arpagona-gona-relay.service 2>/dev/null || true
    rm -f /etc/systemd/system/arpagona-gona-relay.service "$DROPIN"
    systemctl daemon-reload; systemctl restart arpagona-api.service
    echo "pont retiré (clé conservée)"
    ;;
  *) sed -n 2,8p "$0"; exit 2 ;;
esac
