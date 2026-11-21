# OfficeFlow — протокол опытной эксплуатации и пользовательской проверки

**Дата актуализации:** 21 ноября 2026 г.  
**Объект:** OfficeFlow — онлайн-сервис бронирования переговорных комнат.  
**Локальная среда ручной проверки:** Windows, PowerShell 5.1, Docker Desktop Linux engine, Docker Compose, `http://localhost:8080`.  
**Облачный стенд:** Render Free + Neon Free, публичный URL `https://officeflow-x6ay.onrender.com/`; пользователь подтвердил статус Live, успешный вход и создание переговорных 21.11.2026.
**Статус:** локальная ручная проверка 8/8; Chromium acceptance 27/27 в CI #117; PR #20 CI run #44843044175: Quality/Docker/Scale Validation Success, 92 pytest passed; Render + Neon Live подтверждены пользователем. UptimeRobot, Alertmanager recipient и off-site R2 backup ещё требуют внешней настройки.

## 1. Паспорт проверенной среды

| Поле | Значение |
|---|---|
| ОС / терминал | Windows / PowerShell 5.1 |
| Контейнерная среда | Docker Desktop, Linux engine |
| Приложение | Django 5.2, Python 3.12, Gunicorn |
| База данных (локально) | PostgreSQL 16 |
| База данных (облако) | Neon Free, Frankfurt, branch `production`, database `neondb`, direct connection (pooling off) |
| Кэш / сессии (локально) | Redis 7 |
| Reverse proxy (локально) | Nginx 1.27 |
| Облачный runtime | Render Free, Gunicorn + WhiteNoise; Redis/Nginx/Caddy в Render-схеме не используются |
| Локальный URL | `http://localhost:8080` |
| Публичный URL | `https://officeflow-x6ay.onrender.com/` (Render Free + Neon Free) |
| CPU/RAM хоста ручной проверки | Не зафиксированы |
| CI среда | GitHub-hosted runner, временные контейнеры и изолированные Docker volumes |

## 2. Ручная пользовательская проверка

Результаты ниже сообщены пользователем после локального запуска и не являются независимой приёмкой.

| № | Сценарий | Результат |
|---|---|---|
| 1 | Вход сотрудника | УСПЕХ |
| 2 | Каталог переговорных | УСПЕХ |
| 3 | Создание бронирования | УСПЕХ |
| 4 | Защита от конфликта двойного бронирования | УСПЕХ |
| 5 | VIP-согласование | УСПЕХ |
| 6 | Отмена бронирования | УСПЕХ |
| 7 | Разграничение прав доступа | УСПЕХ |
| 8 | CSV-экспорт | УСПЕХ |

**Итог: 8/8 сценариев — УСПЕХ.** Ручное редактирование, регистрация и полный административный CRUD отдельно пользователем не подтверждались; они проверялись автоматизированными браузерными сценариями.

## 3. Автоматизированная приёмка интерфейса

**PR #18 / CI run #117:** Chromium acceptance **27/27** — Success. Покрыты регистрация, вход/выход, доступы, назначение/отзыв ролей, бронирования, VIP, CRUD комнат, CSV-фильтры и адаптивные размеры 375/768/1440 px. Проверка выполнялась на временной CI-базе.

Ссылка на run: https://github.com/Ramig2007/OfficeFlow/actions/runs/44829732693.

## 4. Нагрузочные и надёжностные проверки

| Испытание | Фактический результат | Ограничение |
|---|---|---|
| Авторизованное чтение, k6 | ~199,2 HTTP req/s, p95 13,19 мс, 0 HTTP errors | 30 секунд, одна сессия, GET only |
| Независимые сессии | **1000/1000** успешных логинов, пик 1000 VU, 41 294 HTTP-запроса, p95 **9,50 мс**, 0 HTTP-ошибок | PR #20 CI run #44843044175, GitHub runner; не 1000 одновременных HTTP-запросов и не production |
| Create/edit/cancel | **3749** завершённых циклов, 11 247 операций записи, 18 745/18 745 checks, p95 **14,47 мс**, 0 ошибок и 0 dropped iterations | PR #20 CI run #44843044175, пик около 60 write HTTP RPS; не production |
| Mixed read/write | 15 466 HTTP-запросов за 3 минуты, средняя фактическая скорость **85,03 RPS**, p95 **17,82 мс**, 0 ошибок, 0 dropped iterations; 1079 полных booking cycles | PR #20 CI run #44843044175; профиль был настроен на пик 100 RPS, но средняя фактическая скорость была ниже 100 |
| PostgreSQL concurrency | PostgreSQL test: при одновременной попытке пересекающейся брони выигрывает только одна | Изолированный PostgreSQL CI |
| Database/Redis recovery | Stop → readiness 503 → start → readiness 200 | Не является автоматическим HA failover |
| Backup/restore | `INDEPENDENT_RESTORE_OK`, SHA-256, counts и GiST constraint в отдельном PostgreSQL контейнере | CI #117; тот же Docker-host. Новый Neon→R2 workflow добавлен, но bucket/secrets и первый удалённый backup ещё не настроены |

### Новый смешанный нагрузочный профиль

В PR #20 добавлен отдельный `scripts/loadtest-mixed-100-rps.js`, который запускается в `scale-validation.yml`; прежний write-only тест сохранён отдельно.

Два параллельных сценария были настроены на пик: HTML-чтение до 79 GET/с и циклы create/edit/cancel до 7 циклов/с (21 API write/с), то есть целевой пик 100 HTTP RPS. В PR #20 CI run #44843044175 тест завершился успешно: 15 466 HTTP-запросов за 3 минуты, фактическая средняя интенсивность **85,03 HTTP RPS**, p95 17,82 мс, 0 HTTP-ошибок, 17 544/17 544 checks и 0 `dropped_iterations`. Это подтверждает прохождение порогов для фактически достигнутой нагрузки, но **не подтверждает устойчивые 100 HTTP RPS**. Предыдущий более тяжёлый профиль 25 циклов/с (75 write + 25 read) не прошёл CI #136/#137: в #137 0 HTTP-ошибок и 100% checks, но 221 dropped iterations и p95 1062 мс. Этот неуспешный результат сохраняется как ограничение конкретного CI стенда.

## 5. Мониторинг, алерты и резервирование

- Prometheus: 3/3 targets UP в локальном стенде; пять alert rules прошли проверку.
- Grafana dashboard: конфигурация подготовлена, локальный observability stack запускался.
- Alertmanager: default receiver — `null-receiver`; реальная доставка не включена, пока владелец не выбрал и не добавил HTTPS webhook endpoint.
- Публичный Render + Neon сервис Live; для независимых email alerts подготовлена настройка UptimeRobot на `/health/ready/`, но аккаунт, monitor и Alert Contact ещё не созданы.
- Backup: локальный dump и independent restore проверены CI #117.
- Off-site: в текущей PR-ветке добавлен GitHub Actions workflow ежедневного Neon dump → полный restore в disposable PostgreSQL → Cloudflare R2 upload/download + SHA-256. Bucket, GitHub secrets/variables и первый успешный run ещё не настроены.
- SLA 99,9% не подтверждён. Для учебной практики запланировано внешнее наблюдение UptimeRobot в течение 24–48 часов; в отчёт вносится только фактически накопленный период, число проверок, uptime и инциденты.

## 6. Расширенный чек-лист опытной эксплуатации

| ID | Сценарий | Подтверждение | Статус |
|---|---|---|---|
| PILOT-01 | Регистрация сотрудника | Chromium CI #117 | Автоматически проверено |
| PILOT-02 | Вход/выход | Ручной вход + Chromium CI #117 logout | Проверено в смешанном объёме |
| PILOT-03 | Каталог и расписание | Ручной smoke + Playwright | Проверено |
| PILOT-04 | Бронирование на 1–4 часа | Ручной smoke + service tests | Проверено |
| PILOT-05 | Конфликт повторной брони | Ручной smoke + API/PG tests | Проверено |
| PILOT-06 | Параллельная бронь в PostgreSQL | Concurrency CI | Проверено в CI |
| PILOT-07 | Редактирование и отмена | Chromium CI #117 + k6 #106 | Автоматически проверено |
| PILOT-08 | VIP-заявка | Ручной smoke | Проверено |
| PILOT-09 | VIP approve/reject | Ручной smoke + API tests | Проверено |
| PILOT-10 | Смена роли | Chromium CI #117 | Автоматически проверено |
| PILOT-11 | CRUD/деактивация комнаты | Chromium CI #117 | Автоматически проверено |
| PILOT-12 | CSV и фильтры | Ручной экспорт + Chromium CI #117 | Проверено |
| PILOT-13 | IDOR/CSRF/mass assignment | API negative tests; Bandit | Частично; внешний DAST не выполнялся |
| PILOT-14 | Метрики и доставка алертов | Prometheus rules; HTTPS webhook renderer; UptimeRobot setup guide | Частично; Alertmanager recipient и UptimeRobot email contact не подключены |
| PILOT-15 | Backup/restore | Independent PostgreSQL restore CI #117; Neon→R2 GitHub Actions workflow added | Restore в CI проверен; R2 bucket/secrets и первый удалённый backup ожидают настройки |
| PILOT-16 | Mixed read/write load | PR #20 CI run #44843044175 | Пороги пройдены; фактическая средняя интенсивность 85,03 HTTP RPS, не устойчивые 100 RPS |
| PILOT-17 | Деградация PostgreSQL/Redis | Stop→503→start→200 в CI | Проверено; HA failover не проверен |
| PILOT-18 | UX 375/768/1440 | Chromium CI #117 | Проверено |
| PILOT-19 | Приватность schedule API | PR #12 regression test | Проверено |

## 7. Дефекты и открытые риски

Ранее обнаруженные и устранённые дефекты OF-001…OF-005, а также эксплуатационные риски OF-R01…OF-R09 перечислены в `DEFECT_LOG_2026-11-19.md`. Важные открытые ограничения:

1. Render + Neon уже Live; полный внешний smoke всех бизнес-сценариев ещё не оформлен.
2. Нет настоящего Alertmanager webhook recipient и подтверждённой доставки.
3. Нет R2 bucket/secrets и первого успешного off-site backup/restore.
4. Нет автоматической репликации/failover PostgreSQL.
5. Нет полного 30-дневного измерения SLA 99,9%; UptimeRobot ещё не включён.
6. Нет независимой пользовательской приёмки.
7. Нет фактических скриншотов публичного сайта в итоговом Word-документе.
8. GHCR package остаётся private (публичный source repository доступен).

## 8. Формальная приёмка

- Независимый проверяющий: ____________________
- Роль/организация: ____________________
- Дата и время проверки: ____________________
- Проверенные сценарии: ____________________
- Открытые замечания: ____________________
- Подпись/согласование (если требуется): ____________________

**Заключение на дату актуализации:** основные пользовательские функции и автоматизированные CI проверки подтверждены в перечисленных средах. Это предварительная учебная приёмка, а не доказательство промышленной готовности или SLA 99,9%.
