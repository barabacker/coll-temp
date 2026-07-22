# Plan & Act Workflow

Claude Code runs the whole loop. There is no separate planner/executor tool.

## Roles (all played by Claude Code)

- PLAN / REVIEW — think before and after implementation.
- ACT — implement within scope.
- Superpowers — execution discipline (TDD, debugging, plans, review).
- Native tools (`Read`, `Grep`, `Glob`, `git`) — repository context.

## Default workflow

1. Read the user request and pick the current phase.
2. Inspect relevant files before changing code (`Read` / `Grep` / `Glob`).
3. Confirm assumptions against the repository, not memory.
4. Produce a plan for non-trivial work (`superpowers:writing-plans`).
5. Execute only within scope (`superpowers:executing-plans`).
6. Add or update tests for changed behavior.
7. Run relevant validation.
8. Prepare a review summary (see `review_protocol.md`).

## Phase → skill mapping

- Fuzzy problem / multiple directions → `superpowers:brainstorming`
- Diagnostic / root cause unknown → `superpowers:systematic-debugging`
- Direction chosen, needs a plan → `superpowers:writing-plans`
- Scope clear, execute → `superpowers:executing-plans`
- Implementing feature/bugfix → `superpowers:test-driven-development`
- Verifying the result → `superpowers:requesting-code-review`,
  `superpowers:verification-before-completion`

Prefer `writing-plans` for serious backend tasks unless the task is clearly
execution-ready. Use `executing-plans` directly only for small, low-risk fixes.

## Do not

- redesign the task without saying so
- silently broaden scope
- touch unrelated code
- skip tests for behavior changes
- hide uncertainty
- claim completion without validation

## Stop and ask

Stop if:
- actual code contradicts the plan
- multiple valid implementation paths appear
- the task requires a larger refactor
- backward-compatibility risk appears
- tests reveal unexpected behavior
- assumptions are wrong

## Greenfield / new service

For new services, require an **Architecture Baseline** before execution
(`docs/agent/new_service_architecture.md`). Default to a simple modular service
with DDD-lite modeling. Do not let structure emerge ad hoc.
