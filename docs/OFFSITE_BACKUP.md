# OfficeFlow — резервное копирование за пределы сервера

## Что добавлено

- `scripts/backup.sh` создаёт custom-format PostgreSQL dump, проверяет читаемость через `pg_restore --list` и сохраняет SHA-256.
- `scripts/backup-offsite.sh` отправляет dump и checksum в отдельный S3 bucket с SSE-S3 (`AES256`) или SSE-KMS, затем скачивает оба объекта и повторно проверяет SHA-256.
- `infra/backup/officeflow-backup.service` и `officeflow-backup.timer` запускают резервное копирование ежедневно в 02:15 UTC с небольшим случайным смещением.

**Важно:** наличие скрипта не означает, что удалённая копия уже существует. Нужны отдельный bucket/account, credentials или IAM role, включённое versioning и проверенная политика хранения.

## Предварительные условия

1. Отдельный S3 bucket в другом аккаунте или хотя бы в отдельном регионе/провайдере от хоста OfficeFlow.
2. Включить bucket versioning и блокировать публичный доступ.
3. Настроить lifecycle policy, например 30 ежедневных, 12 недельных и 12 месячных копий. Сроки согласовать с владельцем данных.
4. Выдать хосту минимальные IAM-права: `s3:PutObject`, `s3:GetObject`, `s3:ListBucket` только для выделенного префикса. Не использовать root credentials.
5. Установить AWS CLI v2 и Docker Compose plugin. Для IAM role предпочтительнее instance profile; если используются статические credentials, хранить их только в защищённом системном окружении и регулярно ротировать.
6. Убедиться, что `/opt/officeflow/.env` доступен Docker Compose, а PostgreSQL сервис называется `db`.

## Ручной запуск

В корне репозитория на сервере:

```bash
sudo install -d -m 0700 /var/backups/officeflow
sudo install -m 0600 /dev/null /etc/officeflow-backup.env
sudoedit /etc/officeflow-backup.env
```

Пример содержимого файла:

```ini
OFFSITE_S3_URI=s3://YOUR_PRIVATE_BUCKET/officeflow
OFFSITE_S3_SSE=AES256
```

Если используется KMS:

```ini
OFFSITE_S3_URI=s3://YOUR_PRIVATE_BUCKET/officeflow
OFFSITE_S3_SSE=aws:kms
OFFSITE_S3_KMS_KEY_ID=arn:aws:kms:REGION:ACCOUNT:key/KEY-ID
```

Для S3-compatible endpoint задайте `AWS_ENDPOINT_URL_S3` в системном окружении. Не добавляйте AWS secret key в Git, чат, systemd unit или командную строку.

Запуск и ожидаемый результат:

```bash
sudo -E env OFFSITE_S3_URI=s3://YOUR_PRIVATE_BUCKET/officeflow \
  bash scripts/backup-offsite.sh
# В конце должно появиться:
# OFFSITE_BACKUP_OK: encrypted S3 object and SHA-256 verification passed.
```

При ручном запуске укажите `BACKUP_DIR`, если хотите хранить локальные копии в другом каталоге. Секреты и endpoint передаются через защищённое окружение.

## Автоматический запуск через systemd

Скопируйте unit-файлы после клонирования проекта:

```bash
sudo install -d -m 0700 /var/backups/officeflow
sudo install -m 0600 /dev/null /etc/officeflow-backup.env
sudoedit /etc/officeflow-backup.env
sudo install -m 0644 infra/backup/officeflow-backup.service /etc/systemd/system/
sudo install -m 0644 infra/backup/officeflow-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now officeflow-backup.timer
systemctl list-timers officeflow-backup.timer
```

Сервис запускается от root, чтобы обращаться к Docker socket, но не предоставляет удалённый доступ к Docker. Убедитесь, что systemd service может читать `/opt/officeflow/.env` и что права на `/etc/officeflow-backup.env` ограничены root. После первого запуска проверьте:

```bash
sudo systemctl start officeflow-backup.service
sudo systemctl status officeflow-backup.service --no-pager
sudo journalctl -u officeflow-backup.service -n 100 --no-pager
aws s3 ls s3://YOUR_PRIVATE_BUCKET/officeflow/
```

## Проверка восстановления

Наличие удалённого объекта и checksum недостаточно. Для DR-проверки скачайте backup на отдельный хост, затем используйте уже проверенный скрипт:

```bash
aws s3 cp s3://YOUR_PRIVATE_BUCKET/officeflow/officeflow-YYYYMMDDTHHMMSSZ.dump /tmp/officeflow.dump
aws s3 cp s3://YOUR_PRIVATE_BUCKET/officeflow/officeflow-YYYYMMDDTHHMMSSZ.dump.sha256 /tmp/officeflow.dump.sha256
cd /tmp
# Имя в checksum-файле должно совпадать с officeflow.dump; при переименовании
# создайте checksum заново после сравнения SHA-256 с исходным файлом.
sha256sum officeflow.dump
```

Затем выполните восстановление в отдельном PostgreSQL контейнере по процедуре `scripts/test-restore-independent.sh` после размещения checksum рядом с файлом и согласования сверки с исходными counts. Не запускайте restore поверх рабочей БД.

## RPO / RTO и ограничения

- Предложенная периодичность — ежедневно; целевой RPO до 24 часов является плановым допущением, а не измеренным результатом.
- RTO не заявляется до отдельного теста восстановления и переключения.
- Успешная загрузка + SHA-256 подтверждает целостность переданного файла, но не физическую независимость, если bucket и сервер находятся в одном аккаунте/регионе.
- Off-site backup не заменяет репликацию и автоматический failover PostgreSQL.
- После фактического запуска сохранить время, размер объекта, URI без секретов, checksum, результат restore и измеренное время восстановления в `docs/PILOT.md`.

