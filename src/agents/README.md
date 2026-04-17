# agents

AI-агенты для автоматизации SDLC.

## Code Agent

**Файл:** `code_agent.py`

Генерирует код по GitHub Issue и создаёт Pull Request.

**Процесс:**
1. Получает Issue из GitHub (title, body)
2. Клонирует репозиторий во временную директорию
3. Отправляет контекст в LLM с system prompt
4. Парсит ответ LLM (файлы для создания/изменения)
5. Применяет изменения к репозиторию
6. Создаёт ветку, коммит, Push
7. Создаёт или обновляет Pull Request

**При наличии review feedback:**
- Парсит blocking issues из предыдущего review
- Добавляет их в prompt для исправления

## Reviewer Agent

**Файл:** `reviewer_agent.py`

Проводит code review Pull Request и принимает решение approve/reject.

**Процесс:**
1. Получает PR diff из GitHub
2. Получает linked Issue (требования)
3. Проверяет статус CI checks
4. Отправляет контекст в LLM
5. Парсит ответ: список issues с severity
6. Постит review comment на GitHub
7. Выставляет вердикт: APPROVE или REQUEST_CHANGES

**Severity levels:**

| Level | Blocking | Описание |
|-------|----------|----------|
| `error` | ✅ | Баги, уязвимости, runtime errors |
| `requirement` | ✅ | Не соответствует требованиям Issue |
| `refactor` | ❌ | SOLID/DRY нарушения |
| `style` | ❌ | Форматирование, нейминг |
| `suggestion` | ❌ | Nice-to-have улучшения |

**CI интеграция:**
- `failure`, `timed_out`, `cancelled` → автоматический `error` с тегом `[CI]`
