# Сводка фактической готовности OfficeFlow — 21.11.2026

## Репозиторий, ветка и CI

- Репозиторий исходного кода: https://github.com/Ramig2007/OfficeFlow — публичный.
- Основная ветка: `main`.
- PR #8, #9, #10, #12, #13 и #16 объединены в `main`. PR #16 расширил Playwright до 21 сценария, добавил k6 write load, проверки отказа PostgreSQL/Redis и конфигурацию webhook Alertmanager.
- Последний отдельно подтверждённый полный main pipeline до PR #16: run #73 (`quality`, `docker`) — Success. **Актуальный код PR #16** прошёл PR run **#93** (`quality`, `docker`) — Success, 62 pytest passed, coverage 91,67%, Chromium **21/21**, k6 write test и PostgreSQL/Redis fault recovery. Merge commit — `f9a1957`.
- Main run #73 собрал и опубликовал Docker image в GHCR с тегами `latest` и commit SHA. GHCR package остаётся **Private**; публичны исходники, а не контейнерный пакет.
- Docker CI поднимал временный Compose stack, создавал demo fixtures только в изолированной БД, запускал Playwright Chromium через Compose network и загружал скриншоты как artifact `officeflow-browser-e2e` (retention 7 дней). После проверки контейнеры и volumes удалялись.
- Production-конфигурация и runtime smoke находятся в основной ветке: Caddy, HTTPS-настройки Django, Compose overlay, сбор статики, миграции и проверка readiness/CSS через Nginx.

## Подтверждённые результаты

| Область | Факт | Статус / ограничение |
|---|---|---|
| Пользовательская проверка | 8/8 сценариев отмечены пользователем как УСПЕХ | Один пользователь, локальная среда |
| Django tests | 60/60 прошли в локальном прогоне пользователя; 62 passed в main CI run #73 | Локальный прогон был до добавления двух regression tests |
| Покрытие критического кода | 91,67% для `workspace.services` и `workspace.queries` | Не покрытие всего приложения |
| Browser E2E | Playwright Chromium: 9/9 в историческом read-only прогоне; **21/21** в PR CI #93, screenshot artifact uploaded | Изолированная временная CI-база |
| k6 read | ~199,2 HTTP req/s, p95=13,19 мс, 0% HTTP-ошибок, 30 секунд | Авторизованные GET, одна тестовая сессия |
| k6 write | **240** циклов создания/отмены, **720/720** проверок, **0** HTTP-ошибок, **0** пропусков, p95 **16,92 мс** | 8 целевых циклов/с, 30 секунд, до 11 активных VU; не тест 1000 пользователей |
| Backup/restore | `RESTORE_TEST_OK`, counts совпали, GiST constraint проверен | Временная БД в том же PostgreSQL-контейнере |
| Мониторинг | Prometheus 3/3 targets UP; 5 правил проверены; CI #93 проверил конфигурацию null и HTTPS webhook | Для фактической доставки нужен реальный webhook endpoint |
| CI quality | Ruff, Bandit, static audit, Django checks, OpenAPI validation, deploy checks, migrations, collectstatic, pytest | Main run #73 Success; 62 passed, coverage 91,67% |
| CI Docker | Compose/Caddy и Alertmanager validation, runtime smoke, Playwright 21/21, k6 write, PostgreSQL/Redis recovery | PR run #93 Success; merged PR #16 |
| API privacy | Schedule API отдаёт только календарные поля; regression test проверяет отсутствие заметок и данных владельца | PR #12; run #66 Success; main run #73 Success; merge commit `6a9fe11` |
| Production config | Caddy HTTPS overlay, secure Django settings, backup/restore scripts | В main; реальный VPS ещё не развёрнут |
| Demo account seeding | Новые demo-пользователи получают пароль из `DEMO_PASSWORD`; повторный запуск не перезаписывает действующий пароль | PR #13; regression tests включены в 62 passed main CI run #73 |

Подробные записи: `docs/USER_ACCEPTANCE_2026-11-19.md`, `docs/E2E_BROWSER_RUN.md`, `docs/LOADTEST_RESULTS_2026-11-19.md`, `docs/BACKUP_VALIDATION.md`, `docs/TESTING.md`.

## Что ещё требуется до полной сдачи и публичного запуска

1. Получить VPS и домен, настроить DNS/firewall и выполнить реальный HTTPS deploy.
2. Пройти внешний smoke-test сайта: вход, каталог, расписание, бронирование, конфликт, VIP, права, CSV, статические файлы и health endpoints.
3. Настроить backup за пределы VPS и проверить восстановление на отдельной машине.
4. Настроить реальный receiver Alertmanager, если это требуется для сдачи.
5. Изолированный write workload и тест нескольких сессий завершены в CI #93. Для доказательства 1000 независимых пользователей, 100/200 RPS **записи** и длительной устойчивости потребуются отдельные испытания.
6. Вставить фактические скриншоты сайта в подготовленный Word-отчёт и завершить формальную приёмку.

## Ограничения, которые нельзя скрывать

- ~199,2 HTTP RPS измерены для авторизованного чтения; отдельно 8 целевых циклов записи/отмены в секунду проверены в CI #93.
- Краткий write test доказал работу до 11 активных VU, но не 1000 одновременных пользователей или 100/200 RPS записи.
- SLA 99,9% требует длительного измерения.
- Одна PostgreSQL база без репликации остаётся единой точкой отказа.
- Alertmanager `null-receiver` не доставляет реальные уведомления.
- Production-конфигурация и runtime smoke проверены в CI, но публичный VPS и DNS ещё не настроены.
- GHCR package приватный; для первого VPS-деплоя используйте сборку из публичного Git-репозитория, как описано в `docs/DEPLOYMENT.md`, либо отдельно измените видимость пакета.

Подробная оценка: `docs/FINAL_READINESS_2026-11-20.md`; результаты новых проверок: `docs/VERIFICATION_2026-11-21.md`; инструкция: `docs/DEPLOYMENT.md`.
