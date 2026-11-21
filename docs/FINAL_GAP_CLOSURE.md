# OfficeFlow — актуальный план закрытия оставшихся требований

**Актуализация:** 21 ноября 2026 г.  
**Основная ветка:** main; PR #20 и PR #33–#35 объединены.  
**Текущая PR-ветка:** scale-validation/final-ops-2026-11-21.  
**Публичный сервис:** https://officeflow-x6ay.onrender.com/ (Render Free + Neon Free). Пользователь подтвердил Live, вход и создание переговорных.

Документ отделяет подтверждённые результаты от действий, которые требуют внешних аккаунтов, секретов, независимого проверяющего или времени наблюдения.

## Подтверждено в репозитории и CI

| Область | Результат | Ограничение |
|---|---|---|
| Quality CI | PR #20 run #44843044175 — Success; **92 pytest passed**, coverage **91,67%** | Coverage относится к workspace.services и workspace.queries, не ко всему приложению |
| Docker / browser | Chromium **27/27**, runtime smoke, independent PostgreSQL restore и PostgreSQL/Redis recovery в CI #117 | Временная CI-среда, не публичный Render |
| 1000 сессий | **1000/1000** успешных логинов, 41 294 HTTP-запроса, p95 **9,50 мс**, 0 HTTP-ошибок, пик 1000 VU | GitHub-hosted runner; не 1000 одновременных HTTP-запросов и не production |
| Write workload | **3749** завершённых create/edit/cancel циклов, 11 247 операций записи, p95 **14,47 мс**, 0 ошибок и 0 dropped iterations | Пик около 60 write HTTP RPS в изолированной CI-БД |
| Mixed workload | 15 466 HTTP-запросов за 3 минуты, средняя фактическая скорость **85,03 RPS**, p95 **17,82 мс**, 0 ошибок, 0 dropped iterations | Профиль был настроен на пик 100 RPS; устойчивые 100 RPS не подтверждены |
| Render + Neon | Пользователь подтвердил публичный Render service **Live**, вход и создание комнат | Полный внешний smoke всех сценариев ещё не оформлен; Render Free не даёт SLA |
| Prometheus / Grafana | Локальные 3/3 targets UP, пять alert rules; Grafana dashboard | Локальный observability stack не развёрнут на Render |
| Backup / restore | Independent PostgreSQL restore подтверждён CI #117 | Off-site backup в R2 ещё не запущен |

Источники CI: [PR #20 run #44843044175](https://github.com/Ramig2007/OfficeFlow/actions/runs/44843044175), [PR #18 run #44829732693](https://github.com/Ramig2007/OfficeFlow/actions/runs/44829732693), [последний main run #44853052929](https://github.com/Ramig2007/OfficeFlow/actions/runs/44853052929).

## Что добавлено в текущей PR-ветке

| Изменение | Файл | Текущий статус |
|---|---|---|
| Ежедневный Neon off-site backup | .github/workflows/backup-neon-r2.yml в `main` | Workflow готов к запуску; нужны GitHub secrets/variables и приватный R2 bucket |
| Уведомления Alertmanager | `scripts/render_alertmanager_config.py`, `compose.yaml` | В текущей PR добавляется native Telegram receiver, CI validation и инструкция реальной доставки |
| Инструкция внешних операций | docs/EXTERNAL_OPERATIONS.md | Подготовлены шаги UptimeRobot, Telegram Alertmanager, Cloudflare R2 и GitHub Secrets |
| Обновление статуса проекта | README.md, docs/STATUS.md, docs/REQUIREMENTS.md, docs/PILOT.md | Синхронизируются с Live deploy и PR #20 evidence |
| Документация Render/Neon | docs/RENDER_NEON_DEPLOYMENT.md | Фиксируется фактический Live URL и текущая конфигурация |
| Мониторинг доступности | docs/UPTIME_MONITORING.md | Добавляется UptimeRobot как простой независимый внешний вариант |

### Как устроен Neon → Cloudflare R2 workflow

1. По расписанию ежедневно в 02:15 UTC или вручную запускается GitHub Actions.
2. pg_dump получает custom-format dump из Neon direct connection.
3. pg_restore --list проверяет архив.
4. Полный restore выполняется в отдельный временный PostgreSQL 17 container.
5. Dump и SHA-256 загружаются в приватный R2 bucket.
6. Workflow скачивает оба объекта обратно и проверяет checksum.
7. Успешный run должен показать RESTORE_TEST_OK и OFFSITE_BACKUP_OK.

Workflow безопасно пропускает работу, если secrets/variables не заданы; такой пропуск **не считается backup success**. После создания bucket нужно настроить Lifecycle retention, например 30 дней, и выполнить первый ручной запуск.

## Внешние действия владельца проекта

| Приоритет | Задача | Что сделать | Доказательство закрытия |
|---|---|---|---|
| P1 | Cloudflare R2 | Создать private bucket и S3 token Object Read & Write только для bucket | Bucket создан, доступ ограничен |
| P1 | GitHub backup secrets | Добавить NEON_CONNECTION_STRING, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY как Secrets; R2_ACCOUNT_ID, R2_BUCKET как Variables | Ручной workflow run завершился с RESTORE_TEST_OK и OFFSITE_BACKUP_OK |
| P1 | UptimeRobot | Создать HTTP(s) monitor для https://officeflow-x6ay.onrender.com/health/ready/ с 5-минутным интервалом и подтвердить email Alert Contact | Monitor Up; дата начала измерения зафиксирована |
| P1 | Alertmanager recipient | Выбрать совместимый HTTPS webhook и задать URL/token в локальном секретном .env | Test alert фактически доставлен |
| P1 | 30-дневное измерение | Не прерывать внешний мониторинг минимум 30 дней | Свежий отчёт за 30 дней с uptime, инцидентами и оценкой простоя |
| P1 | Word-отчёт | Сделать реальные скриншоты публичного интерфейса и обновить отчёт | Рисунки и ссылки в тексте совпадают |
| P1 | Независимая приёмка | Попросить наставника/одногруппника пройти сценарии | Дата, роль, результаты и подпись/согласование, если требуется |
| P2 | PostgreSQL HA | Выделенная репликация и failover drill | Измеренные RTO/RPO и успешное переключение |

## Что нельзя заявлять до получения доказательств

- SLA 99,9% — пока нет полного свежего 30-дневного внешнего измерения. Для 30 дней бюджет простоя при 99,9% составляет **43 минуты 12 секунд**.
- Off-site backup — пока нет первого успешного workflow run и объекта в отдельном R2 bucket.
- Внешние уведомления Alertmanager — пока не получено реальное сообщение от test alert.
- Устойчивые 100 HTTP RPS — mixed CI profile был настроен на пик 100 RPS, но фактическая средняя скорость составила 85,03 RPS.
- Производительность на 1000 реальных пользователей — 1000 VU были синтетическими и тестировались на GitHub runner.
- Автоматический PostgreSQL HA/failover — одна Neon база без отдельной реплики не доказывает HA.

## Рекомендуемый порядок завершения

1. Объединить текущую PR-ветку после успешного CI.
2. Создать R2 bucket и добавить GitHub Actions secrets/variables.
3. Запустить backup workflow вручную и проверить оба маркера успеха.
4. Создать UptimeRobot monitor и зафиксировать дату начала.
5. Выбрать канал для Alertmanager и проверить test alert.
6. Через 30 дней сохранить uptime report, затем обновить Word-отчёт и завершить формальную приёмку.

**Итог:** OfficeFlow уже развёрнут публично и подтверждён пользователем как работающий учебный стенд. Внешний backup, внешние уведомления и длительный SLA не считаются завершёнными до настройки внешних сервисов и получения фактических результатов.
