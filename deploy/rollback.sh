#!/usr/bin/env bash
# Revient à la version active précédente (sudo). Usage : rollback.sh [VERSION]
# La configuration et l'état des missions ne sont pas modifiés ; voir docs/SAUVEGARDE-INSTALLATION-VM.md
# pour l'extraction isolée et les limites de la sauvegarde.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "à lancer avec sudo" >&2; exit 1; }
if [ $# -ge 1 ]; then
    case "$1" in ''|.|..|*[!a-zA-Z0-9._-]*) echo "version invalide" >&2; exit 1;; esac
    TARGET="/opt/agentcore/releases/$1"
else
    LAST=$(ls -1t /var/backups/agentcore/previous-* 2>/dev/null | head -1 || true)
    [ -n "$LAST" ] || { echo "aucune version précédente enregistrée" >&2; exit 1; }
    TARGET=$(cat "$LAST")
fi
case "$TARGET" in /opt/agentcore/releases/*) ;; *) echo "cible hors releases" >&2; exit 1;; esac
[ "$(readlink -e "$TARGET")" = "$TARGET" ] || { echo "cible non canonique" >&2; exit 1; }
[ -x "$TARGET/agentcore" ] || { echo "version introuvable : $TARGET" >&2; ls /opt/agentcore/releases >&2; exit 1; }
ln -sfn "$TARGET" /opt/agentcore/current.new && mv -T /opt/agentcore/current.new /opt/agentcore/current
echo "version active : $(readlink -f /opt/agentcore/current)"
/usr/local/bin/agentcore version
