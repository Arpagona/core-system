#!/usr/bin/env bash
# Construit une archive de version : binaire, empreinte, version, exemple de configuration, dossier de démo.
set -euo pipefail
cd "$(dirname "$0")/.."
test -z "$(git status --porcelain --untracked-files=no)" || { echo "arbre modifié : committer d'abord" >&2; exit 1; }
COMMIT=$(git rev-parse --short=12 HEAD)
VERSION="0.1.0-$COMMIT"
AGENTCORE_COMMIT="$COMMIT" cargo build --release --locked -p agentcore
OUT="dist/agentcore-$VERSION"
rm -rf "$OUT" && mkdir -p "$OUT"
cp target/release/agentcore deploy/config.example.toml deploy/install.sh deploy/rollback.sh deploy/recette.sh "$OUT/"
cp -r demo/dossier-synthetique "$OUT/demo"
cp -r web "$OUT/web" && rm -rf "$OUT/web/__pycache__"
printf 'version=%s\ncommit=%s\nbuilt=%s\n' "$VERSION" "$(git rev-parse HEAD)" "$(date -u +%FT%TZ)" > "$OUT/VERSION"
(cd "$OUT" && sha256sum agentcore > SHA256SUMS)
tar -C dist -czf "$OUT.tar.gz" "agentcore-$VERSION"
sha256sum "$OUT.tar.gz"
