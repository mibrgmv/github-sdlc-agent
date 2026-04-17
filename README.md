# SDLC Agents

Автономная система AI-агентов для автоматизации Software Development Life Cycle на GitHub. Агенты читают Issue, генерируют код, создают Pull Request и проводят code review с итеративными исправлениями до достижения качественного результата.

## Технологии

- **Python 3.11+**
- **FastAPI** — асинхронный веб-сервер для webhook
- **PyGithub** — взаимодействие с GitHub API
- **OpenAI SDK** — универсальный клиент для LLM (OpenAI, Cloud.ru, Groq, Ollama)
- **Pydantic** — валидация конфигурации и settings
- **Click** — CLI интерфейс
- **Docker** — контейнеризация
- **GitHub Apps** — аутентификация и webhook интеграция

## Что делает проект

**Code Agent** получает Issue из GitHub, анализирует требования, генерирует код и создаёт Pull Request. **Reviewer Agent** проводит code review, классифицирует найденные проблемы по критичности и принимает решение об approve или request changes. При отклонении PR запускается новая итерация — Code Agent исправляет код на основе review, и цикл повторяется до approve или достижения лимита итераций.

## Архитектура

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   GitHub Issue  │────▶│   Code Agent    │────▶│   Pull Request  │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                        ┌─────────────────┐              │
                        │ Reviewer Agent  │◀─────────────┘
                        └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
              ✅ Approve                ❌ Changes Requested
                                              │
                                              ▼
                                    Code Agent исправляет
                                              │
                                              └──────▶ Новая итерация
```

---

## GitHub App и Webhook

Основной способ использования — через GitHub App. Сервер принимает webhook события и автоматически запускает агентов.

### Как это работает

1. **GitHub App** устанавливается в репозиторий и получает права на чтение/запись Issues, Pull Requests, Contents
2. **Webhook URL** настраивается в GitHub App и указывает на сервер (`https://your-server.com/webhook`)
3. При событиях в репозитории GitHub отправляет POST запрос на webhook
4. Сервер верифицирует подпись запроса через `GITHUB_WEBHOOK_SECRET`
5. В зависимости от события запускается соответствующий агент

### Триггеры

| Событие | Action | Результат |
|---------|--------|-----------|
| `issues` | `opened` | Code Agent генерирует код и создаёт PR |
| `issues` | `labeled` | Code Agent генерирует код и создаёт PR |
| `pull_request` | `opened` | Reviewer Agent проводит code review |
| `pull_request` | `synchronize` | Reviewer Agent проводит code review (новые коммиты) |

### Полный цикл через webhook

```
Issue создан
    ↓
Webhook: issues.opened
    ↓
Code Agent: клонирует repo → генерирует код → создаёт PR
    ↓
Webhook: pull_request.opened
    ↓
Reviewer Agent: анализирует diff → постит review
    ↓
Если reject → Code Agent исправляет → push
    ↓
Webhook: pull_request.synchronize
    ↓
Reviewer Agent: повторный review
    ↓
... до approve или MAX_ITERATIONS
```

### Подключение GitHub App

1. Установи GitHub App: https://github.com/apps/megaschool-slave
2. Выбери репозиторий для установки
3. Создай Issue с описанием задачи
4. Code Agent автоматически создаст PR
5. Reviewer Agent проведёт code review
6. При необходимости цикл повторится до approve

---

## Два режима работы

### Server — автоматический (production)

FastAPI сервер принимает webhook события от GitHub и запускает агентов в background tasks. Используется `BackgroundTasks` для асинхронной обработки без блокировки.

```bash
python -m uvicorn src.server:app --host 0.0.0.0 --port 8000
```

### CLI — ручной (разработка/отладка)

Запуск агентов вручную из командной строки.

```bash
python -m src.cli solve <issue_number> --repo owner/repo
python -m src.cli review <pr_number> --repo owner/repo
```

---

## Установка и запуск

### Вариант 1: Через GitHub App (рекомендуется)

Не требует локальной установки. Просто подключи App к репозиторию.

1. Установи GitHub App: https://github.com/apps/megaschool-slave
2. Создай Issue → получи PR автоматически

### Вариант 2: Локально из исходников

```bash
git clone https://github.com/mibrgmv/sdlc-agent.git
cd sdlc-agent

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt && pip install -e .
```

Создай `.env`:
```
OPENAI_API_KEY=<api-key>
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

GITHUB_APP_ID=<app-id>
GITHUB_APP_PRIVATE_KEY_PATH=./private-key.pem
GITHUB_APP_INSTALLATION_ID=<installation-id>
```

Запуск:
```bash
python -m src.cli solve 1 --repo owner/repo
```

### Вариант 3: Через Docker

```bash
docker pull ghcr.io/mibrgmv/sdlc-agent:latest

docker run --rm \
  --env-file .env \
  -v $(pwd)/private-key.pem:/app/private-key.pem:ro \
  ghcr.io/mibrgmv/sdlc-agent:latest \
  python -m src.cli solve 1 --repo owner/repo
```

---

## LLM провайдеры

Проект использует OpenAI-совместимый API. На production сервере подключен **Cloud.ru Foundation Models**, но локально можно использовать любой провайдер:

| Провайдер | BASE_URL | Модели |
|-----------|----------|--------|
| Cloud.ru | `https://foundation-models.api.cloud.ru/v1` | `openai/gpt-oss-120b` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o`, `gpt-4o-mini` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| Ollama | `http://localhost:11434/v1` | Любые локальные модели |

---

## CLI команды

### solve

Генерирует код по Issue и создаёт PR.

```bash
python -m src.cli solve <issue_number> --repo owner/repo [--auto] [--new]
```

| Флаг | Описание |
|------|----------|
| `--repo` | Репозиторий (owner/repo) — обязательный |
| `--auto` | Полный цикл: solve → review → fix → ... до approve или MAX_ITERATIONS |
| `--new` | Создать новый PR вместо обновления существующего |

### review

Запускает code review для PR.

```bash
python -m src.cli review <pr_number> --repo owner/repo
```

---

## Логика Code Review

Reviewer Agent анализирует diff и классифицирует проблемы по severity:

### Blocking (блокируют merge)

| Severity | Описание | Примеры |
|----------|----------|---------|
| `error` | Баги, уязвимости, падение CI | Runtime exceptions, failed tests, security issues |
| `requirement` | Не соответствует требованиям Issue | Функция не реализована, неверное поведение |

### Non-blocking (предложения)

| Severity | Описание | Примеры |
|----------|----------|---------|
| `refactor` | SOLID/DRY нарушения | God class, дублирование кода |
| `style` | Нейминг, форматирование | Неинформативные имена |
| `suggestion` | Nice-to-have | Альтернативные подходы |

### Решение approve/reject

```
if blocking_issues > 0 OR ci_failed:
    reject → новая итерация
else:
    approve → merge ready
```

CI checks проверяются автоматически. Падение тестов = blocking error с тегом `[CI]`.

---

## Итеративный цикл

При использовании webhook или флага `--auto` система работает в автономном режиме:

1. **Code Agent** создаёт/обновляет PR по Issue
2. **Reviewer Agent** анализирует diff + CI статус
3. Если есть blocking issues → **Code Agent** исправляет → возврат к п.2
4. Если только non-blocking → **approve**
5. Максимум `MAX_ITERATIONS` (default: 5) итераций

Каждый review содержит номер итерации для отслеживания прогресса.

---

## Деплой на сервер

### docker-compose.yml

```yaml
services:
  server:
    image: ghcr.io/mibrgmv/sdlc-agent:latest
    container_name: sdlc-server
    command: ["python", "-m", "uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000"]
    env_file:
      - .env
    ports:
      - "8000:8000"
    volumes:
      - ./private-key.pem:/app/private-key.pem:ro
    restart: unless-stopped
```

### .env (server)

```
OPENAI_API_KEY=<api-key>
OPENAI_BASE_URL=https://foundation-models.api.cloud.ru/v1
OPENAI_MODEL=openai/gpt-oss-120b

GITHUB_APP_ID=<app-id>
GITHUB_APP_PRIVATE_KEY_PATH=/app/private-key.pem
GITHUB_APP_INSTALLATION_ID=<installation-id>
GITHUB_WEBHOOK_SECRET=<webhook-secret>
```

### Команды

```bash
scp docker-compose.yml user@server:/home/user/
scp private-key.pem user@server:/home/user/

ssh user@server "docker compose up -d"
ssh user@server "docker compose logs -f"
```

### Пересборка образа

```bash
docker build --platform linux/amd64 -t ghcr.io/mibrgmv/sdlc-agent:latest -f docker/Dockerfile .
docker push ghcr.io/mibrgmv/sdlc-agent:latest

ssh user@server "docker compose pull && docker compose down && docker compose up -d"
```

---

## API Endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Health check |
| `/webhook` | POST | GitHub webhook receiver |

---

## Переменные окружения

| Переменная | Обязательная | Описание |
|------------|--------------|----------|
| `OPENAI_API_KEY` | ✅ | API ключ LLM провайдера |
| `OPENAI_BASE_URL` | ❌ | URL API (default: OpenAI) |
| `OPENAI_MODEL` | ❌ | Модель (default: gpt-4o-mini) |
| `GITHUB_APP_ID` | ✅ | ID GitHub App |
| `GITHUB_APP_PRIVATE_KEY_PATH` | ✅ | Путь к приватному ключу |
| `GITHUB_APP_INSTALLATION_ID` | ✅ | ID установки App |
| `GITHUB_WEBHOOK_SECRET` | ❌ | Secret для webhook (для server mode) |
| `MAX_ITERATIONS` | ❌ | Лимит итераций (default: 5) |
