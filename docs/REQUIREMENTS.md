# Матрица обязательных требований ИСП49

**Источник:** преподавательский кейс «Онлайн-сервис бронирования переговорных комнат в офисе», разделы 1–8. Статусы разделяют реализацию, фактические проверки и незакрытые пункты. «Проверено» означает только описанный в документах сценарий и среду; это не подтверждение SLA или промышленной готовности.

## Бизнес-требования и сквозные критерии

| ID | Требование | Реализация/доказательство | Статус |
|---|---|---|---|
| BR-01 | Список комнат | `rooms`, `/api/v1/rooms/`; каталог прошёл ручную и browser smoke проверку | Проверено в локальном сценарии |
| BR-02 | Занятость по часам | недельный `schedule`, `/api/v1/schedule/`; страница расписания проверена в Playwright | Проверено в smoke-сценарии |
| BR-03 | Бронирование 1–4 часа | `services._validate_time`, форма, API; ручное создание и тесты диапазона времени | Проверено в заявленном сценарии |
| BR-04 | Изменение и отмена | `services.update_booking/cancel_booking`, интерфейс/API; Chromium 27/27 и 3750 полных циклов create/edit/cancel | Проверено в PR CI #117 и #106; ручное редактирование отдельно не зафиксировано |
| BR-05 | Админ CRUD комнат и права | `/control/rooms/`, `/control/users/`, API; Chromium create/edit/deactivate, назначение и отзыв ролей | Автоматически проверено в PR CI #117 (27/27); ручная приёмка отдельно |
| BR-06 | Авторизация и история | Django auth, `/my-bookings/`; вход и история проверены в пользовательском/E2E прогоне | Проверено в smoke-сценарии |
| BR-07 | Конфликт двойной брони | блокировка строки Room, PG GiST constraint и concurrency test в PostgreSQL CI | Проверено в PostgreSQL CI; отдельный write-load PR #17 успешно завершён без конфликтов на раздельных слотах |
| BR-08 | Базовая отчётность | `/reports/`, `/api/v1/reports/summary/`; CSV-экспорт проверен пользователем | CSV подтверждён; полная отчётность проверяется отдельно |
| NFR-01 | Доступность ≥99,9% | UptimeRobot HTTP(s) monitor “OfficeFlow Production” на публичном readiness endpoint, интервал 5 минут. Последний сохранённый снимок 21.11.2026 18:04:56 UTC: Up, 14 ч 52 мин, 99,931% за отображаемые 24 часа, один инцидент 37 секунд; GitHub Actions push probe #44950272193 и scheduled probe #44954099116 прошли | Нужен актуальный снимок после полного 24–48-часового окна; email contact создан, Test Notification не подтверждён. Месячный SLA 99,9% не доказан |
| NFR-02 | p95 latency ≤200 мс | Main Scale Validation #3: 1000 VU p95 6,15 мс; write lifecycle p95 9,73 мс; mixed 93,06 RPS p95 12,46 мс / p99 18,77 мс; authenticated read 99,96 RPS p95 12,06 мс / p99 14,93 мс | Все обязательные профили прошли на GitHub Actions runner; дополнительный read-only stress 150 RPS не прошёл (109,25 RPS, p95 5,13 с, dropped iterations). Не переносить на Render Free |
| NFR-03 | Error rate ≤0,1% | Main Scale Validation #3: 0 HTTP errors во всех четырёх профилях; 0 dropped iterations; все k6 checks прошли | Подтверждено только в disposable CI runner, не долгосрочная гарантия и не production SLA |
| NFR-04 | Логирование действий | `AuditEvent` и console log (доменные переходы) | Реализовано; полноту аудита для всех административных действий проверить |

## 1. Инструментальные средства и CI/CD

| ID | Обязательный пункт | Реализация/результат | Статус |
|---|---|---|---|
| 1.1 | Выбран и обоснован стек | `ARCHITECTURE.md`, `CAPACITY.md` | документация |
| 1.2 | IDE + линтер + форматер | `.vscode/`, `pyproject.toml`, Ruff | конфигурация |
| 1.3 | Репозиторий Git | публичный `Ramig2007/OfficeFlow`, README и `.gitignore` | Проверено в GitHub |
| 1.4 | Окружение с app, БД, Redis | `compose.yaml`, `Dockerfile`; локальный стек работал, app healthy | Проверено локально |
| 1.5 | CI: сборка, тесты, стиль | `.github/workflows/ci.yml`, `scale-validation.yml`; Main CI #235 | Quality и Docker jobs — Success; включает production build, runtime smoke, browser E2E, independent PostgreSQL restore, DB/Redis recovery и observability validation |
| 1.6 | Доступный Docker-образ | `ghcr.io/ramig2007/officeflow:latest` опубликован | Пакет Private; публичная доступность не подтверждена |

## 2. Разработка программного кода

| ID | Обязательный пункт | Реализация/результат | Статус |
|---|---|---|---|
| 2.1 | User/Role/Room/Booking | `workspace/models.py`, migrations | код |
| 2.2 | Список, создание и отмена API | `workspace/api.py` | код |
| 2.3 | История бронирований API | GET `/api/v1/bookings/` с разграничением доступа | код |
| 2.4 | CRUD переговорных (админ) | `RoomViewSet` + формы | код |
| 2.5 | Валидация данных | формы, serializers, `services.py` | код |
| 2.6 | Конфликт и конкурентность | `0002_postgres_overlap_guard`, `test_concurrent_booking_only_one_wins` | Проверено в PostgreSQL CI |
| 2.7 | Лог действий, ошибки | `AuditEvent`, `LOGGING`, REST 400/403/404/409 | код |
| 2.8 | ≥70% строк критических модулей | pytest-cov для `workspace.services` + `workspace.queries` | 91,67% в CI; не покрытие всего приложения |
| 2.9 | Приватность общего API расписания | `ScheduleBookingSerializer`; тест проверяет отсутствие notes, creator, reviewer и rejection metadata | PR #12; run #66 и main run #73 Success; merge commit `6a9fe11` |

## 3. Состав оборудования и ПО

| ID | Обязательный пункт | Реализация/результат | Статус |
|---|---|---|---|
| 3.1 | Таблица компонент/назначение/обоснование | `CAPACITY.md` | документация |
| 3.2 | CPU/RAM/диск на 1000 пользователей, 100 RPS | формульная оценка `CAPACITY.md` | оценка, не измерение |
| 3.3 | Отказоустойчивость, репликация | Архитектурное обоснование managed Neon в `CAPACITY.md`: stateless compute, отказоустойчивый storage и provider-managed compute recovery; read replica не является независимым standby | Собственная streaming replication/Patroni не внедряется для выбранной Neon Free-схемы; приложение использует постоянный Neon endpoint. Провайдерский механизм не подвергался нашему failover-тесту, RTO/RPO не измерены |
| 3.4 | Backup/restore | Workflow `.github/workflows/backup-neon-yandex.yml`: Neon dump → restore в disposable PostgreSQL 18 → Yandex upload/download → SHA-256 verification → Lifecycle read-back. Run #44951659002 (#13) прошёл; восстановлено 14 таблиц | Удалённая копия, целостность, восстановление и 30-дневное правило хранения подтверждены через S3 API |
| 3.5 | Healthcheck | `/health/live/`, `/health/ready/`, Compose checks; app healthy локально | Проверено локально |
| 3.6 | Бенчмарки и обоснования | `CAPACITY.md`, `SCALE_RESULTS_2026-11-21.md`, Main Scale Validation #3 | 1000 VU, 3750 write cycles, mixed 93,06 RPS average и authenticated read 99,96 RPS; 0 HTTP errors, 0 dropped iterations. Тесты на CI runner, не Render |

## 4. Модификация информационной системы

| ID | Обязательный пункт | Реализация/результат | Статус |
|---|---|---|---|
| 4.1 | VIP ожидает одобрения | `Booking.Status.PENDING`, `review_booking` | код |
| 4.2 | Админ одобряет/отклоняет | `/approvals/`, `approve`/`reject` REST actions | код |
| 4.3 | Нельзя обойти согласование | статус выбирается сервером, тесты проверяют VIP pending и запрет self-approval | Реализовано и покрыто тестами |
| 4.4 | CSV экспорт и фильтры | `queries.export_csv`, date/room | код |
| 4.5 | Impact analysis | `CHANGE_ANALYSIS.md` | документация |
| 4.6 | Регрессионное тестирование | `test_booking_service.py`, `test_http_api.py`, pytest CI | PR #20 CI run #44843044175: 92 passed; два критических модуля — 91,67% coverage |

## 5. Критерии надёжности

| ID | Обязательный пункт | Реализация/результат | Статус |
|---|---|---|---|
| 5.1 | SLA 99,9% / p95≤200 мс / error≤0,1% | `CAPACITY.md`, Prometheus alert rules | цели |
| 5.2 | Метрики HTTP, ошибки, задержки | `django-prometheus`, Prometheus scrape; target officeflow UP | Проверено локально |
| 5.3 | Метрики Redis и PostgreSQL | redis_exporter / postgres_exporter; оба targets UP | Проверено локально |
| 5.4 | Алерты по SLA | Prometheus rules, Alertmanager native Telegram receiver, UptimeRobot, GitHub Actions probe и `.github/workflows/telegram-delivery-check.yml` | UptimeRobot monitor и email contact созданы, но Test Notification не подтверждён; Telegram secrets не заданы и фактическая доставка не проверена |
| 5.5 | Grafana dashboard | `infra/grafana/dashboards/officeflow.json`: 9 панелей HTTP, PostgreSQL и Redis; Docker Compose `observability` profile | Main CI #235 подтвердил 3/3 Prometheus targets UP, пять дополнительных DB/Redis метрик доступны, dashboard provisioned. Локальный Docker стенд, не Render Free |
| 5.6 | Нагрузочный тест 100–200 RPS и анализ деградации | `scale-validation.yml`; Main Scale Validation #3: 1000 VU, write lifecycle, mixed и authenticated read 100 RPS | 1000 VU, 3750 циклов, mixed 93,06 RPS и read 99,96 RPS прошли без HTTP errors/dropped iterations. 150 RPS read stress ранее не прошёл. Тесты не на Render |
| 5.7 | Деградация БД и анализ | PR CI #93: PostgreSQL stop→readiness 503→start→readiness 200; аналогично Redis; архитектура managed Neon и границы provider-managed failover описаны в `CAPACITY.md` | Локальная деградация проверена; принудительный отказ compute Neon и RTO/RPO не тестировались |

## 6. Методики тестирования

| ID | Обязательный пункт | Реализация/результат | Статус |
|---|---|---|---|
| 6.1 | Unit бизнес-логики | `test_booking_service.py`, `test_http_api.py`, uptime/alertmanager/off-site tests | PR #37 CI #44942581093: **112 pytest passed**, coverage 91,67% для `workspace.services` и `workspace.queries`; это не покрытие всего приложения |
| 6.2 | Integration API + PostgreSQL | `test_http_api.py`, PostgreSQL service в CI | CI quality прошёл успешно |
| 6.3 | Проверка транзакций/конкурентности | `test_concurrent_booking_only_one_wins` | Запущен в PostgreSQL CI, job прошёл |
| 6.4 | E2E сценарии | `e2e/browser_smoke.py` (Playwright Chromium), Docker CI | **27/27** browser acceptance в PR #37 CI #44942581093: booking CRUD, VIP, room admin, регистрация/logout, роли, CSV, responsive viewport checks |
| 6.5 | Load JMeter/k6 | Main Scale Validation #3, run #44951299898; artifact `officeflow-scale-validation` ID 14727005489 | 1000/1000 логинов, max 1000 VU; 3750 циклов create/edit/cancel; mixed 93,06 RPS; read 99,96 RPS; 0 HTTP errors и 0 dropped iterations. 150 RPS stress не прошёл. CI runner, не Render |
| 6.6 | Статический анализ | Ruff, Bandit, static audit, Django `check`, `check --deploy` и OpenAPI schema validation | PR #20 CI run #44843044175: Quality Success |
| 6.7 | ≥70% покрытия | CI gate на `workspace.services` + `workspace.queries` | PR #20 CI run #44843044175: 91,67% coverage и 92 pytest passed; покрытие не относится ко всему приложению |
| 6.8 | Дефект-реестр с приоритетами | `docs/DEFECT_LOG_2026-11-19.md` — записи с ID, severity, шагами, ожидаемым/фактическим результатом, исправлением и доказательством | Реестр структурирован; открытые эксплуатационные риски отделены от подтверждённых дефектов |

## 7. Проектная документация

| ID | Обязательный пункт | Реализация/результат | Статус |
|---|---|---|---|
| 7.1 | Краткое ТЗ | этот файл, README | документация |
| 7.2 | C4/UML, потоки | `ARCHITECTURE.md` | документация |
| 7.3 | ER модель | `ARCHITECTURE.md` | документация |
| 7.4 | OpenAPI/Swagger | `/api/schema/`, `/api/docs/`; схема проверяется в CI | Реализовано; OpenAPI validation проходит в CI |
| 7.5 | План, сроки, риски | `PROJECT_PLAN.md`, `RISKS.md` | документация |
| 7.6 | Руководство администратора | `OPERATIONS.md` | документация |
| 7.7 | Рецензирование и согласование | отметка наставника / одногруппника | приёмка |

## 8. Опытная эксплуатация

| ID | Обязательный пункт | Реализация/результат | Статус |
|---|---|---|---|
| 8.1 | Демостенд | Локальный Docker Compose и публичный Render Free + Neon Free: https://officeflow-x6ay.onrender.com/ | Readiness endpoint ответил `ready`; пользователь ранее подтвердил вход и создание переговорных. Полный внешний smoke всех функций отдельно не оформлен; Render Free не доказывает SLA |
| 8.2 | Реалистичные тестовые данные | `seed_demo` создаёт комнаты/встречи и инициализирует пароль новых demo-пользователей из `DEMO_PASSWORD` | Код и regression tests; используется только в DEBUG=1 |
| 8.3 | Чеклист сценариев | `PILOT.md`, 8/8 ручных локальных сценариев, Chromium CI 27/27 | Основные сценарии проверены; независимая приёмка с подписью и полный внешний smoke ещё не подтверждены |
| 8.4 | Трекер ошибок (шаги/скриншоты/логи) | `docs/DEFECT_LOG_2026-11-19.md`, CI artifacts и E2E screenshots | Реестр и CI screenshots есть; реальные скриншоты публичного интерфейса для Word-отчёта и подтверждение независимого проверяющего ещё нужны |
| 8.5 | Performance/Security/UX | `TESTING.md`, Bandit, Chromium 375/768/1440, k6 profiles, Grafana dashboard (9 panels) | Main CI #235: Bandit, browser E2E, Docker smoke и observability validation прошли; внешний DAST и длительное публичное измерение доступности не выполнены |
| 8.6 | Регрессия после исправлений | pytest, CI, Playwright smoke | Выполнена в заявленном объёме |
| 8.7 | Отчёт и вывод готовности | `PILOT.md`, `STATUS.md`, `REQUIREMENTS.md`, `SCALE_RESULTS_2026-11-21.md`, `BACKUP_VALIDATION.md`, `FINAL_READINESS_2026-11-22.md` | Техническая документация актуализирована; Word-отчёт, реальные скриншоты публичного сайта и формальное согласование остаются |

## Критерий финального закрытия

Подтверждены локальный Docker Compose, PostgreSQL concurrency CI, 112 pytest passed в PR #37 CI run #44942581093, 91,67% покрытия двух критических модулей, Chromium acceptance 27/27, 8/8 ручных пользовательских сценариев, Main CI #235 Success, 1000 одновременных авторизованных VU (1000/1000 логинов), 3750 циклов create/edit/cancel, mixed 93,06 RPS average, authenticated read 99,96 RPS, 0 HTTP errors, 0 dropped iterations, независимое восстановление PostgreSQL, Prometheus 3/3 targets и Grafana dashboard 9 панелей. Удалённый backup #13 успешно восстановлен (14 таблиц), SHA-256 и Lifecycle 30 дней проверены. Дополнительный read-only стресс 150 RPS не прошёл: 109,25 RPS, p95 5,13 с, 11 739 dropped iterations. UptimeRobot настроен на 5-минутный интервал; последний сохранённый снимок показал Up и 99,931% за отображаемые 24 часа, но актуальное 24–48-часовое окно и Test Notification требуют подтверждения. Реальная доставка Telegram не проверена. Публичный Render + Neon readiness отвечает, но нагрузочные показатели CI нельзя переносить на Render Free. Месячный SLA 99,9%, Neon failover/RTO/RPO, внешний DAST, независимая формальная приёмка и реальные скриншоты публичного сайта остаются открытыми.
