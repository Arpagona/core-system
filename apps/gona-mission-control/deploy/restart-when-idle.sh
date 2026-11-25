#!/bin/sh
# Redémarre le serveur Mission Control seulement quand aucun tour n'est en cours (pas de réponse coupée).
DB="$HOME/.hermes/profiles/gpt5/gona-mission-control/chat.db"
calm=0
for i in $(seq 1 720); do   # 1 h max
  n=$(/usr/bin/python3 -c "import sqlite3,sys;c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True);print(c.execute(\"select count(*) from submissions where state in ('queued','running')\").fetchone()[0])" "$DB" 2>/dev/null || echo 1)
  if [ "$n" = "0" ]; then calm=$((calm+1)); else calm=0; fi
  if [ $calm -ge 4 ]; then systemctl --user restart arpagona-mission-control-alpha.service; echo "redémarré $(date)"; exit 0; fi
  sleep 5
done
echo "abandon : tour toujours en cours"; exit 1
