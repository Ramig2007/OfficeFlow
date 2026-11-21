# OfficeFlow: бесплатный деплой на Render Free + Neon Free

**Назначение:** повторить подход проекта MeetingRoomBooking: **Render** запускает Django/Gunicorn, **Neon** хранит PostgreSQL, GitHub используется для исходного кода. Покупка VPS и домена не требуется: Render выдаёт поддомен `*.onrender.com` и HTTPS.

**Состояние:** файлы конфигурации подготовлены; фактическое создание и проверка облачной БД/сервиса требует подключённых аккаунтов Render и Neon. Не путайте успешную проверку Docker CI с настоящим облачным деплоем.

## 1. Что изменено и почему

| Компонент | Файл / способ | Замечание |
|---|---|---|
| Render Blueprint | `render.yaml` | Один Docker web service, Frankfurt, Free; в целях безопасности auto-deploy отключён |
| Render image | `Dockerfile.render` | Изолирован от существующего `Dockerfile` и локального `compose.yaml` |
| Render startup | `scripts/render-start.sh` | `collectstatic`, `migrate`, затем Gunicorn на `$PORT` |
| Конфигурация Django | `officeflow/settings_render.py` | DEBUG=0, HTTPS cookies, HSTS, Django sessions в PostgreSQL, прямой Neon/TLS |
| CSS/JS | WhiteNoise | Не нужны Nginx, Caddy или постоянный том |
| Redis | Не требуется | Сессии хранятся в Neon, кэш — локальный для одной инстанции; не подходит для масштабирования на много инстанций |
| `/metrics` | Недоступен извне | У Render прямой вход в Gunicorn без защищающего Nginx; endpoint не публикуется |
| Начальный администратор | `bootstrap_render_admin` | Одноразовое создание через переменные окружения; пароль существующего админа никогда не сбрасывается |

Для VPS/Docker Compose продолжает использоваться `officeflow.settings`, прежние Nginx/Caddy/Redis/Prometheus и исходная БД не изменяются.

## 2. Neon: новая PostgreSQL для OfficeFlow

1. Откройте https://console.neon.tech, создайте **отдельный проект OfficeFlow** на тарифе Free. Не используйте базу MeetingRoomBooking, чтобы не смешать схемы, миграции и данные.
2. По возможности выберите регион **AWS Europe (Frankfurt / eu-central-1)**, соответствующий Render Frankfurt.
3. Откройте Neon project → **Connect** и отключите **Connection pooling**, выбрав **Direct connection** (без `-pooler` в имени хоста). Приложение использует прямое подключение: оно также необходимо для миграций и работы с PostgreSQL GiST.
4. В карточке подключения сохраните у себя:
   - **host**: `ep-....eu-central-1.aws.neon.tech` → `NEON_HOST` (только хост, без `postgresql://` и порта);
   - **database** → `NEON_DATABASE` (часто `neondb`);
   - **role / user** → `NEON_USER` (часто `neondb_owner`);
   - **password** → `NEON_PASSWORD`.
5. Для Render + Neon используйте **точно тот пароль, который Neon выдал** для выбранной роли. Neon создаёт случайные пароли с не менее чем 60 битами энтропии; их длина может быть меньше 24 символов. Конфигурация `officeflow.settings_render` допускает такие пароли от **12 символов**, тогда как обычное production-развёртывание OfficeFlow по-прежнему требует минимум 24 символа. Не дописывайте символы к выданному Neon паролю: это вызовет `password authentication failed`. После сброса пароля замените `NEON_PASSWORD` в Render → Environment и сохраните изменения.
6. Подключение будет происходить с `sslmode=verify-full` и `sslrootcert=/etc/ssl/certs/ca-certificates.crt`: проверяются TLS-сертификат и соответствие имени сервера. Не отключайте проверку сертификата.

Важно: в OfficeFlow есть миграция `0002_postgres_overlap_guard`, создающая расширение `btree_gist` и PostgreSQL exclusion constraint для защиты от двойного бронирования. Используйте роль Neon, имеющую право на миграции и создание расширения. Проверьте в Render Logs, что миграция завершилась успешно.

**Диагностика TLS (Render):** если при `manage.py migrate` было `SSL error: certificate verify failed`, исправление использует явный системный CA-bundle Debian (`/etc/ssl/certs/ca-certificates.crt`), установленный через `ca-certificates` в `Dockerfile.render`. Проверка сертификата и hostname в режиме `verify-full` **сохраняется**. IPv6 `Network is unreachable` может появляться вместе с ошибками IPv4 и не является доказательством отсутствия соединения по IPv4. Успешный CI не проверяет настоящий TLS к Neon: подтвердите миграции на Render и `/health/ready/`. Не подменяйте сертификаты и не меняйте `sslmode` на `disable`/`require` для обхода проверки.

**Никогда не присылайте в чат пароль или полный URL Neon с паролем.**

## 3. Render: создать бесплатный Web Service

Самый простой путь через готовый Blueprint:

1. Откройте https://dashboard.render.com → **New** → **Blueprint**.
2. Подключите репозиторий `https://github.com/Ramig2007/OfficeFlow` (ветка `main`). Выберите конфигурацию `render.yaml`.
3. Render создаст один Docker Web Service с тарифом **Free** и регионом **Frankfurt**. Не создавайте Render Postgres: база уже размещена в Neon.
4. При первоначальной настройке Blueprint заполните четыре переменные `NEON_HOST`, `NEON_DATABASE`, `NEON_USER`, `NEON_PASSWORD`. Они обозначены `sync: false`, поэтому не сохраняются в файле репозитория.
5. `RENDER_SECRET_KEY` создаётся Render автоматически как стойкое 256-битное случайное значение. **Не удаляйте и не меняйте его при последующих деплоях** — это может сделать существующие сеансы недействительными.
6. Примените Blueprint, откройте сервис `officeflow` → **Events / Logs**. Дождитесь сборки Docker image и строк о миграциях. После успешного запуска сервис должен стать **Live**.

Альтернатива при ручном создании: Render → New → Web Service → GitHub OfficeFlow → **Language / Runtime: Docker**, **Dockerfile path: `./Dockerfile.render`**, **Instance Type: Free**, **Region: Frankfurt**, **Health Check Path: `/health/ready/`**. Добавьте `DJANGO_SETTINGS_MODULE=officeflow.settings_render`, `DEBUG=0`, `RENDER_SECRET_KEY` (сгенерированное стойкое значение минимум 40 символов), четыре `NEON_*` переменные. Docker-команда берётся из Dockerfile; Build и Start commands Python вручную не нужны.

В обоих вариантах `RENDER_EXTERNAL_HOSTNAME` автоматически содержит адрес вида `officeflow-xxxx.onrender.com`; по нему Django настраивает `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS`. Собственный домен не нужен. При добавлении собственного домена в будущем потребуется добавить его явно в Render Environment → `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS` (включая адрес Render, если он остаётся доступным).

## 4. Создать первого администратора на бесплатном Render

На Render Free нет интерактивной Shell / one-off job, поэтому первый администратор создаётся **один раз** при запуске приложения:

1. В Render Web Service откройте **Environment**.
2. Добавьте `BOOTSTRAP_ADMIN_USERNAME` — желаемый логин администратора.
3. Добавьте `BOOTSTRAP_ADMIN_PASSWORD` — **уникальный пароль от 16 символов**. Никогда не используйте значение `DEMO_PASSWORD` с локального стенда.
4. Выберите **Save, rebuild and deploy** либо инициируйте **Manual Deploy → Deploy latest commit**.
5. В логах появится `First administrator created successfully.` Откройте HTTPS-сайт, войдите через созданный логин.
6. Сразу после успешного входа **удалите обе BOOTSTRAP-переменные в Render** и сохраните изменения. Скрипт при повторных запусках не меняет пароль существующего администратора.

В новой облачной базе не будет локальных демонстрационных комнат и бронирований. Это нормально. Войдите администратором → **Управление переговорными**, создайте комнаты. **Не запускайте `seed_demo` с `DEBUG=0`**.

## 5. Проверка после деплоя

Вместо `officeflow-xxxx.onrender.com` подставьте реальный URL вашего Web Service.

- `https://...onrender.com/health/live/` → HTTP 200 `{"status":"alive"}`.
- `https://...onrender.com/health/ready/` → HTTP 200 `{"status":"ready"}`; иначе проверить Neon secrets/Logs/migrations.
- `https://...onrender.com/accounts/login/` → форма авторизации, CSS отображается.
- После входа проверить комнаты, расписание, создание/редактирование/отмену брони, VIP-модерацию, CSV.
- `https://...onrender.com/metrics` **не должен выдавать Prometheus-метрики**. Для Render предусмотрены Logs и внешняя служба мониторинга; внутренний Prometheus Docker Compose остаётся локальным.
- Проверьте `/admin/` и обычные формы, что POST не отклоняется по CSRF. Никогда не отправляйте скриншоты с секретами.

**Не запускайте** k6/Chromium mutating acceptance против публичного сайта: они рассчитаны исключительно на изолированную базу CI.

## 6. Бесплатный тариф и SLA

На Render Free веб-сервис останавливается после **15 минут простоя**, а первый запрос может ждать около минуты, пока он проснётся. При этом файловая система эфемерная, но данные в Neon сохраняются. Поэтому:

- Такой хостинг **подходит для демонстрации практики**, но не подтверждает SLA 99,9%;
- Тест 1000 VU и 3750 booking lifecycles выполнялся на **совершенно другой конфигурации** (GitHub Actions, локальный Postgres/Redis). Не переносите эти показатели на Render Free + Neon Free;
- Render может ограничить бесплатный сервис при необычно большом исходящем трафике к внешней базе;
- Для настоящего 30-дневного SLA нужен непрерывно работающий сервис подходящего тарифа и независимый мониторинг, как в `docs/UPTIME_MONITORING.md`.

Ранее написанные backup-скрипты Docker Compose **не работают напрямую с Neon**. Для облачного бэкапа используйте отдельный `pg_dump` к Neon и сохраняйте его в независимом защищённом хранилище. Это отдельная задача, которую нельзя считать выполненной существующим CI.

## 7. Что прислать после первого Live

Только **публичную ссылку вида `https://...onrender.com`**, без паролей, токенов и URL базы. По ней можно проверить доступность страниц снаружи и помочь найти проблемы первого запуска. Если на этапе Render/Neon возникла ошибка, достаточно скриншота Logs с закрытыми секретами.

Документация сервисов:
- https://render.com/docs/blueprint-spec
- https://render.com/docs/free
- https://neon.com/docs/connect/connect-from-any-app
