# Логика Code Review

AI Reviewer анализирует PR и классифицирует найденные проблемы по severity.

## Типы проблем

### BLOCKING (блокируют merge)

| Severity | Описание | Примеры |
|----------|----------|---------|
| `error` | Баги, ошибки логики, уязвимости, падение CI | Runtime exceptions, failed tests, security issues |
| `requirement` | Код не соответствует требованиям Issue | Функция не реализована, неверное поведение |

### NON-BLOCKING (предложения по улучшению)

| Severity | Описание | Примеры |
|----------|----------|---------|
| `refactor` | Нарушения SOLID, DRY, архитектурные проблемы | God class, tight coupling, дублирование кода |
| `style` | Нейминг, форматирование, читаемость | Неинформативные имена, отсутствие типов |
| `suggestion` | Nice-to-have улучшения | Альтернативные подходы, оптимизации |

## Логика approve/reject

```
if blocking_issues > 0 OR ci_failed:
    reject → новая итерация
else:
    approve → завершение цикла
```

PR апрувится если:
- Нет `error` и `requirement` проблем
- CI проходит (тесты, сборка)

Non-blocking проблемы не блокируют merge, но отображаются как suggestions.

## CI интеграция

Reviewer автоматически проверяет статус CI checks:
- `failure`, `timed_out`, `cancelled` → автоматический `error` с тегом `[CI]`
- Падение тестов = blocking issue

## Пример review output

```
## AI Code Review (Iteration 2)

**Status:** ❌ Changes Requested
**Requirements Met:** ❌ No
**CI Status:** ❌ Failed

### Summary
The implementation has a critical bug in error handling.

### 🚫 Blocking Issues (must fix)
- **[ERROR] [CI]** CI check 'tests' failed: failure
- **[ERROR]** Division by zero possible in calculate() (`src/math.py:42`)

### 💡 Suggestions (non-blocking)
- **[REFACTOR]** Consider extracting validation to separate function
- **[STYLE]** Variable name 'x' is not descriptive
```

## Цикл итераций

1. Code Agent создаёт/обновляет PR
2. Reviewer анализирует diff + CI статус
3. Если есть blocking issues → Code Agent фиксит → повтор
4. Если только non-blocking → approve
5. Максимум `MAX_ITERATIONS` (default: 5) итераций

Каждый review помечен номером итерации для отслеживания прогресса.
