#!/usr/bin/env bash
# Accès distant au banc par WireGuard terminé sur la VM (à lancer en root sur la VM de test).
#
#   acces-wireguard.sh install <endpoint-public>      tunnel wg0 + pare-feu ; affiche la clé publique du serveur
#   acces-wireguard.sh add-peer <nom> <10.68.100.N> <clé-publique-wg>
#   acces-wireguard.sh remove-peer <nom>
#   acces-wireguard.sh add-ssh-user <login> <10.68.100.N> "<clé-publique-ssh>"
#   acces-wireguard.sh remove-ssh-user <login>
#   acces-wireguard.sh status
#   acces-wireguard.sh uninstall
#
# Principe : le pair n'atteint que la VM (TCP 8700 Mission Control, TCP 22 SSH). Le routage reste
# coupé : depuis le tunnel, le réseau local est injoignable. Aucune clé privée de pair ne transite :
# chaque pair génère la sienne et ne fournit que sa clé publique. Ne touche ni SSH sur le LAN ni le reste.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "à lancer en root" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")" && pwd)"
CONF=/etc/wireguard/wg0.conf
META=/etc/wireguard/arpagona-endpoint
NET=10.68.100
PORT=51820

ip_valide() { [[ "$1" =~ ^10\.68\.100\.([2-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-4])$ ]]; }
cle_wg_valide() { [[ "$1" =~ ^[A-Za-z0-9+/]{42}[AEIMQUYcgkosw480]=$ ]]; }
nom_valide() { [[ "$1" =~ ^[a-z][a-z0-9-]{1,30}$ ]]; }
recharger() { wg syncconf wg0 <(wg-quick strip wg0); }

case "${1:-}" in
install)
  ENDPOINT="${2:?endpoint public attendu (IP ou nom)}"
  command -v wg >/dev/null || DEBIAN_FRONTEND=noninteractive apt-get install -y -q wireguard-tools >/dev/null
  [ "$(cat /proc/sys/net/ipv4/ip_forward)" = 0 ] || { echo "routage IPv4 actif : refus" >&2; exit 1; }
  install -d -m 700 /etc/wireguard /etc/nftables.d
  install -m 644 "$ROOT/arpagona-wg.nft" /etc/nftables.d/arpagona-wg.nft
  # La table LAN accepte aussi Mission Control depuis le tunnel.
  install -m 644 "$ROOT/arpagona-lan.nft" /etc/nftables.d/arpagona-lan.nft
  install -m 644 "$ROOT/arpagona-wg-firewall.service" /etc/systemd/system/arpagona-wg-firewall.service
  if [ ! -s "$CONF" ]; then
    umask 077
    printf '[Interface]\nAddress = %s.1/24\nListenPort = %s\nPrivateKey = %s\n' "$NET" "$PORT" "$(wg genkey)" > "$CONF"
  fi
  printf '%s\n' "$ENDPOINT" > "$META"
  systemctl daemon-reload
  systemctl enable --now arpagona-wg-firewall.service >/dev/null
  systemctl restart arpagona-lan-firewall.service
  systemctl enable --now wg-quick@wg0 >/dev/null
  echo "tunnel actif ; clé publique du serveur : $(wg show wg0 public-key)"
  ;;
add-peer)
  NOM="${2:?nom}"; IP="${3:?ip}"; CLE="${4:?clé publique}"
  nom_valide "$NOM" || { echo "nom invalide" >&2; exit 1; }
  ip_valide "$IP" || { echo "adresse attendue dans $NET.2-254" >&2; exit 1; }
  cle_wg_valide "$CLE" || { echo "clé publique WireGuard invalide" >&2; exit 1; }
  ! grep -q "^# pair: $NOM$" "$CONF" || { echo "pair $NOM déjà présent" >&2; exit 1; }
  ! grep -q "AllowedIPs = $IP/32" "$CONF" || { echo "adresse $IP déjà prise" >&2; exit 1; }
  printf '\n# pair: %s\n[Peer]\nPublicKey = %s\nAllowedIPs = %s/32\n# fin: %s\n' "$NOM" "$CLE" "$IP" "$NOM" >> "$CONF"
  recharger
  cat <<EOF
Pair $NOM ajouté. Configuration à importer sur son poste (il remplace la clé privée par la sienne) :

[Interface]
PrivateKey = <clé privée générée sur ce poste, ne jamais la transmettre>
Address = $IP/32

[Peer]
PublicKey = $(wg show wg0 public-key)
Endpoint = $(cat "$META"):$PORT
AllowedIPs = $NET.1/32
PersistentKeepalive = 25

Mission Control : http://$NET.1:8700
EOF
  ;;
remove-peer)
  NOM="${2:?nom}"; nom_valide "$NOM" || exit 1
  grep -q "^# pair: $NOM$" "$CONF" || { echo "pair $NOM absent" >&2; exit 1; }
  sed -i "/^# pair: $NOM\$/,/^# fin: $NOM\$/d" "$CONF"
  recharger
  echo "pair $NOM retiré"
  ;;
add-ssh-user)
  LOGIN="${2:?login}"; IP="${3:?ip}"; CLE="${4:?clé publique ssh}"
  nom_valide "$LOGIN" || { echo "login invalide" >&2; exit 1; }
  ip_valide "$IP" || { echo "adresse attendue dans $NET.2-254" >&2; exit 1; }
  [[ "$CLE" =~ ^(ssh-ed25519|ecdsa-sha2-nistp256|ssh-rsa)\ [A-Za-z0-9+/=]+( [^\"]*)?$ ]] || { echo "clé SSH invalide" >&2; exit 1; }
  id "$LOGIN" >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "$LOGIN"
  passwd -l "$LOGIN" >/dev/null
  usermod -aG systemd-journal "$LOGIN"
  install -d -m 700 -o "$LOGIN" -g "$LOGIN" "/home/$LOGIN/.ssh"
  # Clé utilisable seulement depuis l'adresse du tunnel, sans redirection ni agent.
  printf 'from="%s",no-port-forwarding,no-agent-forwarding,no-X11-forwarding %s\n' "$IP" "$CLE" > "/home/$LOGIN/.ssh/authorized_keys"
  chown "$LOGIN:$LOGIN" "/home/$LOGIN/.ssh/authorized_keys"; chmod 600 "/home/$LOGIN/.ssh/authorized_keys"
  printf 'Match User %s\n  AllowTcpForwarding no\n  X11Forwarding no\n  AllowAgentForwarding no\n  PermitTunnel no\n' "$LOGIN" \
    > "/etc/ssh/sshd_config.d/arpagona-$LOGIN.conf"
  sshd -t && systemctl reload ssh
  echo "compte $LOGIN : SSH par clé depuis $IP seulement, sans sudo, journaux en lecture"
  ;;
remove-ssh-user)
  LOGIN="${2:?login}"; nom_valide "$LOGIN" || exit 1
  [ "$LOGIN" != agentcore ] || { echo "refus" >&2; exit 1; }
  pkill -KILL -u "$LOGIN" 2>/dev/null || true
  rm -f "/etc/ssh/sshd_config.d/arpagona-$LOGIN.conf"
  userdel -r "$LOGIN" 2>/dev/null || true
  sshd -t && systemctl reload ssh
  echo "compte $LOGIN supprimé"
  ;;
status)
  wg show wg0
  nft list table inet arpagona_wg
  ;;
uninstall)
  systemctl disable --now wg-quick@wg0 2>/dev/null || true
  systemctl disable arpagona-wg-firewall.service 2>/dev/null || true
  nft delete table inet arpagona_wg 2>/dev/null || true
  echo "tunnel arrêté ; /etc/wireguard conservé (clés). Supprimer à la main si définitif."
  ;;
*)
  sed -n '2,13p' "$0"; exit 2
  ;;
esac
