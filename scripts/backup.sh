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
    SOURCE="${DATABASE_URL#sqlite:///}"
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

BACKUP_PATH="$BACKUP_DIR/freelanceflow-$STAMP."$(case "$DATABASE_URL" in postgres://*|postgresql://*) echo dump ;; *) echo db ;; esac)
if [ -f "$BACKUP_PATH" ]; then
  sha256sum "$BACKUP_PATH" > "$BACKUP_PATH.sha256"
fi
RETENTION="${BACKUP_RETENTION:-7}"
mapfile -t OLD < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'freelanceflow-*' ! -name '*.sha256' -printf '%T@ %p\n' | sort -rn | tail -n +$((RETENTION + 1)) | cut -d' ' -f2-)
for file in "${OLD[@]}"; do
  rm -f "$file" "$file.sha256"
done
