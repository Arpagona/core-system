#!/usr/bin/env bash
# Déploie une version de l'API ARPAGONA et de Mission Control sur la VM de test (à lancer avec sudo).
# Usage : deploy-arpagona.sh <archive.tar.gz> <identifiant de version>
# L'archive vient de : git archive --format=tar.gz <commit> services apps deploy
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "à lancer en root" >&2; exit 1; }
ARCHIVE="$1"; VERSION="$2"
[[ "$VERSION" =~ ^[0-9a-f]{7,40}$ ]] || { echo "version attendue : empreinte de commit" >&2; exit 1; }
ROOT=/opt/arpagona; REL="$ROOT/releases/$VERSION"

id arpagona-api >/dev/null 2>&1 || useradd --system --no-create-home --home-dir /nonexistent \
    --shell /usr/sbin/nologin --user-group arpagona-api
install -d -m 755 "$ROOT/releases"
install -d -m 700 -o arpagona-api -g arpagona-api /var/lib/arpagona-api
install -d -m 750 -o root -g arpagona-api /etc/arpagona-api

# Copie de la clé de l'API Hermès pour le seul service ARPAGONA ; jamais affichée.
umask 027
grep -m1 '^API_SERVER_KEY=' /srv/hermes-arpagona/.hermes/.env | cut -d= -f2- > /etc/arpagona-api/hermes_key
chown root:arpagona-api /etc/arpagona-api/hermes_key; chmod 640 /etc/arpagona-api/hermes_key
umask 022

rm -rf "$REL.tmp"; mkdir -p "$REL.tmp"
tar -xzf "$ARCHIVE" -C "$REL.tmp"
rm -rf "$REL"; mv "$REL.tmp" "$REL"
PREVIOUS="$(readlink "$ROOT/current" 2>/dev/null || true)"
[ -z "$PREVIOUS" ] || [ "$PREVIOUS" = "$REL" ] || echo "$PREVIOUS" > "$ROOT/previous"
ln -sfn "$REL" "$ROOT/current"

install -m 644 "$REL/deploy/atlas/arpagona-api.service" /etc/systemd/system/arpagona-api.service
systemctl daemon-reload
systemctl enable arpagona-api.service >/dev/null 2>&1
systemctl restart arpagona-api.service
sleep 2
systemctl is-active arpagona-api.service
curl -fsS -m 5 http://127.0.0.1:8700/api/health; echo
echo "version active : $(readlink "$ROOT/current")"
