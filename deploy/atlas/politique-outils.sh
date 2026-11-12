#!/usr/bin/env bash
# Applique la politique d'outils de l'instance Hermès de test (à lancer avec sudo).
# Principe : liste PERMISE explicite par canal ; tout autre outil est désactivé, y compris
# ceux qu'une future version d'Hermès activerait par défaut.
#
# memory et session_search sont exclus : ils sont communs à toute l'instance et feraient
# passer une information d'un utilisateur à un autre. La mémoire native est aussi coupée
# dans la configuration, pour qu'aucune note ancienne ne soit injectée dans une session.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "à lancer en root" >&2; exit 1; }
ALLOWED="${ARPAGONA_ALLOWED_TOOLSETS:-web todo arpagona}"
PLATFORMS="${ARPAGONA_PLATFORMS:-api_server telegram}"
run() { sudo -u hermes-arpagona -H bash -lc "export PATH=\$HOME/.local/bin:\$PATH; $1"; }

run "hermes config set memory.memory_enabled false >/dev/null; hermes config set memory.user_profile_enabled false >/dev/null"
for platform in $PLATFORMS; do
  names="$(run "hermes tools list --platform $platform" | awk '/enabled|disabled/ {print $3}')"
  to_disable=""
  for name in $names; do
    case " $ALLOWED " in *" $name "*) ;; *) to_disable="$to_disable $name" ;; esac
  done
  [ -z "$to_disable" ] || run "hermes tools disable --platform $platform $to_disable" >/dev/null
  for name in $ALLOWED; do
    case " $names " in *" $name "*) run "hermes tools enable --platform $platform $name" >/dev/null ;; esac
  done
  active="$(run "hermes tools list --platform $platform" | awk '/enabled/ && !/disabled/ {print $3}' | sort | tr '\n' ' ')"
  echo "$platform : $active"
  for name in $active; do
    case " $ALLOWED " in *" $name "*) ;; *) echo "ÉCHEC : $name reste actif sur $platform" >&2; exit 1 ;; esac
  done
done
