# OfficeFlow — актуальная оценка готовности

**Дата проверки:** 21 ноября 2026 г.  
**Репозиторий:** https://github.com/Ramig2007/OfficeFlow  
**Основная ветка:** `main`; PR #8, #9, #10, #12, #13 и #16 объединены. PR #16 — merge commit `f9a1957`.  
**Подтверждённый CI актуальной функциональности:** PR run #93 для head `3ea612d` завершился Success в обоих jobs (`quality`, `docker`): 62 pytest passed, coverage 91,67%, Chromium E2E 21/21, k6 write load и PostgreSQL/Redis fault recovery. Исторический main run #73 также Success. Проверки самого merge commit следует смотреть в GitHub Actions. 
**Назначение:** учебная сдача ИСП49 и подготовка к последующему VPS-развёртыванию. Это не заключение о промышленной готовности.

## 1. Подтверждённое состояние

| Область | Подтверждённый факт | Ограничение |
|---|---|---|
| Репозиторий | Публичный GitHub source repo | GHCR package Private |
| CI | PR run #93: quality + docker Success, 62 pytest | Код PR #16 объединён в main commit f9a1957; тесты были до merge |
| Docker runtime | Compose stack стартовал в CI, миграции применились, readiness 200, CSS отдался через Nginx | Ephemeral GitHub runner, не публичный сервер |
| Django tests | 60/60 в локальном прогоне пользователя; 62 passed в main CI run #73 | Не считать это покрытием всех возможных сценариев |
| Coverage | 91,67% для `workspace.services` и `workspace.queries` | Не покрытие всего репозитория |
| Browser E2E | Playwright Chromium 21/21 в PR CI #93, screenshots uploaded | Временная CI-база, не публичный хост |
| User acceptance | 8/8 сценариев — УСПЕХ | Один пользователь, локальный стенд |
| k6 read | 200 RPS read-only, ~199,2 HTTP req/s, p95=13,19 мс, 0% HTTP errors, 30 секунд | Одна сессия, GET only |
| k6 write | 240 циклов create/cancel, 720/720 checks, 0 ошибок/пропусков, p95 16,92 мс | До 11 активных VU, 30 секунд, 8 целевых циклов/с; не 1000 пользователей |
| Backup/restore | `RESTORE_TEST_OK`, counts совпали, GiST constraint проверен | Restore в том же PostgreSQL контейнере |
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
| Закрыт частично | Write load | Создание+отмена проверены при 8 циклах/с и до 11 VU; отдельная нагрузка на редактирование не выполнялась |
| P3 | 1000 пользователей | Отдельный распределённый тест с независимыми сессиями |
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

На имеющихся доказательствах OfficeFlow готов к учебной демонстрации ключевых пользовательских функций на локальном Docker-стенде; расширенный CI #93 подтвердил 21/21 браузерных сценариев и восстановление readiness после отказа зависимостей. CI проверяет Django, безопасность, production-конфигурацию и фактический запуск контейнерного стека со статическими файлами. Дополнительное исправление приватности API расписания прошло оба CI job и объединено в `main`.

**Не заявлять** доказанный SLA 99,9%, работу при 1000 одновременных пользователях, 100/200 RPS операций записи или промышленную готовность. Подтверждена лишь конкретная короткая нагрузка создания/отмены. Подробности: `docs/VERIFICATION_2026-11-21.md`.
