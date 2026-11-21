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

Prometheus, Grafana и Alertmanager из `compose.yaml` входят в локальный Docker Compose observability-профиль. Они **не развёрнуты внутри Render Free** и не получают метрики публичного Render-сервиса автоматически. UptimeRobot отдельно контролирует публичный Render URL.

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

## 3. Ежедневный Neon backup в Cloudflare R2

Для Render + Neon нельзя использовать Compose/systemd backup timer как расписание облачной БД: Render Free не предоставляет постоянный systemd host. Поэтому добавлен GitHub Actions workflow:

- файл: `.github/workflows/backup-neon-r2.yml`;
- расписание: ежедневно в **02:15 UTC**;
- ручной запуск: GitHub → **Actions** → **OfficeFlow Neon Off-site Backup** → **Run workflow**;
- источник: Neon direct PostgreSQL connection;
- формат: custom PostgreSQL dump;
- проверка: `pg_restore --list`, затем полный restore в отдельный временный PostgreSQL 17 контейнер;
- удалённая копия: приватный Cloudflare R2 bucket;
- после загрузки workflow скачивает dump и checksum обратно и сверяет SHA-256;
- дампы не публикуются как GitHub Actions artifacts.

### 3.1 Создать R2 bucket

1. Откройте https://dash.cloudflare.com/ → **Storage & databases → R2**.
2. Включите R2 для аккаунта и создайте приватный bucket, например `officeflow-backups`.
3. Не включайте публичный доступ к bucket.
4. Создайте S3 API token с **Object Read & Write** только для этого bucket. Не используйте Global API Key или токен администратора.
5. Сохраните Access Key ID и Secret Access Key в менеджере паролей. Secret Access Key показывается при создании; повторно получить его может быть нельзя.
6. Скопируйте Account ID из Cloudflare dashboard.
7. Настройте Lifecycle rule для удаления старых объектов, например через **30 дней**. Если нужен более долгий срок, измените правило осознанно.
8. Cloudflare R2 имеет включённую защиту данных и бесплатный месячный объём Standard storage до 10 GB-month, 1 млн Class A и 10 млн Class B операций; превышение бесплатных лимитов тарифицируется. Сверяйте актуальные значения: [R2 pricing](https://developers.cloudflare.com/r2/pricing/).

### 3.2 Добавить GitHub Actions secrets и variables

В GitHub откройте репозиторий → **Settings → Secrets and variables → Actions**.

Добавьте в **Secrets**:

| Имя | Значение |
|---|---|
| `NEON_CONNECTION_STRING` | Direct connection string из Neon для той же базы, что использует Render; не pooled connection |
| `R2_ACCESS_KEY_ID` | S3 Access Key ID из Cloudflare R2 |
| `R2_SECRET_ACCESS_KEY` | S3 Secret Access Key из Cloudflare R2 |

Добавьте в **Variables**:

| Имя | Значение |
|---|---|
| `R2_ACCOUNT_ID` | Cloudflare Account ID |
| `R2_BUCKET` | Имя созданного приватного bucket, например `officeflow-backups` |
| `R2_PREFIX` | `officeflow/daily` (необязательно; это префикс внутри bucket) |

Для `NEON_CONNECTION_STRING` используйте **Direct connection**, не строку с `-pooler`. Убедитесь, что параметр SSL в URI — `sslmode=verify-full`. Используйте то же значение только через GitHub Secret; не вставляйте его в файл репозитория, issue, PR или чат.

### 3.3 Запустить и проверить

После добавления всех трёх secrets и двух обязательных variables:

1. Откройте **Actions → OfficeFlow Neon Off-site Backup**.
2. Нажмите **Run workflow** на ветке `main`.
3. Дождитесь завершения job.
4. В логах должны присутствовать:
   - `RESTORE_TEST_OK` — дамп восстановлен в отдельную временную PostgreSQL;
   - `OFFSITE_BACKUP_OK` — копия загружена в R2, скачана обратно и прошла SHA-256.
5. Откройте R2 bucket и убедитесь, что там появились `.dump` и `.dump.sha256` в `officeflow/daily/`.
6. После успешного первого запуска проверьте Lifecycle rule и запланируйте отдельную ручную DR-проверку по `docs/OFFSITE_BACKUP.md`.

Если secrets/variables ещё не добавлены, workflow безопасно завершится с пометкой **backup not configured** и ничего не скачает из Neon/не загрузит в R2. Это не является успешным резервным копированием.

### 3.4 Ограничения

- GitHub Actions — внешний планировщик, но его cron может запускаться с задержкой; проверяйте историю запусков.
- Ежедневный backup задаёт плановый RPO около 24 часов, но фактический RPO зависит от времени последней успешной копии.
- SHA-256 подтверждает целостность переданного объекта, а полный restore в disposable DB подтверждает читаемость/восстановимость дампа в тестовой среде.
- Не восстанавливайте дамп поверх рабочей Neon DB во время автоматической проверки.
- Настоящий bucket, credentials, успешная первая загрузка и расписание считаются настроенными только после успешного ручного workflow run.

## 4. Текущий статус

| Компонент | Статус |
|---|---|
| Render + Neon production URL | Пользователь подтвердил Live, вход и создание переговорных |
| UptimeRobot monitor | Инструкция готова; аккаунт, email contact и первый Up ещё требуют настройки владельцем |
| Внешние email alerts | Будут включены через Alert Contacts UptimeRobot после подтверждения email |
| Alertmanager Telegram | Native receiver поддерживается кодом и проверяется CI; bot token/chat ID и фактическое test delivery ещё требуют настройки владельцем |
| GitHub Actions backup workflow | Добавлен; требует Neon/R2 secrets и variables |
| Cloudflare R2 bucket | Требует создания владельцем |
| Первая удалённая копия | Не подтверждена до успешного workflow run |
| 30-дневная доступность | Начнёт измеряться после включения внешнего монитора; SLA 99,9% пока не подтверждён |

## 5. Безопасность

- Не присылайте в чат `NEON_CONNECTION_STRING`, пароли, R2 Secret Access Key, Telegram token или webhook URL с токеном.
- Все секреты вводите напрямую в Render, GitHub Actions Secrets или соответствующий внешний сервис.
- Не делайте R2 bucket публичным.
- Не храните резервные дампы в GitHub repository или обычных CI artifacts.
- Для проверки/восстановления используйте отдельную временную PostgreSQL, не production.
