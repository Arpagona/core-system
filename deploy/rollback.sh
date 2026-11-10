#!/usr/bin/env bash
# Revient à la version active précédente (sudo). Usage : rollback.sh [VERSION]
# La configuration et l'état des missions ne sont pas modifiés ; restauration complète :
#   tar -xzf /var/backups/agentcore/avant-<version>-<date>.tar.gz -C /
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "à lancer avec sudo" >&2; exit 1; }
if [ $# -ge 1 ]; then
    TARGET="/opt/agentcore/releases/$1"
else
    LAST=$(ls -1t /var/backups/agentcore/previous-* 2>/dev/null | head -1 || true)
    [ -n "$LAST" ] || { echo "aucune version précédente enregistrée" >&2; exit 1; }
    TARGET=$(cat "$LAST")
fi
[ -x "$TARGET/agentcore" ] || { echo "version introuvable : $TARGET" >&2; ls /opt/agentcore/releases >&2; exit 1; }
ln -sfn "$TARGET" /opt/agentcore/current.new && mv -T /opt/agentcore/current.new /opt/agentcore/current
echo "version active : $(readlink -f /opt/agentcore/current)"
/usr/local/bin/agentcore version
