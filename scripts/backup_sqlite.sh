#!/usr/bin/env bash
# Daily SQLite backup + audit_log encrypted backup.
# Cron: 04:00 HKT every day.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="$ROOT/data/briefalpha.db"
DEST="$ROOT/data/backups/$(date +%Y%m%d)"

if [[ ! -f "$DB" ]]; then
  echo "[backup] no db yet at $DB" >&2
  exit 0
fi

mkdir -p "$DEST"
chmod 700 "$DEST"
sqlite3 "$DB" ".backup '$DEST/briefalpha.db'"
chmod 600 "$DEST/briefalpha.db"

# Encrypt the audit_log dump separately so it can be off-loaded to cold storage.
sqlite3 "$DB" ".dump audit_log" | \
  openssl enc -aes-256-cbc -salt -pbkdf2 -in - -out "$DEST/audit_log.enc" \
  -pass file:"$ROOT/data/.secrets/alias_key"

echo "[backup] wrote $DEST"
