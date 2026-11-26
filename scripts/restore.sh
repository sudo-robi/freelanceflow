#!/usr/bin/env bash
# Restore a FreelanceFlow database backup. Stops/app services must be quiesced first.
# Usage: scripts/restore.sh <backup-file>
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <backup-file>" >&2
  exit 1
fi
BACKUP_FILE="$1"
[ -f "$BACKUP_FILE" ] || { echo "Backup file not found: $BACKUP_FILE" >&2; exit 1; }
DATABASE_URL="${DATABASE_URL:-sqlite:///./freelanceflow.db}"

case "$DATABASE_URL" in
  postgres://*|postgresql://*)
    command -v pg_restore >/dev/null || { echo "pg_restore is required" >&2; exit 1; }
    export PGPASSWORD="${PGPASSWORD:-}"
    pg_restore --clean --if-exists --no-owner --dbname "$DATABASE_URL" "$BACKUP_FILE"
    ;;
  sqlite:///*)
    TARGET="${DATABASE_URL#sqlite:///}"
    python3 - "$BACKUP_FILE" "$TARGET" <<'PY'
import sqlite3, sys
source = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
target = sqlite3.connect(sys.argv[2])
source.backup(target)
target.close()
source.close()
PY
    ;;
  *)
    echo "Unsupported DATABASE_URL scheme" >&2
    exit 1
    ;;
esac

echo "Restore complete. Run the application to apply any pending additive migrations."
