# OfficeFlow — внешние уведомления, мониторинг и резервирование

**Публичный сервис:** https://officeflow-x6ay.onrender.com/  
**Проверка готовности:** https://officeflow-x6ay.onrender.com/health/ready/  
**Среда:** Render Free (Frankfurt) + Neon Free (Frankfurt, PostgreSQL, direct connection). Пользователь подтвердил состояние Render **Live**, успешный вход и создание переговорных 21.11.2026.

Этот документ разделяет то, что уже подтверждено, что автоматизировано в репозитории и какие действия требуют внешних аккаунтов и секретов. Пароли, connection strings, API keys и webhook URLs с токенами нельзя добавлять в Git или отправлять в чат.

## 1. Внешние уведомления о доступности — UptimeRobot

Для публичного Render-сервиса используется независимый мониторинг, а не внутренний Prometheus. В бесплатном плане UptimeRobot доступны до 50 мониторов и проверки каждые 5 минут; уведомления по email можно включить через Alert Contacts. Актуальные ограничения: [UptimeRobot pricing](https://uptimerobot.com/pricing/) и [monitoring interval](https://help.uptimerobot.com/en/articles/11360876-what-is-a-monitoring-interval-in-uptimerobot).

### Создание монитора

1. Создайте аккаунт на https://uptimerobot.com/ и подтвердите email.
2. В панели нажмите **Add New Monitor**.
3. Выберите **HTTP(s)**.
4. Укажите:
   - Friendly Name: `OfficeFlow Production — readiness`
   - URL: `https://officeflow-x6ay.onrender.com/health/ready/`
   - Monitoring Interval: **5 minutes** (Free).
5. В **Alert Contacts** добавьте и подтвердите свой email.
6. Сохраните монитор и убедитесь, что его состояние **Up**.
7. Не создавайте дополнительные мониторы без необходимости: один readiness monitor достаточно для учебной демонстрации и проверяет приложение вместе с критической зависимостью Neon.

UptimeRobot проверяет публичный HTTPS-маршрут извне. Проверка readiness должна возвращать HTTP 200. На Free доступны персональный email contact и бесплатные push-уведомления через мобильное приложение; контакт нужно явно назначить монитору. Telegram-интеграция доступна на платном Solo, а webhook-интеграция — на Team; см. [notification channels](https://help.uptimerobot.com/en/articles/11360978-understanding-notification-channels) и [mobile push](https://help.uptimerobot.com/en/articles/17662644-uptimerobot-mobile-app-push-notifications). Сохраните дату и время включения монитора — это начало измерительного окна.

### Период наблюдения для сдачи практики

- **24 часа — минимальная цель** (около 288 проверок при интервале 5 минут).
- **48 часов — рекомендуемая цель** (около 576 проверок); собирайте столько, сколько реально успеете до сдачи.
- 5-минутный интервал не видит кратковременные сбои между пробами. Это внешняя демонстрация наблюдения, а не договорная гарантия SLA.
- Перед сдачей сохраните скриншоты статуса Up/Down, uptime за фактический период, даты начала/окончания, число проверок и историю событий/инцидентов.
- Формулировка в отчёте должна содержать фактическую длительность. **Не называйте 24–48 часов подтверждением месячного или годового SLA 99,9%.**

Render Free засыпает после 15 минут без входящего трафика, поэтому 5-минутные проверки будут удерживать сервис активным. За 24–48 часов мониторинг израсходует примерно 24–48 Free instance hours. У Render лимит **750 Free instance hours на весь workspace за календарный месяц**; перед запуском проверьте совместный расход в Render Dashboard → Billing → Monthly included usage, особенно если в workspace работают другие Free web services. Источник: [Render Free limitations](https://render.com/docs/free).

## 2. Реальный получатель уведомлений Prometheus / Alertmanager — Telegram

Prometheus, Grafana и Alertmanager из `compose.yaml` входят в локальный Docker Compose observability-профиль. Они **не развёрнуты внутри Render Free** и не получают метрики публичного Render-сервиса автоматически. UptimeRobot отдельно контролирует публичный Render URL; по пользовательскому скриншоту монитор уже Up и накопил 14 ч 52 мин наблюдения.

В репозитории настроен генератор `scripts/render_alertmanager_config.py`: он поддерживает native Telegram receiver и дополнительный HTTPS webhook. Без настроек сохраняется безопасный `null-receiver`; CI проверяет корректность Telegram-конфигурации через `amtool check-config`.

### 2.1 Создать Telegram-бота и получить chat ID

1. В Telegram откройте [@BotFather](https://t.me/BotFather), отправьте `/newbot` и выполните инструкции.
2. Сохраните выданный **bot token**. Не отправляйте его в чат и не добавляйте в GitHub.
3. Откройте созданного бота по ссылке, нажмите **Start** и отправьте ему `/start`.
4. В PowerShell на своём компьютере выполните:

```powershell
$token = Read-Host "Вставьте Telegram bot token (ввод не публикуйте)"
$updates = Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/getUpdates"
$updates.result[-1].message.chat.id
```

Сохраните числовой `chat.id`. Если хотите получать уведомления в группе, добавьте туда бота, отправьте команду и получите ID группы (он обычно отрицательный).

### 2.2 Включить Telegram в локальном Docker Compose

В локальном `.env` (не в `.env.example`) добавьте:

```ini
ALERTMANAGER_TELEGRAM_BOT_TOKEN=ВАШ_ТОКЕН_БОТА
ALERTMANAGER_TELEGRAM_CHAT_ID=ВАШ_CHAT_ID
```

Не добавляйте реальные значения в Git. Генератор записывает конфигурацию в закрытый Docker named volume `alertmanager_config`; токен не печатается в лог.

Пересоздайте observability-профиль:

```powershell
docker compose --profile observability up -d --build --force-recreate
docker compose logs --tail=50 alertmanager-config alertmanager
```

### 2.3 Отправить контрольное уведомление

Когда Alertmanager запущен, выполните в PowerShell:

```powershell
$start = (Get-Date).ToUniversalTime()
$end = $start.AddMinutes(2)
$payload = @(
  @{
    labels = @{ alertname = "OfficeFlowTestAlert"; severity = "info" }
    annotations = @{
      summary = "OfficeFlow: тестовое уведомление"
      description = "Проверка фактической доставки из Alertmanager в Telegram."
    }
    startsAt = $start.ToString("yyyy-MM-ddTHH:mm:ssZ")
    endsAt = $end.ToString("yyyy-MM-ddTHH:mm:ssZ")
    generatorURL = "http://localhost:9090/alerts"
  }
) | ConvertTo-Json -Depth 6

Invoke-RestMethod -Uri "http://localhost:9093/api/v2/alerts" -Method Post -ContentType "application/json" -Body $payload
```

Закрытым считается только фактический результат: сообщение `OfficeFlow: тестовое уведомление` пришло в указанный Telegram chat. При отсутствии сообщения проверьте `docker compose logs --tail=100 alertmanager` и правильность bot token/chat ID.

Этот тест подтверждает доставку тестового события из локального Alertmanager. Он **не означает**, что Alertmanager автоматически собирает метрики публичного Render: для этого нужен постоянно работающий внешний Prometheus с доступным источником метрик. Внешние уведомления о доступности самого Render обеспечиваются отдельным UptimeRobot monitor.

## 3. Ежедневный Neon backup в Yandex Object Storage

Для Render + Neon используется GitHub Actions: Render Free не предоставляет постоянный systemd host для расписания облачной БД. Workflow хранит PostgreSQL dump во внешнем приватном S3-совместимом бакете Yandex Object Storage.

- файл: `.github/workflows/backup-neon-yandex.yml`;
- расписание: ежедневно в **02:15 UTC**;
- ручной запуск: GitHub → **Actions** → **OfficeFlow Neon Off-site Backup** → **Run workflow**;
- источник: Neon direct PostgreSQL connection;
- формат: custom PostgreSQL dump;
- проверка: `pg_restore --list`, затем полный restore в отдельный временный PostgreSQL 18 контейнер;
- удалённая копия: приватный Yandex Object Storage bucket через S3 API (`https://storage.yandexcloud.net`);
- после загрузки workflow скачивает dump и checksum обратно и сверяет SHA-256;
- дампы не публикуются как GitHub Actions artifacts.

### 3.1 Создать bucket в Yandex Object Storage

1. Откройте https://console.yandex.cloud/ и войдите в Yandex ID.
2. Убедитесь, что у облака есть активный платёжный аккаунт со статусом `ACTIVE` или `TRIAL_ACTIVE`. Для физических лиц доступные способы оплаты и требования зависят от фактического резидентства: [способы оплаты Yandex Cloud](https://yandex.cloud/ru/docs/billing/payment/payment-methods-individual). Не указывайте фиктивный адрес или страну.
3. Выберите облако и каталог (folder), откройте **Storage → Object Storage** и создайте bucket с именем `officeflow-backups` (если имя занято — добавьте короткий суффикс).
4. Выберите регион/локацию, доступную для вашего облака, и класс хранения **Standard**.
5. Оставьте публичный доступ выключенным. Не включайте anonymous read/list и не публикуйте объекты.
6. Запишите имя bucket. Endpoint S3 API: `https://storage.yandexcloud.net`; регион подписи AWS CLI: `ru-central1`.
7. Настройте Lifecycle для удаления старых объектов через 30 дней, если доступно в настройках bucket. Это ограничивает накопление хранения; проверьте правило после создания.

### 3.2 Создать отдельную учётную запись и ключ S3

1. В **Identity and Access Management → Service accounts** создайте отдельный service account, например `officeflow-backup`.
2. Назначьте ему роль `storage.editor` на нужный каталог или, если консоль позволяет, только на bucket `officeflow-backups`. Не используйте owner/admin-учётную запись для GitHub Actions.
3. Для service account создайте **Static access key**.
4. Сохраните `key_id` и `secret` в менеджере паролей сразу после создания: secret показывается только при выпуске ключа и повторно может быть недоступен.
5. Не отправляйте ключи в чат, issue, PR или репозиторий. Официальная инструкция: [S3 API Yandex Object Storage](https://yandex.cloud/ru/docs/storage/s3/).

### 3.3 Добавить GitHub Actions secrets и variables

В GitHub откройте репозиторий → **Settings → Secrets and variables → Actions**.

Добавьте в **Secrets**:

| Имя | Значение |
|---|---|
| `NEON_CONNECTION_STRING` | Direct connection string из Neon для production database; не pooled connection |
| `YC_ACCESS_KEY_ID` | `key_id` статического ключа service account Yandex |
| `YC_SECRET_ACCESS_KEY` | `secret` статического ключа service account Yandex |

Добавьте в **Variables**:

| Имя | Значение |
|---|---|
| `YC_BUCKET` | Точное имя приватного bucket, например `officeflow-backups` |
| `YC_PREFIX` | `officeflow/daily` (необязательно; префикс объектов внутри bucket) |

Endpoint и регион уже заданы в workflow: `https://storage.yandexcloud.net` и `ru-central1`. Для `NEON_CONNECTION_STRING` используйте **Direct connection**, не строку с `-pooler`; connection string остаётся только в GitHub Secret.

### 3.4 Запустить и проверить

После добавления всех трёх secrets и обязательной variable:

1. Откройте **Actions → OfficeFlow Neon Off-site Backup**.
2. Нажмите **Run workflow** на ветке `main`.
3. Дождитесь завершения job.
4. В логах должны присутствовать:
   - `RESTORE_TEST_OK` — дамп восстановлен в отдельную временную PostgreSQL;
   - `OFFSITE_BACKUP_OK` — копия загружена в Yandex Object Storage, скачана обратно и прошла SHA-256.
5. Откройте bucket и убедитесь, что появились `.dump` и `.dump.sha256` в `officeflow/daily/`.
6. Сохраните ссылку на успешный run и скриншот списка объектов. После этого можно считать первую удалённую копию подтверждённой.

Если secrets/variables ещё не добавлены, workflow безопасно завершится с пометкой **backup not configured** и ничего не скачает из Neon/не загрузит в bucket. Это не является успешным резервным копированием.

### 3.5 Ограничения

- GitHub Actions cron может запускаться с задержкой; проверяйте историю запусков.
- Ежедневный backup задаёт плановый RPO около 24 часов, но фактический RPO зависит от времени последней успешной копии.
- SHA-256 подтверждает целостность переданного объекта, а полный restore в disposable DB подтверждает восстановимость дампа в тестовой среде.
- Не восстанавливайте дамп поверх рабочей Neon DB во время автоматической проверки.
- Хранилище тарифицируется по условиям Yandex Cloud; до включения регулярных копий проверьте цены, установите бюджет/уведомления о расходах и Lifecycle retention.
- Первая удалённая копия считается настроенной только после успешного ручного workflow run с обоими маркерами.

## 4. Текущий статус

| Компонент | Статус |
|---|---|
| Render + Neon production URL | Пользователь подтвердил Live, вход и создание переговорных |
| UptimeRobot monitor | Создан, HTTP(s), проверка каждые 5 минут; на пользовательском скриншоте статус Up, 14 ч 52 мин работы, 99,931% за отображаемые 24 часа, один инцидент 503 длительностью 37 секунд; среднее время ответа 165 ms |
| Внешние email alerts | Будут включены через Alert Contacts UptimeRobot после подтверждения email |
| Alertmanager Telegram | Native receiver поддерживается кодом и проверяется CI; bot token/chat ID и фактическое test delivery ещё требуют настройки владельцем |
| GitHub Actions backup workflow | Добавлен; требует Neon/Yandex secrets и variables |
| Yandex Object Storage bucket | Требует создания владельцем |
| Первая удалённая копия | Не подтверждена до успешного workflow run |
| Внешнее наблюдение доступности | Наблюдение уже идёт; продолжить до фактических 24–48 часов и сохранить финальный скриншот. Короткий период не подтверждает месячный SLA 99,9% |

## 5. Безопасность

- Не присылайте в чат `NEON_CONNECTION_STRING`, пароли, Yandex S3 secret key, Telegram token или webhook URL с токеном.
- Все секреты вводите напрямую в Render, GitHub Actions Secrets или соответствующий внешний сервис.
- Не делайте Yandex bucket публичным.
- Не храните резервные дампы в GitHub repository или обычных CI artifacts.
- Для проверки/восстановления используйте отдельную временную PostgreSQL, не production.
