# Architect для Claude Code

Инженерный харнес **Plan & Act** для Claude Code. Раньше это была связка
ChatGPT-«Architect» (планировал) + Codex (исполнял). Здесь всё делает **один**
инструмент — Claude Code: планирует, пишет код и ревьюит сам.

---

## Что внутри

```
CLAUDE.md                 — правила, которые Claude Code читает автоматически
docs/agent/
  engineering_principles.md      — инженерный чек-лист (Simple Made Easy)
  plan_act_workflow.md           — как идёт цикл PLAN → ACT → REVIEW
  review_protocol.md             — как проверять результат (git diff + тесты)
  task_continuity.md             — state.md для длинных задач
  new_service_architecture.md    — baseline для новых сервисов
  planning_and_briefs.md         — режимы планирования и шаблоны brief
```

---

## Требование

В твоём Claude Code должен быть установлен плагин **superpowers** (он ставится
на уровень пользователя, поэтому работает во всех проектах сразу). Проверить:
навыки `superpowers:brainstorming`, `superpowers:writing-plans`,
`superpowers:executing-plans` должны быть доступны. Если их нет — установи
плагин superpowers, и харнес заработает во всех репозиториях.

---

## Как подключить к проекту

Скопируй **содержимое** этой папки в корень своего репозитория так, чтобы
`CLAUDE.md` оказался в корне рядом с `.git`:

```bash
cp CLAUDE.md /путь/к/проекту/CLAUDE.md
cp -r docs/agent /путь/к/проекту/docs/agent
```

PowerShell (Windows):

```powershell
Copy-Item CLAUDE.md 'C:\путь\к\проекту\CLAUDE.md'
Copy-Item docs\agent 'C:\путь\к\проекту\docs\agent' -Recurse
```

Важно: именно `CLAUDE.md` должен лежать **в корне** проекта — Claude Code
подхватывает его автоматически при запуске. `docs/agent/` — справочные файлы,
на которые ссылается `CLAUDE.md`.

Если в проекте уже есть свой `CLAUDE.md` — не перезаписывай его, а вставь блок
из этого `CLAUDE.md` в конец существующего.

---

## Как этим пользоваться

Просто ставь задачу на русском. Claude Code сам выберет фазу и нужный навык
superpowers. Ориентиры-триггеры:

| Ты говоришь | Что произойдёт |
|---|---|
| «Задача расплывчатая, давай разберём варианты» | фаза **Brainstorm** → `superpowers:brainstorming` |
| «Что-то падает / непонятна причина, спланируй расследование» | фаза **Investigation** → `superpowers:systematic-debugging` |
| «Направление ясно, составь план» | **Plan** → `superpowers:writing-plans` |
| «Делай по плану» / мелкая понятная правка | **Execute** → `superpowers:executing-plans` |
| «Проверь результат» | **Review** → `superpowers:requesting-code-review` + `verification-before-completion` |
| «Новый сервис с нуля» | сначала **Architecture Baseline** (`docs/agent/new_service_architecture.md`), потом план |

Можно и явно: `/superpowers:brainstorming`, `/superpowers:writing-plans` и т.д.

### Типовой цикл

1. Описываешь задачу.
2. Claude Code уточняет контекст, читает нужные файлы (`Read`/`Grep`/`Glob`),
   задаёт вопросы, предлагает направления.
3. Для нетривиальных задач — сначала план (`writing-plans`), потом исполнение.
4. Пишутся/обновляются тесты, прогоняется валидация.
5. Ревью: `git diff` + тесты + прямое чтение изменённых файлов.
6. Для длинных задач — состояние в `.agent/tasks/<task-id>/state.md`, чтобы
   продолжить в новой сессии.

### Стартовые фразы (аналог conversation starters)

```
Разбери задачу как инженер: уточни контекст, риски и выбери следующий шаг
Это диагностическая задача — спланируй расследование перед фиксом
Направление выбрано — составь repo-aware план по задаче
Проверь результат: пройдись по git diff, тестам и изменённым файлам
Помоги спроектировать новый сервис: architecture baseline, границы, тесты
```

---

## Чем отличается от старой Codex-версии

- `AGENTS.md` → `CLAUDE.md` (авто-загрузка в Claude Code).
- Команды `/superpowers:brainstorm|write-plan|execute-plan` → реальные навыки
  `superpowers:brainstorming` / `writing-plans` / `executing-plans`.
- Строка `Codex intelligence: ...` убрана — в Claude Code такого переключателя нет.
- Repomix-выгрузки (`--style xml`) убраны — Claude Code читает репозиторий
  напрямую; ревью идёт по `git diff` и прямому чтению.
- Роли PLAN и ACT объединены — ChatGPT и Codex больше не нужны.
