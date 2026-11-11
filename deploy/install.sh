#!/usr/bin/env bash
# Installe une version dans la VM de test (à lancer avec sudo depuis le dossier extrait).
# Sauvegarde préalable de la configuration, de l'état et de la version active ; réversible par rollback.sh.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
[ "$(id -u)" = 0 ] || { echo "à lancer avec sudo" >&2; exit 1; }
(cd "$HERE" && sha256sum -c SHA256SUMS)
VERSION=$(sed -n 's/^version=//p' "$HERE/VERSION")
USER_NAME=${AGENTCORE_USER:-agentcore}
TS=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p /var/backups/agentcore
tar -czf "/var/backups/agentcore/avant-$VERSION-$TS.tar.gz" --ignore-failed-read \
    /etc/agentcore /var/lib/agentcore /opt/agentcore/current 2>/dev/null || true
readlink -f /opt/agentcore/current > "/var/backups/agentcore/previous-$TS" 2>/dev/null || true
REL="/opt/agentcore/releases/$VERSION"
install -d -m 0755 "$REL"
install -m 0755 "$HERE/agentcore" "$REL/agentcore"
install -m 0644 "$HERE/VERSION" "$HERE/SHA256SUMS" "$REL/"
install -m 0755 "$HERE/install.sh" "$HERE/rollback.sh" "$HERE/recette.sh" "$REL/"
rm -rf "$REL/demo" && cp -r "$HERE/demo" "$REL/demo" && chmod -R a+rX "$REL/demo"
if [ -d "$HERE/web" ]; then rm -rf "$REL/web" && cp -r "$HERE/web" "$REL/web" && chmod -R a+rX "$REL/web"; fi
ln -sfn "$REL" /opt/agentcore/current.new && mv -T /opt/agentcore/current.new /opt/agentcore/current
ln -sfn /opt/agentcore/current/agentcore /usr/local/bin/agentcore
install -d -m 0750 -o root -g "$USER_NAME" /etc/agentcore
if [ ! -e /etc/agentcore/config.toml ]; then
    install -m 0640 -o root -g "$USER_NAME" "$HERE/config.example.toml" /etc/agentcore/config.toml
    echo "configuration initiale installée"
else
    echo "configuration existante conservée (exemple de cette version : $REL/config.example.toml)"
    install -m 0644 "$HERE/config.example.toml" "$REL/config.example.toml"
fi
install -d -m 0750 -o "$USER_NAME" -g "$USER_NAME" /var/lib/agentcore
if [ -f "$HERE/agentcore-console.service" ] && command -v systemctl >/dev/null 2>&1; then
    install -m 0644 "$HERE/agentcore-console.service" /etc/systemd/system/agentcore-console.service
    systemctl daemon-reload
    systemctl enable agentcore-console.service >/dev/null 2>&1
    systemctl restart agentcore-console.service
    echo "console : $(systemctl is-active agentcore-console.service) (127.0.0.1:8765, tunnel SSH)"
fi
[ -s /etc/agentcore/api_key ] || echo "ATTENTION : /etc/agentcore/api_key absent ou vide (root:$USER_NAME 0640)"
echo "installé : $VERSION ; sauvegarde : /var/backups/agentcore/avant-$VERSION-$TS.tar.gz"
/usr/local/bin/agentcore version
