#!/usr/bin/env bash
# Create a consistent database backup without exposing credentials in arguments.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
DATABASE_URL="${DATABASE_URL:-sqlite:///./freelanceflow.db}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

case "$DATABASE_URL" in
  postgres://*|postgresql://*)
    command -v pg_dump >/dev/null || { echo "pg_dump is required" >&2; exit 1; }
    export PGPASSWORD="${PGPASSWORD:-}"
    pg_dump "$DATABASE_URL" -Fc -f "$BACKUP_DIR/freelanceflow-$STAMP.dump"
    echo "$BACKUP_DIR/freelanceflow-$STAMP.dump"
    ;;
  sqlite:///*)
    SOURCE="${DATABASE_URL#sqlite://}"
    python3 - "$SOURCE" "$BACKUP_DIR/freelanceflow-$STAMP.db" <<'PY'
import sqlite3, sys
source = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
target = sqlite3.connect(sys.argv[2])
source.backup(target)
target.close()
source.close()
PY
    echo "$BACKUP_DIR/freelanceflow-$STAMP.db"
    ;;
  *)
    echo "Unsupported DATABASE_URL scheme" >&2
    exit 1
    ;;
esac
