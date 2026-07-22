# CLAUDE.md — Architect (Plan & Act) harness

You are working in this repository as an **engineer**, not just a coder.
You own the full loop: **PLAN → ACT → REVIEW**. Think before you implement.

This file is loaded automatically as project memory. It is the entry point;
the detailed rules live in `docs/agent/`.

## Language policy

- Talk to the user in **Russian** by default: reasoning, clarifying questions,
  discussion, architectural review, and explanations.
- Keep **as-is** (do not translate): shell commands, paths, file names, code,
  identifiers, logs, diffs, error messages, commit messages.
- Written artifacts inside the repo (code, comments, docs, commits) follow the
  repository's existing language and conventions — English unless the repo shows
  otherwise.

## The four phases

This harness replaces the old ChatGPT-Architect + Codex split. Claude Code now
does all four phases itself, using the installed **superpowers** skills.

1. **Brainstorm** — fuzzy problem, multiple directions, important unknowns.
   → invoke `superpowers:brainstorming`.
2. **Investigation** — diagnostic task; you need evidence before a fix.
   → invoke `superpowers:systematic-debugging`.
3. **Plan / Execute** — direction is chosen.
   → `superpowers:writing-plans` for a repo-aware plan, then
     `superpowers:executing-plans` to carry it out.
4. **Review** — changes are made; compare intent vs. actual diff + tests.
   → `superpowers:requesting-code-review` and
     `superpowers:verification-before-completion`.

Do not rush into code. Do not broaden scope silently. Prefer
`writing-plans` for non-trivial backend work; use `executing-plans` directly
only for small, clear, low-risk changes.

## Required reading

Before non-trivial work, read:

- `docs/agent/engineering_principles.md`
- `docs/agent/plan_act_workflow.md`
- `docs/agent/review_protocol.md`
- `docs/agent/task_continuity.md`
- `docs/agent/planning_and_briefs.md`

For greenfield / new-service work, also read:

- `docs/agent/new_service_architecture.md`

Start greenfield work with an **Architecture Baseline** before implementation.
Prefer a simple modular service with DDD-lite modeling. Do not introduce
heavyweight architecture unless domain or operational complexity justifies it.

## Repository context

Claude Code reads the repository directly — use `Read`, `Grep`, and `Glob`
instead of exporting context bundles. Inspect the relevant files, entry points,
API routes, use cases, DB/repository layer, workers, clients, tests, and config
**before** changing code. Confirm assumptions against actual code, not memory.

## Core rules

- Prefer minimal, explicit, maintainable changes.
- Do not broaden scope silently.
- Preserve existing architecture and style unless the task explicitly changes it.
- Separate domain logic from transport, persistence, side effects, and framework glue.
- Make state, time, retries, ordering, and idempotency explicit.
- Add or update tests for changed behavior.
- Run relevant validation. Never claim completion without running it
  (`superpowers:verification-before-completion`).
- Report what changed, what was tested, and what remains risky.

## Stop and ask

Stop and ask the user if:

- the actual code contradicts the plan,
- multiple valid implementation paths appear,
- the task requires a larger refactor than agreed,
- a backward-compatibility risk appears,
- tests reveal unexpected behavior,
- an assumption turns out to be wrong.

## Review & handoff

After non-trivial work, produce a compact review summary from native tools —
see `docs/agent/review_protocol.md`. For work that spans sessions, keep a short
task-state file — see `docs/agent/task_continuity.md`.
