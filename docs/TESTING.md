# Стратегия тестирования и критерии качества

## Уровни

| Уровень | Инструмент | Проверяемые сценарии | Доказательство |
|---|---|---|---|
| Unit | pytest + Django тест DB | valid window, 1–4 часа, overlap, pending, отмена, роли | CI log |
| Integration | APIClient + PostgreSQL | REST 201/400/403/404/409, CSV, IDOR, audit | CI log |
| Concurrency | 2 threads + PostgreSQL | только одна запись на занятый слот | CI log + test trace |
| Browser E2E | Playwright | login, создание и отмена из UI | screenshot/log |
| Load | k6 | 100 RPS, 200 RPS, проверка HTTP latency/error | exported k6 JSON |
| Static | Ruff, Django checks, dependency audit | ошибки кода и конфигурации | CI log |
| Security | ручные тесты и автоматизированные API negative cases | CSRF, IDOR, privilege escalation, CSV injection | протокол |
| UX | desktop/tablet/mobile | кликабельность, масштаб, таблицы, сообщения | фото/скриншоты |

## Запуск unit и integration в CI

`.github/workflows/ci.yml` запускает Postgres 16 и Redis 7 в качестве job services. Порядок: installation → Ruff → Django check → migration drift check → pytest/coverage → Docker build/push main. Команды:

```powershell
python -m pytest workspace/tests -q --cov=workspace.services --cov=workspace.queries --cov-report=term-missing --cov-fail-under=70
ruff check .
python manage.py check
python manage.py makemigrations --check --dry-run
```

**Порог ≥70% применяется только к критическим доменным модулям `services` и `queries`, а не ко всему репозиторию.** Если преподаватель потребует охват всех критических модулей, расширьте `--cov` на `api`/`models`, добавьте тесты и приложите отчёт покрытия.

## E2E (только после локального запуска демостенда)

```powershell
pip install -r requirements-e2e.txt
playwright install chromium
$env:BASE_URL = "http://localhost:8080"
$env:DEMO_PASSWORD = "<значение DEMO_PASSWORD из .env>"
python -m pytest e2e -q -m e2e
```

Перед E2E выполните `seed_demo`. Сценарий создаёт и отменяет реальную тестовую бронь. Если дата/слот уже занят, исправьте тестовые данные или используйте новую тестовую БД. Прогон требует установленный браузер и работающий сайт.

## Поведение при одновременной записи

Поточный тест с `Barrier(2)` одновременно создаёт две записи в одну комнату/интервал. В ожидаемом результате ровно один `created`, другой `conflict`, а в базе только одна активная запись. Проверка пропускается на SQLite; PG необходимо подтвердить в CI.

## План нагрузочных испытаний

1. Baseline liveness: `k6 run -e TARGET_RPS=100 -e DURATION=2m scripts/loadtest.js` (100 RPS).
2. Повторить baseline при 200 RPS, снять метрики Nginx/Django/DB/Redis.
3. Создать расширенный k6 сценарий с authenticated cookie/CSRF, включив 70% GET расписания, 10% GET комнаты, 20% POST booking; использовать заранее подготовленные интервалы.
4. Снимать p50/p95, errors, 409 отдельно от 5xx, очереди и соединения PG.
5. Построить графики RPS→p95 и RPS→error rate, оценить насыщение.
6. Искусственно ухудшить БД (например, ресурсы/задержка на изолированном стенде), проверить 503/alert и восстановление. **Не проводить fault injection в рабочей базе.**

Цели: availability ≥99,9% (по корректно выбранному периоду), p95 ≤200 мс и error rate ≤0,1%. Результат ниже цели — дефект или ограничение, а не основание переписать цель. Сохранить `k6 --summary-export`, Prometheus snapshots и конфигурацию окружения.

## Дополнительные ручные проверки

- POST на бронь длительностью 0.5/5 часов → 400.
- Бронирование в прошлом → 400.
- Два соседних интервала → оба разрешены.
- Два пересекающихся → 409; PG ограничение реально существует.
- VIP → pending без возможности самосогласования.
- У сотрудника GET чужой `/api/v1/bookings/{id}/` → 404.
- У сотрудника POST чужой `cancel/` → 404.
- У сотрудника POST `approve/` → 403.
- POST с неожиданным `status`/`creator` не меняет бизнес-статус.
- CSRF POST из браузера без токена и неаутентифицированные API requests отвергаются.
- Реальные CSV с формулой Excel безопасны, фильтры дат корректны.
- Создание/деактивация комнаты, редактирование профиля, повышение/понижение роли.
- Проверить responsive ширины 375, 768, 1440 px; расписание/таблицы горизонтально прокручиваются, кнопки доступны.
- Проверить `collectstatic` и отсутствие ошибок загрузки CSS/JS.

## Реестр дефектов и приоритеты

**P0:** потеря данных, обход ролей, неконтролируемая двойная бронь. **P1:** API/API/UI функция недоступна, неверный статус VIP. **P2:** неполное сообщение/неверная фильтрация. **P3:** визуальное отклонение без влияния на сценарий. Регистрировать в GitHub Issues с окружением, шагами, Expected/Actual, приоритетом, log/screenshot, commit исправления и повторным тестом.
