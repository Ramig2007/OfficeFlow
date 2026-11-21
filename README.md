# OfficeFlow

**OfficeFlow** — учебное веб-приложение для бронирования переговорных, построенное вокруг недельного расписания. Отдельный проект, не основанный на MeetingRoomBooking. Язык интерфейса: русский. Стек: Django 5.2 LTS, PostgreSQL, Redis, Django REST Framework, Nginx, Caddy (production TLS), Docker Compose, Prometheus, Grafana.

> **Текущее состояние на 22.11.2026:** исходный репозиторий публичен, основная ветка `main`. Публичный стенд Render + Neon: https://officeflow-x6ay.onrender.com/ .
>
> - Main CI **#235 — Success**: quality checks, production image, runtime smoke, Chromium E2E, многопользовательская запись, независимый PostgreSQL restore, DB/Redis recovery и observability validation.
> - Main Scale Validation **#3 — Success**: 1000/1000 авторизаций и максимум 1000 VU; 3750 циклов create/edit/cancel; mixed 93,06 RPS average; authenticated read 99,96 RPS; 0 HTTP errors и 0 dropped iterations.
> - Off-site backup **#13 — Success**: полный restore 14 таблиц в PostgreSQL 18, Yandex Object Storage upload/download, SHA-256 и Lifecycle retention 30 дней.
> - Grafana Dashboard содержит 9 панелей; CI подтвердил 3/3 Prometheus targets и пять дополнительных метрик PostgreSQL/Redis. Dashboard запускается локальным Docker Compose observability-профилем, не на Render Free.
> - UptimeRobot monitor “OfficeFlow Production” настроен на HTTP(s) readiness endpoint с интервалом 5 минут. Последний сохранённый скриншот (21.11.2026 18:04:56 UTC): Up, возраст монитора 14 ч 52 мин, 99,931% за отображаемые 24 часа и один инцидент 37 секунд. Это исторический снимок, не текущая проверка; для отчёта нужно зафиксировать актуальное 24–48-часовое окно. Email contact создан, но Test Notification не подтверждён.
> - Реальная доставка Telegram пока не подтверждена: нужны GitHub Actions secrets `ALERTMANAGER_TELEGRAM_BOT_TOKEN` и `ALERTMANAGER_TELEGRAM_CHAT_ID`.
>
> **Ограничения:** все нагрузочные цифры получены на изолированном GitHub Actions runner, а не на Render Free. Дополнительный read-only стресс 150 RPS не прошёл (109,25 RPS, p95 5,13 с, 11 739 dropped iterations). Месячный SLA 99,9%, внешний DAST, Neon failover/RTO/RPO и независимая формальная приёмка не подтверждены.
>
> Подробности: [фактический статус](docs/STATUS.md), [матрица требований](docs/REQUIREMENTS.md), [нагрузочные результаты](docs/SCALE_RESULTS_2026-11-21.md), [резервное копирование](docs/BACKUP_VALIDATION.md), [внешний мониторинг](docs/UPTIME_MONITORING.md), [итоговая готовность](docs/FINAL_READINESS_2026-11-22.md), [инструкция VS Code для Windows](docs/VS_CODE_SETUP.md).

## Возможности

- Панель управления с показателями встреч и занятости.
- Недельное расписание переговорных и переход к созданию брони.
- Фильтр комнат по вместимости и VIP; карточка переговорной.
- Бронирование на **1–4 часа**, редактирование, отмена, история.
- Серверная проверка временных окон, ролей и пересечений.
- Защита от двойного бронирования через PostgreSQL GiST exclusion constraint.
- VIP-заявки удерживают слот до одобрения/отклонения администратором.
- CRUD переговорных (удаление = деактивация), назначение ролей.
- Отчётность и защищённый от CSV formula injection экспорт.
- REST API и OpenAPI/Swagger, аудит действий; общий API расписания выдаёт только необходимые календарю поля.
- Docker, CI, нагрузочные сценарии, Grafana/Prometheus, healthcheck.

## Быстрый старт на Windows / PowerShell

Все команды ниже выполняются **в PowerShell, в корневой папке OfficeFlow**, где лежит `compose.yaml`.

1. Установите Docker Desktop (запущен движок Docker), Git, VS Code.
2. Создайте файл окружения из шаблона:

```powershell
Copy-Item .env.example .env
```

3. Откройте `.env` в редакторе и обязательно замените `SECRET_KEY`, `DB_PASSWORD`, `DEMO_PASSWORD` на уникальные случайные значения; используйте тестовый `DEBUG=1` только локально.

```powershell
code .env
```

4. Проверьте, что Docker доступен, и соберите сервисы:

```powershell
docker compose version
docker compose up -d --build
```

**Ожидаемый результат:** контейнеры `db`, `redis`, `app`, `proxy` получают состояние `running` / `healthy`. Первая сборка скачивает зависимости и занимает некоторое время. Контейнер приложения ожидает готовность PostgreSQL и Redis.

5. Примените миграции:

```powershell
docker compose exec app python manage.py migrate
```

**Ожидаемый результат:** `Applying workspace.0001_initial... OK`, `Applying workspace.0002_postgres_overlap_guard... OK`. Сборка статических файлов выполняется entrypoint приложения при каждом запуске контейнера, поэтому Nginx получает актуальный `staticfiles` volume.

6. Создайте демонстрационные комнаты и тестовые аккаунты **только при DEBUG=1**:

```powershell
docker compose exec app python manage.py seed_demo
```

Логины: `manager` (администратор), `employee` (сотрудник); пароль — ваше значение `DEMO_PASSWORD` из `.env`. Никогда не используйте демоданные в настоящем рабочем окружении.

7. Откройте **http://localhost:8080** — должен появиться экран входа. После авторизации — панель управления. API: **http://localhost:8080/api/docs/**. Проверка живости: **http://localhost:8080/health/live/**, готовность: **http://localhost:8080/health/ready/**.

8. При необходимости создайте настоящего суперпользователя:

```powershell
docker compose exec app python manage.py createsuperuser
```

9. Проверьте состояние и логи:

```powershell
docker compose ps
docker compose logs --tail=100 app
```

10. Для остановки **без удаления данных**:

```powershell
docker compose down
```

Не используйте `docker compose down -v`, если хотите сохранить бронирования: `-v` удаляет volumes базы и Redis.

### Распространённые ошибки

| Проблема | Что проверить |
|---|---|
| `DB_PASSWORD` не задан | `.env` создан и значение непустое |
| Порт 8080 занят | Измените в `compose.yaml` `127.0.0.1:8080:80` на, например, `127.0.0.1:8088:80` |
| Ошибка `relation ... does not exist` | Выполните `python manage.py migrate` в контейнере приложения |
| `Invalid HTTP_HOST header` | В `ALLOWED_HOSTS` включён используемый адрес |
| `CSRF verification failed` | В `CSRF_TRUSTED_ORIGINS` добавлен точный адрес с протоколом |
| `503 /health/ready/` | Проверить `docker compose ps`, логи БД и Redis |
| Ошибка миграции `btree_gist` | PostgreSQL должен разрешать `CREATE EXTENSION btree_gist`; используйте официальный образ БД |
| Ошибка входа в демоаккаунт | `.env` `DEMO_PASSWORD` использовался **до** первого `seed_demo`; смените пароль через админку либо Django shell |
| Нет оформления | Entrypoint автоматически запускает `collectstatic`; проверить `docker compose logs app`, volume `staticfiles` и логи Nginx |

## Бесплатный хостинг Render + Neon (как в MeetingRoomBooking)

Для публикации OfficeFlow **без VPS и платного домена** подготовлены `render.yaml`,
`Dockerfile.render`, `officeflow/settings_render.py` и автоматическое создание
первого администратора. Render Free запускает Gunicorn и отдаёт HTTPS по
`*.onrender.com`, Neon Free хранит отдельную PostgreSQL-базу. Redis, Nginx
и Caddy в этом варианте не требуются; локальный Docker Compose не затронут.

**Пошаговая инструкция:** [docs/RENDER_NEON_DEPLOYMENT.md](docs/RENDER_NEON_DEPLOYMENT.md).
Runtime-секрет Neon хранится в Render Environment. Для отдельного backup workflow direct connection string дополнительно хранится только в GitHub Actions Secret NEON_CONNECTION_STRING; не помещайте секреты в отслеживаемые файлы, issue, PR или чат.
Фактический сервис создан: https://officeflow-x6ay.onrender.com/ . Пользователь подтвердил Live, успешный вход и создание переговорных; полный внешний smoke всех сценариев и длительная доступность фиксируются отдельно.
На Render Free сервис может засыпать после 15 минут простоя,
поэтому этот вариант **не подтверждает SLA 99,9%** и не наследует
показатели теста 1000 VU на CI runner.

## Подготовка к VPS-хостингу

Production-конфигурация для альтернативного VPS-варианта находится в основной ветке: `compose.production.yaml`, шаблон переменных — `.env.production.example`, подробная инструкция — [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). **Текущий публичный стенд уже работает на Render Free + Neon Free**; VPS-инструкция нужна только если позднее решим перенести сервис на собственный сервер.

Локальный Compose публикует Nginx только на `127.0.0.1:8080`. Для VPS используйте оба файла Compose и Caddy; не открывайте внутренние порты приложения, PostgreSQL, Redis и мониторинга.

## Разработка без Docker (только быстрый UI smoke-test)

Установите Python 3.12, откройте PowerShell в корне проекта:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:DEBUG = "1"
$env:SECRET_KEY = "local-dev-only"
python manage.py migrate
python manage.py runserver
```

Без `DB_HOST` используется локальная SQLite. **На SQLite нельзя подтвердить защиту от конкурентного двойного бронирования** — соответствующий PostgreSQL exclusion constraint включается только в PostgreSQL. Для сдачи используйте Docker/PostgreSQL.

## Тесты, линтеры, нагрузка

```powershell
# В Docker при мигрированной базе (нужны dev-зависимости; удобнее локальная .venv):
pip install -r requirements-dev.txt
$env:DEBUG = "1"
python -m pytest workspace/tests -q --cov=workspace.services --cov=workspace.queries --cov-report=term-missing --cov-fail-under=70
ruff check .
python manage.py check
```

При запуске тестов с PostgreSQL задайте `DB_HOST`, `DB_USER`, `DB_NAME`, `DB_PASSWORD` и `REDIS_URL` для тестового окружения. В CI они настроены в GitHub Actions. **Не запускайте тесты на рабочей БД с реальными данными.**

Нагрузочный скрипт `scripts/loadtest.js` использует k6 и задаёт 100 RPS по умолчанию только к `/health/live/`; это **не** полноценная проверка реальной логики бронирования. Например:

```powershell
k6 run -e BASE_URL=http://localhost:8080 -e TARGET_RPS=100 -e DURATION=2m .\scripts\loadtest.js
k6 run -e BASE_URL=http://localhost:8080 -e TARGET_RPS=200 -e DURATION=2m .\scripts\loadtest.js
```

Сценарий авторизованного чтения реализован в `scripts/loadtest-auth-read.js`. Также успешно проведены два расширенных теста на одноразовом CI-стенде: `scripts/loadtest-1000-users.js` и `scripts/loadtest-booking-create-edit-cancel.js`. Фактические результаты, профили и ограничения приведены в `docs/SCALE_RESULTS_2026-11-21.md`. **Проведение тестов из этих файлов на рабочей БД запрещено.**

## Мониторинг

```powershell
docker compose --profile observability up -d --build
```

- Grafana: http://localhost:3000 (логин `GRAFANA_USER`, пароль `GRAFANA_PASSWORD`; задайте их в `.env`).
- Prometheus: http://localhost:9090
- Alertmanager: http://localhost:9093
- Метрики приложения доступны **только внутри Docker** по `app:8000/metrics`, внешний Nginx блокирует `/metrics`.
- В локальном Alertmanager приёмник по умолчанию `null-receiver`; для публичного Render внешние уведомления о доступности настраиваются через независимый UptimeRobot. Инструкция: `docs/EXTERNAL_OPERATIONS.md`.

## Резервное копирование

```powershell
.\scripts\backup.ps1
# ОПАСНО: только после чтения docs/OPERATIONS.md
.\scripts\restore.ps1 -BackupFile .\backups\officeflow-YYYYMMDD-HHmmss.dump
```

Восстановление требует подтверждения и заменяет содержимое базы. Папка `backups/` добавлена в `.gitignore`; копии нужно хранить отдельно от сервера, шифровать и периодически проверять восстановление. Для фактической Render + Neon базы добавлен ежедневный GitHub Actions workflow `.github/workflows/backup-neon-yandex.yml`; для запуска нужны Neon/Yandex secrets и приватный Yandex Object Storage bucket. См. `docs/EXTERNAL_OPERATIONS.md`. Дополнительно в Linux/Docker CI #117 проверен `bash scripts/test-restore-independent.sh backups/<имя>.dump`: он поднимает отдельный временный PostgreSQL-контейнер, не изменяет основную базу и требует SHA-256, Docker и OpenSSL. См. `docs/BACKUP_VALIDATION.md`.

## Структура

```text
officeflow/                 настройки проекта и маршруты
workspace/                  бизнес-модели, сервисы, API, формы, представления
workspace/migrations/       схема PostgreSQL, исключение пересечений
workspace/tests/            unit + integration + permission + concurrency tests
e2e/                        браузерный сценарий Playwright
templates/                  страницы и авторизация
static/                     оригинальная светлая дизайн-система
infra/                      Nginx, Caddy, Prometheus, Grafana, Alertmanager
scripts/                    PowerShell и Linux backup/restore, k6
.github/workflows/          CI и публикация Docker image в GHCR
docs/                       матрица ИСП49, архитектура, эксплуатация, риски
```

## Документация практики

1. `docs/REQUIREMENTS.md` — матрица требований всех восьми разделов ИСП49.
2. `docs/ARCHITECTURE.md` — C4/ER, модель ролей, статусы, API.
3. `docs/CAPACITY.md` — предварительная оценка инфраструктуры под 1000 пользователей / 100 RPS.
4. `docs/CHANGE_ANALYSIS.md` — влияние VIP-подтверждения и CSV.
5. `docs/TESTING.md` — стратегия тестирования, сценарии E2E, регрессия.
6. `docs/OPERATIONS.md` — установка, мониторинг, восстановление, безопасность.
7. `docs/PILOT.md` — шаблон опытной эксплуатации и дефектов.
8. `docs/PROJECT_PLAN.md` — план работ, трудозатраты и критерии готовности.
9. `docs/RISKS.md` — реестр рисков.
10. `docs/DEPLOYMENT.md` — инструкция VPS/HTTPS.
11. `docs/FINAL_READINESS_2026-11-22.md` — актуальная оценка готовности.
12. `docs/VERIFICATION_2026-11-21.md` — подтверждённые результаты CI #93, 21 E2E, k6 и отказоустойчивости readiness.
13. `docs/SCALE_VALIDATION.md` — методика испытания 1000 независимых сессий и нагрузки на создание/редактирование/отмену.
14. `docs/UPTIME_MONITORING.md` — внешний минутный мониторинг и расчёт доступности 99,9%.
15. `docs/SCALE_RESULTS_2026-11-21.md` — фактические результаты 1000 VU, 3750 полных циклов бронирования, показатели CPU/RAM и журнал CI #106.
16. `docs/RENDER_NEON_DEPLOYMENT.md` — бесплатный Render Free + Neon Free; фактический публичный сервис Live.
17. `docs/EXTERNAL_OPERATIONS.md` — UptimeRobot, внешние уведомления и ежедневные Neon backups в Yandex Object Storage.
18. `docs/VS_CODE_SETUP.md` — перенос актуального `main` в VS Code на Windows и запуск через Docker Compose.

### Оговорки для защиты

Исходный код опубликован в публичном GitHub-репозитории `Ramig2007/OfficeFlow`; GHCR package остаётся приватным. Публичный Render + Neon сервис ранее подтверждён пользователем как Live. Нагрузочные показатели k6 подтверждаются только результатами CI и не переносятся на публичный Render. UptimeRobot monitor настроен на 5-минутный интервал; последний сохранённый снимок показывал 14 ч 52 мин наблюдения, но для отчёта нужен актуальный снимок после полного 24–48-часового окна. Email Test Notification и реальная доставка Telegram ещё не подтверждены. Off-site backup, полный restore и Lifecycle retention 30 дней уже прошли workflow #13.
