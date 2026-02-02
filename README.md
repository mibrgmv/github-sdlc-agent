# SDLC Agents

Автоматизированная агентная система для GitHub: генерация кода по Issue и AI code review.

## Компоненты

- **Code Agent** — читает Issue, генерирует код, создаёт Pull Request
- **Reviewer Agent** — анализирует PR, оставляет code review
- **Webhook Server** — принимает события от GitHub, запускает агентов

## Быстрый старт

### Серверный режим (Cloud.ru)

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

```bash
docker-compose -f docker/docker-compose.yml up
```

### Локальный режим

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
```

## CLI

### solve

Генерирует код по Issue и создаёт PR.

```bash
python -m src.cli solve <issue> --repo owner/repo [--auto] [--new]
```

| Флаг | Описание |
|------|----------|
| `--repo` | Репозиторий (owner/repo) — обязательный |
| `--auto` | Полный цикл: solve → review → fix → ... до approve или MAX_ITERATIONS |
| `--new` | Создать новый PR вместо обновления существующего |

### review

Запускает code review для PR.

```bash
python -m src.cli review <pr> --repo owner/repo
```

| Флаг | Описание |
|------|----------|
| `--repo` | Репозиторий (owner/repo) — обязательный |

## Code Review

Reviewer классифицирует проблемы:

| Тип | Блокирует | Описание |
|-----|-----------|----------|
| `error` | ✅ | Баги, уязвимости, runtime exceptions |
| `requirement` | ✅ | Не соответствует требованиям Issue |
| `refactor` | ❌ | SOLID/DRY нарушения, архитектура |
| `style` | ❌ | Нейминг, форматирование |
| `suggestion` | ❌ | Nice-to-have улучшения |

**Approve:** нет blocking issues (`error`, `requirement`)

Подробнее: [docs/REVIEW.md](docs/REVIEW.md)

## API

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Health check |
| `/webhook` | POST | GitHub webhook receiver |

## GitHub App

1. https://github.com/apps/megaschool-slave → Install
2. Выбрать репозиторий
