#!/usr/bin/env bash
# Déploie une version de l'API ARPAGONA et de Mission Control sur la VM de test (à lancer avec sudo).
# Usage : deploy-arpagona.sh <archive.tar.gz> <identifiant de version>
# L'archive vient de : git archive --format=tar.gz <commit> services apps deploy plugins tests
# Le script est rejouable : il ne remplace ni la base, ni un jeton de service déjà valide.
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

# Jeton de service propre aux outils du plugin : distinct de la clé Hermès, tiré une seule fois.
HERMES_HOME=/srv/hermes-arpagona/.hermes
TOKEN=/etc/arpagona-api/service_token
if [ ! -s "$TOKEN" ] || cmp -s "$TOKEN" /etc/arpagona-api/hermes_key; then
  openssl rand -hex 32 > "$TOKEN"
fi
chown root:arpagona-api "$TOKEN"; chmod 640 "$TOKEN"
install -m 600 -o hermes-arpagona -g hermes-arpagona "$TOKEN" "$HERMES_HOME/arpagona_service_token"
# Le moteur lit sa propre copie : il n'a pas à appartenir au groupe du service ARPAGONA.
if id -nG hermes-arpagona | tr ' ' '\n' | grep -qx arpagona-api; then gpasswd -d hermes-arpagona arpagona-api >/dev/null; fi
sed -i -E '/^ARPAGONA_(SERVICE_TOKEN_FILE|API_URL)=/d' "$HERMES_HOME/.env"
printf 'ARPAGONA_API_URL=http://127.0.0.1:8700\nARPAGONA_SERVICE_TOKEN_FILE=%s\n' \
  "$HERMES_HOME/arpagona_service_token" >> "$HERMES_HOME/.env"
chown hermes-arpagona:hermes-arpagona "$HERMES_HOME/.env"; chmod 600 "$HERMES_HOME/.env"
# Jeton distinct pour la passerelle Kanban, partagé uniquement avec les deux services.
KTOKEN=/etc/arpagona-api/kanban_token
[ -s "$KTOKEN" ] || openssl rand -hex 32 > "$KTOKEN"
chown root:arpagona-api "$KTOKEN"; chmod 640 "$KTOKEN"
install -m 600 -o hermes-arpagona -g hermes-arpagona "$KTOKEN" "$HERMES_HOME/arpagona_kanban_token"
umask 022

rm -rf "$REL.tmp"; mkdir -p "$REL.tmp"
tar -xzf "$ARCHIVE" -C "$REL.tmp"
rm -rf "$REL"; mv "$REL.tmp" "$REL"
PREVIOUS="$(readlink "$ROOT/current" 2>/dev/null || true)"
[ -z "$PREVIOUS" ] || [ "$PREVIOUS" = "$REL" ] || echo "$PREVIOUS" > "$ROOT/previous"
ln -sfn "$REL" "$ROOT/current"

# Plugin Hermès : copié hors de l'arbre d'Hermès, puis activé avec la politique d'outils.
PLUGIN="$HERMES_HOME/plugins/arpagona-core"
rm -rf "$PLUGIN.tmp"; mkdir -p "$HERMES_HOME/plugins"
cp -r "$REL/plugins/arpagona-core" "$PLUGIN.tmp"
rm -rf "$PLUGIN"; mv "$PLUGIN.tmp" "$PLUGIN"
chown -R hermes-arpagona:hermes-arpagona "$HERMES_HOME/plugins"
sudo -u hermes-arpagona -H bash -lc 'export PATH=$HOME/.local/bin:$PATH; hermes plugins enable arpagona-core' >/dev/null
bash "$REL/deploy/atlas/politique-outils.sh"
systemctl restart hermes-arpagona-gateway.service

install -m 644 "$REL/deploy/atlas/arpagona-api.service" /etc/systemd/system/arpagona-api.service
install -m 644 "$REL/deploy/atlas/kanban-bridge.service" /etc/systemd/system/kanban-bridge.service
systemctl daemon-reload
systemctl enable --now kanban-bridge.service
systemctl restart kanban-bridge.service
systemctl enable arpagona-api.service >/dev/null 2>&1
systemctl restart arpagona-api.service
for _ in $(seq 1 20); do
  sleep 2
  curl -fsS -m 3 http://127.0.0.1:8700/api/health >/dev/null 2>&1 \
    && curl -fsS -m 3 http://127.0.0.1:8642/v1/health >/dev/null 2>&1 && break
done
systemctl is-active arpagona-api.service hermes-arpagona-gateway.service
curl -fsS -m 5 http://127.0.0.1:8700/api/health; echo
echo "version active : $(readlink "$ROOT/current")"
