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
7. Дополнительно можно создать второй HTTP(s)-монитор для `https://officeflow-x6ay.onrender.com/accounts/login/`, чтобы контролировать доступность пользовательской страницы, а не только readiness endpoint.

UptimeRobot проверяет публичный HTTPS-маршрут извне. Проверка readiness должна возвращать HTTP 200. На Free доступны персональный email contact и бесплатные push-уведомления через мобильное приложение; контакт нужно явно назначить монитору. Telegram-интеграция доступна на платном Solo, а webhook-интеграция — на Team; см. [notification channels](https://help.uptimerobot.com/en/articles/11360978-understanding-notification-channels) и [mobile push](https://help.uptimerobot.com/en/articles/17662644-uptimerobot-mobile-app-push-notifications). Сохраните дату и время включения монитора — это начало измерительного окна.

### Как подтвердить 99,9%

Для сдачи учебной практики 30-дневное ожидание не требуется. Целевое окно — **24–48 часов**: 24 часа (около 288 проверок при интервале 5 минут) — минимально приемлемая демонстрация; 48 часов (около 576 проверок) — рекомендуемая цель, если монитор включён 21 ноября и сдача проходит 23 ноября. Если до сдачи остаётся меньше времени, сохраните фактически накопленный период и явно укажите его длительность.
- Free-план проверяет раз в 5 минут, поэтому кратковременные сбои между пробами могут быть не замечены. Такой результат — внешняя оценка доступности за конкретный короткий период, а не договорная гарантия SLA.
- Перед сдачей сохраните скриншоты текущего статуса, периода/истории, uptime и зарегистрированных инцидентов (если они были), а также дату и время начала/окончания наблюдения.
- Формулировка для отчёта: **«Проведено внешнее наблюдение доступности публичного сервиса OfficeFlow в течение [фактическая длительность] с интервалом проверки 5 минут с помощью UptimeRobot. За период зафиксировано [N] проверок, доступность составила [значение]%, зарегистрировано [N] инцидентов. Полученные данные характеризуют только период наблюдения и не являются подтверждением SLA 99,9% за месяц или год»**.

Render Free засыпает после 15 минут без входящего трафика. Проверка UptimeRobot раз в 5 минут будет удерживать сервис активным и расходовать Free instance hours. Render выделяет **750 Free instance hours на весь workspace за календарный месяц**, а не на каждый сервис; один постоянно работающий сервис потребляет примерно 720 часов за 30 дней или 744 часа за 31 день. Если в том же workspace работает ещё один Free web service (например, MeetingRoomBooking), суммарный расход может превысить лимит и Render приостановит все Free web services до следующего месяца. Перед включением 5-минутного монитора проверьте Render Dashboard → Billing → Monthly included usage и число других Free services. Частые проверки не превращают Free в SLA. Время проб, инциденты и ограничения тарифа нужно указывать в итоговом отчёте. Источник: [Render Free limitations](https://render.com/docs/free).

## 2. Внешние уведомления Prometheus / Alertmanager

Prometheus, Grafana и Alertmanager из `compose.yaml` входят в локальный Docker Compose observability-профиль. Они **не развёрнуты внутри Render Free** и не получают метрики публичного Render-сервиса автоматически.

- Правила Prometheus находятся в `infra/prometheus/alerts.yml`.
- В Alertmanager реализован безопасный HTTPS webhook renderer: `scripts/render_alertmanager_config.py`.
- Если `ALERTMANAGER_WEBHOOK_URL` не задан, используется `null-receiver`: правила вычисляются, но уведомления человеку не доставляются.
- Чтобы включить webhook в локальном стенде, задайте `ALERTMANAGER_WEBHOOK_URL` и при необходимости `ALERTMANAGER_WEBHOOK_BEARER_TOKEN` в локальном `.env`, затем пересоздайте observability-профиль:

```powershell
docker compose --profile observability up -d --build
docker compose logs --tail=50 alertmanager-config alertmanager
```

Используйте только HTTPS endpoint, совместимый с форматом webhook Alertmanager. URL и Bearer token хранятся только в локальном `.env` или в секретном хранилище провайдера. Не коммитьте их. Реальную доставку нужно подтвердить тестовым alert и полученным сообщением.

Для внешнего контроля публичного Render-сервиса email-оповещения UptimeRobot независимы от локального Alertmanager. Если нужны именно Telegram-уведомления от Alertmanager, потребуется отдельный Telegram webhook/relay и секреты; это не следует считать настроенным до проверки доставки.

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
| Alertmanager webhook | Код и тесты есть; endpoint/получатель ещё не выбран и доставка не подтверждена |
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
