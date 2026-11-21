# OfficeFlow — перенос проекта в VS Code (Windows)

Эта инструкция переносит актуальную ветку `main` из публичного GitHub-репозитория на компьютер. Старую папку `OfficeFlow_source\OfficeFlow` пока не удаляйте и не перезаписывайте: новый клон будет создан отдельно, чтобы сохранить старую копию до проверки.

## 1. Что должно быть установлено

- Git for Windows.
- Visual Studio Code.
- Docker Desktop с запущенным Docker Engine (WSL 2 backend подходит).

Проверка в PowerShell:

```powershell
git --version
docker compose version
code --version
```

Если команда `code` не найдена, откройте VS Code вручную и используйте File → Open Folder.

## 2. Скачать актуальный main

Откройте PowerShell и выполните:

```powershell
Set-Location "$HOME\Desktop"
git clone https://github.com/Ramig2007/OfficeFlow.git OfficeFlow-vscode
Set-Location .\OfficeFlow-vscode
git status --short --branch
git log -1 --oneline
code .
```

Репозиторий публичный; GitHub Desktop не требуется. Папка `OfficeFlow-vscode` будет отдельной от старого `OfficeFlow_source\OfficeFlow`.

В VS Code откройте Extensions. При появлении подсказки **Install Recommended Extensions** установите рекомендованные расширения из `.vscode/extensions.json` (Python, Ruff, Docker, GitLens). Форматирование Python при сохранении настроено в `.vscode/settings.json`.

## 3. Создать локальное окружение

В терминале VS Code (Terminal → New Terminal, PowerShell) убедитесь, что текущая папка — корень репозитория, рядом находятся `compose.yaml` и `manage.py`.

```powershell
Copy-Item .env.example .env
code .env
```

В `.env` замените placeholder-значения на свои локальные секреты:
- `SECRET_KEY`
- `DB_PASSWORD`
- `DEMO_PASSWORD`
- `GRAFANA_PASSWORD`

Для генерации каждого случайного значения можно отдельно выполнить:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Используйте разные значения. Оставьте `DEBUG=1` только для локального учебного запуска. Не вставляйте production Neon/Yandex/Telegram secrets в `.env.example`, исходники или Git. Файл `.env` исключён из Git через `.gitignore`.

## 4. Запустить приложение

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose exec app python manage.py migrate --noinput
docker compose exec app python manage.py seed_demo
docker compose ps
```

После того как сервисы станут healthy, откройте:

- Сайт: http://localhost:8080/
- API docs: http://localhost:8080/api/docs/
- Liveness: http://localhost:8080/health/live/
- Readiness: http://localhost:8080/health/ready/

Демо-аккаунты: `manager` (администратор) и `employee` (сотрудник). Пароль — значение `DEMO_PASSWORD` из вашего локального `.env`. Команду `seed_demo` использовать только при `DEBUG=1`, не в production.

## 5. Открыть Grafana локально (необязательно)

Перед запуском observability-профиля задайте в `.env` сильный `GRAFANA_PASSWORD`. Затем:

```powershell
docker compose --profile observability up -d
docker compose ps
```

- Grafana: http://localhost:3000/
- Prometheus targets: http://localhost:9090/targets/
- Alertmanager: http://localhost:9093/

В Grafana войдите с `GRAFANA_USER` (по умолчанию `admin`) и паролем из `.env`. Dashboard: **OfficeFlow · Reliability** (9 панелей). Этот стек работает на локальном компьютере и не означает, что Grafana размещена на Render.

## 6. Использовать готовые VS Code tasks

Откройте Terminal → Run Task. В списке доступны:
- **OfficeFlow: Start local stack**
- **OfficeFlow: Apply migrations**
- **OfficeFlow: Seed demo data**
- **OfficeFlow: Show services**
- **OfficeFlow: Follow app logs**
- **OfficeFlow: Start observability**
- **OfficeFlow: Stop stack (keep data)**

Tasks запускают Docker Compose из корня открытого workspace.

## 7. Обновлять код и отправлять изменения

Получить свежий `main`:

```powershell
git pull --ff-only origin main
```

Посмотреть изменения:

```powershell
git status
git diff
```

Если у вас есть права push и вы хотите отправить собственные изменения:

```powershell
git add .
git commit -m "Describe the change"
git push origin main
```

После push проверяйте GitHub → Actions: CI должен запуститься автоматически. Не добавляйте `.env`, дампы БД, резервные копии, токены и пароли в коммит.

## 8. Остановить приложение без удаления данных

```powershell
docker compose down
```

Команда `docker compose down` останавливает контейнеры, но сохраняет volumes базы данных. **Не используйте `docker compose down -v`**, если хотите сохранить локальные бронирования и данные.

## 9. Если что-то не запускается

```powershell
docker compose ps
docker compose logs --tail=100 app
docker compose logs --tail=100 db
docker compose logs --tail=100 redis
```

Проверьте, что Docker Desktop запущен, `.env` создан, `DB_PASSWORD` не пустой, а порт 8080 не занят. Для остальных типичных проблем смотрите раздел «Распространённые ошибки» в корневом `README.md`.
