#!/usr/bin/env bash
# Run from any directory: bash scripts/backup.sh
# Requires Docker Compose and a running OfficeFlow PostgreSQL service.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$BACKUP_DIR/officeflow-$STAMP.dump"
TEMP="$TARGET.tmp"
VERIFY_PATH="/tmp/officeflow-verify-$STAMP.dump"

umask 077
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

cleanup() {
    rm -f "$TEMP"
    docker compose exec -T db rm -f "$VERIFY_PATH" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Creating PostgreSQL custom-format backup..."
docker compose exec -T db sh -c \
    'pg_dump --format=custom --no-owner --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' \
    > "$TEMP"

test -s "$TEMP" || { echo "Backup is empty" >&2; exit 1; }
mv "$TEMP" "$TARGET"

echo "Verifying PostgreSQL archive..."
docker compose cp "$TARGET" "db:$VERIFY_PATH" >/dev/null
docker compose exec -T db pg_restore --list "$VERIFY_PATH" >/dev/null
(cd "$BACKUP_DIR" && sha256sum "$(basename -- "$TARGET")" > "$(basename -- "$TARGET").sha256")

echo "Backup created and verified: $TARGET"
cat "$TARGET.sha256"
echo "Copy this backup and checksum to encrypted off-host storage."
