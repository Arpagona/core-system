#!/usr/bin/env bash
# Agents personnels par utilisateur sur le banc Atlas (à lancer avec sudo, rejouable).
# Pour chaque utilisateur : compte Unix propre, HERMES_HOME propre (config, mémoire, skills, Kanban,
# secrets), banque Hindsight propre derrière un portier, boîte mail fictive (Maildir) propre.
# Le code d'Hermès reste commun et en lecture seule (ACL du groupe hermes-core).
# Usage : agents-perso.sh install [--seed] | status | acl
# Le Hermès « commun » (hermes-arpagona) n'est ni arrêté ni modifié, hormis deux ACL de traversée.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "à lancer en root" >&2; exit 1; }
REL="$(cd "$(dirname "$0")/../.." && pwd)"          # racine de la version déployée
LEGACY=/srv/hermes-arpagona/.hermes
CLI="$LEGACY/hermes-agent/.hermes/bin/hermes"
CONF=/etc/arpagona-agents
API_CONF=/etc/arpagona-api
GATE_CONF=/etc/hindsight-gate
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

  # 1. Socle commun en lecture seule : le groupe hermes-core traverse et lit le code, rien d'autre.
  acl_cmd
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
    usermod -aG hermes-core "$user"
    chmod 700 "$home"
    install -d -m 700 -o "$user" -g "$user" "$hh" "$hh/plugins" "$hh/hindsight"

    # 3. Environnement Python propre au compte (le code est emprunté, jamais copié).
    as_agent "$login" "$CLI" pm repair >/dev/null 2>&1 || as_agent "$login" "$CLI" pm repair
    # 4. Jetons : tous propres au compte, tirés une fois.
    secret "$hh/api_server_key"; secret "$hh/arpagona_service_token"
    secret "$hh/arpagona_kanban_token"; secret "$hh/hindsight_gate_token"
    chown "$user:$user" "$hh"/api_server_key "$hh"/arpagona_service_token "$hh"/arpagona_kanban_token "$hh"/hindsight_gate_token
    chmod 600 "$hh"/api_server_key "$hh"/arpagona_service_token "$hh"/arpagona_kanban_token "$hh"/hindsight_gate_token
    # 5. Configuration : modèle de l'instance commune (politique d'outils déjà appliquée, sans secret).
    [ -f "$hh/config.yaml" ] || install -m 600 -o "$user" -g "$user" "$LEGACY/config.yaml" "$hh/config.yaml"
    install -m 600 -o "$user" -g "$user" /dev/null "$hh/.env.new"
    {
      echo "API_SERVER_ENABLED=true"; echo "API_SERVER_HOST=127.0.0.1"; echo "API_SERVER_PORT=$hport"
      echo "API_SERVER_KEY=$(cat "$hh/api_server_key")"
      echo "OPENCODE_GO_API_KEY=$model_key"
      echo "HINDSIGHT_API_KEY=$(cat "$hh/hindsight_gate_token")"
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
    # 6. Surcouche personnelle : personnalité et compétence propres à ce compte.
    cat > "$hh/SOUL.md" <<SOUL
Tu es l'assistant personnel de $name sur le banc ARPAGONA (données fictives).
Tu ne sers que $name : sa boîte mail ($login@banc.invalid), sa mémoire, son Kanban.
Tu ne prépares que des brouillons ; tu n'envoies rien.
SOUL
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
    chown -h "$user:$user" "$hh"/plugins/*
    as_agent "$login" "$CLI" plugins enable arpagona-core >/dev/null
    as_agent "$login" "$CLI" plugins enable arpagona-mail >/dev/null
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
    # 9. Kanban propre : base créée sous HERMES_HOME du compte, jamais partagée.
    install -d -m 750 -o root -g root "$CONF"
    printf 'KANBAN_BRIDGE_PORT=%s\n' "$kport" > "$CONF/$login.env"
    # 10. Registre côté API : copies lisibles par le seul service ARPAGONA.
    install -d -m 750 -o root -g arpagona-api "$API_CONF/agents/$login"
    for f in "api_server_key:hermes_key" "arpagona_kanban_token:kanban_token" "arpagona_service_token:service_token"; do
      install -m 640 -o root -g arpagona-api "$hh/${f%%:*}" "$API_CONF/agents/$login/${f##*:}"
    done
    tenants="$tenants{\"name\":\"$login\",\"bank\":\"arpagona-$login\",\"port\":$gport,\"token_sha256\":\"$(tr -d '\n' < "$hh/hindsight_gate_token" | sha256sum | cut -d' ' -f1)\"},"
    registry="$registry\"$login\":{\"hermes_url\":\"http://127.0.0.1:$hport\",\"hermes_key_file\":\"$API_CONF/agents/$login/hermes_key\",\"kanban_url\":\"http://127.0.0.1:$kport\",\"kanban_token_file\":\"$API_CONF/agents/$login/kanban_token\",\"service_token_file\":\"$API_CONF/agents/$login/service_token\"},"
  done
  printf '{"upstream":"http://127.0.0.1:18897","upstream_key_file":"%s/upstream_key","tenants":[%s]}\n' "$GATE_CONF" "${tenants%,}" > "$GATE_CONF/gate.json"
  chown root:hindsight-gate "$GATE_CONF/gate.json"; chmod 640 "$GATE_CONF/gate.json"
  printf '{"agents":{%s}}\n' "${registry%,}" > "$API_CONF/agents.json"
  chown root:arpagona-api "$API_CONF/agents.json"; chmod 640 "$API_CONF/agents.json"

  # 11. Services.
  install -m 644 "$REL/deploy/atlas/hindsight-gate.service" /etc/systemd/system/
  install -m 644 "$REL/deploy/atlas/arpagona-agent@.service" /etc/systemd/system/
  install -m 644 "$REL/deploy/atlas/arpagona-kanban-bridge@.service" /etc/systemd/system/
  install -m 644 "$REL/deploy/atlas/arpagona-api.service" /etc/systemd/system/arpagona-api.service
  install -d /etc/systemd/system/arpagona-api.service.d
  printf '[Service]\nEnvironment=ARPAGONA_AGENTS_FILE=%s/agents.json\n' "$API_CONF" \
    > /etc/systemd/system/arpagona-api.service.d/agents.conf
  systemctl daemon-reload
  systemctl enable --now hindsight-gate.service >/dev/null 2>&1; systemctl restart hindsight-gate.service
  for entry in "${AGENTS[@]}"; do
    IFS='|' read -r login _ _ _ _ <<<"$entry"
    systemctl enable "arpagona-kanban-bridge@$login.service" "arpagona-agent@$login.service" >/dev/null 2>&1
    systemctl restart "arpagona-kanban-bridge@$login.service" "arpagona-agent@$login.service"
  done
  if [ "$seed" = "--seed" ]; then seed_kanban; fi
  systemctl restart arpagona-api.service
  for _ in $(seq 1 30); do
    sleep 2
    curl -fsS -m 3 http://127.0.0.1:8700/api/health >/dev/null 2>&1 && break
  done
  status_cmd
}

seed_kanban() {  # cartes fictives, une carte « décision » bloquée par utilisateur ; une seule fois
  local entry login name
  for entry in "${AGENTS[@]}"; do
    IFS='|' read -r login name _ _ _ <<<"$entry"
    if as_agent "$login" "$CLI" kanban list --json 2>/dev/null | grep -q "CANARI-KANBAN-${login^^}"; then continue; fi
    as_agent "$login" "$CLI" kanban create --body="Carte fictive de $name (banc)." --json -- \
      "[${login^^}] Relancer le devis fictif CANARI-KANBAN-${login^^}" >/dev/null
    local id
    id="$(as_agent "$login" "$CLI" kanban create --body="Décision fictive attendue de $name." --json -- \
      "[${login^^}] Décision : valider le devis ${login^^}-4417" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
    as_agent "$login" "$CLI" kanban block -- "$id" "Décision attendue de $name : valider le devis ${login^^}-4417 ?" >/dev/null
  done
}

status_cmd() {
  local entry login hport kport gport
  systemctl is-active hindsight-gate.service arpagona-api.service
  for entry in "${AGENTS[@]}"; do
    IFS='|' read -r login _ hport kport gport <<<"$entry"
    printf '%s : agent=%s bridge=%s moteur=%s\n' "$login" \
      "$(systemctl is-active "arpagona-agent@$login.service")" \
      "$(systemctl is-active "arpagona-kanban-bridge@$login.service")" \
      "$(curl -s -o /dev/null -w '%{http_code}' -m 5 "http://127.0.0.1:$hport/v1/health" || true)"
  done
}

case "${1:-}" in
  install) install_cmd "${2:-}" ;;
  status) status_cmd ;;
  acl) acl_cmd ;;
  *) echo "usage : $0 install [--seed] | status | acl" >&2; exit 2 ;;
esac
