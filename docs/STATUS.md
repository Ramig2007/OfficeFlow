# Сводка фактической готовности OfficeFlow — 21.11.2026

## Репозиторий, ветка и CI

- Репозиторий исходного кода: https://github.com/Ramig2007/OfficeFlow — публичный.
- Основная ветка: `main`.
- PR #8, #9, #10, #12, #13, #16, #17 и #18 объединены в `main`. PR #18 довёл Chromium acceptance до 27/27, добавил независимый restore в другом контейнере PostgreSQL и повторно проверил fault recovery.
- **Код PR #17** прошёл PR CI **run #106**: jobs `quality`, `docker` и `scale-validation` — **Success**, 68 pytest passed, coverage 91,67% для двух критических модулей, 1000 успешных отдельных авторизаций, 3750 циклов создания/редактирования/отмены, 0 HTTP-ошибок. PR #17 объединён в `main`, merge commit `754ec0c`. **PR #18 CI #117** (`quality` и `docker`) — Success; Chromium 27/27, отдельный PostgreSQL restore и readiness fault recovery. Merge commit PR #18 — `3910bfd`. Исторический PR #16 CI run #93 также успешен.
- Main run #73 собрал и опубликовал Docker image в GHCR с тегами `latest` и commit SHA. GHCR package остаётся **Private**; публичны исходники, а не контейнерный пакет.
- Docker CI поднимал временный Compose stack, создавал demo fixtures только в изолированной БД, запускал Playwright Chromium через Compose network и загружал скриншоты как artifact `officeflow-browser-e2e` (retention 7 дней). После проверки контейнеры и volumes удалялись.
- Production-конфигурация и runtime smoke находятся в основной ветке: Caddy, HTTPS-настройки Django, Compose overlay, сбор статики, миграции и проверка readiness/CSS через Nginx.

## Подтверждённые результаты

| Область | Факт | Статус / ограничение |
|---|---|---|
| Пользовательская проверка | 8/8 сценариев отмечены пользователем как УСПЕХ | Один пользователь, локальная среда |
| Django tests | 60/60 в историческом локальном прогоне; **68 passed** в PR CI #106 | Новые тесты мониторинга; покрытие не всего приложения |
| Покрытие критического кода | 91,67% для `workspace.services` и `workspace.queries` | Не покрытие всего приложения |
| Browser E2E | Chromium **27/27** в PR CI #117: регистрация, вход/выход, управление ролями, VIP, брони, комнаты и CSV фильтры | Изолированная временная CI-база, ручная приёмка отдельно |
| k6 read | ~199,2 HTTP req/s, p95=13,19 мс, 0% HTTP-ошибок, 30 секунд | Авторизованные GET, одна тестовая сессия |
| k6 write | **3750** create/edit/cancel циклов, 11 250 успешных записей, 18 750/18 750 checks, p95 10,40 мс, 0 ошибок/пропусков | CI #106, 4 мин, до 40 активных VU, верхняя ступень 20 циклов/с, ≈60 write RPS |
| k6 1000 users | **1000** независимых логинов, пик 1000 VU, 41 299 HTTP запросов, p95 6,91 мс, 0 ошибок | CI #106, 10 мин, 3 мин удержания; не 1000 RPS и не production хост |
| Backup/restore | CI #117: **`INDEPENDENT_RESTORE_OK`**, checksum, отдельный изолированный PostgreSQL контейнер, counts и GiST constraint | Один Docker-хост; off-host backup/внешний DR не выполнены |
| Мониторинг | Prometheus 3/3 targets UP; 5 правил проверены; CI #93 проверил конфигурацию null и HTTPS webhook | Для фактической доставки нужен реальный webhook endpoint |
| CI quality | Ruff, Bandit, static audit, Django checks, OpenAPI validation, deploy checks, migrations, collectstatic, pytest | Main run #73 Success; 62 passed, coverage 91,67% |
| CI Docker | Compose/Caddy и Alertmanager validation, runtime smoke, Chromium **27/27**, k6 write, независимый restore и PostgreSQL/Redis recovery | **PR CI #117 Success**; merged PR #18 |
| API privacy | Schedule API отдаёт только календарные поля; regression test проверяет отсутствие заметок и данных владельца | PR #12; run #66 Success; main run #73 Success; merge commit `6a9fe11` |
| Production config | Caddy HTTPS overlay, secure Django settings, backup/restore scripts | В main; реальный VPS ещё не развёрнут |
| Demo account seeding | Новые demo-пользователи получают пароль из `DEMO_PASSWORD`; повторный запуск не перезаписывает действующий пароль | PR #13; regression tests включены в 62 passed main CI run #73 |

Подробные записи: `docs/USER_ACCEPTANCE_2026-11-19.md`, `docs/E2E_BROWSER_RUN.md`, `docs/LOADTEST_RESULTS_2026-11-19.md`, `docs/SCALE_RESULTS_2026-11-21.md`, `docs/BACKUP_VALIDATION.md`, `docs/TESTING.md`.

## Что ещё требуется до полной сдачи и публичного запуска

1. Получить VPS и домен, настроить DNS/firewall и выполнить реальный HTTPS deploy.
2. Пройти внешний smoke-test сайта: вход, каталог, расписание, бронирование, конфликт, VIP, права, CSV, статические файлы и health endpoints.
3. Настроить backup за пределы VPS и проверить восстановление на отдельной машине.
4. Настроить реальный receiver Alertmanager, если это требуется для сдачи.
5. Тест 1000 независимых сессий и 3750 полных циклов записи успешно выполнен в CI #106. Для подтверждения 100/200 RPS **только записи**, работы production VPS и длительного SLA 99,9% потребуются отдельные испытания.
6. Вставить фактические скриншоты сайта в подготовленный Word-отчёт и завершить формальную приёмку.

## Ограничения, которые нельзя скрывать

- ~199,2 HTTP RPS измерены для авторизованного чтения на одной сессии; отдельно CI #106 проверил до 1000 независимых сессий и ступень 20 циклов записи/с.
- 1000 синтетических VU подтверждены в 10-минутном CI-тесте, а create/edit/cancel — на ступени ~60 write RPS. Это не 1000 одновременных HTTP-запросов, не 100/200 RPS исключительно записи и не доказательство производительности реального VPS.
- SLA 99,9% требует длительного измерения.
- Одна PostgreSQL база без репликации остаётся единой точкой отказа.
- Alertmanager `null-receiver` не доставляет реальные уведомления.
- Production-конфигурация и runtime smoke проверены в CI, но публичный VPS и DNS ещё не настроены.
- GHCR package приватный; для первого VPS-деплоя используйте сборку из публичного Git-репозитория, как описано в `docs/DEPLOYMENT.md`, либо отдельно измените видимость пакета.

Подробная оценка: `docs/FINAL_READINESS_2026-11-20.md`; результаты тестов: `docs/VERIFICATION_2026-11-21.md` и `docs/SCALE_RESULTS_2026-11-21.md`; инструкция: `docs/DEPLOYMENT.md`.
