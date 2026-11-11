#!/usr/bin/env bash
# Installe une version dans la VM de test (à lancer avec sudo depuis le dossier extrait).
# Sauvegarde préalable de la configuration, de l'état et de la version active ; réversible par rollback.sh.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
[ "$(id -u)" = 0 ] || { echo "à lancer avec sudo" >&2; exit 1; }
(cd "$HERE" && sha256sum -c SHA256SUMS)
VERSION=$(sed -n 's/^version=//p' "$HERE/VERSION")
USER_NAME=${AGENTCORE_USER:-agentcore}
# Sauvegardes privées, même si l'appelant a un umask permissif.
umask 077
case "$VERSION" in
    ''|.|..|*[!a-zA-Z0-9._-]*) echo "version invalide" >&2; exit 1 ;;
esac
REL="/opt/agentcore/releases/$VERSION"
[ ! -e "$REL" ] && [ ! -L "$REL" ] || { echo "release existante : $REL" >&2; exit 1; }
install -d -m 0700 /var/backups/agentcore
chmod 0700 /var/backups/agentcore
TS=$(date -u +%Y%m%dT%H%M%S.%NZ)
BACKUP="/var/backups/agentcore/avant-$VERSION-$TS.tar.gz"
PREVIOUS="/var/backups/agentcore/previous-$TS"
TMP=$(mktemp -d /var/backups/agentcore/.install-XXXXXXXX)
trap 'rm -rf -- "$TMP"' EXIT
inputs=()
for path in /etc/agentcore /var/lib/agentcore; do
    if [ -e "$path" ] || [ -L "$path" ]; then inputs+=("$path"); fi
done
if [ -e /opt/agentcore/current ] || [ -L /opt/agentcore/current ]; then
    [ -L /opt/agentcore/current ] || { echo "current n'est pas un lien" >&2; exit 1; }
    ACTIVE=$(readlink -e /opt/agentcore/current) || { echo "current invalide" >&2; exit 1; }
    case "$ACTIVE" in /opt/agentcore/releases/*) ;; *) echo "release active hors périmètre" >&2; exit 1;; esac
    [ -d "$ACTIVE" ] && [ -x "$ACTIVE/agentcore" ] || { echo "release active invalide" >&2; exit 1; }
    inputs+=(/opt/agentcore/current "$ACTIVE")
    printf '%s\n' "$ACTIVE" > "$TMP/previous"
fi
# Tar doit réussir, être lisible et correspondre aux fichiers à l'instant de comparaison.
# Une installation initiale a légitimement une archive vide.
if [ ${#inputs[@]} -gt 0 ]; then
    tar -czf "$TMP/backup.tar.gz" -- "${inputs[@]}"
else
    tar -czf "$TMP/backup.tar.gz" --files-from /dev/null
fi
tar -tzf "$TMP/backup.tar.gz" >/dev/null
tar -dzf "$TMP/backup.tar.gz" -C /
chmod 0600 "$TMP/backup.tar.gz"
mv -n "$TMP/backup.tar.gz" "$BACKUP"
[ ! -e "$TMP/backup.tar.gz" ] || { echo "sauvegarde existante" >&2; exit 1; }
if [ -f "$TMP/previous" ]; then
    chmod 0600 "$TMP/previous"
    mv -n "$TMP/previous" "$PREVIOUS"
    [ ! -e "$TMP/previous" ] || { echo "référence existante" >&2; exit 1; }
fi
install -d -m 0755 /opt/agentcore/releases
mkdir -m 0755 "$REL" # atomique : ne jamais écraser une release existante
install -m 0755 "$HERE/agentcore" "$REL/agentcore"
install -m 0644 "$HERE/VERSION" "$HERE/SHA256SUMS" "$REL/"
install -m 0755 "$HERE/install.sh" "$HERE/rollback.sh" "$HERE/recette.sh" "$REL/"
cp -r "$HERE/demo" "$REL/demo" && chmod -R a+rX "$REL/demo"
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
[ -s /etc/agentcore/api_key ] || echo "ATTENTION : /etc/agentcore/api_key absent ou vide (root:$USER_NAME 0640)"
echo "installé : $VERSION ; sauvegarde : ${BACKUP}"
/usr/local/bin/agentcore version
