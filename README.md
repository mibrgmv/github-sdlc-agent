# SDLC Agents

Автоматизированная агентная система для полного цикла разработки ПО в GitHub.

## Компоненты

- **Code Agent** — читает Issue, анализирует требования, генерирует код и создаёт Pull Request
- **AI Reviewer Agent** — анализирует PR и оставляет code review
- **Webhook Server** — принимает события от GitHub и запускает агентов автоматически

---

## Быстрый старт

### 1. Установить GitHub App

1. Перейти по ссылке: https://github.com/apps/megaschool-slave
2. Нажать **Install**
3. Выбрать репозиторий для тестирования

### 2. Подготовить credentials

Создать файл `.env`:
```bash
OPENAI_API_KEY=<получить у автора>
OPENAI_MODEL=llama-3.3-70b-versatile
OPENAI_BASE_URL=https://api.groq.com/openai/v1

GITHUB_APP_ID=2756616
GITHUB_APP_PRIVATE_KEY_PATH=/app/private-key.pem
GITHUB_APP_INSTALLATION_ID=106871180
GITHUB_WEBHOOK_SECRET=hudfslmkadsoifgh
```

Файл `private-key.pem` уже есть в репозитории.

### 3. Запустить сервер

```bash
# Скачать образ
docker pull ghcr.io/mibrgmv/sdlc-agent:latest

# Запустить (из папки где лежат .env и private-key.pem)
docker run -d \
  --name sdlc-server \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/private-key.pem:/app/private-key.pem:ro \
  ghcr.io/mibrgmv/sdlc-agent:latest \
  sh -c "python -m uvicorn src.server:app --host 0.0.0.0 --port 8000"
```

### 4. Пробросить через ngrok

```bash
ngrok http 8000
```

ngrok выдаст URL типа `https://abc123.ngrok-free.app`

### 5. Обновить Webhook URL

Сообщить автору ngrok URL, либо обновить самостоятельно:

GitHub → Settings → Developer settings → GitHub Apps → megaschool-slave → Webhook URL:
```
https://abc123.ngrok-free.app/webhook
```

### 6. Готово!

Создай Issue в репозитории где установлен App:
```
Title: Create hello.py
Body: Create a file hello.py with function greet() that returns "Hello!"
```

Агент получит webhook, сгенерирует код и создаст PR. При создании PR — автоматически запустится review.

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
└── .env.example
```

---

## API Endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Health check |
| `/webhook` | POST | GitHub webhook receiver |
