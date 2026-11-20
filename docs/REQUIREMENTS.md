# Матрица обязательных требований ИСП49

**Источник:** преподавательский кейс «Онлайн-сервис бронирования переговорных комнат в офисе», разделы 1–8. Статусы разделяют реализацию, фактические проверки и незакрытые пункты. «Проверено» означает только описанный в документах сценарий и среду; это не подтверждение SLA или промышленной готовности.

## Бизнес-требования и сквозные критерии

| ID | Требование | Реализация/доказательство | Статус |
|---|---|---|---|
| BR-01 | Список комнат | `rooms`, `/api/v1/rooms/`; каталог прошёл ручную и browser smoke проверку | Проверено в локальном сценарии |
| BR-02 | Занятость по часам | недельный `schedule`, `/api/v1/schedule/`; страница расписания проверена в Playwright | Проверено в smoke-сценарии |
| BR-03 | Бронирование 1–4 часа | `services._validate_time`, форма, API; ручное создание и тесты диапазона времени | Проверено в заявленном сценарии |
| BR-04 | Изменение и отмена | `services.update_booking/cancel_booking`, интерфейс/API; Chromium acceptance 21/21, плюс 3750 полных циклов create/edit/cancel | Проверено автоматически в PR CI #93 и #106; ручное редактирование отдельно не зафиксировано |
| BR-05 | Админ CRUD комнат и права | `/control/rooms/`, `/control/users/`, API; Chromium create/edit/deactivate и проверки прав | Автоматически проверено в PR CI #93 (21/21); ручная приёмка отдельно |
| BR-06 | Авторизация и история | Django auth, `/my-bookings/`; вход и история проверены в пользовательском/E2E прогоне | Проверено в smoke-сценарии |
| BR-07 | Конфликт двойной брони | блокировка строки Room, PG GiST constraint и concurrency test в PostgreSQL CI | Проверено в PostgreSQL CI; отдельный write-load PR #17 успешно завершён без конфликтов на раздельных слотах |
| BR-08 | Базовая отчётность | `/reports/`, `/api/v1/reports/summary/`; CSV-экспорт проверен пользователем | CSV подтверждён; полная отчётность проверяется отдельно |
| NFR-01 | Доступность ≥99,9% | Prometheus + алерты | Не измерена за длительный период |
| NFR-02 | p95 latency ≤200 мс | Историческое чтение 13,19 мс; PR CI #106 — 1000 VU p95 6,91 мс, create/edit/cancel p95 10,40 мс | Пройдено только для измеренных CI-профилей и периодов, не для публичного VPS |
| NFR-03 | Error rate ≤0,1% | PR CI #106: 41 299 HTTP чтений/логинов + 11 350 HTTP запросов write-сценария, 0% HTTP-ошибок | Пройдено только для измеренных CI-профилей и периодов, не долгосрочная гарантия |
| NFR-04 | Логирование действий | `AuditEvent` и console log (доменные переходы) | Реализовано; полноту аудита для всех административных действий проверить |

## 1. Инструментальные средства и CI/CD

| ID | Обязательный пункт | Реализация/результат | Статус |
|---|---|---|---|
| 1.1 | Выбран и обоснован стек | `ARCHITECTURE.md`, `CAPACITY.md` | документация |
| 1.2 | IDE + линтер + форматер | `.vscode/`, `pyproject.toml`, Ruff | конфигурация |
| 1.3 | Репозиторий Git | публичный `Ramig2007/OfficeFlow`, README и `.gitignore` | Проверено в GitHub |
| 1.4 | Окружение с app, БД, Redis | `compose.yaml`, `Dockerfile`; локальный стек работал, app healthy | Проверено локально |
| 1.5 | CI: сборка, тесты, стиль | `.github/workflows/ci.yml` и `scale-validation.yml`; PR CI #106 | Quality + Docker + Scale Validation Success; 68 pytest, Chromium 21/21 и k6 испытания |
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
| 3.3 | Отказоустойчивость, репликация | топология и ограничения в `CAPACITY.md` | проектная рекомендация |
| 3.4 | Backup/restore | `scripts/backup.ps1`, `test-restore.ps1`, `backup.sh`, `test-restore.sh` | Windows restore проверен во временной БД; Linux scripts прошли syntax CI, на VPS ещё не запускались |
| 3.5 | Healthcheck | `/health/live/`, `/health/ready/`, Compose checks; app healthy локально | Проверено локально |
| 3.6 | Бенчмарки и обоснования | `CAPACITY.md`, k6 baseline и `SCALE_RESULTS_2026-11-21.md` | Подтверждены 1000 отдельных синтетических сессий и 3750 create/edit/cancel циклов в PR CI #106; production не измерен |

## 4. Модификация информационной системы

| ID | Обязательный пункт | Реализация/результат | Статус |
|---|---|---|---|
| 4.1 | VIP ожидает одобрения | `Booking.Status.PENDING`, `review_booking` | код |
| 4.2 | Админ одобряет/отклоняет | `/approvals/`, `approve`/`reject` REST actions | код |
| 4.3 | Нельзя обойти согласование | статус выбирается сервером, тесты проверяют VIP pending и запрет self-approval | Реализовано и покрыто тестами |
| 4.4 | CSV экспорт и фильтры | `queries.export_csv`, date/room | код |
| 4.5 | Impact analysis | `CHANGE_ANALYSIS.md` | документация |
| 4.6 | Регрессионное тестирование | `test_booking_service.py`, `test_http_api.py`, тесты uptime, CI pytest | PR CI #106: 68 passed, два критических модуля — 91,67% |

## 5. Критерии надёжности

| ID | Обязательный пункт | Реализация/результат | Статус |
|---|---|---|---|
| 5.1 | SLA 99,9% / p95≤200 мс / error≤0,1% | `CAPACITY.md`, Prometheus alert rules | цели |
| 5.2 | Метрики HTTP, ошибки, задержки | `django-prometheus`, Prometheus scrape; target officeflow UP | Проверено локально |
| 5.3 | Метрики Redis и PostgreSQL | redis_exporter / postgres_exporter; оба targets UP | Проверено локально |
| 5.4 | Алерты по SLA | `infra/prometheus/alerts.yml`, 5 правил прошли promtool tests | Правила проверены; Alertmanager `null-receiver`, внешняя доставка не настроена |
| 5.5 | Grafana dashboard | `infra/grafana/dashboards/officeflow.json` | Конфигурация готова; запуск Prometheus/Grafana проверен в локальном observability-стенде |
| 5.6 | 100–200 RPS стресс-тест | baseline/авторизованное чтение и `scripts/loadtest-booking-create-edit-cancel.js` | Ранее ~199,2 RPS авторизованных GET; дополнительно PR CI #106 — 1000 сессий и ступень ~60 write RPS, но не 100/200 write RPS |
| 5.7 | Деградация БД и анализ | PR CI #93: PostgreSQL stop→readiness 503→start→readiness 200; аналогично Redis | Автоматический сценарий прошёл; HA/failover БД не доказан |

## 6. Методики тестирования

| ID | Обязательный пункт | Реализация/результат | Статус |
|---|---|---|---|
| 6.1 | Unit бизнес-логики | `test_booking_service.py`, `test_uptime_monitoring.py` | PR CI #106: 68 passed |
| 6.2 | Integration API + PostgreSQL | `test_http_api.py`, PostgreSQL service в CI | CI quality прошёл успешно |
| 6.3 | Проверка транзакций/конкурентности | `test_concurrent_booking_only_one_wins` | Запущен в PostgreSQL CI, job прошёл |
| 6.4 | E2E сценарии | `e2e/browser_smoke.py` (Playwright Chromium), Docker CI | 21/21 browser acceptance в PR CI #93 и #106: booking CRUD, VIP approval/reject, room admin, responsive 375/768 px |
| 6.5 | Load JMeter/k6 | `scripts/loadtest.js`, `scripts/loadtest-auth-read.js`, 1000 VU и create/edit/cancel k6 | PR CI #106: 1000 отдельных логинов, 3750 жизненных циклов (11 250 записей), все checks успешны |
| 6.6 | Статический анализ | Ruff, Bandit, static audit, Django `check`, `check --deploy` и OpenAPI schema validation | PR CI #106 quality Success |
| 6.7 | ≥70% покрытия | CI gate на `workspace.services` + `workspace.queries` | PR CI #106: 91,67% в двух критических модулях, 68 pytest passed, порог выполнен |
| 6.8 | Дефект-реестр с приоритетами | `docs/DEFECT_LOG_2026-11-19.md` и `docs/PILOT.md` | Исправления и открытые ограничения задокументированы; формальный issue tracker не обязателен для локального протокола |

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
| 8.1 | Демостенд | локальный Docker Compose и `seed_demo` | Проверено локально; публичный VPS не развёрнут |
| 8.2 | Реалистичные тестовые данные | `seed_demo` создаёт комнаты/встречи и инициализирует пароль новых demo-пользователей из `DEMO_PASSWORD` | Код и regression tests; используется только в DEBUG=1 |
| 8.3 | Чеклист сценариев | `PILOT.md`, пользовательская приёмка | 8/8 ручных сценариев; полный 18-пунктовый чек-лист частичный |
| 8.4 | Трекер ошибок (шаги/скриншоты/логи) | `docs/DEFECT_LOG_2026-11-19.md`, E2E artifacts локально; в Word-отчёте предусмотрены 9 мест и инструкция для скриншотов сайта | Реестр есть; фактические скриншоты ещё нужно вставить |
| 8.5 | Performance/Security/UX | `TESTING.md`, Bandit, Chromium 375/768/1440, k6 1000 VU и create/edit/cancel | Автоматическая часть подтверждена CI #106; нет внешнего DAST и production smoke |
| 8.6 | Регрессия после исправлений | pytest, CI, Playwright smoke | Выполнена в заявленном объёме |
| 8.7 | Отчёт и вывод готовности | `PILOT.md`, `FINAL_READINESS_2026-11-20.md`, обновлённый Word-отчёт OfficeFlow | Отчёт подготовлен; фактические скриншоты и формальное согласование остаются |

## Критерий финального закрытия

Подтверждены локальный Docker-стенд, PostgreSQL concurrency CI, 68 pytest в PR CI #106, 91,67% покрытия двух критических модулей, Chromium acceptance 21/21, 8/8 ручных пользовательских сценариев, краткие read-only тесты, 1000 отдельных синтетических логинов, 3750 полных циклов create/edit/cancel (11 250 операций записи), backup/restore во временной БД и защита приватности API расписания. Подробности: `SCALE_RESULTS_2026-11-21.md`. До полной приёмки остаются внешняя эксплуатационная среда и HTTPS smoke (если требуется), off-host backup, проверка доставки алертов, длительное внешнее измерение SLA 99,9%, формальная приёмка, скриншоты и финальный отчёт. 1000 VU доказаны лишь для конкретного профиля на CI runner, а не для production сервера.
