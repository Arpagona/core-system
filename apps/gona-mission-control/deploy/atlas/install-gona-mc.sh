#!/bin/bash
# Installe / met a jour GONA Mission Control (mode api) sur le banc Atlas. A lancer en root.
#   install-gona-mc.sh install <archive.tar.gz>   release horodatee + bascule du lien `current` (ancien -> `previous`)
#   install-gona-mc.sh rollback                    revient a `previous`
# Port 127.0.0.1:8711 uniquement (acces par tunnel SSH). Aucun secret dans l'archive.
set -euo pipefail
BASE=/opt/gona-mission-control; ETC=/etc/gona-mission-control; VAR=/var/lib/gona-mission-control
UNIT=gona-mission-control.service
case "${1:-}" in
install)
  ARCH=${2:?archive}; REL=$BASE/releases/$(date +%Y%m%d-%H%M%S)
  id gona-mc >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin gona-mc
  install -d -m 755 $BASE $BASE/releases; install -d -m 750 -o root -g gona-mc $ETC
  install -d -m 700 -o gona-mc -g gona-mc $VAR $VAR/data $VAR/profile
  mkdir -p $REL; tar xzf "$ARCH" -C $REL; chown -R root:root $BASE; chmod -R go-w $BASE
  python3 -m py_compile $REL/server.py
  [ -f $ETC/token ] || { head -c 24 /dev/urandom | base64 | tr -d '=+/' > $ETC/token; }
  # cle du moteur Hermes de test : copiee depuis l'API existante, lisible par gona-mc seulement
  install -m 640 -o root -g gona-mc /etc/arpagona-api/hermes_key $ETC/hermes_key
  chown root:gona-mc $ETC/token; chmod 640 $ETC/token
  if [ -e $BASE/current ]; then ln -sfn "$(readlink -f $BASE/current)" $BASE/previous; fi
  ln -sfn $REL $BASE/current
  install -m 644 $REL/deploy/atlas/$UNIT /etc/systemd/system/$UNIT
  systemctl daemon-reload; systemctl enable $UNIT >/dev/null 2>&1; systemctl restart $UNIT
  sleep 2; systemctl is-active $UNIT; echo "release: $REL" ;;
rollback)
  [ -e $BASE/previous ] || { echo "pas de version precedente"; exit 1; }
  TARGET=$(readlink -f $BASE/previous); CUR=$(readlink -f $BASE/current)
  ln -sfn "$CUR" $BASE/previous; ln -sfn "$TARGET" $BASE/current; systemctl restart $UNIT; sleep 2; systemctl is-active $UNIT ;;
*) echo "usage: $0 install <archive> | rollback"; exit 2 ;;
esac
