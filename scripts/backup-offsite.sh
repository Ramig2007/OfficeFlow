#!/usr/bin/env bash
# Create a verified PostgreSQL dump and copy it to an independent S3 bucket.
# Requires: running OfficeFlow Compose stack, AWS CLI v2, and an IAM role or
# AWS credentials supplied by the host environment (never commit credentials).
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${OFFSITE_S3_URI:?Set OFFSITE_S3_URI, e.g. s3://private-bucket/officeflow}"
if [[ ! "$OFFSITE_S3_URI" =~ ^s3://[A-Za-z0-9._-]+(/.*)?$ ]]; then
    echo "OFFSITE_S3_URI must be an S3 bucket URI." >&2
    exit 2
fi
command -v aws >/dev/null 2>&1 || {
    echo "AWS CLI v2 is required to upload off-site backups." >&2
    exit 2
}

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
export BACKUP_DIR
mkdir -p "$BACKUP_DIR"
umask 077

# The existing backup script creates a custom-format dump, verifies it with
# pg_restore --list, and writes a SHA-256 checksum.
bash "$ROOT/scripts/backup.sh"

DUMP="$(ls -1t "$BACKUP_DIR"/officeflow-*.dump 2>/dev/null | head -n 1 || true)"
if [[ -z "$DUMP" || ! -s "$DUMP" || ! -s "$DUMP.sha256" ]]; then
    echo "No complete verified dump/checksum pair found in $BACKUP_DIR." >&2
    exit 1
fi

DESTINATION="${OFFSITE_S3_URI%/}/$(basename "$DUMP")"
CHECKSUM_DESTINATION="$DESTINATION.sha256"
SSE="${OFFSITE_S3_SSE:-AES256}"

case "$SSE" in
    AES256)
        SSE_ARGS=(--sse AES256)
        ;;
    aws:kms)
        : "${OFFSITE_S3_KMS_KEY_ID:?Set OFFSITE_S3_KMS_KEY_ID when OFFSITE_S3_SSE=aws:kms}"
        SSE_ARGS=(--sse aws:kms --sse-kms-key-id "$OFFSITE_S3_KMS_KEY_ID")
        ;;
    *)
        echo "OFFSITE_S3_SSE must be AES256 or aws:kms." >&2
        exit 2
        ;;
esac

echo "Uploading verified OfficeFlow backup to independent S3 storage..."
aws s3 cp "$DUMP" "$DESTINATION" --only-show-errors "${SSE_ARGS[@]}"
aws s3 cp "$DUMP.sha256" "$CHECKSUM_DESTINATION" --only-show-errors "${SSE_ARGS[@]}"

# Download both objects and verify the checksum after transfer. This detects
# truncated/corrupted uploads instead of assuming that a successful PUT is enough.
VERIFY_DIR="$(mktemp -d)"
trap 'rm -rf "$VERIFY_DIR"' EXIT
aws s3 cp "$DESTINATION" "$VERIFY_DIR/$(basename "$DUMP")" --only-show-errors
aws s3 cp "$CHECKSUM_DESTINATION" "$VERIFY_DIR/$(basename "$DUMP").sha256" --only-show-errors
(
    cd "$VERIFY_DIR"
    sha256sum -c "$(basename "$DUMP").sha256"
)

echo "OFFSITE_BACKUP_OK: encrypted S3 object and SHA-256 verification passed."
echo "Backup URI: $DESTINATION"
echo "Configure bucket versioning and a lifecycle/retention policy separately."
