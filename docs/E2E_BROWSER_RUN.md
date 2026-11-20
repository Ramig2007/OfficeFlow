# OfficeFlow: браузерные E2E-тесты

## Назначение

`e2e/browser_smoke.py` открывает реальный Chromium, проверяет анонимный редирект, вход через HTML-форму, панель, каталог, переход на карточку переговорной, VIP-фильтр, недельное расписание, историю, серверную блокировку административных маршрутов для сотрудника и мобильный каталог.

Это **read-only smoke-test**: он **не создаёт, не изменяет и не отменяет** бронирования. Отдельный `e2e/test_user_journey.py` содержит сценарий создания и отмены; его следует запускать только на изолированном демостенде.

## Подтверждённый локальный прогон — 19.11.2026

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
