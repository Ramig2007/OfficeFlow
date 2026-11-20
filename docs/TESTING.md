# Стратегия тестирования и фактические результаты

## Уровни тестирования

| Уровень | Инструмент | Проверяемые сценарии | Доказательство |
|---|---|---|---|
| Unit | pytest + Django test DB | временные интервалы, 1–4 часа, пересечения, VIP, отмена, роли | CI / локальный pytest |
| Integration | DRF APIClient + PostgreSQL | REST 201/400/403/404/409, CSV, IDOR, audit, schedule API privacy | CI log / PR #12 regression test |
| Concurrency | 2 threads + PostgreSQL | только одна запись на занятый слот | PostgreSQL CI |
| Browser acceptance E2E | Playwright Chromium | **27 сценариев**: регистрация, login/logout, роли, 375/768px, booking lifecycle, VIP, room admin, CSV filters | CI #117 и `docs/PILOT.md` |
| Load | k6 | baseline/GET, 1000 отдельных логинов и 3750 изолированных create/edit/cancel циклов | `docs/LOADTEST_RESULTS_2026-11-19.md`, `docs/SCALE_RESULTS_2026-11-21.md` |
| Static | Ruff, Bandit, structural audit | ошибки кода, распространённые security patterns, структура | GitHub Actions |
| Django security | `manage.py check --deploy` | production security settings | GitHub Actions |
| UX | Chromium 375, 768 и 1440 px | mobile/tablet каталоги без горизонтального overflow и desktop dashboard | CI #93 screenshots |

## CI pipeline

Текущий workflow `.github/workflows/ci.yml` выполняет:

1. PostgreSQL 16 и Redis 7 services;
2. Ruff lint;
3. Bandit scan по `workspace` (миграции и тесты исключены);
4. `scripts/static_audit.py`;
5. `python manage.py check`;
6. production security check `python manage.py check --deploy` с безопасным тестовым окружением;
7. `makemigrations --check --dry-run`;
8. `collectstatic --noinput`;
9. pytest с coverage gate ≥70% для `workspace.services` и `workspace.queries`;
10. production Compose validation, Caddyfile validation и shell syntax checks;
11. Docker image build; push в GHCR выполняется только при push в `main`, с тегами `latest` и `sha-<commit>`;
12. Runtime Compose smoke: app startup, migrations, readiness endpoint и фактическая отдача hashed CSS через Nginx;
13. Создание demo fixtures в изолированной БД, сборка Playwright Chromium image, browser acceptance **27/27** в CI #117, загрузка screenshots artifact (7 дней);
14. k6 write load с отдельными тестовыми сессиями (создание+отмена) на временной БД;
15. PostgreSQL/Redis stop → readiness 503 → start → readiness 200;
17. Реальная проверка PostgreSQL backup/restore в отдельный контейнер без сети и постоянного хранилища: **INDEPENDENT_RESTORE_OK** в CI #117;
16. Валидация обеих конфигураций Alertmanager: null-receiver и HTTPS webhook.

После merge PR #13 GitHub Actions main run #73 завершился успешно: jobs `quality` и `docker` — Success. Quality job подтвердил **62 passed** и coverage **91,67%** для `workspace.services` и `workspace.queries`. Docker job поднял временный Compose stack, применил миграции, проверил readiness и отдачу CSS через Nginx, создал изолированные demo fixtures и запустил Chromium browser smoke: **9/9 checks passed**. Скриншоты загружены как artifact `officeflow-browser-e2e`. Это проверяет приложение в ephemeral CI, но не выполняет публичный VPS deploy.

Подтверждение актуальной версии (PR #16, CI run #93): **62 passed**, **91,67%** покрытия двух критических модулей, jobs `quality` + `docker` — Success, Playwright **21/21**, write-load и тест возврата readiness после отказа PostgreSQL/Redis. Исходный исторический результат main run #73 сохранён ниже как этап разработки.

## Unit и integration tests

Локальный прогон пользователя до последних regression tests: **60/60 pytest passed**. Main CI run #73: **62 passed**, coverage `workspace.services` и `workspace.queries` — **91,67%** при пороге 70%. Это покрытие двух указанных критических модулей, не всего приложения.

Команды локального прогона (использовать тестовую БД, не рабочие данные):

```powershell
python -m pytest workspace/tests -q --cov=workspace.services --cov=workspace.queries --cov-report=term-missing --cov-fail-under=70
ruff check .
python manage.py check
python manage.py makemigrations --check --dry-run
```

## PostgreSQL concurrency

Тест `test_concurrent_booking_only_one_wins` использует `Barrier(2)` и одновременно создаёт две брони на одну комнату/интервал. Он пропускается на SQLite и запускается на PostgreSQL. В CI используется PostgreSQL 16; текущий quality job прошёл успешно.

Ожидаемый инвариант: одна транзакция создаёт бронь, вторая получает конфликт, активная бронь остаётся одна. Независимое ограничение GiST exclusion остаётся последним уровнем защиты. Отдельный тест schedule API подтверждает, что другой сотрудник не получает внутренние заметки и данные владельца бронирования.

## Browser E2E

Исторический Chromium smoke-run: 9/9 checks локально и main CI #73 (только чтение). **В PR run #93 проверено 21/21, а в PR run #117 — 27/27 Chromium acceptance:** создание/редактирование/отмена брони, VIP approve/reject, создание/редактирование/деактивация комнаты, доступы/403, UI и проверка 375/768/1440 px. Добавлены регистрация, logout, назначение и отзыв административной роли, а также CSV с фильтрами. Изменения создаются только во временной CI-базе, после тестов она удаляется. Скриншоты: artifact `officeflow-browser-e2e`. См. `docs/PILOT.md` и `docs/VERIFICATION_2026-11-21.md`.

Отдельный `e2e/test_user_journey.py` создаёт и отменяет тестовую бронь; его следует запускать только на изолированной демонстрационной БД.

## Load testing

Есть два разных сценария, результаты нельзя смешивать:

1. `scripts/loadtest.js` — baseline `/health/live/`; 100 и 200 RPS за 30 секунд, p95 1,40 и 1,49 мс.
2. `scripts/loadtest-auth-read.js` — login + авторизованные GET `/rooms/`, `/schedule/`, `/my-bookings/`; около 199,2 HTTP req/s, p95 13,19 мс, 0 HTTP-ошибок за 30 секунд.

Второй исторический сценарий использовал одну авторизованную сессию и не создавал бронирования. В CI #93 дополнительный k6 write test выполнил 240 create/cancel циклов. **Актуальная расширенная проверка PR #17, CI #106:** 1000 независимых успешных логинов, 41 299 HTTP запросов без ошибок (p95 6,91 мс); отдельно **3750** create/edit/cancel циклов (11 250 успешных записей), 18 750/18 750 проверок, 0 HTTP-ошибок и dropped iterations, p95 **10,40 мс**, до 40 активных VU. Это не доказывает промышленную производительность на произвольном VPS, 100/200 RPS исключительно записи или SLA 99,9%. Подробные значения и первичный artifact: `docs/SCALE_RESULTS_2026-11-21.md`.

План следующих нагрузочных испытаний:
- отдельная изолированная БД;
- несколько независимых тестовых пользователей;
- 70% чтения и 30% записей как начальная модель;
- создание/редактирование/отмена брони и конфликт 409;
- фиксация p50/p95, ошибок 5xx, ожидаемых 409, RPS, DB connections и CPU/RAM;
- не проводить write workload на базе с реальными данными.

## Backup / restore

Исторически подтверждён `RESTORE_TEST_OK` во временную БД в том же контейнере. **В PR CI #117 подтверждён также `INDEPENDENT_RESTORE_OK`**: SHA-256, восстановление в отдельный временный PostgreSQL-контейнер, сверка counts и GiST exclusion constraint, без изменения исходной БД. Это не off-host backup и не тест полного отказа физического сервера. См. `docs/BACKUP_VALIDATION.md`.

Для VPS добавлен Linux backup script `scripts/backup.sh`; он проверяет читаемость архива и создаёт SHA-256. Для защиты от потери сервера backup нужно копировать в отдельное зашифрованное off-host хранилище.

## Дополнительные ручные проверки

- POST брони длительностью менее 1 часа или более 4 часов → отказ.
- Бронирование в прошлом → отказ.
- Два соседних интервала → оба разрешены.
- Два пересекающихся → конфликт; PostgreSQL constraint существует.
- VIP → pending без возможности самосогласования.
- Сотрудник не может читать чужую бронь или вызывать административные actions.
- CSRF для unsafe browser requests остаётся включённым.
- Неожиданные `status` / `creator` поля не должны менять серверный статус брони.
- CSV формулы экранируются, фильтры дат/комнат проверяются.
- Responsive widths 375/768/1440 px проверены в Chromium CI #93; для публичного сервера потребуется повторное smoke-тестирование.
- После Docker image update проверить, что entrypoint обновляет shared `staticfiles` volume.

## Открытые проверки

- 100/200 RPS исключительно операций записи (проверено примерно 60 write RPS на верхней ступени);
- длительное измерение SLI/SLA;
- HA/failover PostgreSQL (базовые shutdown/start + readiness 503/200 уже проверены в CI #93);
- DAST / внешний security review;
- реальные уведомления Alertmanager (CI проверяет генерацию HTTPS webhook конфигурации, но endpoint не задан);
- публичный VPS deploy и внешняя проверка HTTPS.
