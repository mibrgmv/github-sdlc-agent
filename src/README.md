# src

Основной пакет SDLC Agents.

## Модули

| Файл | Описание |
|------|----------|
| `cli.py` | CLI интерфейс (Click). Команды `solve` и `review` |
| `server.py` | FastAPI webhook сервер. Принимает события от GitHub |
| `runner.py` | Оркестрация агентов. Логика итеративного цикла solve→review→fix |
| `config.py` | Pydantic Settings. Загрузка конфигурации из env |
| `github_client.py` | Обёртка над PyGithub. Аутентификация через GitHub App |
| `llm_client.py` | Клиент для LLM. OpenAI-совместимый API |

## Точки входа

**CLI:**
```bash
python -m src.cli solve <issue> --repo owner/repo
python -m src.cli review <pr> --repo owner/repo
```

**Server:**
```bash
python -m uvicorn src.server:app --host 0.0.0.0 --port 8000
```

## Зависимости

- `agents/` — реализация Code Agent и Reviewer Agent