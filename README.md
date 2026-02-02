# SDLC Agents

Автоматизированная агентная система для GitHub: генерация кода по Issue и AI code review.

## Компоненты

- **Code Agent** — читает Issue, генерирует код, создаёт Pull Request
- **Reviewer Agent** — анализирует PR, оставляет code review
- **Webhook Server** — принимает события от GitHub, запускает агентов

## Два режима работы

### 1. Серверный режим (Cloud.ru)

Для production-деплоя. Сервер крутится в Cloud.ru, использует их LLM API.

```bash
# .env
GITHUB_APP_ID=...
GITHUB_APP_PRIVATE_KEY_PATH=/app/private-key.pem
GITHUB_APP_INSTALLATION_ID=...
GITHUB_WEBHOOK_SECRET=...

OPENAI_API_KEY=<cloudru-api-key>
OPENAI_BASE_URL=https://foundation-models.api.cloud.ru/v1/
OPENAI_MODEL=qwen3-235b
```

Доступные модели Cloud.ru: `qwen3-235b`, `qwen3-coder`, `glm-4.5`, `gpt-oss-120b`

```bash
docker-compose -f docker/docker-compose.yml up
```

### 2. Локальный режим (VPN)

Для разработки и тестирования. Работает через CLI с любым OpenAI-совместимым провайдером.

```bash
git clone https://github.com/mibrgmv/sdlc-agent.git
cd sdlc-agent

brew install python@3.13

python3.13 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt && pip install -e .
```

```bash
# .env
GITHUB_APP_ID=...
GITHUB_APP_PRIVATE_KEY_PATH=./private-key.pem
GITHUB_APP_INSTALLATION_ID=...

OPENAI_API_KEY=<your-api-key>
OPENAI_MODEL=gpt-4o-mini
# OPENAI_BASE_URL= (не указывать для OpenAI)
```

```bash
python -m src.cli solve 1 --repo owner/repo
python -m src.cli review 1 --repo owner/repo
```

## Установка GitHub App

1. https://github.com/apps/megaschool-slave → Install
2. Выбрать репозиторий

## API

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Health check |
| `/webhook` | POST | GitHub webhook receiver |
