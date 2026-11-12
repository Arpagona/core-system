#!/usr/bin/env bash
# Installe Hermès Agent officiel, épinglé, sur la VM de test (à lancer avec sudo).
# N'écrit aucun secret : la clé du modèle est fournie par un fichier existant sur la VM.
set -euo pipefail

HERMES_COMMIT="${HERMES_COMMIT:-3b421578588243f920886e6fe79a6faa87ea026e}"   # tag v0.23.1
SERVICE_USER="hermes-arpagona"
SERVICE_HOME="/srv/hermes-arpagona"
MODEL_KEY_FILE="${MODEL_KEY_FILE:?chemin du fichier contenant la clé opencode-go}"
UNIT_SRC="$(dirname "$(readlink -f "$0")")/hermes-arpagona-gateway.service"

[ "$(id -u)" -eq 0 ] || { echo "à lancer en root" >&2; exit 1; }
[ -r "$MODEL_KEY_FILE" ] || { echo "clé illisible : $MODEL_KEY_FILE" >&2; exit 1; }

id "$SERVICE_USER" >/dev/null 2>&1 || useradd --system --create-home --home-dir "$SERVICE_HOME" \
    --shell /bin/bash --user-group "$SERVICE_USER"
chmod 750 "$SERVICE_HOME"

sudo -u "$SERVICE_USER" -H bash -c "
  set -euo pipefail; cd ~
  curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/$HERMES_COMMIT/scripts/install.sh -o install-$HERMES_COMMIT.sh
  bash install-$HERMES_COMMIT.sh --commit $HERMES_COMMIT --skip-setup --skip-browser --skip-computer-use
  export PATH=\$HOME/.local/bin:\$PATH
  [ -f ~/.hermes/config.yaml.orig-install ] || cp -p ~/.hermes/config.yaml ~/.hermes/config.yaml.orig-install
  hermes config set model.default deepseek-v4.1-flash >/dev/null
  hermes config set model.provider opencode-go >/dev/null
"

ENV_FILE="$SERVICE_HOME/.hermes/.env"
umask 077
API_KEY="$(grep -m1 '^API_SERVER_KEY=' "$ENV_FILE" | cut -d= -f2- || true)"
[ -n "$API_KEY" ] || API_KEY="$(openssl rand -hex 32)"
sed -i -E '/^(OPENCODE_GO_API_KEY|API_SERVER_ENABLED|API_SERVER_KEY|API_SERVER_HOST|API_SERVER_PORT)=/d' "$ENV_FILE"
{
  printf 'OPENCODE_GO_API_KEY=%s\n' "$(tr -d '\n\r' < "$MODEL_KEY_FILE")"
  printf 'API_SERVER_ENABLED=true\nAPI_SERVER_HOST=127.0.0.1\nAPI_SERVER_PORT=8642\n'
  printf 'API_SERVER_KEY=%s\n' "$API_KEY"
} >> "$ENV_FILE"
chown "$SERVICE_USER:$SERVICE_USER" "$ENV_FILE"; chmod 600 "$ENV_FILE"

install -m 644 "$UNIT_SRC" /etc/systemd/system/hermes-arpagona-gateway.service
systemctl daemon-reload
systemctl enable --now hermes-arpagona-gateway.service
sleep 12
systemctl is-active hermes-arpagona-gateway.service
curl -fsS -m 5 http://127.0.0.1:8642/v1/health; echo
sudo -u "$SERVICE_USER" git -C "$SERVICE_HOME/.hermes/hermes-agent" rev-parse HEAD
