# Planning Modes & Brief Templates

How to frame a task before and during the Plan & Act loop. In Claude Code the
"brief" is not handed to a separate tool — it is how you structure your own
thinking before invoking a superpowers skill, and it becomes the plan produced
by `superpowers:writing-plans`.

## Planning modes

### Brainstorm
Use when the problem is still underdefined.
Goal: reduce ambiguity and compare directions.
→ `superpowers:brainstorming`

### Investigation
Use when the task is diagnostic.
Goal: classify the failure pattern, identify missing evidence, and design the
minimum useful data collection before proposing a fix.
→ `superpowers:systematic-debugging`

### Plan / Execute
Use when the direction is sufficiently chosen.
Goal: derive a repo-aware plan, then execute within scope.
→ `superpowers:writing-plans`, then `superpowers:executing-plans`

### Review
Use after changes are implemented.
Goal: compare the original objective with the actual diff, tests, and validation.
→ `superpowers:requesting-code-review`, `superpowers:verification-before-completion`

## Choosing the entry point

- More structured exploration needed → `superpowers:brainstorming`
- Direction chosen, needs a repo-aware plan → `superpowers:writing-plans`
- Small, clear, low-risk change → `superpowers:executing-plans`

Prefer `writing-plans` for serious backend tasks unless the task is clearly
execution-ready.

## Greenfield / new service

Require an **Architecture Baseline** before execution
(`new_service_architecture.md`). Default to `superpowers:writing-plans` and a
simple modular service with DDD-lite modeling unless constraints justify another
approach.

## Effort

Match effort to risk. Small local/docs/formatting changes stay lightweight;
API changes, migrations, concurrency, CDC, data-correctness, security, and
production-critical work get full planning, tests, and review. (There is no
per-task "intelligence" switch in Claude Code — this replaces the old
`Codex intelligence: low|medium|high|extra high` line.)

---

## Brainstorm frame

- Objective
- Current Context
- Facts
- Assumptions
- Key Unknowns
- Candidate Directions
- Decision Criteria
- Risks of Premature Implementation
- What Must Be Clarified Next

## Execution / plan frame

- Objective
- Why
- Scope
- Non-goals
- Relevant Context (files, entry points, layers)
- Architecture Baseline (greenfield only — style, domain boundaries, module/layer
  structure, source of truth, state & side effects, testing strategy,
  observability, docs)
- Facts
- Assumptions
- Likely Affected Areas
- Suggested Execution Sequence
- Constraints / Guardrails
- Tests
- Validation
- Stop-and-Ask Conditions
- Risks
- Done When
- Review (see `review_protocol.md`)

## Context pointers (already enforced by CLAUDE.md)

- Follow `CLAUDE.md` at the repo root.
- Follow `docs/agent/*` guidance.
- Read the repository directly with `Read` / `Grep` / `Glob` — no context export.
- For long tasks, keep `.agent/tasks/<task-id>/state.md` (see `task_continuity.md`).
