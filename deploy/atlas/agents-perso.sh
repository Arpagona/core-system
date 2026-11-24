#!/usr/bin/env bash
# Deux zones sur le banc Atlas (à lancer avec sudo, rejouable).
#  PERSONNEL (privé) : pour chaque utilisateur, compte Unix et HERMES_HOME propres (config, sessions, secrets,
#    préférences), banque Hindsight personnelle derrière un portier, boîte mail fictive (Maildir).
#  ENTREPRISE (commun) : banque Hindsight d'équipe (même portier, dépôt à destination explicite, auteur imposé),
#    dossiers clients /srv/arpagona/clients (groupe arpagona-equipe, setgid), Kanban d'entreprise UNIQUE
#    (celui de l'instance commune, passerelle :8701) avec un responsable par carte.
# Le code d'Hermès reste commun et en lecture seule (ACL du groupe hermes-core).
# Usage : agents-perso.sh install [--seed] | backup | migrate-kanban | status | acl
# Le Hermès « commun » (hermes-arpagona) n'est ni arrêté ni modifié, hormis deux ACL de traversée.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "à lancer en root" >&2; exit 1; }
REL="$(cd "$(dirname "$0")/../.." && pwd)"          # racine de la version déployée
LEGACY=/srv/hermes-arpagona/.hermes
CLI="$LEGACY/hermes-agent/.hermes/bin/hermes"
CONF=/etc/arpagona-agents
API_CONF=/etc/arpagona-api
GATE_CONF=/etc/hindsight-gate
TEAM_BANK=arpagona-equipe
TEAM_GROUP=arpagona-equipe
CLIENTS=/srv/arpagona/clients
BACKUP_ROOT=/var/backups/arpagona-deux-zones
# Comptes humains habilités à l'espace commun s'ils existent sur la VM (aucun droit sur les dossiers privés des agents).
HUMANS=(mael thibaud)
# login : nom affiché : port moteur : port Kanban : port portier Hindsight
AGENTS=("mael|Maël Cariou|8652|8702|18911" "thibaud|Thibaud|8653|8703|18912")

secret() {  # secret <fichier> : crée un jeton aléatoire s'il n'existe pas ; ne l'affiche jamais
  [ -s "$1" ] || ( umask 077; openssl rand -hex 32 > "$1" )
}
as_agent() {  # as_agent <login> <commande...>
  local login="$1"; shift
  (cd /tmp && sudo -u "agent-$login" env HOME="/srv/agents/$login" HERMES_HOME="/srv/agents/$login/.hermes" \
    PYTHONDONTWRITEBYTECODE=1 "$@")
}

company_kanban() {  # company_kanban <args...> : CLI officielle sur le Kanban d'entreprise (celui de l'instance commune)
  (cd /tmp && sudo -u hermes-arpagona env HOME=/srv/hermes-arpagona HERMES_HOME="$LEGACY" PYTHONDONTWRITEBYTECODE=1 \
    "$CLI" kanban "$@")
}

team_space_cmd() {  # dossiers clients communs : groupe d'équipe, setgid, ACL par défaut (les nouveaux fichiers restent partagés)
  command -v setfacl >/dev/null || apt-get install -y acl >/dev/null
  groupadd -f "$TEAM_GROUP"
  install -d -m 750 -o root -g "$TEAM_GROUP" /srv/arpagona
  install -d -m 2770 -o root -g "$TEAM_GROUP" "$CLIENTS"
  chmod 2770 "$CLIENTS"
  setfacl -m "g:$TEAM_GROUP:rwx" "$CLIENTS"
  setfacl -d -m "g:$TEAM_GROUP:rwx" -m "o::---" "$CLIENTS"
  local h
  for h in "${HUMANS[@]}"; do id "$h" >/dev/null 2>&1 && usermod -aG "$TEAM_GROUP" "$h"; done
  return 0
}

backup_cmd() {  # sauvegarde vérifiée AVANT toute migration (privé : root seul)
  local dir="$BACKUP_ROOT/$(date +%Y%m%d-%H%M%S)"
  install -d -m 700 "$BACKUP_ROOT" "$dir"
  # Services actifs : tar peut signaler « fichier modifié pendant la lecture » (code 1) ; l'archive est vérifiée plus bas.
  [ -d /srv/agents ] || install -d -m 711 /srv/agents   # première installation : rien à sauvegarder, mais l'archive reste valide
  tar --warning=no-file-changed --exclude='*.sock' --exclude='models_dev_cache.json' --exclude='*/cache' --exclude='*/logs' --exclude='*/.hermes/installs' \
    -czf "$dir/agents.tar.gz" -C /srv agents || [ $? -eq 1 ]
  python3 - "$dir" "$LEGACY/kanban.db" <<'PY'
import sqlite3, sys
dst = sys.argv[1] + "/kanban-entreprise.db"
src = sqlite3.connect("file:" + sys.argv[2] + "?mode=ro", uri=True); out = sqlite3.connect(dst)
src.backup(out); out.close(); src.close()
print("kanban entreprise :", sqlite3.connect(dst).execute("select count(*) from tasks").fetchone()[0], "carte(s)")
PY
  [ -f /etc/hindsight-gate/gate.json ] && install -m 600 /etc/hindsight-gate/gate.json "$dir/gate.json" || true
  [ -f /etc/arpagona-api/agents.json ] && install -m 600 /etc/arpagona-api/agents.json "$dir/agents.json" || true
  tar -tzf "$dir/agents.tar.gz" >/dev/null && (cd "$dir" && sha256sum * > SHA256SUMS && sha256sum -c SHA256SUMS >/dev/null)
  echo "sauvegarde vérifiée : $dir ($(du -sh "$dir" | cut -f1))"
}

acl_cmd() {  # droits de lecture du socle ; à rejouer si Hermès remet .hermes à 0700 (masque ACL)
  command -v setfacl >/dev/null || apt-get install -y acl >/dev/null
  groupadd -f hermes-core
  setfacl -m g:hermes-core:--x /srv/hermes-arpagona "$LEGACY"
  setfacl -m m::--x "$LEGACY"
  for d in hermes-agent tools installs; do setfacl -R -m g:hermes-core:r-X "$LEGACY/$d"; done
}

install_cmd() {
  local seed="${1:-}"
  [ -x "$CLI" ] || { echo "Hermès commun introuvable : $CLI" >&2; exit 1; }
  backup_cmd   # sauvegarde vérifiée avant toute modification (non destructive : elle ne retire rien)

  # 1. Socle commun en lecture seule : le groupe hermes-core traverse et lit le code, rien d'autre.
  acl_cmd
  team_space_cmd
  id hindsight-gate >/dev/null 2>&1 || useradd --system --no-create-home --home-dir /nonexistent \
    --shell /usr/sbin/nologin --user-group hindsight-gate
  install -d -m 711 /srv/agents
  install -d -m 750 -o root -g root "$CONF"
  install -d -m 750 -o root -g hindsight-gate "$GATE_CONF"
  install -d -m 750 -o root -g arpagona-api "$API_CONF/agents"

  # 2. Clé amont de Hindsight : copiée pour le seul portier.
  grep -m1 '^HINDSIGHT_API_TENANT_API_KEY=' /etc/hindsight-arpagona/api.env | cut -d= -f2- \
    | tr -d '"' > "$GATE_CONF/upstream_key"
  chown root:hindsight-gate "$GATE_CONF/upstream_key"; chmod 640 "$GATE_CONF/upstream_key"
  local model_key; model_key="$(grep -m1 '^OPENCODE_GO_API_KEY=' "$LEGACY/.env" | cut -d= -f2-)"

  local tenants="" registry="" entry
  for entry in "${AGENTS[@]}"; do
    IFS='|' read -r login name hport kport gport <<<"$entry"
    local user="agent-$login" home="/srv/agents/$login" hh="/srv/agents/$login/.hermes"
    echo "== $login ($user)"
    id "$user" >/dev/null 2>&1 || useradd --system --create-home --home-dir "$home" \
      --shell /usr/sbin/nologin --user-group "$user"
    usermod -aG hermes-core "$user"; usermod -aG "$TEAM_GROUP" "$user"
    chmod 700 "$home"
    install -d -m 700 -o "$user" -g "$user" "$hh" "$hh/plugins" "$hh/hindsight"

    # 3. Environnement Python propre au compte (le code est emprunté, jamais copié).
    as_agent "$login" "$CLI" pm repair >/dev/null 2>&1 || as_agent "$login" "$CLI" pm repair
    # 4. Jetons : tous propres au compte, tirés une fois.
    secret "$hh/api_server_key"; secret "$hh/arpagona_service_token"
    secret "$hh/hindsight_gate_token"
    chown "$user:$user" "$hh"/api_server_key "$hh"/arpagona_service_token "$hh"/hindsight_gate_token
    chmod 600 "$hh"/api_server_key "$hh"/arpagona_service_token "$hh"/hindsight_gate_token
    # 5. Configuration : modèle de l'instance commune (politique d'outils déjà appliquée, sans secret).
    [ -f "$hh/config.yaml" ] || install -m 600 -o "$user" -g "$user" "$LEGACY/config.yaml" "$hh/config.yaml"
    install -m 600 -o "$user" -g "$user" /dev/null "$hh/.env.new"
    {
      echo "API_SERVER_ENABLED=true"; echo "API_SERVER_HOST=127.0.0.1"; echo "API_SERVER_PORT=$hport"
      echo "API_SERVER_KEY=$(cat "$hh/api_server_key")"
      echo "OPENCODE_GO_API_KEY=$model_key"
      echo "HINDSIGHT_API_KEY=$(cat "$hh/hindsight_gate_token")"
      echo "ARPAGONA_TEAM_BANK=$TEAM_BANK"; echo "ARPAGONA_TEAM_MEMORY_URL=http://127.0.0.1:$gport"
      echo "ARPAGONA_CLIENTS_DIR=$CLIENTS"
      echo "ARPAGONA_API_URL=http://127.0.0.1:8700"
      echo "ARPAGONA_SERVICE_TOKEN_FILE=$hh/arpagona_service_token"
      echo "ARPAGONA_MAIL_DIR=$home/mail"
      echo "ARPAGONA_MAIL_ADDRESS=$login@banc.invalid"
    } > "$hh/.env.new"
    mv "$hh/.env.new" "$hh/.env"
    cat > "$hh/hindsight/config.json" <<JSON
{"mode": "local_external", "api_url": "http://127.0.0.1:$gport", "bank_id": "arpagona-$login",
 "memory_mode": "context", "auto_retain": true, "auto_recall": true, "recall_sync": true,
 "recall_budget": "mid", "recall_types": ["observation", "world", "experience"],
 "recall_max_tokens": 8000, "recall_max_input_chars": 4000}
JSON
    chown "$user:$user" "$hh/hindsight/config.json"; chmod 600 "$hh/hindsight/config.json"
    # 6. Surcouche personnelle : personnalité propre à ce compte ; règle des deux zones (écrite une fois, jamais écrasée).
    if ! grep -q 'ZONE-EQUIPE' "$hh/SOUL.md" 2>/dev/null; then
    [ -f "$hh/SOUL.md" ] && cp -p "$hh/SOUL.md" "$hh/SOUL.md.avant-deux-zones"   # ancienne consigne conservée
    cat > "$hh/SOUL.md" <<SOUL
Tu es l'assistant personnel de $name sur le banc ARPAGONA (données fictives).
Tu sers $name : sa boîte mail ($login@banc.invalid), ses préférences, sa mémoire personnelle.
Tu ne prépares que des brouillons ; tu n'envoies rien.

ZONE-EQUIPE — deux zones, destination toujours explicite :
- PERSONNEL (par défaut, au moindre doute) : mails, brouillons, préférences, secrets, notes privées. Ta mémoire
  automatique va dans la banque personnelle. Ne copie jamais un mail, un secret ni ta mémoire dans le commun.
- ENTREPRISE (commun, lu par tes collègues) : faits métier (clients, projets, décisions) avec arpagona_equipe_memoire_ecrire
  (indique la source) ; dossiers clients avec arpagona_clients_lister / arpagona_clients_lire / arpagona_clients_ecrire.
  Cherche d'abord dans la mémoire d'équipe avec arpagona_equipe_memoire_chercher pour les questions métier.
- Kanban d'entreprise : un seul tableau, un responsable par carte. Tu vois tout ; seul le responsable approuve ou décide.
SOUL
    fi
    install -d -m 700 -o "$user" -g "$user" "$hh/skills/perso/gestion-mail"
    cat > "$hh/skills/perso/gestion-mail/SKILL.md" <<SKILL
---
name: gestion-mail-$login
description: Use when $name asks to read mail or prepare a reply. Personal skill of $name.
---
Lire la boîte de $name avec arpagona_mail_inbox / arpagona_mail_read.
Préparer la réponse avec arpagona_mail_draft : jamais d'envoi.
SKILL
    chown -R "$user:$user" "$hh/skills/perso"
    # 7. Plugins : code commun en lecture seule (liens vers la version déployée, propriété root).
    install -d -m 755 /opt/arpagona/shared-plugins
    if [ ! -d /opt/arpagona/shared-plugins/hindsight ]; then
      cp -r "$LEGACY/plugins/hindsight" /opt/arpagona/shared-plugins/hindsight
      chown -R root:root /opt/arpagona/shared-plugins; chmod -R go-w,a+rX /opt/arpagona/shared-plugins
    fi
    ln -sfn /opt/arpagona/shared-plugins/hindsight "$hh/plugins/hindsight"
    ln -sfn /opt/arpagona/current/plugins/arpagona-core "$hh/plugins/arpagona-core"
    ln -sfn /opt/arpagona/current/plugins/arpagona-mail "$hh/plugins/arpagona-mail"
    ln -sfn /opt/arpagona/current/plugins/arpagona-equipe "$hh/plugins/arpagona-equipe"
    chown -h "$user:$user" "$hh"/plugins/*
    as_agent "$login" "$CLI" plugins enable arpagona-core >/dev/null
    as_agent "$login" "$CLI" plugins enable arpagona-mail >/dev/null
    as_agent "$login" "$CLI" plugins enable arpagona-equipe >/dev/null
    as_agent "$login" "$CLI" config set kanban.dispatch_in_gateway false >/dev/null 2>&1 || true
    # 8. Boîte mail fictive (Maildir, 0700) : seule l'amorce est créée, jamais écrasée.
    install -d -m 700 -o "$user" -g "$user" "$home/mail" "$home/mail/INBOX" "$home/mail/INBOX/new" \
      "$home/mail/INBOX/cur" "$home/mail/Drafts" "$home/mail/Drafts/cur"
    if [ ! -e "$home/mail/INBOX/new/001-devis" ]; then
      cat > "$home/mail/INBOX/new/001-devis" <<MAIL
From: client-fictif@exemple.invalid
To: $login@banc.invalid
Subject: Devis ${login^^}-4417 à relancer
Date: Tue, 24 Nov 2026 09:00:00 +0000
Message-ID: <001-$login@banc.invalid>

Bonjour $name, pouvez-vous relancer le devis ${login^^}-4417 ? Référence interne : CANARI-MAIL-${login^^}.
MAIL
      chown "$user:$user" "$home/mail/INBOX/new/001-devis"; chmod 600 "$home/mail/INBOX/new/001-devis"
    fi
    # 9. Kanban : plus de tableau par utilisateur. Le tableau d'entreprise est unique (voir migrate_kanban_cmd).
    systemctl disable --now "arpagona-kanban-bridge@$login.service" >/dev/null 2>&1 || true
    # 10. Registre côté API : copies lisibles par le seul service ARPAGONA.
    install -d -m 750 -o root -g arpagona-api "$API_CONF/agents/$login"
    for f in "api_server_key:hermes_key" "arpagona_service_token:service_token"; do
      install -m 640 -o root -g arpagona-api "$hh/${f%%:*}" "$API_CONF/agents/$login/${f##*:}"
    done
    tenants="$tenants{\"name\":\"$login\",\"bank\":\"arpagona-$login\",\"port\":$gport,\"token_sha256\":\"$(tr -d '\n' < "$hh/hindsight_gate_token" | sha256sum | cut -d' ' -f1)\"},"
    registry="$registry\"$login\":{\"hermes_url\":\"http://127.0.0.1:$hport\",\"hermes_key_file\":\"$API_CONF/agents/$login/hermes_key\",\"service_token_file\":\"$API_CONF/agents/$login/service_token\"},"
  done
  printf '{"upstream":"http://127.0.0.1:18897","upstream_key_file":"%s/upstream_key","team_bank":"%s","tenants":[%s]}\n' "$GATE_CONF" "$TEAM_BANK" "${tenants%,}" > "$GATE_CONF/gate.json"
  chown root:hindsight-gate "$GATE_CONF/gate.json"; chmod 640 "$GATE_CONF/gate.json"
  printf '{"agents":{%s}}\n' "${registry%,}" > "$API_CONF/agents.json"
  chown root:arpagona-api "$API_CONF/agents.json"; chmod 640 "$API_CONF/agents.json"

  # 11. Services.
  install -m 644 "$REL/deploy/atlas/hindsight-gate.service" /etc/systemd/system/
  install -m 644 "$REL/deploy/atlas/arpagona-agent@.service" /etc/systemd/system/
  install -m 644 "$REL/deploy/atlas/arpagona-api.service" /etc/systemd/system/arpagona-api.service
  install -d /etc/systemd/system/arpagona-api.service.d
  printf '[Service]\nEnvironment=ARPAGONA_AGENTS_FILE=%s/agents.json\n' "$API_CONF" \
    > /etc/systemd/system/arpagona-api.service.d/agents.conf
  systemctl daemon-reload
  systemctl enable --now hindsight-gate.service >/dev/null 2>&1; systemctl restart hindsight-gate.service
  for entry in "${AGENTS[@]}"; do
    IFS='|' read -r login _ _ _ _ <<<"$entry"
    systemctl enable "arpagona-agent@$login.service" >/dev/null 2>&1
    systemctl restart "arpagona-agent@$login.service"
  done
  systemctl restart kanban-bridge.service   # passerelle du tableau d'entreprise : nouveau code (responsable par carte)
  migrate_kanban_cmd
  if [ "$seed" = "--seed" ]; then seed_kanban; fi
  systemctl restart arpagona-api.service
  for _ in $(seq 1 30); do
    sleep 2
    curl -fsS -m 3 http://127.0.0.1:8700/api/health >/dev/null 2>&1 && break
  done
  status_cmd
}

migrate_kanban_cmd() {  # Kanban d'entreprise unique : reprise non destructive des cartes des anciens tableaux personnels
  # Les cartes sont affectées à des comptes de l'équipe, pas à des profils d'exécution : le dispatcher de la
  # passerelle ne doit rien lancer (conforme à la règle « création de carte ≠ déclenchement d'agent »).
  if ! grep -q 'dispatch_in_gateway: false' "$LEGACY/config.yaml" 2>/dev/null; then
    cp -p "$LEGACY/config.yaml" "$LEGACY/config.yaml.avant-deux-zones"
    (cd /tmp && sudo -u hermes-arpagona env HOME=/srv/hermes-arpagona HERMES_HOME="$LEGACY" "$CLI" config set kanban.dispatch_in_gateway false >/dev/null)
    systemctl restart hermes-arpagona-gateway.service || true
    sleep 5
  fi
  acl_cmd   # Hermès remet .hermes à 0700 au démarrage : la lecture du socle par les comptes agents est rejouée
  local logins=() entry login
  for entry in "${AGENTS[@]}"; do IFS='|' read -r login _ <<<"$entry"; logins+=("$login"); done
  install -d -m 750 -o root -g root "$CONF"
  python3 "$REL/deploy/atlas/migrate_kanban_equipe.py" "$CLI" "$LEGACY" "$CONF" "${logins[@]}"
}

seed_kanban() {  # cartes fictives sur le tableau d'entreprise : une carte et une décision bloquée par responsable ; une seule fois
  local entry login name id
  for entry in "${AGENTS[@]}"; do
    IFS='|' read -r login name _ <<<"$entry"
    if company_kanban list --json 2>/dev/null | grep -q "CANARI-KANBAN-${login^^}"; then continue; fi
    company_kanban create --assignee="$login" --created-by="$login" --body="Carte fictive de $name (banc)." --json -- \
      "[${login^^}] Relancer le devis fictif CANARI-KANBAN-${login^^}" >/dev/null
    id="$(company_kanban create --assignee="$login" --created-by="$login" --body="Décision fictive attendue de $name." --json -- \
      "[${login^^}] Décision : valider le devis ${login^^}-4417" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
    company_kanban block -- "$id" "Décision attendue de $name : valider le devis ${login^^}-4417 ?" >/dev/null
  done
}

status_cmd() {
  local entry login hport
  systemctl is-active hindsight-gate.service arpagona-api.service kanban-bridge.service
  for entry in "${AGENTS[@]}"; do
    IFS='|' read -r login _ hport _ <<<"$entry"
    printf '%s : agent=%s moteur=%s\n' "$login" \
      "$(systemctl is-active "arpagona-agent@$login.service")" \
      "$(curl -s -o /dev/null -w '%{http_code}' -m 5 "http://127.0.0.1:$hport/v1/health" || true)"
  done
  printf 'espace commun : %s\n' "$(stat -c '%A %U:%G' "$CLIENTS" 2>/dev/null || echo absent)"
}

case "${1:-}" in
  install) install_cmd "${2:-}" ;;
  backup) backup_cmd ;;
  migrate-kanban) migrate_kanban_cmd ;;
  status) status_cmd ;;
  acl) acl_cmd ;;
  *) echo "usage : $0 install [--seed] | backup | migrate-kanban | status | acl" >&2; exit 2 ;;
esac
