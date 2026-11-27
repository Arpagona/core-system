#!/usr/bin/env bash
# Usage : sudo bash install.sh ; accès réseau inchangé, aucune ouverture de port.
set -euo pipefail
umask 077
[ "$(id -u)" = 0 ] || { echo 'root requis' >&2; exit 1; }
here=$(cd -- "$(dirname -- "$0")" && pwd)
backup=/var/backups/arpagona-tls/$(date +%Y%m%d-%H%M%S)
mkdir -p -m 700 /var/backups/arpagona-tls
bash "$here/backup.sh" "$backup"
[ ! -e /etc/systemd/system/arpagona-api.service.d/90-tls-local.conf ] || { echo 'TLS déjà configuré : ne pas réécrire sans revue.' >&2; exit 1; }
# Ne jamais démarrer le serveur nginx par défaut ni ouvrir son port 80.
if ! command -v nginx >/dev/null; then
  systemctl mask --runtime nginx.service
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nginx
  systemctl disable nginx.service
fi
if [ ! -e /etc/arpagona-tls ]; then bash "$here/generate-ca.sh" /etc/arpagona-tls; fi
openssl verify -CAfile /etc/arpagona-tls/ca.crt /etc/arpagona-tls/server.crt
install -m 644 "$here/nginx.conf" /etc/arpagona-tls/nginx.conf
install -m 644 "$here/arpagona-tls.service" /etc/systemd/system/arpagona-tls.service
mkdir -p /etc/systemd/system/arpagona-api.service.d
printf 'ARPAGONA_BIND=127.0.0.1\nARPAGONA_COOKIE_SECURE=1\n' > /etc/arpagona-tls/api.env
printf '[Service]\nEnvironmentFile=/etc/arpagona-tls/api.env\n' > /etc/systemd/system/arpagona-api.service.d/90-tls-local.conf
# root lit la configuration TLS ; l'API ne lit pas le dossier de clés (systemd lit api.env).
chmod 700 /etc/arpagona-tls
systemctl daemon-reload
trap 'echo "Échec : retour arrière $backup" >&2; bash "$here/rollback.sh" "$backup"' ERR
systemctl disable --now arpagona-gona-relay.service
systemctl restart arpagona-api.service
ready=0
for _ in {1..20}; do
  if curl -fsS --max-time 2 http://127.0.0.1:8700/api/health >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
[ "$ready" = 1 ] || { echo 'API non prête après 20 essais' >&2; false; }
install -d -m 755 /run/arpagona-tls
/usr/sbin/nginx -t -c /etc/arpagona-tls/nginx.conf
systemctl enable --now arpagona-tls.service
ready=0
for _ in {1..20}; do
  if curl -fsS --max-time 3 --cacert /etc/arpagona-tls/ca.crt https://192.168.68.240:8700/api/health >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
[ "$ready" = 1 ] || { echo 'Proxy TLS non prêt après 20 essais' >&2; false; }
curl -fsS --max-time 10 --cacert /etc/arpagona-tls/ca.crt https://192.168.68.240:8700/api/health
trap - ERR
printf '\nTLS actif. Sauvegarde rollback : %s\nCertificat PUBLIC client : /etc/arpagona-tls/ca.crt\n' "$backup"
