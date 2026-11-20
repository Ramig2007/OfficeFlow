# Стратегия тестирования и фактические результаты

## Уровни тестирования

| Уровень | Инструмент | Проверяемые сценарии | Доказательство |
|---|---|---|---|
| Unit | pytest + Django test DB | временные интервалы, 1–4 часа, пересечения, VIP, отмена, роли | CI / локальный pytest |
| Integration | DRF APIClient + PostgreSQL | REST 201/400/403/404/409, CSV, IDOR, audit | CI log |
| Concurrency | 2 threads + PostgreSQL | только одна запись на занятый слот | PostgreSQL CI |
| Browser smoke E2E | Playwright Chromium | login, dashboard, catalogue, schedule, permissions, mobile | `docs/E2E_BROWSER_RUN.md` |
| Load | k6 | baseline liveness и авторизованные GET страницы | `docs/LOADTEST_RESULTS_2026-11-19.md` |
| Static | Ruff, Bandit, structural audit | ошибки кода, распространённые security patterns, структура | GitHub Actions |
| Django security | `manage.py check --deploy` | production security settings | GitHub Actions |
| UX | Chromium 375px и 1440px | mobile catalogue и desktop dashboard | E2E screenshots |

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
12. Runtime Compose smoke: app startup, migrations, readiness endpoint и фактическая отдача hashed CSS через Nginx.

На PR #1 `Prepare OfficeFlow for secure VPS hosting` GitHub Actions run #6 завершился успешно: jobs `quality` и `docker` — Success. Это проверяет CI и Docker build, но не выполняет публичный deploy.

## Unit и integration tests

Локальный прогон пользователя: **60/60 pytest passed**. В CI coverage для `workspace.services` и `workspace.queries` ранее составило **91,67%** при пороге 70%. Это покрытие двух указанных критических модулей, не всего приложения.

Команды локального прогона (использовать тестовую БД, не рабочие данные):

```powershell
python -m pytest workspace/tests -q --cov=workspace.services --cov=workspace.queries --cov-report=term-missing --cov-fail-under=70
ruff check .
python manage.py check
python manage.py makemigrations --check --dry-run
```

## PostgreSQL concurrency

Тест `test_concurrent_booking_only_one_wins` использует `Barrier(2)` и одновременно создаёт две брони на одну комнату/интервал. Он пропускается на SQLite и запускается на PostgreSQL. В CI используется PostgreSQL 16; текущий quality job прошёл успешно.

Ожидаемый инвариант: одна транзакция создаёт бронь, вторая получает конфликт, активная бронь остаётся одна. Независимое ограничение GiST exclusion остаётся последним уровнем защиты.

## Browser E2E

Подтверждён локальный Playwright Chromium smoke-run: **9/9 checks passed**. Он проверяет анонимный редирект, вход, dashboard, карточку комнаты, VIP filter, расписание, историю, 403 на административные маршруты и мобильный каталог. Прогон read-only и не меняет бронирования. Подробности и команды: `docs/E2E_BROWSER_RUN.md`.

Отдельный `e2e/test_user_journey.py` создаёт и отменяет тестовую бронь; его следует запускать только на изолированной демонстрационной БД.

## Load testing

Есть два разных сценария, результаты нельзя смешивать:

1. `scripts/loadtest.js` — baseline `/health/live/`; 100 и 200 RPS за 30 секунд, p95 1,40 и 1,49 мс.
2. `scripts/loadtest-auth-read.js` — login + авторизованные GET `/rooms/`, `/schedule/`, `/my-bookings/`; около 199,2 HTTP req/s, p95 13,19 мс, 0 HTTP-ошибок за 30 секунд.

Второй сценарий использовал одну авторизованную сессию и не создавал бронирования. Он не подтверждает 1000 независимых пользователей, нагрузку на запись, долгосрочную доступность или SLA 99,9%. Подробные значения: `docs/LOADTEST_RESULTS_2026-11-19.md`.

План следующих нагрузочных испытаний:
- отдельная изолированная БД;
- несколько независимых тестовых пользователей;
- 70% чтения и 30% записей как начальная модель;
- создание/редактирование/отмена брони и конфликт 409;
- фиксация p50/p95, ошибок 5xx, ожидаемых 409, RPS, DB connections и CPU/RAM;
- не проводить write workload на базе с реальными данными.

## Backup / restore

Подтверждён `RESTORE_TEST_OK`: PostgreSQL dump восстановлен во временную БД в том же контейнере, количества users/rooms/bookings/audit_events/migrations совпали, GiST overlap constraint найден, временная БД удалена. См. `docs/BACKUP_VALIDATION.md`.

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
- Проверить responsive widths 375, 768, 1440 px; 768px пока отдельно не подтверждён.
- После Docker image update проверить, что entrypoint обновляет shared `staticfiles` volume.

## Открытые проверки

- нагрузка на создание/редактирование/отмену бронирований;
- 1000 независимых пользователей;
- длительное измерение SLI/SLA;
- PostgreSQL fault injection в изолированной среде;
- DAST / внешний security review;
- реальные уведомления Alertmanager (сейчас `null-receiver`);
- публичный VPS deploy и внешняя проверка HTTPS.
