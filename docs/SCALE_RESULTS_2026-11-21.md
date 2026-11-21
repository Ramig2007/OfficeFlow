# OfficeFlow — результаты масштабных испытаний (21.11.2026)

## Источник

- Репозиторий: https://github.com/Ramig2007/OfficeFlow
- PR #17: https://github.com/Ramig2007/OfficeFlow/pull/17
- Проверенный PR head: `5fb8f4bcfed3163673806b6ecdf6686dbb74a963`; объединён в `main` squash commit `754ec0cb8e1ed9608bcadf8a07acd7babeb4c57c`.
- GitHub Actions: **run #106**, https://github.com/Ramig2007/OfficeFlow/actions/runs/44825746865
- CI jobs `quality`, `docker`, `scale-validation / scale-validation`: **Success**.
- Сырые логи и summary: artifact `officeflow-scale-validation`, https://github.com/Ramig2007/OfficeFlow/actions/runs/44825746865/artifacts/14675715208 (retention 90 days, истекает 18.02.2027). Файлы: `1000-users.log`, `1000-users-summary.json`, `booking-create-edit-cancel.log`, `booking-create-edit-cancel-summary.json`, `docker-stats.log`, `exit-codes.txt`.
- Сценарии и конфигурация: `scripts/loadtest-1000-users.js`, `scripts/loadtest-booking-create-edit-cancel.js`, `.github/workflows/scale-validation.yml`.

## 1. Проверка 1000 независимых авторизованных пользователей

- 1000 уникальных учётных записей `loadtest01` … `loadtest1000` создано в изолированной БД, успешность подтверждена отдельной проверкой SQL count.
- Каждая виртуальная сессия прошла собственную HTML-авторизацию, получила Django session cookie. **1000/1000 успешных логинов**, `officeflow_login_failures=0`.
- k6 сценарий `ramping-vus`: рост от 0 до 1000 VU, удержание целевого уровня в течение 3 минут, плавное снижение; общий сценарий 10 минут (плюс завершение).
- `vus.max=1000` и `vus_max=1000`. На каждой итерации авторизованный GET к API комнат / собственных броней / расписания, примерно раз в 10 секунд на VU.
- **41 299 HTTP-запросов**, средняя скорость за всё окно (с ramp-up/ramp-down) **67,83 HTTP req/s**; **39 299 рабочих итераций**.
- **41 299 / 41 299 checks passed** (100,00%), **0 HTTP-ошибок**, `http_req_failed=0`.
- Задержка HTTP: средняя **7,84 мс**, p95 **6,91 мс**, максимум **184,44 мс**. Порог p99 менее 5 секунд — пройден, численное значение p99 стандартный summary не выводит.
- Итог k6: **PASS**, код выхода `capacity_exit_code=0`.

## 2. Нагрузка на создание, редактирование и отмену

Сценарий `ramping-arrival-rate`: от 5 до 10, затем до **20 жизненных циклов бронирования в секунду** с удержанием максимальной ступени 2 минуты, общая заданная длительность 4 минуты.

Каждая итерация: `POST /api/v1/bookings/` → `PATCH /api/v1/bookings/{id}/` → `POST /api/v1/bookings/{id}/cancel/`. Проверяется ответ, сохранение изменённого названия и конечный статус `cancelled`. Учётные записи и интервалы изолированы; операции проводились только с синтетическими данными.

- **3 750 завершённых жизненных циклов**, `created=3750`, `edited=3750`, `cancelled=3750`.
- Таким образом выполнено **11 250 успешных операций записи** (по 3750 каждого типа).
- **11 350 HTTP-запросов** с учётом начальных авторизаций отдельных VU; фактическая средняя скорость за всё окно **46,90 HTTP req/s** (профиль ramp-up, итоговая длительность включает завершение итераций).
- **18 750 / 18 750 checks passed** (100,00%), **0 HTTP-ошибок**, **0 dropped iterations**, **0 write login failures**.
- Задержка HTTP: средняя **8,31 мс**, p95 **10,40 мс**, максимум **156,82 мс**. Пороги p95 менее 1,5 секунды и p99 менее 3 секунд пройдены.
- Максимум **40 реально активных VU** в ходе теста записи; резерв k6 — 50 VU.
- Итог k6: **PASS**, код выхода `write_edit_exit_code=0`.

**Интерпретация:** верхняя ступень означала ~20 полных жизненных циклов/с, то есть около 60 API write-запросов/с. Это не утверждение о постоянных 60 write RPS на протяжении всех 4 минут; фактическое среднее по окну ниже из-за постепенного нарастания нагрузки.

## 3. Ресурсы Docker (снимки каждые ~5–7 секунд)

Максимальные **наблюдённые значения**, рассчитанные по `docker-stats.log`, а не гарантия фиксированного потребления:

| Контейнер | Пиковая RAM | Пиковая CPU, % Docker |
|---|---:|---:|
| `officeflow-app-1` | **267,7 MiB** | **108,76%** |
| `officeflow-db-1` | **72,2 MiB** | **11,67%** |
| `officeflow-redis-1` | **5,30 MiB** | **3,49%** |
| `officeflow-proxy-1` | **11,21 MiB** | **2,20%** |

Docker CPU может превышать 100%, если использовано более одного логического ядра. Показания CPU/RAM относятся к эфемерному GitHub-hosted runner, не к произвольному VPS. Значения получены из периодических срезов и могут пропустить краткосрочные пики.

## 4. Дополнительная регрессия

- `quality` — **68 pytest passed**, покрытие именно `workspace.services` и `workspace.queries` — **91,67%**.
- `docker` — **Success**; включает браузерные acceptance-сценарии и предыдущие тесты изолированной записи.
- Утверждения о нагрузке относятся к `DEBUG=1` временной Compose-среде с синтетическими данными. После тестов volumes удалены.

## 5. Ограничения и следующие шаги

- **1000 независимых синтетических сессий подтверждены**, но не 1000 одновременно исполняемых HTTP-запросов; достигнутое среднее RPS включает разгон/снижение.
- Проверены около **60 write-запросов/с на максимальной ступени**, а не 100/200 RPS исключительно операций записи.
- Параметры тестового runner, тестовые данные, работа без публичного TLS и сравнительно короткое окно нельзя экстраполировать на production без повторного испытания.
- Долгосрочный **SLA/SLO 99,9% НЕ подтверждён**: нет публичного HTTPS-сервера и истории внешнего мониторинга за 30/90 дней. Подготовлены `scripts/uptime_probe.py`, `scripts/uptime_report.py`, `infra/uptime/` и `docs/UPTIME_MONITORING.md`, но измерение не запущено.
- Для повышения уверенности в промышленной эксплуатации нужны внешний хостинг, сетевой TLS smoke, off-host backup, реальные уведомления, длительный мониторинг, пользовательская приёмка.

**Вывод:** два запрошенных масштабных испытания завершились успешно и имеют проверяемые GitHub CI артефакты. Подготовлен механизм измерения доступности, но подтверждать SLA 99,9% без непрерывных внешних измерений нельзя.


## 6. PR #37 — дополнительный длительный прогон (21.11.2026)

Источник: [GitHub Actions run #449392](https://github.com/Ramig2007/OfficeFlow/actions/runs/44939237867), artifact `officeflow-scale-validation` (ID 14721991969). Проверенный commit: `232a2b95cfd6c52577ed93166eb0c29ac7b12d82`.

| Профиль | Фактический результат | Итог |
|---|---|---|
| 1000 независимых пользователей | 1000 VU, 41 291 HTTP requests, 0 HTTP errors, 100% checks, avg 10,21 мс, p95 8,81 мс | PASS |
| Create/edit/cancel | 3 750 полных циклов каждого типа, 11 350 HTTP requests, 0 HTTP errors, 0 dropped iterations, p95 13,26 мс | PASS |
| Mixed target 100 RPS | 33 686 HTTP requests, 93,08 RPS average over the whole window including ramp-up; p95 27,19 мс, p99 77,04 мс, 0 HTTP errors, 0 dropped iterations | PASS |
| Authenticated read stress 150 RPS | 33 264 requests, фактически 109,25 RPS, 0 HTTP errors, checks 100%, но 11 739 dropped iterations; avg 3,13 с, p95 5,13 с, p99 6,04 с | FAIL — дополнительный стресс-профиль |

Во время 150 RPS профиля максимальные наблюдавшиеся значения Docker CPU: app **386,23%**, PostgreSQL **30,15%**, Redis **5,42%**, proxy **5,03%**. Это указывает на насыщение CPU Django/Gunicorn в данном CI runner; показатели не являются замером публичного Render.

**Интерпретация:** обязательный смешанный профиль с целевыми 100 RPS прошёл. Дополнительный read-only тест 150 RPS не прошёл, поэтому его нельзя выдавать за подтверждённую производительность. В следующем CI прогоне read-only acceptance выровнен по целевым 100 RPS, а пороги ужесточены до p95 <200 мс / p99 <500 мс; добавлены отдельные latency Trends для трёх HTML-маршрутов.


## 7. PR #37 CI #188 — повторная проверка 100 RPS acceptance

Источник: PR #37 CI run **#44942581093** (все три job: quality, scale-validation и docker — Success):  
https://github.com/Ramig2007/OfficeFlow/actions/runs/44942581093

Артефакт `officeflow-scale-validation` (ID `14722659567`) содержит исходные k6 logs, JSON summaries и Docker resource snapshots.

| Профиль | Результат | Итог |
|---|---|---|
| 1000 независимых пользователей | 1000/1000 успешных логинов, max 1000 VU, 41 288 HTTP requests, 0 HTTP errors, 100% checks, p95 11,08 мс | PASS |
| Create/edit/cancel | 3 749 полных циклов; 3 749 create + 3 749 edit + 3 749 cancel; 11 347 HTTP requests с авторизациями; 0 HTTP errors; 0 dropped iterations; p95 13,63 мс | PASS |
| Mixed target 100 RPS | 33 686 HTTP requests, 93,08 RPS average over the whole window including ramp-up; p95 27,36 мс, p99 209,02 мс; 0 HTTP errors; 0 dropped iterations | PASS |
| Authenticated read-only 100 RPS | 30 003 HTTP requests, 99,93 RPS average; 30 001/30 001 checks; p95 32,36 мс, p99 50,16 мс; 0 HTTP errors; 0 dropped iterations | PASS |

**Интерпретация:** 100 RPS read-only acceptance и mixed workload прошли на GitHub-hosted CI runner. Средняя интенсивность mixed-профиля за весь интервал составила 93,08 RPS из-за ramp-up/ramp-down; это не следует описывать как ровные 100 RPS в каждую секунду. Тесты не являются замером публичного Render Free.

Дополнительный read-only стресс на 150 RPS в предыдущем run #449392 не прошёл: 109,25 RPS, p95 5,13 с, p99 6,04 с и 11 739 dropped iterations. Этот результат сохранён как ограничение и не должен скрываться.


---

## 8. Main branch Scale Validation #3 — повторное подтверждение (22.11.2026)

Источник: [GitHub Actions run #44951299898](https://github.com/Ramig2007/OfficeFlow/actions/runs/44951299898), branch `main`, commit `4440bf8c5d7375237b9bcae1f6bb9e3717d48e1e`.  
Artifact: `officeflow-scale-validation`, ID `14727005489` (содержит k6 logs, JSON summaries, exit-codes.txt и Docker stats).

Все четыре k6 процесса завершились с кодом **0**. В логах каждый профиль помечен k6 как успешный; итоговый workflow job `Require all scale tests to pass` — Success. Все испытания выполнялись на одноразовом GitHub-hosted Docker Compose runner с синтетическими пользователями и тестовой БД. Публичный Render не нагружался.

| Профиль | Фактический результат | Итог |
|---|---|---|
| 1000 concurrent authenticated users | 1000/1000 login page checks и 1000/1000 login submissions; max 1000 VU, удержание 1000 VU на 3 минуты; 41 302 HTTP requests, 39 302 authenticated API iterations, 0 HTTP errors, 100% checks; p95 6,15 мс, max 273,36 мс | PASS |
| Booking create/edit/cancel | 3750 полных циклов; 3750 create + 3750 edit + 3750 cancel; 11 350 HTTP requests, 18 750/18 750 checks, 0 HTTP errors, 0 dropped iterations; p95 9,73 мс | PASS |
| Mixed target 100 RPS | 33 689 HTTP requests; 93,06 RPS average over full window including ramp-up/ramp-down; 26 369 authenticated reads и 2340 полных booking cycles; p95 12,46 мс, p99 18,77 мс; 0 HTTP errors, 0 dropped iterations; 38 069/38 069 checks | PASS |
| Authenticated read-only 100 RPS | 30 003 HTTP requests; 99,96 RPS average; 30 001/30 001 checks; p95 12,06 мс, p99 14,93 мс; 0 HTTP errors, 0 dropped iterations | PASS |

**Интерпретация:** 1000 независимых сессий, изолированный write lifecycle, смешанный профиль и authenticated read около 100 RPS повторно прошли на CI. Mixed-профиль усредняет ramp-up/ramp-down, поэтому 93,06 RPS — среднее за весь интервал, а не утверждение о ровно 100 RPS каждую секунду. 1000 VU не означает 1000 одновременных HTTP-запросов. Эти результаты не являются замером публичного Render Free.

Дополнительный read-only стресс на 150 RPS из предыдущего PR #37 прогона по-прежнему не пройден: 109,25 RPS, p95 5,13 с, p99 6,04 с и 11 739 dropped iterations. Этот результат остаётся явным ограничением.
