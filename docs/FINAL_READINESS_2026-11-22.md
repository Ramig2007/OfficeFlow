# OfficeFlow — итоговая техническая готовность на 22.11.2026

## Подтверждено

- **Main CI #235 — Success:** quality checks, Django/production checks, migrations, OpenAPI, Bandit, production image build, app smoke, browser E2E, multi-session booking write test, independent PostgreSQL restore, DB/Redis recovery и observability validation.
  - https://github.com/Ramig2007/OfficeFlow/actions/runs/44953159041
- **Main Scale Validation #3 — Success:** 1000/1000 логинов и max 1000 VU; 3750 booking create/edit/cancel cycles; mixed 93,06 RPS average; authenticated read 99,96 RPS; 0 HTTP errors и 0 dropped iterations.
  - https://github.com/Ramig2007/OfficeFlow/actions/runs/44951299898
- **Observability:** Prometheus targets officeflow/postgres/redis — UP; пять метрик PostgreSQL/Redis доступны; Grafana provisioned dashboard загрузился с 9 панелями.
  - https://github.com/Ramig2007/OfficeFlow/actions/runs/44953159041
- **Remote backup #13 — Success:** Neon dump, disposable PostgreSQL 18 restore (14 public tables), Yandex upload/download, SHA-256 и Lifecycle read-back 30 дней.
  - https://github.com/Ramig2007/OfficeFlow/actions/runs/44951659002
- **Grafana:** dashboard хранится в `infra/grafana/dashboards/officeflow.json` и запускается локальным Docker Compose observability profile.
- **Public site:** Render + Neon readiness endpoint отвечает `ready`; пользователь ранее подтвердил вход и создание переговорных.
- **External monitoring:** UptimeRobot monitor “OfficeFlow Production” создан на HTTP(s) readiness endpoint с интервалом 5 минут. Последний сохранённый снимок 21.11.2026 18:04:56 UTC: Up, 14 ч 52 мин, 99,931% за отображаемые 24 часа, один инцидент 37 секунд, response 165 мс. Это исторический снимок, не текущий live-статус.

## Что остаётся открытым

1. **Telegram delivery:** receiver и workflow проверки готовы, но repository secrets `ALERTMANAGER_TELEGRAM_BOT_TOKEN` и `ALERTMANAGER_TELEGRAM_CHAT_ID` не заданы. Первый test workflow безопасно пропустил отправку. Добавить их в GitHub → Settings → Secrets and variables → Actions, затем запустить OfficeFlow Telegram Delivery Check. Bot token не присылать в чат.
2. **Длительное наблюдение:** получить актуальный скриншот UptimeRobot после полного 24–48-часового окна. Последний сохранённый снимок был только 14 ч 52 мин. Email contact создан, но Test Notification не подтверждён. GitHub Actions cron настроен; push-triggered run #44950272193 и первый scheduled run #44954099116 прошли, но длительное 24–48-часовое окно ещё не подтверждено.
3. **Формальная приёмка:** нужна независимая подпись/рецензия наставника или заказчика.
4. **Отчёт:** нужны реальные скриншоты публичного сайта; CI screenshots показывают тестовый Docker стенд и не заменяют скриншоты публичного сайта.
5. **Безопасность и восстановление:** внешний DAST, managed Neon failover, RTO/RPO не подтверждены.

## Ограничения, которые нельзя скрывать

- 150 RPS read-only stress в предыдущем тесте не прошёл: около 109,25 RPS, p95 около 5,13 s и 11 739 dropped iterations.
- CI-нагрузка выполнялась на одноразовом GitHub Actions Docker runner, а не на публичном Render Free; её нельзя выдавать за capacity публичного хостинга.
- 1000 VU — это 1000 одновременных авторизованных сессий, не 1000 одновременных HTTP-запросов.
- Mixed профиль дал 93,06 RPS average over full window including ramp-up/ramp-down, не ровно 100 RPS каждую секунду.
- Grafana/Prometheus dashboard работает в локальном или собственном Docker Compose observability profile; Grafana не размещена на Render Free.
- Render production намеренно не публикует `/metrics` наружу.
- Telegram receiver пока не проверен фактическим сообщением.
- Короткое 24–48-часовое наблюдение не доказывает месячный/годовой SLA 99,9%.

## Технические точки входа

- Backup: `.github/workflows/backup-neon-yandex.yml`
- Uptime probe: `.github/workflows/uptime-monitor.yml`
- Telegram test: `.github/workflows/telegram-delivery-check.yml`
- Scale validation: `.github/workflows/scale-validation.yml`
- Grafana dashboard: `infra/grafana/dashboards/officeflow.json`
- Operations guide: `docs/EXTERNAL_OPERATIONS.md`
- Requirements matrix: `docs/REQUIREMENTS.md`
- VS Code setup: `docs/VS_CODE_SETUP.md`
