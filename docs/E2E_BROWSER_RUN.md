# OfficeFlow: браузерные E2E-тесты

## Назначение

`e2e/browser_smoke.py` открывает реальный Chromium, проверяет анонимный редирект, вход через HTML-форму, панель, каталог, переход на карточку переговорной, VIP-фильтр, недельное расписание, историю, серверную блокировку административных маршрутов для сотрудника и мобильный каталог.

До PR #16 скрипт являлся read-only smoke-тестом. С PR #16 он выполняет **21 acceptance-сценарий**, включая создание/редактирование/отмену брони, VIP approve/reject, управление переговорными и 375/768 px. Модифицирующая часть допустима **только на одноразовой CI-базе**, которая уничтожается после job. Старые результаты 9/9 ниже оставлены как историческое свидетельство; текущий проверенный результат — **21/21** (PR CI #93).

## Исторический read-only локальный прогон — 19.11.2026

Фактический результат, предоставленный пользователем:

```text
PASS 1: anonymous redirect
PASS 2: browser login
PASS 3: dashboard
PASS 4: room detail navigation
PASS 5: room filter
PASS 6: schedule
PASS 7: bookings history
PASS 8: permissions (HTTP 403)
PASS 9: mobile catalogue
RESULT: 9/9 browser checks passed
No bookings or users were modified.
```

Скриншоты локального прогона:
- `e2e/artifacts/dashboard-desktop.png`
- `e2e/artifacts/rooms-mobile.png`

Эти файлы создаются в локальной папке `e2e/artifacts/` и исключены из Git. Их нужно приложить к итоговому отчёту вручную, если они сохранились на компьютере.

## Исторический автоматический smoke-прогон в GitHub Actions — 20.11.2026

PR #13 добавил Playwright Chromium smoke в Docker job CI. Main run #73 после merge PR #13 завершился успешно:
- jobs `quality` и `docker` — **Success**;
- browser smoke — **9/9 checks passed**;
- проверены анонимный редирект, вход сотрудника, dashboard, карточка комнаты, VIP-фильтр, расписание, история, 403 для административных маршрутов и мобильный каталог;
- screenshot artifact `officeflow-browser-e2e` успешно загружен (retention 7 дней).

CI использует отдельный временный Compose stack и тестовую PostgreSQL базу. Demo fixtures создаются только в этом окружении; после проверки контейнеры и volumes удаляются. Пароль demo employee передаётся только тестовому процессу как CI-only значение. Browser smoke не меняет бронирования.

## Запуск из PowerShell (в папке OfficeFlow)

1. Убедиться, что рабочий сайт запущен и `docker compose ps app` показывает `healthy`.
2. Установить `K6_USERNAME` и `K6_PASSWORD` в том же терминале:

```powershell
$env:K6_USERNAME = 'employee'
$secure = Read-Host 'Введите пароль employee' -AsSecureString
$env:K6_PASSWORD = [System.Net.NetworkCredential]::new('', $secure).Password
Remove-Variable secure
```

3. Собрать браузерный образ:

```powershell
docker build -f e2e/Dockerfile.browser -t officeflow-e2e e2e
```

4. Запустить:

```powershell
docker run --rm --ipc=host --network officeflow_internal --env K6_USERNAME --env K6_PASSWORD -e BASE_URL=http://proxy -v "${PWD}\e2e:/tests" officeflow-e2e
```

После завершения можно очистить пароль: `Remove-Item Env:\K6_PASSWORD`.

## Область действия и ограничения

- Проверяется только перечисленный smoke-набор; полный пользовательский сценарий записи проверяется отдельно.
- Нагрузка 200 RPS и конкурентная запись проверяются другими тестами.
- Доступность 99,9% и готовность к эксплуатации этим тестом не подтверждаются.
- Во время работы пароль находится в окружении временного контейнера; не отправлять скриншоты терминала с секретами.

## Актуальная версия: полный acceptance в CI (PR #16, 21.11.2026)

- PR CI run #93: https://github.com/Ramig2007/OfficeFlow/actions/runs/44821321505
- **21/21 браузерных проверок успешно**: роли и права, 375/768 px, бронирование create/edit/cancel, VIP approval/rejection, room create/edit/deactivate.
- Скриншоты dashboard, mobile и tablet входят в artifact `officeflow-browser-e2e`; файл `failure.png` формируется при сбое.
- Демо-данные изменяются только в контейнерном CI-стенде, затем Compose volumes уничтожаются.
- Полный протокол: `docs/VERIFICATION_2026-11-21.md`.
