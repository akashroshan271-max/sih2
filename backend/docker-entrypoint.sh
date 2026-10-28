#!/bin/sh
# Prepares upload storage (and optionally the demo schema) before dropping root.
set -eu

UPLOAD_DIR="${LOCAL_STORAGE_DIR:-/data/uploads}"
mkdir -p "$UPLOAD_DIR"
chown -R veriflow:veriflow "$UPLOAD_DIR" 2>/dev/null || true

if [ "${SEED_DEMO_DATA:-0}" = "1" ]; then
    echo "[entrypoint] ensuring schema and demo dataset"
    gosu veriflow python -m app.db.seed
fi

exec gosu veriflow "$@"
