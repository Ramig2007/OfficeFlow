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
| NFR-01 | Доступность ≥99,9% | Внешний HTTPS мониторинг UptimeRobot для `https://officeflow-x6ay.onrender.com/health/ready/` | SLA 99,9% не подтверждён; для сдачи практики планируется 24–48-часовое наблюдение как демонстрация внешнего мониторинга, а не доказательство долгосрочного SLA |
| NFR-02 | p95 latency ≤200 мс | CI #20: mixed workload p95 17,82 мс; read-only CI profile ~199,2 RPS, p95 13,19 мс | Пройдено для тестовых CI-профилей, не для публичного Render; mixed фактическая средняя скорость 85,03 RPS |
| NFR-03 | Error rate ≤0,1% | PR #20 CI: 1000-user, write и mixed profiles завершились с 0% HTTP errors | Пройдено в CI runner; не долгосрочная гарантия и не production SLA |
| NFR-04 | Логирование действий | `AuditEvent` и console log (доменные переходы) | Реализовано; полноту аудита для всех административных действий проверить |

## 1. Инструментальные средства и CI/CD

| ID | Обязательный пункт | Реализация/результат | Статус |
|---|---|---|---|
| 1.1 | Выбран и обоснован стек | `ARCHITECTURE.md`, `CAPACITY.md` | документация |
| 1.2 | IDE + линтер + форматер | `.vscode/`, `pyproject.toml`, Ruff | конфигурация |
| 1.3 | Репозиторий Git | публичный `Ramig2007/OfficeFlow`, README и `.gitignore` | Проверено в GitHub |
| 1.4 | Окружение с app, БД, Redis | `compose.yaml`, `Dockerfile`; локальный стек работал, app healthy | Проверено локально |
| 1.5 | CI: сборка, тесты, стиль | `.github/workflows/ci.yml`, `scale-validation.yml`; PR #20 CI run #44843044175 | Quality + Docker + Scale Validation Success; 92 pytest, 91,67% coverage, Chromium 27/27 в отдельном CI #117 |
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
| 3.4 | Backup/restore | CI #117 independent restore; GitHub Actions workflow `.github/workflows/backup-neon-r2.yml` для ежедневного Neon dump, полного restore test и загрузки в Cloudflare R2 | Workflow добавлен в PR-ветку; R2 bucket/secrets и первый успешный off-site backup ещё не настроены |
| 3.5 | Healthcheck | `/health/live/`, `/health/ready/`, Compose checks; app healthy локально | Проверено локально |
| 3.6 | Бенчмарки и обоснования | `CAPACITY.md`, k6 baseline и `SCALE_RESULTS_2026-11-21.md` | 1000 синтетических сессий и 3749 create/edit/cancel циклов подтверждены PR #20 CI; смешанный профиль — 85,03 RPS в среднем при пике 100 RPS; production не измерен |

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
| 5.4 | Алерты по SLA | 5 Prometheus rules, HTTPS webhook renderer; внешний мониторинг публичного Render описан через UptimeRobot | Alertmanager receiver и UptimeRobot email contact ещё не подключены; доставка уведомлений не подтверждена |
| 5.5 | Grafana dashboard | `infra/grafana/dashboards/officeflow.json` | Конфигурация готова; запуск Prometheus/Grafana проверен в локальном observability-стенде |
| 5.6 | 100–200 RPS стресс-тест | Read-only ~199,2 HTTP RPS; write peak около 60 HTTP write RPS; PR #20 mixed workload настроен на пик 100 RPS | Mixed run: 15 466 запросов за 3 минуты, фактическая средняя скорость **85,03 RPS**, p95 17,82 мс, 0 errors, 0 dropped; устойчивые 100 RPS не подтверждены |
| 5.7 | Деградация БД и анализ | PR CI #93: PostgreSQL stop→readiness 503→start→readiness 200; аналогично Redis | Автоматический сценарий прошёл; HA/failover БД не доказан |

## 6. Методики тестирования

| ID | Обязательный пункт | Реализация/результат | Статус |
|---|---|---|---|
| 6.1 | Unit бизнес-логики | `test_booking_service.py`, `test_http_api.py`, uptime/alertmanager/off-site tests | PR #20 CI: **92 pytest passed**, coverage 91,67% для двух критических модулей; это не покрытие всего приложения |
| 6.2 | Integration API + PostgreSQL | `test_http_api.py`, PostgreSQL service в CI | CI quality прошёл успешно |
| 6.3 | Проверка транзакций/конкурентности | `test_concurrent_booking_only_one_wins` | Запущен в PostgreSQL CI, job прошёл |
| 6.4 | E2E сценарии | `e2e/browser_smoke.py` (Playwright Chromium), Docker CI | **27/27** browser acceptance в PR CI #117: booking CRUD, VIP, room admin, регистрация/logout, роли, CSV, 375/768 px |
| 6.5 | Load JMeter/k6 | 1000 независимых авторизаций, create/edit/cancel workload и mixed read/write сценарий | PR #20 CI: 1000/1000 логинов, 3749 циклов записи, mixed 85,03 HTTP RPS в среднем; тесты на CI runner, не Render |
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
| 8.1 | Демостенд | Локальный Docker Compose и публичный Render Free + Neon Free: https://officeflow-x6ay.onrender.com/ | Render подтверждён пользователем как Live; вход и создание переговорных выполнены; полный внешний smoke всех функций ещё не оформлен |
| 8.2 | Реалистичные тестовые данные | `seed_demo` создаёт комнаты/встречи и инициализирует пароль новых demo-пользователей из `DEMO_PASSWORD` | Код и regression tests; используется только в DEBUG=1 |
| 8.3 | Чеклист сценариев | `PILOT.md`, 8/8 ручных локальных сценариев, Chromium CI 27/27 | Основные функции проверены; независимая приёмка и полный внешний smoke ещё не проведены |
| 8.4 | Трекер ошибок (шаги/скриншоты/логи) | `docs/DEFECT_LOG_2026-11-19.md`, CI artifacts и E2E screenshots | Реестр и CI screenshots есть; реальные скриншоты публичного интерфейса для Word-отчёта и подтверждение независимого проверяющего ещё нужны |
| 8.5 | Performance/Security/UX | `TESTING.md`, Bandit, Chromium 375/768/1440, k6 capacity/write/mixed profiles | CI профили подтверждены; внешний DAST и длительное публичное измерение доступности не выполнены |
| 8.6 | Регрессия после исправлений | pytest, CI, Playwright smoke | Выполнена в заявленном объёме |
| 8.7 | Отчёт и вывод готовности | `PILOT.md`, `FINAL_READINESS_2026-11-20.md`, `FINAL_GAP_CLOSURE.md`, Word-отчёт OfficeFlow | Техническая основа готова; обновление отчёта, скриншоты и формальное согласование остаются |

## Критерий финального закрытия

Подтверждены локальный Docker-стенд, PostgreSQL concurrency CI, **92 pytest passed** в PR #20 CI run #44843044175, 91,67% покрытия двух критических модулей, Chromium acceptance **27/27** в CI #117, 8/8 ручных пользовательских сценариев, 1000 отдельных синтетических логинов, 3749 циклов create/edit/cancel, независимое восстановление PostgreSQL и защита приватности API расписания. Публичный Render + Neon сервис https://officeflow-x6ay.onrender.com/ пользователь подтвердил как Live; вход и создание переговорных выполнены. PR #20 CI также подтвердил mixed workload: 15 466 HTTP-запросов за 3 минуты, фактическая средняя интенсивность 85,03 RPS, p95 17,82 мс, 0 HTTP-ошибок и 0 dropped iterations. В текущей PR-ветке добавлены документация внешней эксплуатации и GitHub Actions workflow ежедневного Neon backup в Cloudflare R2; bucket/secrets и первый backup ещё требуют настройки. До полной приёмки остаются полный внешний smoke, реальный Alertmanager webhook, настройка UptimeRobot и краткосрочное 24–48-часовое наблюдение для отчёта, первый успешный off-site backup/restore, независимая приёмка и фактические скриншоты. Короткое наблюдение не подтверждает SLA 99,9%. Нагрузочные показатели CI нельзя переносить на публичный Render Free.
