# Развёртывание OfficeFlow на VPS

> **Другая, бесплатная схема:** Render Free + Neon Free (без VPS, Nginx и Caddy) описана в [`docs/RENDER_NEON_DEPLOYMENT.md`](RENDER_NEON_DEPLOYMENT.md). Это отдельная конфигурация; не следует применять команды из этого VPS-руководства к Render.

**Статус:** production-конфигурация объединена в `main` и прошла CI/runtime smoke; публичный сервер ещё не развёрнут.  
**Цель:** безопасно опубликовать приложение по HTTPS, не открывая PostgreSQL, Redis и служебные панели мониторинга в Интернет.

## 1. Целевая схема

```text
Браузер
  |
  | HTTPS :443 / HTTP :80 (HTTP redirect)
  v
Caddy (TLS, автоматический сертификат)
  |
  | Docker network
  v
Nginx (reverse proxy + static files)
  |
  v
Django / Gunicorn
  |                 |
  v                 v
PostgreSQL 16      Redis 7
```

Подготовленные файлы:
- `.env.production.example` — шаблон переменных production-окружения;
- `compose.production.yaml` — дополнительный Compose-файл с Caddy и обязательными HTTPS-настройками Django;
- `infra/caddy/Caddyfile` — автоматический TLS reverse proxy;
- `docker-entrypoint.sh` — сбор статических файлов при старте приложения;
- `scripts/backup.sh` — Linux backup PostgreSQL с проверкой читаемости архива и SHA-256;
- `scripts/test-restore.sh` — полное восстановление во временную БД и сверка основных таблиц.

Общая конфигурация остаётся в `compose.yaml`. Локальный Nginx опубликован только на loopback `127.0.0.1:8080`; при production-деплое публичные 80/443 принимает Caddy.

## 2. Что нужно до запуска

1. VPS с Linux и правами администратора.
2. Домен или поддомен, которым можно управлять через DNS.
3. Публичный IPv4 VPS.
4. DNS A-запись домена на IPv4 сервера. Если IPv6 не настроен на VPS, не добавлять AAAA-запись.
5. Firewall: SSH (лучше ограничить доверенными IP), HTTP 80 и HTTPS 443.
6. Установленные Docker Engine и Docker Compose plugin.

**Пока нет VPS и домена, конфигурацию можно проверить в CI, но нельзя утверждать, что сайт уже размещён в Интернете.**

## 3. Подготовка сервера

Получить исходный код из публичного репозитория:

```bash
git clone https://github.com/Ramig2007/OfficeFlow.git
cd OfficeFlow
cp .env.production.example .env
chmod 600 .env
```

Открыть `.env` и заменить все placeholder-значения. Обязательные параметры:
- `DOMAIN` — точный публичный домен;
- `ALLOWED_HOSTS` — тот же hostname без протокола;
- `CSRF_TRUSTED_ORIGINS` — origin с `https://`;
- `SECRET_KEY` — уникальный случайный ключ не короче 50 символов;
- `DB_PASSWORD` — отдельный длинный случайный пароль PostgreSQL;
- `GRAFANA_PASSWORD` — отдельный пароль, если будет включён профиль мониторинга.

Сгенерировать значения локально на сервере, не публикуя их в Git или чате:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
```

Не использовать демонстрационные учётные данные. Не запускать `seed_demo` в production: команда специально доступна только при `DEBUG=1`.

## 4. Проверка и запуск

Все команды выполнять из корня репозитория, где находятся оба Compose-файла и `.env`.

Сначала проверить итоговую конфигурацию:

```bash
docker compose -f compose.yaml -f compose.production.yaml config --quiet
```

Затем собрать и запустить:

```bash
docker compose -f compose.yaml -f compose.production.yaml up -d --build
```

Применить миграции:

```bash
docker compose -f compose.yaml -f compose.production.yaml exec app python manage.py migrate --noinput
```

Создать первого администратора:

```bash
docker compose -f compose.yaml -f compose.production.yaml exec app python manage.py createsuperuser
```

Сбор статических файлов выполняется entrypoint приложения при каждом старте контейнера. Это важно для обновления уже существующего named volume `staticfiles`.

Проверить состояние:

```bash
docker compose -f compose.yaml -f compose.production.yaml ps
docker compose -f compose.yaml -f compose.production.yaml logs --tail=100 app
docker compose -f compose.yaml -f compose.production.yaml logs --tail=100 caddy
```

## 5. Проверка HTTPS и функций

С внешнего устройства проверить:
- `https://<DOMAIN>/` открывается без предупреждения сертификата;
- HTTP `http://<DOMAIN>/` перенаправляется на HTTPS;
- `https://<DOMAIN>/health/live/` возвращает 200;
- `https://<DOMAIN>/health/ready/` возвращает 200;
- вход, каталог комнат, расписание, создание/отмена брони, конфликт слотов и VIP-согласование работают;
- сотрудник получает 403 на административных страницах и API;
- CSS и JavaScript загружаются без 404;
- session и CSRF cookies имеют Secure-флаг.

Примеры:

```bash
curl -I https://<DOMAIN>/
curl -fsS https://<DOMAIN>/health/live/
curl -fsS https://<DOMAIN>/health/ready/
```

## 6. Firewall и служебные панели

Снаружи должны быть доступны только:
- SSH — по возможности только с доверенных IP;
- TCP 80 и 443 — для HTTP redirect и HTTPS.

Не открывать в Интернет:
- PostgreSQL 5432;
- Redis 6379;
- Django/Gunicorn 8000;
- Prometheus 9090;
- Alertmanager 9093;
- Grafana 3000;
- внутренний Nginx 8080.

Prometheus, Grafana и Alertmanager в базовой конфигурации привязаны к loopback. Даже при включении observability-профиля не публиковать их напрямую без VPN/дополнительной аутентификации. Alertmanager пока использует `null-receiver`, то есть реальные уведомления не отправляет.

## 7. Резервное копирование

Создать и проверить архив:

```bash
bash scripts/backup.sh
```

Скрипт:
1. создаёт custom-format PostgreSQL dump;
2. проверяет, что файл не пустой;
3. проверяет читаемость архива через `pg_restore --list` внутри PostgreSQL-контейнера;
4. сохраняет SHA-256 рядом с архивом.

Скрипт сохраняет копию в `backups/` на том же сервере. Это **не off-site backup**. После создания копию и checksum необходимо передавать в отдельное зашифрованное хранилище. Настроить расписание (например, ежедневное) и периодически проверять полное восстановление в отдельной тестовой БД:

```bash
bash scripts/test-restore.sh backups/officeflow-YYYYMMDDTHHMMSSZ.dump
```

Скрипт создаёт временную БД внутри PostgreSQL-контейнера, восстанавливает архив, сравнивает количества основных таблиц и проверяет GiST exclusion constraint; исходная БД используется только для чтения, временная БД удаляется.

Пример cron для ежедневного запуска в 02:15 UTC (путь заменить на фактический):

```cron
15 2 * * * cd /opt/officeflow && /bin/bash scripts/backup.sh >> /var/log/officeflow-backup.log 2>&1
```

Не выполнять `docker compose down -v`: это удаляет volumes с данными.

## 8. Обновление приложения

Перед обновлением убедиться, что backup создан и доступен вне сервера. Затем:

```bash
git pull --ff-only origin main
docker compose -f compose.yaml -f compose.production.yaml config --quiet
docker compose -f compose.yaml -f compose.production.yaml up -d --build
docker compose -f compose.yaml -f compose.production.yaml exec app python manage.py migrate --noinput
```

После обновления повторить health checks и основные пользовательские сценарии. Для отката использовать ранее проверенный commit и совместимый backup; миграции базы не всегда автоматически обратимы.

## 9. Что не входит в текущую подготовку

- VPS, домен и DNS не предоставлены и не настроены;
- публичное HTTPS-развёртывание ещё не выполнено;
- внешний канал уведомлений Alertmanager не настроен;
- HA-кластер, репликация PostgreSQL и доказанный SLA 99,9% не реализованы;
- нагрузка на создание бронирований и 1000 независимых пользователей не подтверждена.

После получения VPS и домена можно выполнить реальный деплой и заполнить фактический протокол в `docs/PILOT.md`.
