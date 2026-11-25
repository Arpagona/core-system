#!/bin/sh
set -eu
ROOT=/home/thibaud/projects/gona-mission-control/new-command
HERMES=/home/thibaud/.openclaw/workspace/hermes-agent
# All scratch, imports and caches stay outside the source tree and live profile.
mkdir -p "$ROOT/.test-runtime/home" "$ROOT/.test-runtime/tmp"
export HOME="$ROOT/.test-runtime/home"
export HERMES_HOME="$ROOT/.test-runtime/home"
export TMPDIR="$ROOT/.test-runtime/tmp"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT:$HERMES"
export HERMES_ENABLE_PROJECT_PLUGINS=0
# Hermes' pre-import bootstrap calls venv_sync.prepare_launch, which may rebuild or
# re-exec the runtime (and download tools) before pytest is importable. This is the
# documented Hermes switch for that lazy install step; the venv is already complete.
export HERMES_DISABLE_LAZY_INSTALLS=1
cd "$ROOT"
exec "$HERMES/venv/bin/python" -m pytest -q -p no:cacheprovider test_new_command.py "$@"
