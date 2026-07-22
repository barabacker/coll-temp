# Review Protocol (native)

At the end of every non-trivial task, review your own work before claiming it is
done. Claude Code reads the repository directly, so there is no Repomix export —
use `git` and direct file reading.

## Self-review steps

1. Run `superpowers:requesting-code-review` on the change.
2. Run `superpowers:verification-before-completion` — actually run the tests and
   validation, and read the output before making any success claim.
3. Re-read the changed files and their immediate neighbors to confirm the change
   fits the surrounding code.

## Evidence to gather

Collect these from native commands (run and read the output — do not assume):

```
git status --short
git diff --stat
git diff
git branch --show-current
git log --oneline --decorate -20
```

Plus the relevant test / lint / typecheck / build commands for this repository,
with their real output.

## Review summary

Report back to the user:

- summary of changes
- commands run and their real output (especially tests)
- files changed
- known risks
- open questions

## Optional written report

If the user wants a persistent handoff artifact (e.g. to paste elsewhere), write
a short report to `docs/review/<task-id>-review.md` or `/tmp/<task-id>-review.md`
containing:

- original objective
- summary of changes
- commands run + test output
- `git status` / `git diff --stat`
- current branch + recent log
- risks / open questions
- continuation notes for long tasks (see `task_continuity.md`)

Do not produce this file unless it is useful — inside Claude Code the review is
usually done live against the diff and the running tests.

## After review

Do not immediately start a follow-up task unless follow-up work is actually
needed. For non-trivial follow-ups, prefer `superpowers:writing-plans`; use
`superpowers:executing-plans` only for small, clear, low-risk fixes.
