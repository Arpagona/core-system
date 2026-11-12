#!/usr/bin/env bash
# Installe le serveur de mémoire Hindsight comme service séparé sur la VM de test (sudo).
# Usage : sudo bash install-hindsight.sh
#
# Pourquoi un service séparé : le démarrage automatique du plugin (« local embarqué ») télécharge
# PyTorch avec CUDA (plus de 9 Go) et tourne dans le service du moteur, dont il sature la mémoire.
# Ici : environnement Python à part, PyTorch CPU, compte dédié, limites propres, boucle locale,
# clé d'accès obligatoire. Rejouable ; ne remplace ni la base ni une clé déjà tirée.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "à lancer en root" >&2; exit 1; }
VERSION="${HINDSIGHT_API_VERSION:-1.2.1}"     # version du serveur attendue par le plugin 1.2.4
PORT="${HINDSIGHT_PORT:-18897}"
HOME_DIR=/srv/hindsight-arpagona
HERMES_HOME=/srv/hermes-arpagona/.hermes
UV="$(ls -d "$HERMES_HOME"/tools/uv-*/uv | sort | tail -1)"

id hindsight-arpagona >/dev/null 2>&1 || useradd --system --home-dir "$HOME_DIR" --create-home --shell /usr/sbin/nologin hindsight-arpagona
install -d -m 750 -o hindsight-arpagona -g hindsight-arpagona "$HOME_DIR"
install -d -m 750 -o root -g hindsight-arpagona /etc/hindsight-arpagona
install -m 755 "$UV" /usr/local/bin/uv-hindsight

# Depuis le dossier du service : uv lit un éventuel uv.toml du dossier courant.
as_hs() { (cd "$HOME_DIR" && sudo -u hindsight-arpagona -H env HOME="$HOME_DIR" UV_CACHE_DIR="$HOME_DIR/.cache/uv" "$@"); }
[ -x "$HOME_DIR/venv/bin/python" ] || as_hs /usr/local/bin/uv-hindsight venv --python 3.13 "$HOME_DIR/venv"
as_hs /usr/local/bin/uv-hindsight pip install --python "$HOME_DIR/venv/bin/python" --torch-backend cpu "hindsight-api==$VERSION"
as_hs /usr/local/bin/uv-hindsight cache clean >/dev/null 2>&1 || true

ENVF=/etc/hindsight-arpagona/api.env
if [ ! -s "$ENVF" ]; then
  umask 027
  {
    echo "HOME=$HOME_DIR"
    echo "TOKENIZERS_PARALLELISM=false"
    echo "HINDSIGHT_API_LLM_PROVIDER=${HINDSIGHT_LLM_PROVIDER:-opencode-go}"
    echo "HINDSIGHT_API_LLM_MODEL=${HINDSIGHT_LLM_MODEL:-deepseek-v4.1-flash}"
    echo "HINDSIGHT_API_LLM_BASE_URL=${HINDSIGHT_LLM_BASE_URL:-https://opencode.ai/zen/go/v1}"
    echo "HINDSIGHT_API_LLM_API_KEY=$(grep ^OPENCODE_GO_API_KEY= "$HERMES_HOME/.env" | cut -d= -f2-)"
    echo "HINDSIGHT_API_LLM_TIMEOUT=240"
    echo "HINDSIGHT_API_LLM_MAX_CONCURRENT=1"
    echo "HINDSIGHT_API_TENANT_EXTENSION=hindsight_api.extensions.builtin.tenant:ApiKeyTenantExtension"
    echo "HINDSIGHT_API_TENANT_API_KEY=$(openssl rand -hex 32)"
  } > "$ENVF"
  umask 022
fi
chown root:hindsight-arpagona "$ENVF"; chmod 640 "$ENVF"

cat > /etc/systemd/system/hindsight-arpagona.service <<UNIT
[Unit]
Description=Hindsight (memoire en graphe) - instance de test ARPAGONA, boucle locale
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
User=hindsight-arpagona
Group=hindsight-arpagona
EnvironmentFile=$ENVF
UnsetEnvironment=PYTHONPATH PYTHONHOME
ExecStart=$HOME_DIR/venv/bin/hindsight-api --host 127.0.0.1 --port $PORT
Restart=on-failure
RestartSec=10
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$HOME_DIR
InaccessiblePaths=/etc/agentcore /var/lib/agentcore /var/backups/agentcore /srv/hermes-arpagona /etc/arpagona-api /var/lib/arpagona-api
MemoryMax=3G
CPUQuota=200%
TasksMax=512

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now hindsight-arpagona.service
systemctl restart hindsight-arpagona.service
for _ in $(seq 1 90); do
  sleep 5
  curl -fsS -m 3 "http://127.0.0.1:$PORT/version" >/dev/null 2>&1 && break
  systemctl is-active -q hindsight-arpagona.service || true
done
systemctl is-active hindsight-arpagona.service
curl -fsS -m 5 "http://127.0.0.1:$PORT/version" | cut -c1-80; echo

# --- Branchement du moteur : plugin du catalogue officiel, en mode « serveur externe » ---------
BANK="${HINDSIGHT_BANK:-arpagona-banc}"     # une banque par instance, donc par client
hermes_do() { sudo -u hermes-arpagona -H bash -lc "export PATH=\$HOME/.local/bin:\$PATH; $1"; }
[ -d "$HERMES_HOME/plugins/hindsight" ] || hermes_do "hermes plugins install hindsight --yes-deps --no-enable </dev/null" >/dev/null
install -d -m 700 -o hermes-arpagona -g hermes-arpagona "$HERMES_HOME/hindsight"
# recall_sync : le rappel précède la réponse ; sans lui il n'arrive qu'au tour suivant.
# memory_mode context : rappel et rétention automatiques, aucun outil de mémoire donné à l'agent.
cat > "$HERMES_HOME/hindsight/config.json" <<JSON
{
  "mode": "local_external",
  "api_url": "http://127.0.0.1:$PORT",
  "bank_id": "$BANK",
  "memory_mode": "context",
  "auto_retain": true,
  "auto_recall": true,
  "recall_sync": true,
  "recall_budget": "mid",
  "recall_types": ["observation", "world", "experience"],
  "recall_max_tokens": 8000,
  "recall_max_input_chars": 4000
}
JSON
chown hermes-arpagona:hermes-arpagona "$HERMES_HOME/hindsight/config.json"; chmod 600 "$HERMES_HOME/hindsight/config.json"
sed -i -E '/^HINDSIGHT_(LLM_API_KEY|API_KEY)=/d' "$HERMES_HOME/.env"
printf 'HINDSIGHT_API_KEY=%s\n' "$(grep ^HINDSIGHT_API_TENANT_API_KEY= "$ENVF" | cut -d= -f2)" >> "$HERMES_HOME/.env"
chown hermes-arpagona:hermes-arpagona "$HERMES_HOME/.env"; chmod 600 "$HERMES_HOME/.env"
hermes_do "hermes config set memory.provider hindsight" >/dev/null
systemctl restart hermes-arpagona-gateway.service
for _ in $(seq 1 20); do sleep 2; curl -fsS -m 2 http://127.0.0.1:8642/v1/health >/dev/null 2>&1 && break; done
hermes_do "hermes memory status" | grep -i -E "Provider|Status"
