# OfficeFlow — актуальная оценка готовности

**Дата проверки:** 21 ноября 2026 г.  
**Репозиторий:** https://github.com/Ramig2007/OfficeFlow  
**Основная ветка:** `main`; PR #8, #9, #10, #12, #13, #16, #17 и #18 объединены. PR #18 — merge commit `3910bfd`.  
**Подтверждённые CI:** PR run #106 (`quality`, `docker`, `scale-validation`) — Success: 68 pytest, 1000 независимых синтетических логинов, 3750 полных циклов create/edit/cancel. **PR run #117 (`quality`, `docker`) — Success:** Chromium 27/27, независимый PostgreSQL restore и fault recovery. PR #18 объединён в `main` squash merge `3910bfd`. Результаты относятся к проверенному коду PR до merge. 
**Назначение:** учебная сдача ИСП49 и подготовка к последующему VPS-развёртыванию. Это не заключение о промышленной готовности.

## 1. Подтверждённое состояние

| Область | Подтверждённый факт | Ограничение |
|---|---|---|
| Репозиторий | Публичный GitHub source repo | GHCR package Private |
| CI | PR #17 run #106: quality/docker/scale-validation Success; PR #18 run #117: quality/docker Success | Проверенный код перенесён в main squash merge 3910bfd |
| Docker runtime | Compose stack стартовал в CI, миграции применились, readiness 200, CSS отдался через Nginx | Ephemeral GitHub runner, не публичный сервер |
| Django tests | 60/60 исторически локально; **68 passed** в PR CI #106 | Не считать покрытием всех возможных сценариев |
| Coverage | 91,67% для `workspace.services` и `workspace.queries` | Не покрытие всего репозитория |
| Browser E2E | Playwright Chromium **27/27** в PR CI #117, screenshots uploaded | Временная CI-база, не публичный хост |
| User acceptance | 8/8 сценариев — УСПЕХ | Один пользователь, локальный стенд |
| k6 read | 200 RPS read-only, ~199,2 HTTP req/s, p95=13,19 мс, 0% HTTP errors, 30 секунд | Одна сессия, GET only |
| k6 write | **3750** create/edit/cancel циклов, 11 250 успешных записей, 18 750 checks, 0 ошибок/пропусков, p95 10,40 мс | 4 минуты, до 40 активных VU, ступень до 20 циклов/с (≈60 write RPS) |
| k6 capacity | **1000 отдельных логинов**, пик 1000 VU, 41 299 HTTP запросов, 0 ошибок, p95 6,91 мс | 10 минут на CI runner, не production сервер и не 1000 одновременных HTTP запросов |
| Backup/restore | **INDEPENDENT_RESTORE_OK** в CI #117: SHA-256, другой контейнер, counts и GiST constraint | На том же Docker-хосте, off-host storage не подтверждено |
| Monitoring | Prometheus targets 3/3 UP, 5 rules validated; CI #93 проверил optional HTTPS webhook config | Доставка реальным адресатам пока не проверена |
| API privacy | Общий schedule API ограничен календарными полями; тест подтверждает отсутствие внутренних заметок и данных владельца | PR #12; CI run #66 прошёл до merge |
| Production settings | HSTS, HTTPS redirect, secure cookies, explicit host/CSRF checks, fail-fast guards | Требуется настоящий домен и VPS |
| Backup tooling | Linux backup и temporary restore scripts добавлены | На VPS ещё не выполнялись |
| Demo fixtures | Новые demo-аккаунты получают заданный пароль; повторный seed сохраняет существующий пароль | PR #13; regression tests в main CI run #73 |

## 2. Что уже находится в main

Production-readiness изменения объединены в основную ветку:
- Caddy automatic HTTPS и production Compose overlay;
- Nginx loopback binding и передача HTTPS scheme до Django;
- fail-closed Django production settings для secret, DB password, hosts, CSRF, cookies, redirect и HSTS;
- сбор статики при старте контейнера;
- исправлен `STATIC_URL=/static/`; CI проверяет фактическую отдачу CSS через Nginx;
- Linux backup и full restore verification во временной БД;
- усиленный CI: Ruff, Bandit, static audit, Django deploy checks, migrations, collectstatic, pytest, Compose/Caddy validation, shell syntax, Docker runtime smoke и Playwright Chromium browser smoke с артефактами;
- ограничение состава данных общего API расписания отдельным сериализатором и регрессионным тестом приватности (PR #12);
- автоматический Playwright Chromium smoke в Docker CI, загрузка скриншотов и исправление инициализации demo-паролей (PR #13);
- GHCR tags `latest` и commit SHA;
- Dependabot для pip и GitHub Actions;
- обновлены README, STATUS, TESTING, PILOT, REQUIREMENTS, DEPLOYMENT и readiness records.

## 3. Остаток до сдачи ИСП49 и публичного запуска

| Приоритет | Задача | Что требуется |
|---|---|---|
| P1 | Итоговый отчёт | Word-документ подготовлен; вставить фактические скриншоты интерфейса и при необходимости добавить подписи/согласование |
| P1 | Формальная приёмка | Указать проверяющего/ответственного и получить подпись или согласование, если требует преподаватель |
| P1 | Реальный хостинг | Нужны VPS, домен/DNS и доступ администратора; затем выполнить deploy |
| P1 | Внешний smoke-test | Проверить сайт по публичному HTTPS домену после размещения |
| P2 | Backup вне VPS | Настроить зашифрованную копию в отдельном хранилище и проверить restore на отдельной машине |
| P2 | Alertmanager | Настроить и проверить реального получателя, если это требуется для сдачи |
| Выполнено для CI-профиля | Write load | 3750 create/edit/cancel циклов, пиковая ступень 20 циклов/с (≈60 write RPS), 0 ошибок; результаты относятся только к CI runner |
| Выполнено для CI-профиля | 1000 пользователей | 1000 независимых успешных логинов и пик 1000 VU, удержание 3 мин; повторить на реальном VPS для production-оценки |
| P3 | SLA 99,9% | Длительный мониторинг; короткий локальный тест SLA не доказывает |

## 4. Критерии публичного запуска

Считать хостинг завершённым только после того, как:
- домен указывает на VPS;
- Caddy выдал действительный TLS-сертификат;
- HTTP перенаправляется на HTTPS;
- Django работает с `DEBUG=0`, корректными `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS`;
- БД, Redis и служебные панели не доступны напрямую из Интернета;
- health endpoints возвращают 200;
- CSS/JS доступны через Nginx;
- проверены вход, каталог, бронирование, конфликт, VIP, права и CSV;
- backup создан, скопирован за пределы VPS и восстановлен в тестовой БД.

## 5. Итог

На имеющихся доказательствах OfficeFlow готов к учебной демонстрации ключевых пользовательских функций на локальном Docker-стенде; CI #117 подтвердил 27/27 браузерных сценариев, независимый PostgreSQL restore и восстановление readiness после отказов зависимостей; CI #106 подтвердил 1000 синтетических сессий и 3750 циклов записи. CI проверяет Django, безопасность, production-конфигурацию и фактический запуск контейнерного стека со статическими файлами. Дополнительное исправление приватности API расписания прошло оба CI job и объединено в `main`.

**Подтверждён тест 1000 отдельных авторизованных синтетических сессий** в изолированном CI runner, но не 1000 одновременных HTTP запросов или промышленная производительность на VPS. **Не заявлять** доказанный SLA 99,9%, 100/200 RPS исключительно операций записи или промышленную готовность. Подробности: `docs/SCALE_RESULTS_2026-11-21.md` и `docs/VERIFICATION_2026-11-21.md`.
