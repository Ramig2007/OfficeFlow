# OfficeFlow — план закрытия оставшихся требований

**Актуализация:** 21 ноября 2026 г.  
**Ветка текущих изменений:** `scale-validation/final-gap-closure`  
**Цель:** закрыть все пункты, которые можно достоверно завершить в репозитории, и отдельно зафиксировать внешние действия, требующие аккаунтов, секретов, публичного URL, независимого проверяющего или времени наблюдения.

## Что добавлено в текущей ветке

| Изменение | Файлы | Что доказывает | Статус |
|---|---|---|---|
| Смешанный нагрузочный профиль | `scripts/loadtest-mixed-100-rps.js` | Параллельные сценарии: 79 read GET/с + 7 booking lifecycle/с × 3 writes = 100 HTTP RPS; пороги p95<200 мс, errors<0,1%, dropped=0. Более тяжёлый профиль 75% writes провалил CI #136/#137, результаты не скрываются | Встроено в существующий scale CI; результат текущего PR ещё ожидает запуска |
| Unit tests Alertmanager | `workspace/tests/test_alertmanager_config.py` | HTTPS-only webhook, Bearer token, null receiver, reject malformed/insecure URLs | Добавлено; ожидает CI |
| Off-site backup | `scripts/backup-offsite.sh` | Backup + SHA-256, upload в S3 с SSE-S3/SSE-KMS, скачивание и повторная проверка checksum | Код добавлен; реальный bucket/IAM не настроен |
| Расписание off-site backup | `infra/backup/officeflow-backup.service`, `officeflow-backup.timer` | Ежедневный systemd запуск | Unit-файлы добавлены; не активированы на сервере |
| Backup tests | `workspace/tests/test_offsite_backup.py` | Mock-S3 upload/download, checksum, обязательные переменные и encryption mode | Добавлено; ожидает CI |
| Документы эксплуатации | `docs/OFFSITE_BACKUP.md`, `docs/OPERATIONS.md` | Установка, IAM, systemd, восстановление, RPO/RTO оговорки | Подготовлено |
| Приёмочные документы | `REQUIREMENTS.md`, `PILOT.md`, `DEFECT_LOG_2026-11-19.md`, `STATUS.md` | Единая evidence-based матрица и приоритеты | Обновлено; итоговый статус после CI следует синхронизировать |

## Что можно считать закрытым после успешного CI

1. Новый mixed 100 HTTP RPS k6 профиль проходит thresholds.
2. Unit tests Alertmanager webhook renderer проходят.
3. Mocked S3 backup tests проходят.
4. Shell/Python тесты входят в обычный pytest gate.
5. Все существующие quality/docker проверки остаются зелёными.

Если mixed profile не проходит p95/error thresholds, он не отмечается как выполненный: нужно исследовать k6 artifact, оптимизировать приложение и повторить.

## Что нельзя закрыть без внешнего действия

| Приоритет | Задача | Что требуется от владельца проекта | Доказательство закрытия |
|---|---|---|---|
| P1 | Render + Neon deploy | Доступ к Render и Neon; создать отдельную Neon DB; добавить четыре `NEON_*` значения и сохранить `RENDER_SECRET_KEY` в Render Environment | Render service Live, миграции успешны, публичный HTTPS URL |
| P1 | HTTPS smoke | После deploy предоставить публичный URL для проверки | Health 200, CSS, login, booking, conflict, VIP, roles, CSV |
| P1 | Alertmanager notifications | Выбрать совместимый HTTPS webhook endpoint и добавить URL/token только на сервере | Test alert фактически доставлен получателю |
| P1 | Off-site backup | Создать private S3 bucket в отдельном аккаунте/регионе, IAM role и lifecycle policy | `OFFSITE_BACKUP_OK`, checksum совпал, restore на отдельном хосте |
| P1 | SLA 99,9% | Запустить независимую probe-службу после появления публичного URL | Полные свежие 30-дневные пробы и отчёт PASS; до этого SLA не подтверждён |
| P1 | Независимая приёмка | Попросить одногруппника/наставника пройти чек-лист | ФИО/роль, дата, результаты, подпись/согласование при необходимости |
| P1 | Скриншоты и Word | Открыть работающий сайт, сделать реальные скриншоты девяти экранов и вставить в подготовленный отчёт | Рисунки пронумерованы, ссылки в тексте совпадают |
| P2 | PostgreSQL HA | Выбрать managed DB HA tier или primary/standby на инфраструктуре с отдельными узлами | Репликация, failover drill, измеренные RTO/RPO |
| P2 | GHCR visibility | При необходимости открыть GHCR package через GitHub Packages settings; исходный репозиторий уже публичный | Преподаватель может pull image без приглашения; иначе сборка из source остаётся допустимой альтернативой |

## Почему некоторые требования не закрываются сейчас

- SLA 99,9% — это измерение на полном интервале, а не настройка в Prometheus. Для 30 дней допустимый простой составляет 43 минуты 12 секунд.
- Off-site backup нельзя доказать mock-S3 тестом: нужен отдельный bucket и restore на независимой машине.
- Alertmanager не может доставить сообщения без реального endpoint/получателя.
- Репликация/failover требуют отдельной инфраструктуры; один PostgreSQL контейнер не является HA.
- Независимая приёмка должна быть проведена реальным человеком; автотесты не заменяют подпись наставника.

## Рекомендуемый порядок финализации

1. Получить успешный PR CI по текущей ветке.
2. Объединить изменения в `main` после проверки.
3. Развернуть Render + Neon и пройти HTTPS smoke.
4. Подключить webhook и S3 bucket, провести первые реальные проверки.
5. Запустить 30-дневный внешний uptime monitor.
6. Получить независимую приёмку, вставить скриншоты, завершить Word-отчёт.

**Честный критерий:** OfficeFlow можно называть готовым к учебной демонстрации после зелёного CI и успешного внешнего smoke. Промышленную доступность 99,9%, HA и off-site DR можно заявлять только после фактических внешних испытаний.
