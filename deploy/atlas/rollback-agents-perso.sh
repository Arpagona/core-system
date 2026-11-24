#!/usr/bin/env bash
# Retour arrière des agents personnels (à lancer avec sudo). Rejouable.
# Niveau 1 (défaut) : arrête et désactive les services par utilisateur, retire le registre de l'API, qui
#   revient au moteur commun (hermes-arpagona). Les données des agents (/srv/agents) sont CONSERVÉES.
# Niveau 2 (--purge) : supprime en plus comptes Unix, données, ACL de traversée, portier et secrets des agents.
# Niveau 3 (VM entière) : sur Atlas, `qm rollback 100 avant-agents-par-utilisateur-20261124`
#   (efface tout ce qui a été fait sur la VM depuis le snapshot).
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "à lancer en root" >&2; exit 1; }
LOGINS="mael thibaud"
for l in $LOGINS; do
  systemctl disable --now "arpagona-agent@$l.service" "arpagona-kanban-bridge@$l.service" 2>/dev/null || true
done
systemctl disable --now hindsight-gate.service 2>/dev/null || true
systemctl reset-failed "arpagona-agent@*.service" "arpagona-kanban-bridge@*.service" 2>/dev/null || true  # l'arrêt de Hermès sort en code 1
rm -f /etc/systemd/system/arpagona-api.service.d/agents.conf
rmdir /etc/systemd/system/arpagona-api.service.d 2>/dev/null || true
systemctl daemon-reload
systemctl restart arpagona-api.service
for _ in $(seq 1 20); do
  sleep 2
  curl -fsS -m 3 http://127.0.0.1:8700/api/health && break
done
echo
if [ "${1:-}" = "--purge" ]; then
  for l in $LOGINS; do
    userdel "agent-$l" 2>/dev/null || true
    rm -rf "/srv/agents/$l" "/etc/arpagona-api/agents/$l" "/etc/arpagona-agents/$l.env"
  done
  rm -f /etc/arpagona-api/agents.json /etc/systemd/system/arpagona-agent@.service \
        /etc/systemd/system/arpagona-kanban-bridge@.service /etc/systemd/system/hindsight-gate.service
  rm -rf /etc/hindsight-gate /opt/arpagona/shared-plugins
  userdel hindsight-gate 2>/dev/null || true
  setfacl -R -x g:hermes-core /srv/hermes-arpagona/.hermes/hermes-agent /srv/hermes-arpagona/.hermes/tools \
    /srv/hermes-arpagona/.hermes/installs
  setfacl -x g:hermes-core /srv/hermes-arpagona /srv/hermes-arpagona/.hermes
  groupdel hermes-core 2>/dev/null || true
  systemctl daemon-reload
  echo "purge faite ; les banques Hindsight arpagona-mael et arpagona-thibaud restent dans Hindsight (à supprimer par son API si voulu)"
fi
echo "agents personnels : retour arrière terminé"
