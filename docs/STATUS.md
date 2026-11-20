# Сводка фактической готовности OfficeFlow — 20.11.2026

## Репозиторий, ветка и CI

- Репозиторий исходного кода: https://github.com/Ramig2007/OfficeFlow — публичный.
- Основная ветка: `main`.
- PR #8 (readiness-документация), PR #9 (закрытие соединений конкурентного теста и схемы API), PR #10 (синхронизация readiness-документации) и PR #12 (ограничение данных общего API расписания) объединены в `main`.
- Подтверждённый полный main pipeline: run #63 для commit `8c1a71c` — **Success** (`quality`, `docker`). Дополнительно PR run #66 проверил security fix #12: оба job завершились **Success** до merge commit `6a9fe11`.
- Запуски #41–#51 были отменены механизмом concurrency при последовательных обновлениях документации; подтверждённые main runs #58, #61 и #63 завершились успешно. PR run #66 отдельно проверил изменение приватности API расписания перед merge PR #12.
- Run #63 собрал и опубликовал Docker image в GHCR с тегами `latest` и commit SHA. GHCR package остаётся **Private**; публичны исходники, а не контейнерный пакет.
- Production-конфигурация и runtime smoke уже входят в основную ветку: Caddy, HTTPS-настройки Django, Compose overlay, сбор статики, миграции и проверка readiness/CSS через Nginx.

Docker job run #63 включал полный временный Compose smoke-stack в GitHub Actions: контейнер приложения запустился, миграции применились, readiness вернул 200, CSS-файл был найден в static volume и успешно отдан через Nginx. Временные контейнеры и volumes CI после проверки удалены.

## Подтверждённые результаты

| Область | Факт | Статус / ограничение |
|---|---|---|
| Пользовательская проверка | 8/8 сценариев отмечены пользователем как УСПЕХ | Один пользователь, локальная среда |
| Django tests | 60/60 прошли в локальном прогоне | Локальный прогон |
| Покрытие критического кода | 91,67% для `workspace.services` и `workspace.queries` | Не покрытие всего приложения |
| Browser E2E | Playwright Chromium: 9/9 | Read-only smoke-набор |
| k6 | ~199,2 HTTP req/s, p95=13,19 мс, 0% HTTP-ошибок, 30 секунд | Авторизованные GET, одна тестовая сессия |
| Backup/restore | `RESTORE_TEST_OK`, counts совпали, GiST constraint проверен | Временная БД в том же PostgreSQL-контейнере |
| Мониторинг | Prometheus 3/3 targets UP; 5 правил проверены | Alertmanager `null-receiver`, реальные уведомления не доставляются |
| CI quality | Ruff, Bandit, static audit, Django checks, OpenAPI validation, deploy checks, migrations, collectstatic, pytest | Main run #63 Success; PR run #66 Success |
| CI Docker | Compose/Caddy config, shell syntax, image build/push, runtime smoke | Main run #63 Success; PR run #66 Success |
| API privacy | Schedule API отдаёт только календарные поля; regression test проверяет отсутствие заметок и данных владельца | PR #12; run #66 `quality` и `docker` Success; merge commit `6a9fe11` |
| Production config | Caddy HTTPS overlay, secure Django settings, backup/restore scripts | В main; реальный VPS ещё не развёрнут |

Подробные записи: `docs/USER_ACCEPTANCE_2026-11-19.md`, `docs/E2E_BROWSER_RUN.md`, `docs/LOADTEST_RESULTS_2026-11-19.md`, `docs/BACKUP_VALIDATION.md`, `docs/TESTING.md`.

## Что ещё требуется до полной сдачи и публичного запуска

1. Получить VPS и домен, настроить DNS/firewall и выполнить реальный HTTPS deploy.
2. Пройти внешний smoke-test сайта: вход, каталог, расписание, бронирование, конфликт, VIP, права, CSV, статические файлы и health endpoints.
3. Настроить backup за пределы VPS и проверить восстановление на отдельной машине.
4. Настроить реальный receiver Alertmanager, если это требуется для сдачи.
5. При необходимости выполнить write workload и тест независимых сессий; 1000 пользователей не подтверждены.
6. Вставить фактические скриншоты сайта в подготовленный Word-отчёт и завершить формальную приёмку.

## Ограничения, которые нельзя скрывать

- 200 RPS измерены только для авторизованного чтения в течение 30 секунд.
- Текущий прогон не доказывает 1000 одновременных пользователей или производительность записи.
- SLA 99,9% требует длительного измерения.
- Одна PostgreSQL база без репликации остаётся единой точкой отказа.
- Alertmanager `null-receiver` не доставляет реальные уведомления.
- Production-конфигурация и runtime smoke проверены в CI, но публичный VPS и DNS ещё не настроены.
- GHCR package приватный; для первого VPS-деплоя используйте сборку из публичного Git-репозитория, как описано в `docs/DEPLOYMENT.md`, либо отдельно измените видимость пакета.

Подробная оценка: `docs/FINAL_READINESS_2026-11-20.md`; инструкция: `docs/DEPLOYMENT.md`.
