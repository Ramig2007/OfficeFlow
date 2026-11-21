# OfficeFlow — фактическая сводка готовности на 22.11.2026

**Репозиторий:** https://github.com/Ramig2007/OfficeFlow (публичный)  
**Основная ветка:** `main`  
**Публичный стенд:** https://officeflow-x6ay.onrender.com/

## Подтверждённые результаты

| Область | Подтверждение | Ограничение |
|---|---|---|
| Quality CI | Main CI #235 — Success: Ruff, Bandit, static audit, Django/production checks, migrations, OpenAPI, test suite и coverage | Coverage относится к критическим модулям, не ко всему приложению |
| Docker CI | Main CI #235 — Success: production image, runtime smoke, Chromium browser E2E, multi-session booking write test, independent PostgreSQL restore, DB/Redis recovery | Изолированный Docker runner, не production Render |
| 1000 пользователей | Main Scale Validation #3: 1000/1000 независимых логинов, max 1000 VU, 41 302 HTTP requests, 0 HTTP errors, 100% checks; p95 6,15 мс | 1000 одновременных авторизованных VU, но не 1000 одновременных HTTP-запросов; CI runner |
| Create/edit/cancel | 3750 полных циклов (3750 create + 3750 edit + 3750 cancel), 11 350 HTTP requests, 18 750/18 750 checks, p95 9,73 мс, 0 errors, 0 dropped iterations | Изолированная тестовая БД |
| Mixed workload | 33 689 requests, 93,06 RPS average over full window including ramp-up, p95 12,46 мс, p99 18,77 мс, 0 errors, 0 dropped iterations; 2340 booking cycles | Среднее ниже целевого пика 100 RPS из-за ramp-up/ramp-down; CI runner |
| Authenticated read 100 RPS | 30 003 requests, 99,96 RPS average, p95 12,06 мс, p99 14,93 мс, 30 001/30 001 checks, 0 errors, 0 dropped iterations | Авторизованные страницы в CI runner |
| Дополнительный read stress 150 RPS | 109,25 RPS, p95 5,13 с, 11 739 dropped iterations | **FAIL**; этот предел нельзя скрывать |
| Удалённый backup | Workflow #13 — Success: Neon dump, restore в PostgreSQL 18 (14 public tables), Yandex upload/download, SHA-256 и Lifecycle read-back 30 дней | Фактическое удаление объектов выполняет Yandex Lifecycle по расписанию |
| Grafana / Prometheus | Main CI #235: officeflow/postgres/redis targets — UP; пять DB/Redis metrics доступны; Grafana provisioned dashboard загрузился с 9 панелями | Локальный Docker Compose observability profile, не Render Free |
| Публичный стенд | Render + Neon readiness endpoint отвечает `ready`; ранее пользователь подтвердил вход и создание переговорных | Render Free не является платформой с доказанным SLA |
| UptimeRobot | HTTP(s) monitor “OfficeFlow Production” на readiness endpoint, интервал 5 минут. Последний сохранённый снимок 21.11.2026 18:04:56 UTC: Up, возраст 14 ч 52 мин, 99,931% за отображаемые 24 часа, один инцидент 37 секунд | Исторический снимок, не текущий live-статус; актуальное 24–48-часовое окно нужно подтвердить новым снимком. Email contact есть, Test Notification не подтверждён |
| GitHub Actions uptime probe | Workflow настроен на cron каждые 5 минут; push-triggered run #44950272193 прошёл HTTP 200 / ready | В истории Actions при последней проверке не найдено schedule-triggered запусков; не считать cron доказанным непрерывным мониторингом |
| Telegram alerts | Native Alertmanager Telegram receiver и одноразовый workflow готовы | Secrets `ALERTMANAGER_TELEGRAM_BOT_TOKEN` и `ALERTMANAGER_TELEGRAM_CHAT_ID` не заданы; фактическое сообщение не отправлялось |
| GHCR | Docker image собирается и публикуется в GHCR | Пакет GHCR остаётся Private; публичен исходный код |

## Ссылки на доказательства

- [Main CI #235 — Success](https://github.com/Ramig2007/OfficeFlow/actions/runs/44953159041)
- [Main Scale Validation #3 — Success](https://github.com/Ramig2007/OfficeFlow/actions/runs/44951299898)
- [Off-site backup #13 — Success](https://github.com/Ramig2007/OfficeFlow/actions/runs/44951659002)
- [Observability CI #230 — Success](https://github.com/Ramig2007/OfficeFlow/actions/runs/44952583321)
- [Uptime probe first confirmed run](https://github.com/Ramig2007/OfficeFlow/actions/runs/44950272193)

## Удалённая резервная копия

- Workflow: `.github/workflows/backup-neon-yandex.yml`.
- Bucket: `officeflow-backups-2026`.
- Prefix: `officeflow/daily/`.
- Последний подтверждённый файл: `officeflow-20261121T212755Z.dump` и SHA-256.
- Полное восстановление проверено в одноразовом PostgreSQL 18; восстановлено 14 public tables.
- Дамп и checksum загружены в bucket, затем скачаны обратно; `sha256sum -c` прошёл.
- Lifecycle rule `officeflow-backups-retention-30-days` прочитан обратно: current objects expire after 30 days, incomplete multipart uploads abort after 7 days; существовавшее стороннее правило сохранено.

## Что ещё нужно закрыть

1. **Telegram:** добавить два GitHub Actions repository secrets, затем вручную запустить Actions → OfficeFlow Telegram Delivery Check и подтвердить получение сообщения. Не присылать bot token в чат.
2. **Внешний мониторинг:** открыть UptimeRobot и сохранить актуальный снимок после полного 24–48-часового окна. Проверить email через Test Notification. Последний сохранённый снимок был 14 ч 52 мин, 99,931% за отображаемые 24 часа и инцидент 37 секунд.
3. **Формальная приёмка:** получить независимую подпись/рецензию наставника или заказчика.
4. **Скриншоты для отчёта:** сделать реальные скриншоты публичного сайта; CI browser screenshots показывают тестовый Docker стенд и не заменяют их.
5. **Безопасность и восстановление:** внешний DAST, managed Neon failover, RTO/RPO не подтверждены.

## Ограничения, которые нельзя скрывать

- 150 RPS read-only stress не прошёл: около 109 RPS, p95 5,13 с и 11 739 dropped iterations.
- Нагрузочные показатели получены на одноразовом GitHub Actions Docker runner, а не на публичном Render Free.
- Grafana/Prometheus работают в локальном или собственном Docker Compose observability profile; Grafana не размещена на Render Free.
- Render production намеренно не публикует `/metrics` наружу.
- Telegram receiver пока не проверен фактическим сообщением.
- Короткое 24–48-часовое наблюдение не доказывает месячный или годовой SLA 99,9%.

## Корректный вывод

Основные функции OfficeFlow, автоматизированная регрессия, браузерные сценарии, нагрузочные профили до 1000 одновременных VU, цикл бронирования, смешанная нагрузка около 93 RPS, authenticated read около 100 RPS, удалённый backup/restore и 30-дневное Lifecycle retention подтверждены результатами GitHub Actions. При этом 150 RPS read stress не пройден, показатели CI нельзя переносить на публичный Render, текущий 24–48-часовой отчёт UptimeRobot, Test Notification, реальная доставка Telegram, независимая приёмка, внешний DAST и Neon failover/RTO/RPO ещё не подтверждены. Не называть систему промышленно готовой.
