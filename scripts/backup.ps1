# Run from repository root: .\scripts\backup.ps1
# Uses docker compose cp instead of redirecting pg_dump's binary stream through PowerShell.
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path "backups" | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = "backups/officeflow-$stamp.dump"
$envMap = @{}
Get-Content .env | Where-Object { $_ -match '^DB_(USER|NAME)=' } | ForEach-Object { $k, $v = $_.Split('=',2); $envMap[$k] = $v }
$dbUser = $envMap['DB_USER']; $dbName = $envMap['DB_NAME']
if (-not $dbUser -or -not $dbName) { throw "DB_USER / DB_NAME отсутствуют в .env" }
& docker compose exec -T db pg_dump -Fc -f /tmp/officeflow-backup.dump -U $dbUser -d $dbName
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed" }
& docker compose cp "db:/tmp/officeflow-backup.dump" $target
if ($LASTEXITCODE -ne 0) { throw "docker compose cp failed" }
& docker compose exec -T db rm -f /tmp/officeflow-backup.dump
Write-Host "Резервная копия: $target"
