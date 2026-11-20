#!/usr/bin/env bash
# Full restore verification in a temporary PostgreSQL database.
# Usage: bash scripts/test-restore.sh backups/officeflow-YYYYMMDDTHHMMSSZ.dump
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -ne 1 ]]; then
    echo "Usage: bash scripts/test-restore.sh <backup.dump>" >&2
    exit 2
fi

BACKUP_FILE="$1"
if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "Backup file not found: $BACKUP_FILE" >&2
    exit 1
fi
BACKUP_FILE="$(cd -- "$(dirname -- "$BACKUP_FILE")" && pwd)/$(basename -- "$BACKUP_FILE")"
if [[ ! -s "$BACKUP_FILE" ]]; then
    echo "Backup file is empty: $BACKUP_FILE" >&2
    exit 1
fi

if [[ -f "$BACKUP_FILE.sha256" ]]; then
    (cd -- "$(dirname -- "$BACKUP_FILE")" && sha256sum -c "$(basename -- "$BACKUP_FILE").sha256")
fi

STAMP="$(date -u +%Y%m%d%H%M%S)_$$"
TEMP_DB="officeflow_restore_check_$STAMP"
CONTAINER_DUMP="/tmp/$TEMP_DB.dump"
COUNTS_SQL="SELECT 'audit_events', COUNT(*) FROM workspace_auditevent UNION ALL SELECT 'bookings', COUNT(*) FROM workspace_booking UNION ALL SELECT 'migrations', COUNT(*) FROM django_migrations UNION ALL SELECT 'rooms', COUNT(*) FROM workspace_room UNION ALL SELECT 'users', COUNT(*) FROM workspace_user ORDER BY 1;"
CONSTRAINT_SQL="SELECT COUNT(*) FROM pg_constraint WHERE conname = 'booking_room_no_overlap' AND contype = 'x';"

cleanup() {
    docker compose exec -T db sh -c 'dropdb --if-exists -U "$POSTGRES_USER" "$1"' sh "$TEMP_DB" >/dev/null 2>&1 || true
    docker compose exec -T db rm -f "$CONTAINER_DUMP" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Verifying archive format..."
docker compose cp "$BACKUP_FILE" "db:$CONTAINER_DUMP" >/dev/null
docker compose exec -T db pg_restore --list "$CONTAINER_DUMP" >/dev/null

echo "Creating isolated restore database: $TEMP_DB"
docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" "$1"' sh "$TEMP_DB"

echo "Restoring backup into temporary database..."
docker compose exec -T db sh -c \
    'pg_restore --exit-on-error --no-owner --no-acl -U "$POSTGRES_USER" -d "$1" "$2"' \
    sh "$TEMP_DB" "$CONTAINER_DUMP"

echo "Comparing business table counts with the source database..."
source_counts="$(docker compose exec -T db sh -c 'psql -X -qAt -F "|" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"' sh "$COUNTS_SQL")"
restored_counts="$(docker compose exec -T db sh -c 'psql -X -qAt -F "|" -U "$POSTGRES_USER" -d "$1" -c "$2"' sh "$TEMP_DB" "$COUNTS_SQL")"

if [[ "$source_counts" != "$restored_counts" ]]; then
    echo "RESTORE_COUNT_MISMATCH" >&2
    echo "Source:" >&2
    printf '%s\n' "$source_counts" >&2
    echo "Restored:" >&2
    printf '%s\n' "$restored_counts" >&2
    exit 1
fi

constraint_count="$(docker compose exec -T db sh -c 'psql -X -qAt -U "$POSTGRES_USER" -d "$1" -c "$2"' sh "$TEMP_DB" "$CONSTRAINT_SQL")"
if [[ "$constraint_count" != "1" ]]; then
    echo "RESTORE_CONSTRAINT_MISSING: booking_room_no_overlap" >&2
    exit 1
fi

echo "Source counts:"
printf '%s\n' "$source_counts"
echo "RESTORE_TEST_OK: temporary restore, table counts, and booking overlap constraint verified."
echo "The source database was queried read-only; the temporary database will be removed."
