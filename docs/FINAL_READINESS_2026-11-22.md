# OfficeFlow — итоговая техническая готовность на 22.11.2026

## Подтверждено

- **CI #230 — Success:** quality checks, Django/production checks, migrations, OpenAPI, Bandit, production image build, app smoke, browser E2E, multi-session booking write test, PostgreSQL backup/restore, DB/Redis recovery и observability validation.
  - https://github.com/Ramig2007/OfficeFlow/actions/runs/44952583321
- **Observability:** Prometheus targets officeflow/postgres/redis — UP; пять метрик PostgreSQL/Redis доступны; Grafana provisioned dashboard загрузился с 9 панелями.
- **Remote backup #13 — Success:** Neon dump, disposable PostgreSQL 18 restore (14 public tables), Yandex upload/download, SHA-256 и Lifecycle read-back.
  - https://github.com/Ramig2007/OfficeFlow/actions/runs/44951659002
- **Grafana:** dashboard хранится в infra/grafana/dashboards/officeflow.json и запускается локальным Docker Compose observability profile.
- **External uptime probe:** первый внешний запрос к публичному readiness endpoint прошёл HTTP 200, JSON status=ready, latency 209,06 ms.
  - https://github.com/Ramig2007/OfficeFlow/actions/runs/44950272193
- **Load:** предыдущий успешный PR #37 прогон подтвердил 1000/1000 независимых логинов и максимум 1000 одновременных VU; mixed/read-only 100 RPS профили имели 0 HTTP errors. Повторный main run #3 запущен и на момент фиксации ещё выполняется.
  - https://github.com/Ramig2007/OfficeFlow/actions/runs/44951299898

## Что остаётся открытым

1. **Telegram delivery:** receiver и workflow проверки готовы, но repository secrets ALERTMANAGER_TELEGRAM_BOT_TOKEN и ALERTMANAGER_TELEGRAM_CHAT_ID не заданы. Первый test workflow безопасно пропустил отправку. Добавить их в GitHub → Settings → Secrets and variables → Actions, затем запустить OfficeFlow Telegram Delivery Check.
2. **Длительное наблюдение:** GitHub Actions probe настроен на каждые 5 минут, но одна проба не доказывает 24–48 часов наблюдения и тем более месячный SLA 99,9%.
3. **Формальная приёмка:** нужна независимая подпись/рецензия наставника или заказчика.
4. **Отчёт:** нужны реальные скриншоты публичного сайта; CI screenshots показывают тестовый Docker стенд и не заменяют публичные скриншоты.
5. **Безопасность и восстановление:** внешний DAST, managed Neon failover, RTO/RPO не подтверждены.

## Ограничения, которые нельзя скрывать

- 150 RPS read-only stress в предыдущем тесте не прошёл: около 109 RPS, p95 около 5,13 s и dropped iterations.
- CI-нагрузка выполнялась на одноразовом GitHub Actions Docker runner, а не на публичном Render Free; её нельзя выдавать за capacity публичного хостинга.
- Grafana/Prometheus dashboard работает в локальном или собственном Docker Compose observability profile; Grafana не размещена на Render Free.
- Render production намеренно не публикует /metrics наружу.
- Telegram receiver пока не проверен фактическим сообщением.

## Технические точки входа

- Backup: .github/workflows/backup-neon-yandex.yml
- Uptime probe: .github/workflows/uptime-monitor.yml
- Telegram test: .github/workflows/telegram-delivery-check.yml
- Scale validation: .github/workflows/scale-validation.yml
- Grafana dashboard: infra/grafana/dashboards/officeflow.json
- Operations guide: docs/EXTERNAL_OPERATIONS.md
- Requirements matrix: docs/REQUIREMENTS.md
