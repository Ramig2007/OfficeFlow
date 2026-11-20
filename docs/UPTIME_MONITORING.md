# OfficeFlow — длительный мониторинг доступности и SLA 99,9%

## Важное ограничение

Пока у OfficeFlow нет работающего публичного домена и независимого мониторингового узла, длительное измерение ещё не началось. Наличие health endpoint, Prometheus, Grafana и проверок CI само по себе не подтверждает SLA.

Для достоверной внешней проверки нужен Linux-хост с systemd, который **не размещён на том же VPS**, что и OfficeFlow. Он будет проверять публичный HTTPS endpoint и сохранять историю локально на мониторинговом хосте.

## Что проверяется

Раз в 60 секунд scripts/uptime_probe.py отправляет HTTPS GET на:

https://<домен-OfficeFlow>/health/ready/

HTTP 200 считается успешной пробой. HTTP 5xx/4xx, сетевые ошибки, DNS/TLS failures и timeout считаются неуспешными. Endpoint readiness проверяет Django, PostgreSQL и Redis, поэтому отказ критической зависимости отражается в измерении. Проверка проходит через публичный DNS/TLS/edge путь.

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

Для 90-дневного окна используйте --window-days 90. Отчёт учитывает только полное свежее окно; если истории недостаточно или последняя проба устарела, результат — INSUFFICIENT_HISTORY, а не PASS. Пропущенные интервалы консервативно считаются недоступностью. Если в одном интервале было несколько проб и хотя бы одна неуспешная, интервал также считается недоступным.

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
