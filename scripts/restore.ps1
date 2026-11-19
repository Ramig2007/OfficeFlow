# DANGEROUS: replaces database contents; only for planned recovery.
param([Parameter(Mandatory=$true)][string]$BackupFile)
$ErrorActionPreference = "Stop"
if (-not (Test-Path $BackupFile)) { throw "Файл не найден: $BackupFile" }
$envMap = @{}
Get-Content .env | Where-Object { $_ -match '^DB_(USER|NAME)=' } | ForEach-Object { $k, $v = $_.Split('=',2); $envMap[$k] = $v }
$dbUser = $envMap['DB_USER']; $dbName = $envMap['DB_NAME']
Write-Warning "Восстановление перезапишет базу $dbName. Остановите входящий трафик и сделайте отдельную копию."
$confirmation = Read-Host "Введите RESTORE для подтверждения"
if ($confirmation -cne "RESTORE") { throw "Отменено" }
& docker compose cp $BackupFile "db:/tmp/officeflow-restore.dump"
if ($LASTEXITCODE -ne 0) { throw "Copy failed" }
& docker compose exec -T db pg_restore --clean --if-exists --no-owner -U $dbUser -d $dbName /tmp/officeflow-restore.dump
$exit = $LASTEXITCODE
& docker compose exec -T db rm -f /tmp/officeflow-restore.dump
if ($exit -ne 0) { throw "Restore failed, exit code $exit" }
Write-Host "Восстановление завершено. Перезапустите приложение и проверьте /health/ready/."
