<#
Verifies a PostgreSQL custom-format OfficeFlow backup by restoring into a uniquely
named temporary database in the existing db container. Never restores into the
production database. The temporary DB and uploaded dump are removed on exit.
Run from the project root: .\scripts\test-restore.ps1
Optional: .\scripts\test-restore.ps1 -BackupFile .\backups\officeflow-....dump
#>
param(
    [string]$BackupFile
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath ".\compose.yaml")) {
    throw "Run this script from the OfficeFlow project root (compose.yaml not found)."
}
if (-not (Test-Path -LiteralPath ".\.env")) {
    throw ".env not found."
}
if ([string]::IsNullOrWhiteSpace($BackupFile)) {
    $latest = Get-ChildItem -Path ".\backups" -Filter "officeflow-*.dump" -File -ErrorAction Stop |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($null -eq $latest) {
        throw "No .dump backups found in .\backups. Run .\scripts\backup.ps1 first."
    }
    $BackupFile = $latest.FullName
}
$backup = Get-Item -LiteralPath $BackupFile -ErrorAction Stop
if ($backup.Length -lt 1024) {
    throw "Backup file is suspiciously small ($($backup.Length) bytes)."
}

$envMap = @{}
Get-Content -LiteralPath ".\.env" | ForEach-Object {
    if ($_ -match '^\s*(DB_USER|DB_NAME)\s*=\s*(.*?)\s*$') {
        $envMap[$Matches[1]] = $Matches[2].Trim('"', "'")
    }
}
$dbUser = $envMap['DB_USER']
$productionDb = $envMap['DB_NAME']
if ([string]::IsNullOrWhiteSpace($dbUser) -or [string]::IsNullOrWhiteSpace($productionDb)) {
    throw "DB_USER and DB_NAME must be configured in .env."
}

# New, short, strictly alphanumeric temporary name every run.
$runId = (Get-Date -Format "yyyyMMddHHmmss") + "_" + ([guid]::NewGuid().ToString('N').Substring(0, 8))
$testDb = "officeflow_restore_check_$runId"
$containerDump = "/tmp/officeflow-restore-check-$runId.dump"
if ($testDb -eq $productionDb) {
    throw "Safety check: test database name equals production database name."
}

$created = $false
$copied = $false
try {
    Write-Host "Backup: $($backup.FullName) ($($backup.Length) bytes)"
    Write-Host "Production database (read-only comparison): $productionDb"
    Write-Host "Temporary restore database: $testDb"

    & docker compose exec -T db createdb -U $dbUser -T template0 $testDb
    if ($LASTEXITCODE -ne 0) { throw "Could not create temporary verification database." }
    $created = $true

    & docker compose cp $backup.FullName "db:$containerDump"
    if ($LASTEXITCODE -ne 0) { throw "Could not copy backup into PostgreSQL container." }
    $copied = $true

    # Explicit destination: testDb, NEVER productionDb.
    & docker compose exec -T db pg_restore --exit-on-error --no-owner --no-acl -U $dbUser -d $testDb $containerDump
    if ($LASTEXITCODE -ne 0) { throw "pg_restore failed in temporary database." }

    # Compare counts of critical business tables + migration history.
    $countSql = @'
SELECT 'audit_events', COUNT(*) FROM workspace_auditevent
UNION ALL SELECT 'bookings', COUNT(*) FROM workspace_booking
UNION ALL SELECT 'migrations', COUNT(*) FROM django_migrations
UNION ALL SELECT 'rooms', COUNT(*) FROM workspace_room
UNION ALL SELECT 'users', COUNT(*) FROM workspace_user
ORDER BY 1;
'@
    $originalCounts = @( & docker compose exec -T db psql -X -qAt -F ',' -U $dbUser -d $productionDb -c $countSql )
    if ($LASTEXITCODE -ne 0) { throw "Cannot count records in production database." }
    $restoredCounts = @( & docker compose exec -T db psql -X -qAt -F ',' -U $dbUser -d $testDb -c $countSql )
    if ($LASTEXITCODE -ne 0) { throw "Cannot count records in restored database." }
    $originalSignature = ($originalCounts | ForEach-Object { $_.Trim() } | Where-Object { $_ }) -join "`n"
    $restoredSignature = ($restoredCounts | ForEach-Object { $_.Trim() } | Where-Object { $_ }) -join "`n"
    Write-Host "Original counts:`n$originalSignature"
    Write-Host "Restored counts:`n$restoredSignature"
    if ($originalSignature -cne $restoredSignature) {
        throw "Record counts differ. If the live system was modified during backup/verification, retry during a quiet period."
    }

    # The GiST exclusion guard is essential to prevent double booking.
    $guardSql = "SELECT count(*) FROM pg_constraint WHERE conname = 'booking_room_no_overlap' AND contype = 'x';"
    $guardCount = @( & docker compose exec -T db psql -X -qAt -U $dbUser -d $testDb -c $guardSql )
    if ($LASTEXITCODE -ne 0) { throw "Cannot inspect exclusion constraint in restored database." }
    if (($guardCount -join "").Trim() -ne "1") {
        throw "Missing booking_room_no_overlap PostgreSQL exclusion constraint in restored backup."
    }

    Write-Host "RESTORE_TEST_OK: restored business tables, matching record counts, and booking overlap constraint verified."
}
finally {
    if ($copied) {
        & docker compose exec -T db rm -f $containerDump
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Could not remove temporary dump inside db container: $containerDump"
        }
    }
    if ($created) {
        & docker compose exec -T db dropdb -U $dbUser $testDb
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Could not remove temporary test DB $testDb. Delete it manually after verifying its name."
        }
        else {
            Write-Host "Temporary verification database removed: $testDb"
        }
    }
}
