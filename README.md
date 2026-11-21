# OfficeFlow

**OfficeFlow** — учебное веб-приложение для бронирования переговорных, построенное вокруг недельного расписания. Отдельный проект, не основанный на MeetingRoomBooking. Язык интерфейса: русский. Стек: Django 5.2 LTS, PostgreSQL, Redis, Django REST Framework, Nginx, Caddy (production TLS), Docker Compose, Prometheus, Grafana.

> **Актуальное состояние на 21.11.2026:** публичный исходный репозиторий `Ramig2007/OfficeFlow`; PR #20 и PR #33–#36 объединены в `main`. Render Free + Neon Free развёрнуты: https://officeflow-x6ay.onrender.com/ . Пользователь подтвердил Render **Live**, успешный вход и создание переговорных. Main CI run #44856385184 после PR #36: Quality + Docker — Success; PR #20 CI run #44843044175 подтвердил 92 pytest passed, coverage 91,67%. В `main` находится ежедневный Neon → Cloudflare R2 backup workflow; R2 bucket/credentials и первая удалённая копия требуют настройки владельцем. Текущая PR #37 добавляет native Telegram receiver и постоянные 5-минутные/5-минутные k6 профили на 100 RPS mixed и 200 RPS authenticated read; окончательные значения будут опубликованы после CI. Для сдачи практики планируется 24–48 часов внешнего UptimeRobot наблюдения; это не подтверждает месячный SLA 99,9%. GHCR package остаётся Private.

## Подтверждённые результаты испытаний — по 21.11.2026

| Проверка | Фактический результат | Ограничение |
|---|---|---|
| Django / pytest | **92 passed** в PR #20 CI run #44843044175 | Покрытие измеряется только для `workspace.services` и `workspace.queries` |
| Покрытие критических модулей | 91,67% в CI (требование ≥70%) | Не равно покрытию всей системы |
| Playwright E2E | **27/27** в CI #117, включая бронирования, VIP, роли, регистрацию, logout, CSV и 375/768 px | Изолированная CI-база, не заменяет независимую ручную приёмку |
| k6, авторизованное чтение | 200 целевых RPS, ~199,2 HTTP RPS, p95 13,19 мс, 0% HTTP-ошибок | GET с одной сессией; не 1000 пользователей |
| k6, создание/изменение/отмена | **3749** полных циклов (11 247 операций записи), 18 745/18 745 checks, p95 **14,47 мс**, 0 HTTP-ошибок и 0 dropped iterations | PR #20 CI run #44843044175; ступень до 20 циклов/с, до 44 активных VU | 
| k6, 1000 пользователей | **1000/1000** независимых авторизаций, пик **1000 VU**, 41 294 HTTP-запроса, 0 HTTP-ошибок, p95 **9,50 мс** | PR #20 CI run #44843044175; тестовый GitHub runner, не Render production |
| k6, mixed read/write | **15 466 HTTP-запросов**, средняя фактическая скорость **85,03 RPS**, p95 **17,82 мс**, 0 HTTP-ошибок, 0 dropped iterations | PR #20 CI run #44843044175; профиль настроен на пик 100 RPS, устойчивые 100 RPS не подтверждены |
| PostgreSQL backup/restore | **INDEPENDENT_RESTORE_OK** в CI #117; новый workflow дополнительно выполняет полный restore Neon dump в отдельный PostgreSQL 17 и remote SHA-256 check перед загрузкой в R2 | Реальный R2 bucket, GitHub secrets и первый успешный workflow run ещё не настроены |
| Prometheus / Alertmanager | Локально 3/3 targets UP и 5 правил проверены; HTTPS webhook renderer есть | Реальный Alertmanager recipient не задан; внешние email-уведомления публичного Render будут настраиваться через UptimeRobot |
| GitHub Actions | PR #20 run #44843044175: Quality, Docker и Scale Validation — Success; main run #44853052929: Quality + Docker — Success | CI подтверждает проверенный код и сценарии runner, но не SLA публичного Render |
| GHCR | `ghcr.io/ramig2007/officeflow:latest` опубликован | Пакет **Private**; публичные исходники можно собрать самостоятельно |

Подробности: [`docs/STATUS.md`](docs/STATUS.md), [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md), [`docs/EXTERNAL_OPERATIONS.md`](docs/EXTERNAL_OPERATIONS.md), [`docs/UPTIME_MONITORING.md`](docs/UPTIME_MONITORING.md).

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

Восстановление требует подтверждения и заменяет содержимое базы. Папка `backups/` добавлена в `.gitignore`; копии нужно хранить отдельно от сервера, шифровать и периодически проверять восстановление. Для фактической Render + Neon базы добавлен ежедневный GitHub Actions workflow `.github/workflows/backup-neon-r2.yml`; для запуска нужны Neon/R2 secrets и приватный Cloudflare R2 bucket. См. `docs/EXTERNAL_OPERATIONS.md`. Дополнительно в Linux/Docker CI #117 проверен `bash scripts/test-restore-independent.sh backups/<имя>.dump`: он поднимает отдельный временный PostgreSQL-контейнер, не изменяет основную базу и требует SHA-256, Docker и OpenSSL. См. `docs/BACKUP_VALIDATION.md`.

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
11. `docs/FINAL_READINESS_2026-11-20.md` — актуальная оценка готовности.
12. `docs/VERIFICATION_2026-11-21.md` — подтверждённые результаты CI #93, 21 E2E, k6 и отказоустойчивости readiness.
13. `docs/SCALE_VALIDATION.md` — методика испытания 1000 независимых сессий и нагрузки на создание/редактирование/отмену.
14. `docs/UPTIME_MONITORING.md` — внешний минутный мониторинг и расчёт доступности 99,9%.
15. `docs/SCALE_RESULTS_2026-11-21.md` — фактические результаты 1000 VU, 3750 полных циклов бронирования, показатели CPU/RAM и журнал CI #106.
16. `docs/RENDER_NEON_DEPLOYMENT.md` — бесплатный Render Free + Neon Free; фактический публичный сервис Live.
17. `docs/EXTERNAL_OPERATIONS.md` — UptimeRobot, внешние уведомления и ежедневные Neon backups в Cloudflare R2.

### Оговорки для защиты

Исходный код опубликован в публичном GitHub-репозитории `Ramig2007/OfficeFlow`; GHCR package остаётся приватным. Публичный Render + Neon сервис подтверждён пользователем как Live. PR #20 CI подтвердил 1000 синтетических сессий, write workload и смешанный профиль; фактическая средняя интенсивность смешанного теста составила 85,03 HTTP RPS при пиковой конфигурации 100 RPS, поэтому не заявляйте устойчивые 100 RPS. Не заявляйте доказанное SLA 99,9% до завершения внешнего 30-дневного измерения. Off-site backup не считается настроенным до первого успешного R2 workflow run.
