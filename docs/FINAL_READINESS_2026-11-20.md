# OfficeFlow — актуальная оценка готовности

**Дата проверки:** 20 ноября 2026 г.  
**Репозиторий:** https://github.com/Ramig2007/OfficeFlow  
**Основная ветка:** `main`, актуальный HEAD на момент проверки — `73c4279`.  
**Последний полностью успешный CI:** GitHub Actions run #40 — jobs `quality` и `docker` Success. Запуски #41–#48 были отменены concurrency при быстрой последовательности обновлений; требуется новый полный pipeline после текущего PR.  
**Назначение:** учебная сдача ИСП49 и подготовка к последующему VPS-развёртыванию. Это не заключение о промышленной готовности.

## 1. Подтверждённое состояние

| Область | Подтверждённый факт | Ограничение |
|---|---|---|
| Репозиторий | Публичный GitHub source repo | GHCR package Private |
| CI | Run #52: quality + docker Success | Более поздние runs #41–#48 отменены; новый pipeline обязателен |
| Docker runtime | Compose stack стартовал в CI, миграции применились, readiness 200, CSS отдался через Nginx | Ephemeral GitHub runner, не публичный сервер |
| Django tests | 60/60 в локальном прогоне | Не считать это покрытием всех возможных сценариев |
| Coverage | 91,67% для `workspace.services` и `workspace.queries` | Не покрытие всего репозитория |
| Browser E2E | Playwright Chromium 9/9 | Read-only smoke |
| User acceptance | 8/8 сценариев — УСПЕХ | Один пользователь, локальный стенд |
| k6 | 200 RPS read-only, ~199,2 HTTP req/s, p95=13,19 мс, 0% HTTP errors, 30 секунд | Одна сессия, GET only |
| Backup/restore | `RESTORE_TEST_OK`, counts совпали, GiST constraint проверен | Restore в том же PostgreSQL контейнере |
| Monitoring | Prometheus targets 3/3 UP, 5 rules validated | Alertmanager null receiver |
| Production settings | HSTS, HTTPS redirect, secure cookies, explicit host/CSRF checks, fail-fast guards | Требуется настоящий домен и VPS |
| Backup tooling | Linux backup и temporary restore scripts добавлены | На VPS ещё не выполнялись |

## 2. Что уже находится в main

Production-readiness изменения объединены в основную ветку:
- Caddy automatic HTTPS и production Compose overlay;
- Nginx loopback binding и передача HTTPS scheme до Django;
- fail-closed Django production settings для secret, DB password, hosts, CSRF, cookies, redirect и HSTS;
- сбор статики при старте контейнера;
- исправлен `STATIC_URL=/static/`; CI проверяет фактическую отдачу CSS через Nginx;
- Linux backup и full restore verification во временной БД;
- усиленный CI: Ruff, Bandit, static audit, Django deploy checks, migrations, collectstatic, pytest, Compose/Caddy validation, shell syntax, Docker runtime smoke;
- GHCR tags `latest` и commit SHA;
- Dependabot для pip и GitHub Actions;
- обновлены README, STATUS, TESTING, PILOT, REQUIREMENTS, DEPLOYMENT и readiness records.

## 3. Остаток до сдачи ИСП49 и публичного запуска

| Приоритет | Задача | Что требуется |
|---|---|---|
| P0 | Новый полный CI | Дождаться успешных jobs quality и docker для актуального коммита после PR |
| P1 | Итоговый отчёт | Подготовить Word-документ, вставить фактические скриншоты интерфейса и доказательства CI/тестов |
| P1 | Формальная приёмка | Указать проверяющего/ответственного и получить подпись или согласование, если требует преподаватель |
| P1 | Реальный хостинг | Нужны VPS, домен/DNS и доступ администратора; затем выполнить deploy |
| P1 | Внешний smoke-test | Проверить сайт по публичному HTTPS домену после размещения |
| P2 | Backup вне VPS | Настроить зашифрованную копию в отдельном хранилище и проверить restore на отдельной машине |
| P2 | Alertmanager | Настроить и проверить реального получателя, если это требуется для сдачи |
| P2 | Write load | Отдельный изолированный сценарий создания/редактирования/отмены брони |
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

На имеющихся доказательствах OfficeFlow готов к учебной демонстрации ключевых пользовательских функций на локальном Docker-стенде. CI проверяет Django, безопасность, production-конфигурацию и фактический запуск контейнерного стека со статическими файлами. Production-конфигурация подготовлена и объединена в main.

**Не заявлять** доказанный SLA 99,9%, работу при 1000 одновременных пользователях, производительность записи под нагрузкой или промышленную готовность до соответствующих измерений и эксплуатации.
