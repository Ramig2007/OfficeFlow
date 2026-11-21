# OfficeFlow — внешний мониторинг доступности OfficeFlow

## Текущее состояние

Публичный Render + Neon сервис доступен по адресу https://officeflow-x6ay.onrender.com/; пользователь подтвердил Live, вход и создание переговорных. **UptimeRobot monitor ещё должен быть создан владельцем.** Для сдачи практики целимся в 24–48 часов внешнего наблюдения; фиксируем фактическое время старта и фактически накопленную статистику. Наличие health endpoint, Prometheus, Grafana и проверок CI само по себе не подтверждает SLA.

Для быстрого старта рекомендуется UptimeRobot Free: до 50 мониторов, HTTP(s) проверки раз в 5 минут и email notifications через Alert Contacts. См. [официальный тариф](https://uptimerobot.com/pricing/) и [описание интервала](https://help.uptimerobot.com/en/articles/11360876-what-is-a-monitoring-interval-in-uptimerobot).

### Быстрый запуск через UptimeRobot

1. Создайте аккаунт на https://uptimerobot.com/ и подтвердите email.
2. Нажмите **Add New Monitor** → **HTTP(s)**.
3. Friendly Name: OfficeFlow Production — readiness.
4. URL: https://officeflow-x6ay.onrender.com/health/ready/.
5. Интервал: **5 minutes** (Free).
6. В Alert Contacts добавьте подтверждённый email и сохраните monitor.
7. В настройках уведомлений монитора выберите персональный Email contact; для push установите мобильное приложение UptimeRobot, войдите в аккаунт, разрешите уведомления и включите Push для этого монитора.
8. Убедитесь, что состояние **Up**, и зафиксируйте дату/время начала измерения.

Не создавайте второй monitor без необходимости: один readiness monitor уже проверяет публичное приложение и его критическую зависимость Neon. Free-план даёт 5-минутную дискретность: краткие сбои между пробами могут быть пропущены, поэтому это внешняя оценка, а не договорная гарантия SLA. Важно: Render Free засыпает после 15 минут без входящего трафика, поэтому 5-минутные проверки удерживают сервис активным. Лимит 750 Free instance hours общий для workspace; один постоянно активный сервис расходует 720–744 часа за 30/31-дневный месяц. Если в workspace есть другие Free web services, сначала проверьте совместный расход в Render Dashboard → Billing → Monthly included usage. Источник: [Render Free limitations](https://render.com/docs/free).

Для более детальной минутной истории можно использовать приведённый ниже uptime_probe.py на независимом Linux-хосте с systemd. Такой хост должен находиться вне инфраструктуры приложения.

## Что проверяется

Раз в 60 секунд scripts/uptime_probe.py отправляет HTTPS GET на:

https://officeflow-x6ay.onrender.com/health/ready/

HTTP 200 считается успешной пробой. HTTP 5xx/4xx, сетевые ошибки, DNS/TLS failures и timeout считаются неуспешными. В текущей Render + Neon конфигурации критическая внешняя зависимость — Neon PostgreSQL; Redis для этого варианта деплоя не используется. Отказ приложения или базы должен отражаться в readiness probe. Проверка проходит через публичный DNS/TLS/edge путь.

Каждая проба записывается в JSONL: UTC timestamp, HTTP status, latency, success и error. Внешние зависимости не нужны — используются стандартная библиотека Python и проверка TLS сертификата.

## Установка на отдельный Linux monitoring host

Скопируйте каталог репозитория на независимый мониторинговый сервер или передайте ему эти файлы. Нужны Python 3 и systemd.

~~~bash
sudo install -d -m 0755 /opt/officeflow-monitor
sudo install -m 0755 scripts/uptime_probe.py /opt/officeflow-monitor/
sudo install -m 0755 scripts/uptime_report.py /opt/officeflow-monitor/
sudo install -m 0644 infra/uptime/officeflow-uptime-probe.service /etc/systemd/system/
sudo install -m 0644 infra/uptime/officeflow-uptime-probe.timer /etc/systemd/system/
sudo install -m 0600 infra/uptime/officeflow-uptime.env.example /etc/officeflow-uptime.env
sudoedit /etc/officeflow-uptime.env
~~~

В /etc/officeflow-uptime.env укажите реальный публичный origin:

~~~ini
OFFICEFLOW_URL=https://officeflow.example.com
~~~

Затем активируйте минутный timer:

~~~bash
sudo systemctl daemon-reload
sudo systemctl enable --now officeflow-uptime-probe.timer
systemctl list-timers officeflow-uptime-probe.timer
sudo journalctl -u officeflow-uptime-probe.service -n 20 --no-pager
~~~

Файл истории будет храниться в /var/lib/officeflow-uptime/probes.jsonl. Служба работает с DynamicUser и ограниченной записью только в StateDirectory. Мониторинговый узел должен быть независим от приложения, иметь стабильное питание/сеть и исходящий HTTPS доступ.

## Расчёт доступности

На monitoring host выполните:

~~~bash
sudo python3 /opt/officeflow-monitor/uptime_report.py \
  /var/lib/officeflow-uptime/probes.jsonl \
  --interval-seconds 60 --window-days 30 --target-percent 99.9
~~~

Для короткого учебного окна используйте --window-days 1 (24 часа) или --window-days 2 (48 часов); для более длинного наблюдения — --window-days 7, 30 или 90. Отчёт учитывает только полное свежее окно; если истории недостаточно или последняя проба устарела, результат — INSUFFICIENT_HISTORY, а не PASS. Пропущенные интервалы консервативно считаются недоступностью. Если в одном интервале было несколько проб и хотя бы одна неуспешная, интервал также считается недоступным.

## Бюджет недоступности для 99,9%

| Период | Максимальный бюджет простоя |
|---|---:|
| 30 дней | 43 мин 12 сек |
| 90 дней | 2 ч 9 мин 36 сек |
| 365 дней | 8 ч 45 мин 36 сек |

Для учебного подтверждения рекомендуется непрерывное наблюдение минимум 30 дней, предпочтительно 90 дней. Короткий нагрузочный тест не заменяет измерение доступности.

## Что приложить к отчёту

- публичный URL и дату начала измерения;
- место расположения независимого monitoring host;
- интервал проб и timeout;
- полное окно измерения (30/90 дней);
- число успешных, неуспешных и пропущенных интервалов;
- рассчитанную доступность и оценку простоя;
- журнал инцидентов, planned maintenance и подтверждение восстановления.

**Нельзя заявлять SLA 99,9%, пока нет полного измеренного окна и свежих внешних проб.** Отчёт по одному локальному CI run или внутренним Prometheus targets не является доказательством публичного SLA.
