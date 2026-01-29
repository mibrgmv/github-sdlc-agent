# SDLC Agents

Автоматизированная агентная система для полного цикла разработки ПО в GitHub.

## Компоненты

- **Code Agent** — читает Issue, анализирует требования, генерирует код и создаёт Pull Request
- **AI Reviewer Agent** — анализирует PR и оставляет code review
- **Webhook Server** — принимает события от GitHub и запускает агентов автоматически

## Режимы работы

| Режим | Описание | Когда использовать |
|-------|----------|-------------------|
| **Webhook Server** | Автоматическая обработка событий | Production, облако |
| **CLI** | Ручной запуск агентов | Отладка, разовые задачи |
| **GitHub Actions** | Запуск через CI/CD GitHub | Если не нужен свой сервер |

---

## Быстрый старт: Webhook Server + ngrok (локально)

### 1. Получить API ключи

**Groq (LLM, бесплатно):**
1. https://console.groq.com → Create API Key

**GitHub App:**
1. GitHub → Settings → Developer settings → GitHub Apps → **New GitHub App**
2. Заполнить:
   - **GitHub App name:** `SDLC Agent` (уникальное имя)
   - **Homepage URL:** `https://github.com`
3. **Webhook:**
   - **Active:** ✅ Включить
   - **Webhook URL:** `https://your-ngrok-url.ngrok.io/webhook` (заполним позже)
   - **Webhook secret:** придумать секрет (например `mysecret123`)
4. **Permissions → Repository permissions:**
   - Contents: Read and write
   - Issues: Read and write
   - Pull requests: Read and write
   - Metadata: Read-only
5. **Subscribe to events:**
   - ✅ Issues
   - ✅ Pull request
6. **Where can this GitHub App be installed:** Any account
7. **Create GitHub App**
8. Сохранить **App ID** (вверху страницы)
9. **Generate a private key** → скачать `.pem` файл
10. **Install App** → выбрать репозиторий

### 2. Настроить переменные окружения

```bash
cp .env.example .env
```

Заполнить `.env`:
```bash
# Groq
OPENAI_API_KEY=gsk_your_key
OPENAI_MODEL=llama-3.3-70b-versatile
OPENAI_BASE_URL=https://api.groq.com/openai/v1

# GitHub App
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=./private-key.pem
GITHUB_APP_INSTALLATION_ID=12345678
GITHUB_WEBHOOK_SECRET=mysecret123
```

### 3. Запустить сервер

```bash
cd docker
docker-compose build
docker-compose up server
```

Сервер запустится на `http://localhost:8000`

### 4. Пробросить через ngrok

В новом терминале:
```bash
# Установить ngrok: https://ngrok.com/download
ngrok http 8000
```

ngrok выдаст URL типа `https://abc123.ngrok-free.app`

### 5. Настроить Webhook URL в GitHub App

1. GitHub → Settings → Developer settings → GitHub Apps → твой app
2. В поле **Webhook URL** вставить: `https://abc123.ngrok-free.app/webhook`
3. Save changes

### 6. Тестирование

1. Создать Issue в репозитории где установлен App:
   ```
   Title: Create hello.py
   Body: Create a file hello.py with function greet() that returns "Hello!"
   ```
2. Смотреть логи сервера — он получит webhook и создаст PR
3. При создании PR — сервер автоматически сделает review

---

## CLI режим (ручной запуск)

```bash
cd docker

# Обработать Issue
ISSUE_NUMBER=1 docker-compose run code-agent

# Ревью PR
PR_NUMBER=1 docker-compose run reviewer-agent
```

Или локально:
```bash
source .venv/bin/activate
pip install -r requirements.txt && pip install -e .

python -m src.cli solve 1 --repo username/repo
python -m src.cli review 1 --repo username/repo
```

---

## GitHub Actions режим

Если не хочется поднимать свой сервер — агенты могут работать через GitHub Actions.

**Настройка секретов в репозитории:**

Settings → Secrets and variables → Actions:
- `OPENAI_API_KEY` — ключ Groq
- `GH_APP_ID` — ID приложения
- `GH_APP_PRIVATE_KEY` — содержимое .pem файла
- `GH_APP_INSTALLATION_ID` — ID установки

**Variables:**
- `OPENAI_MODEL` = `llama-3.3-70b-versatile`
- `OPENAI_BASE_URL` = `https://api.groq.com/openai/v1`

При создании Issue или PR workflows запустятся автоматически.

---

## Деплой в облако

Webhook сервер можно задеплоить в:
- **Yandex Cloud Functions** (serverless)
- **Cloud.ru**
- **Любой VPS** с Docker

Для production замените ngrok URL на реальный домен сервера.

---

## Переменные окружения

| Переменная | Описание | Обязательная |
|------------|----------|--------------|
| `OPENAI_API_KEY` | API ключ (Groq/OpenAI) | Да |
| `OPENAI_MODEL` | Модель LLM | Да |
| `OPENAI_BASE_URL` | URL API | Для Groq |
| `GITHUB_APP_ID` | ID GitHub App | Да |
| `GITHUB_APP_PRIVATE_KEY_PATH` | Путь к .pem | Да |
| `GITHUB_APP_INSTALLATION_ID` | ID установки | Да |
| `GITHUB_WEBHOOK_SECRET` | Секрет для webhook | Для сервера |
| `GITHUB_TOKEN` | Personal Access Token | Альтернатива App |

---

## Структура проекта

```
├── src/
│   ├── agents/
│   │   ├── code_agent.py     # Code Agent
│   │   └── reviewer_agent.py # AI Reviewer
│   ├── server.py             # Webhook сервер (FastAPI)
│   ├── cli.py                # CLI интерфейс
│   ├── config.py             # Конфигурация
│   ├── github_client.py      # GitHub API + App auth
│   └── llm_client.py         # LLM клиент
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .github/workflows/
│   ├── on_issue.yml          # Workflow для Issue
│   └── on_pr.yml             # Workflow для PR
└── .env.example
```

---

## API Endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Health check |
| `/webhook` | POST | GitHub webhook receiver |
