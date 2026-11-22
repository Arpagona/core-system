#!/usr/bin/env bash
# Mode TEST seulement. Ne modifie que la table arpagona_lan, jamais SSH.
# Exécuter en root, puis confirmer depuis une nouvelle connexion SSH :
# systemctl stop arpagona-lan-rollback.timer
set -euo pipefail
[ "$(id -u)" -eq 0 ] || exit 1
command -v nft >/dev/null || { echo 'Installer nftables avant de continuer' >&2; exit 1; }
ROOT=/opt/arpagona/current/deploy/atlas
install -d -m 755 /etc/nftables.d
install -m 644 "$ROOT/arpagona-lan.nft" /etc/nftables.d/arpagona-lan.nft
# filet de sécurité : ferme l'API LAN et retire uniquement notre table après 180 s.
systemd-run --unit=arpagona-lan-rollback --on-active=180 /bin/sh -c \
 'rm -f /etc/arpagona-api/lan.env; systemctl restart arpagona-api; nft delete table inet arpagona_lan; systemctl disable arpagona-lan-firewall.service'
install -m 644 "$ROOT/arpagona-lan-firewall.service" /etc/systemd/system/arpagona-lan-firewall.service
systemctl daemon-reload
systemctl enable --now arpagona-lan-firewall.service
# Écoute IPv4 seulement ; loopback conservée pour les outils internes du plugin.
printf 'ARPAGONA_BIND=0.0.0.0\nARPAGONA_COOKIE_SECURE=0\n' > /etc/arpagona-api/lan.env
chmod 640 /etc/arpagona-api/lan.env
chown root:arpagona-api /etc/arpagona-api/lan.env
systemctl restart arpagona-api.service
echo 'Confirmer SSH + santé LAN sous 180 s, puis arrêter arpagona-lan-rollback.timer.'
