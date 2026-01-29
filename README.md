# SDLC Agents

Автоматизированная агентная система для полного цикла разработки ПО в GitHub.

## Компоненты

- **Code Agent** — CLI-инструмент, который читает Issue, анализирует требования, генерирует код и создаёт Pull Request
- **AI Reviewer Agent** — автоматический ревьюер, который запускается в GitHub Actions и анализирует PR

## Требования

- Python 3.11+
- GitHub Token с правами на репозиторий
- OpenAI API Key (или совместимый API)

## Установка и запуск

### Вариант 1: Локально

```bash
# Клонировать репозиторий
git clone <repo-url>
cd mega-school-26

# Создать виртуальное окружение
python3.11 -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
pip install -e .

# Настроить переменные окружения
cp .env.example .env
# Отредактировать .env и заполнить значения

# Запустить Code Agent для issue
python -m src.cli solve <issue_number> --repo owner/repo

# Запустить Reviewer для PR
python -m src.cli review <pr_number> --repo owner/repo
```

### Вариант 2: Docker

```bash
cd docker

# Настроить переменные окружения
export GITHUB_TOKEN=ghp_your_token
export OPENAI_API_KEY=sk-your-key
export TARGET_REPO=owner/repo

# Запустить Code Agent
ISSUE_NUMBER=1 docker-compose run code-agent

# Запустить Reviewer
PR_NUMBER=1 docker-compose run reviewer-agent
```

### Вариант 3: GitHub Actions (автоматически)

1. Добавить секреты в репозиторий:
   - `OPENAI_API_KEY` — ключ OpenAI API
   - `OPENAI_BASE_URL` — (опционально) URL альтернативного API

2. Создать Issue в репозитории — Code Agent автоматически создаст PR

3. При создании/обновлении PR — AI Reviewer автоматически проведёт ревью

## Переменные окружения

| Переменная | Описание | Обязательная |
|------------|----------|--------------|
| `GITHUB_TOKEN` | GitHub токен | Да |
| `OPENAI_API_KEY` | OpenAI API ключ | Да |
| `TARGET_REPO` | Репозиторий (owner/repo) | Да |
| `OPENAI_MODEL` | Модель (по умолчанию gpt-4o-mini) | Нет |
| `OPENAI_BASE_URL` | URL альтернативного API | Нет |
| `MAX_ITERATIONS` | Макс. итераций (по умолчанию 5) | Нет |

## Тестирование

### Ручное тестирование Code Agent

1. Создать тестовый репозиторий на GitHub
2. Настроить переменные окружения
3. Создать Issue с описанием задачи, например:
   ```
   Title: Add hello function
   Body: Create a file hello.py with a function that returns "Hello, World!"
   ```
4. Запустить:
   ```bash
   python -m src.cli solve 1 --repo your-username/test-repo
   ```
5. Проверить созданный PR в репозитории

### Ручное тестирование Reviewer Agent

1. Создать PR в тестовом репозитории
2. Запустить:
   ```bash
   python -m src.cli review 1 --repo your-username/test-repo
   ```
3. Проверить комментарий-ревью в PR

### Тестирование полного цикла через GitHub Actions

1. Запушить код в репозиторий
2. Добавить секреты `OPENAI_API_KEY` в Settings → Secrets and variables → Actions
3. Создать Issue — workflow автоматически создаст PR
4. Проверить, что AI Reviewer оставил комментарий в PR

## Структура проекта

```
├── src/
│   ├── agents/
│   │   ├── code_agent.py    # Code Agent
│   │   └── reviewer_agent.py # AI Reviewer
│   ├── cli.py               # CLI интерфейс
│   ├── config.py            # Конфигурация
│   ├── github_client.py     # Работа с GitHub API
│   └── llm_client.py        # Работа с LLM
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .github/workflows/
│   ├── on_issue.yml         # Workflow для Issue
│   └── on_pr.yml            # Workflow для PR
├── requirements.txt
└── pyproject.toml
```
