#!/usr/bin/env bash
# Verify a PostgreSQL backup in an INDEPENDENT, disposable Postgres container.
# Usage: bash scripts/test-restore-independent.sh backups/officeflow-*.dump
# No ports are published, no production volumes are mounted, and the source is read-only.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -ne 1 ]]; then
    echo "Usage: bash scripts/test-restore-independent.sh <backup.dump>" >&2
    exit 2
fi

BACKUP_FILE="$1"
if [[ ! -s "$BACKUP_FILE" ]]; then
    echo "Backup file missing or empty: $BACKUP_FILE" >&2
    exit 1
fi
BACKUP_FILE="$(cd -- "$(dirname -- "$BACKUP_FILE")" && pwd)/$(basename -- "$BACKUP_FILE")"

if [[ ! -f "$BACKUP_FILE.sha256" ]]; then
    echo "Missing checksum: $BACKUP_FILE.sha256" >&2
    exit 1
fi
(
    cd -- "$(dirname -- "$BACKUP_FILE")"
    sha256sum -c "$(basename -- "$BACKUP_FILE").sha256"
)

if ! command -v openssl >/dev/null 2>&1; then
    echo "openssl is required to generate an ephemeral restore password." >&2
    exit 1
fi

DR_CONTAINER="officeflow-dr-$$_${RANDOM}"
DR_USER="officeflow_dr"
DR_DB="officeflow_dr"
DR_PASSWORD="$(openssl rand -hex 32)"
COUNTS_SQL="SELECT 'audit_events', COUNT(*) FROM workspace_auditevent UNION ALL SELECT 'bookings', COUNT(*) FROM workspace_booking UNION ALL SELECT 'migrations', COUNT(*) FROM django_migrations UNION ALL SELECT 'rooms', COUNT(*) FROM workspace_room UNION ALL SELECT 'users', COUNT(*) FROM workspace_user ORDER BY 1;"
CONSTRAINT_SQL="SELECT COUNT(*) FROM pg_constraint WHERE conname='booking_room_no_overlap' AND contype='x';"

cleanup() {
    docker rm -f "$DR_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Starting separate temporary PostgreSQL 16 container: no network access, ports or persistent volumes."
docker run -d --rm \
    --network none \
    --name "$DR_CONTAINER" \
    -e POSTGRES_USER="$DR_USER" \
    -e POSTGRES_DB="$DR_DB" \
    -e POSTGRES_PASSWORD="$DR_PASSWORD" \
    postgres:16-alpine >/dev/null

ready=0
for attempt in $(seq 1 60); do
    if docker exec "$DR_CONTAINER" pg_isready -U "$DR_USER" -d "$DR_DB" >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 1
done
if [[ "$ready" -ne 1 ]]; then
    echo "Independent PostgreSQL container did not become ready." >&2
    exit 1
fi

docker cp "$BACKUP_FILE" "$DR_CONTAINER:/tmp/officeflow-dr.dump" >/dev/null
docker exec "$DR_CONTAINER" pg_restore --list /tmp/officeflow-dr.dump >/dev/null
docker exec "$DR_CONTAINER" sh -c \
    'pg_restore --exit-on-error --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB" /tmp/officeflow-dr.dump'

echo "Checking restored application tables and PostgreSQL exclusion constraint..."
restored_counts="$(docker exec "$DR_CONTAINER" sh -c \
    'psql -X -qAt -F "|" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"' sh "$COUNTS_SQL")"
source_counts="$(docker compose exec -T db sh -c \
    'psql -X -qAt -F "|" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"' sh "$COUNTS_SQL")"

if [[ "$source_counts" != "$restored_counts" ]]; then
    echo "INDEPENDENT_RESTORE_COUNT_MISMATCH" >&2
    echo "Source counts: $source_counts" >&2
    echo "Restored counts: $restored_counts" >&2
    exit 1
fi

constraint_count="$(docker exec "$DR_CONTAINER" sh -c \
    'psql -X -qAt -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"' sh "$CONSTRAINT_SQL")"
if [[ "$constraint_count" != "1" ]]; then
    echo "INDEPENDENT_RESTORE_CONSTRAINT_MISSING" >&2
    exit 1
fi

printf '%s\n' "$restored_counts"
echo "INDEPENDENT_RESTORE_OK: checksum, separate container, schema, table counts, and overlap constraint verified."
echo "The source database was read-only; the disposable restore container will be destroyed."
