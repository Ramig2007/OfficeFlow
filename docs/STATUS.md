# OfficeFlow — фактическая сводка готовности на 22.11.2026

**Репозиторий:** https://github.com/Ramig2007/OfficeFlow (публичный)  
**Основная ветка:** `main`  
**PR #37:** объединён в `main` 21.11.2026. Он добавил смешанную нагрузку 100 RPS, read-only acceptance 100 RPS, native Telegram receiver и workflow удалённого backup в Yandex Object Storage.

## Подтверждённые результаты

| Область | Подтверждение | Ограничение |
|---|---|---|
| Quality CI | PR #37 CI run #44942581093: **112 pytest passed**, coverage **91,67%** для `workspace.services` и `workspace.queries`; Ruff, Bandit, Django/OpenAPI/deploy checks прошли | Покрытие относится к двум критическим модулям, не ко всему приложению |
| Docker CI | PR #37 CI run #44942581093: production build, runtime smoke, Chromium **27/27**, multi-session booking write test, independent PostgreSQL restore и DB/Redis recovery — Success | Изолированный CI стенд, не производительность публичного Render |
| 1000 пользователей | 1000/1000 независимых синтетических входов, 41 288 HTTP-запросов, 0 HTTP-ошибок; максимум 1000 VU | Не 1000 одновременных HTTP-запросов; CI runner, не production |
| Create/edit/cancel | 3 749 полных циклов бронирования (3 749 create + 3 749 edit + 3 749 cancel), 0 HTTP-ошибок, 0 dropped iterations | Изолированная тестовая БД |
| Mixed 100 RPS | Целевой профиль 100 RPS; фактически **93,08 RPS** в среднем за окно с ramp-up, p95 **27,36 мс**, p99 **209,02 мс**, 0 ошибок, 0 dropped iterations | Не замер на публичном Render; среднее ниже целевого пика из-за разгона профиля |
| Read-only 100 RPS | **99,93 RPS**, 30 003 HTTP-запроса, p95 **32,36 мс**, p99 **50,16 мс**, 0 ошибок, 0 dropped iterations, 30 001 проверка успешна | Авторизованные HTML-маршруты в CI runner |
| Дополнительный read stress 150 RPS | 109,25 RPS, p95 5,13 с, 11 739 dropped iterations | **FAIL**; это дополнительный стресс-профиль, не выдавать его за успешный |
| Удалённый backup | Workflow run #44948853007 (**run #4**) — Success: Neon dump, полный restore в отдельный PostgreSQL 18, 14 таблиц восстановлены, upload в Yandex Object Storage, remote download и SHA-256 verification прошли | Retention/Lifecycle 30 дней отдельно в консоли Yandex не перепроверен |
| Публичный стенд | Render + Neon: https://officeflow-x6ay.onrender.com/; readiness endpoint ответил `{"status":"ready"}`; ранее пользователь подтвердил вход и создание переговорных | Render Free не является платформой с доказанным SLA |
| Мониторинг | Добавлен GitHub Actions workflow `.github/workflows/uptime-monitor.yml` с внешней HTTPS-проверкой каждые 5 минут; первый run #44950272193: PASS, HTTP 200, `ready`, 209,06 мс | Пока подтверждена одна проба; 24/48-часовое окно ещё не накоплено. Историческая заметка о UptimeRobot Up 14 ч 52 мин не является текущей live-проверкой; месячный SLA 99,9% не доказан |
| Telegram alerts | Native Telegram receiver реализован и конфигурация проходит CI validation | Реальная доставка в Telegram не подтверждена; нужен фактический тест с bot token/chat ID |
| GHCR | Docker image собирается и публикуется в GHCR | Пакет GHCR остаётся Private; публичен исходный код |

## Удалённая резервная копия — детали

- GitHub Actions: [run #44948853007](https://github.com/Ramig2007/OfficeFlow/actions/runs/44948853007).
- Workflow: `.github/workflows/backup-neon-yandex.yml`.
- Bucket: `officeflow-backups-2026`.
- Prefix: `officeflow/daily`.
- Файл: `officeflow-20261121T205358Z.dump` и файл контрольной суммы `.sha256`.
- Полное восстановление проверено в одноразовом PostgreSQL 18 контейнере; восстановлено 14 public tables.
- Дамп и SHA-256 загружены в bucket, затем скачаны обратно; `sha256sum -c` прошёл.
- Правило хранения объектов на 30 дней не считать подтверждённым до проверки Lifecycle в консоли Yandex.

## Что ещё не подтверждено

1. Накопить фактическое 24–48-часовое окно внешнего мониторинга через GitHub Actions; расписание может задерживаться, поэтому считать реальные timestamps и пропуски. Длительный SLA 99,9%: нужны фактические внешние наблюдения за согласованный период; краткий мониторинг не доказывает месячную доступность.
2. Реальная доставка Alertmanager → Telegram: конфигурация готова, но test message не подтверждён.
3. Lifecycle retention 30 дней в Yandex Object Storage: добавлена автоматическая настройка и read-back verification в backup workflow; ждать успешного run #7 перед отметкой PASS.
4. Независимая формальная приёмка и рецензия наставника/одногруппника с датой и подписью.
5. Полный комплект реальных скриншотов интерфейса для Word-отчёта; CI browser screenshots не заменяют скриншоты публичного сайта.
6. Внешний DAST и проверка отказа managed Neon compute/RTO/RPO не выполнены.

## Корректный вывод для отчёта

OfficeFlow реализует основные функции бронирования, VIP-согласования и CSV-отчётности. Подтверждены автоматизированные проверки, браузерный acceptance, синтетические нагрузочные профили 1000 VU, booking write cycles, mixed/read-only 100 RPS, а также первая удалённая резервная копия с восстановлением и проверкой SHA-256. При этом 150 RPS read stress не пройден, показатели CI нельзя переносить на публичный Render, месячный SLA 99,9%, реальная доставка Telegram и формальная независимая приёмка пока не подтверждены. Не называть систему промышленно готовой.


## Дополнение 22.11.2026 — внешняя проверка доступности

Добавлен .github/workflows/uptime-monitor.yml: GitHub-hosted runner проверяет публичный readiness endpoint https://officeflow-x6ay.onrender.com/health/ready/ каждые 5 минут и при push/ручном запуске. Первый run #44950272193 завершился Success; job log зафиксировал 2026-11-21T21:11:56Z, HTTP 200, JSON status ready, latency 209,06 ms. Это первая проба, а не 24-часовой отчёт и не подтверждение SLA. Считать только реальные timestamps и пропущенные интервалы.
