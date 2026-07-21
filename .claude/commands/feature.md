---
description: Implement a plan_steps feature doc end-to-end (branch, TDD, merge to main)
argument-hint: <doc>  e.g. 05  or  05-votings  or  plan_steps/05-votings.md
---

Implement the plan_steps feature doc identified by: `$ARGUMENTS`

Resolve `$ARGUMENTS` to a file under `plan_steps/` (accept a bare number like `05`, a stem like
`05-votings`, or a full path). If it is ambiguous or no such doc exists, list the `plan_steps/*.md`
options and stop.

Then follow the standing procedure in CLAUDE.md ("Implementing a plan_steps doc"):
read README + CONVENTIONS + the target doc, treat BACKEND_SPEC.md as the source of truth, create
branch `feature/<doc-stem>` from an up-to-date `main`, build test-first (domain → application →
API) with small commits, and — only when the slice tests and the full pytest suite are green —
merge `--no-ff` into `main` and delete the branch. Stay within the slice. Stop and ask if the doc
and the spec disagree.
