# CLAUDE.md — mparlament-backend

Guidance for agents working in this repository.

## Project

Python backend (FastAPI + Alembic + Pydantic v2 + dataclasses) for Parlament Młodych RP,
replacing the frontend's MSW mock. **`BACKEND_SPEC.md` is the source of truth** (the contract the
React frontend expects). Architecture: **Domain-Driven Design + Vertical Slices + TDD**, SOLID /
KISS / YAGNI. Per-feature implementation briefs live in `plan_steps/*.md` — read
`plan_steps/README.md` and `plan_steps/CONVENTIONS.md` before implementing anything.

Stack decisions: Python 3.12; **SQLite async** now (aiosqlite + SQLAlchemy 2.0), Postgres/MySQL
later (keep repositories DB-agnostic); realtime (Socket.IO) deferred; backend on port `4000`.

## Git workflow — branch per feature, merge to main

**`main` is the integration branch.** Every feature is developed on its own branch and finishes by
merging back into `main`. No direct commits to `main`.

1. **Start from an up-to-date `main`:**
   ```
   git checkout main
   git pull            # if a remote exists
   ```
2. **Create a feature branch** named `feature/<slice-or-topic>`, matching the `plan_steps` doc
   being implemented. Examples:
   - `feature/00-project-setup`
   - `feature/02-auth-identity`
   - `feature/05-votings`
   ```
   git checkout -b feature/05-votings
   ```
3. **Work TDD-style on the branch:** commit in small, meaningful steps (red → green → refactor).
   Write clear commit messages; end each with the Co-Authored-By trailer.
4. **Finish the feature by merging into `main`:** only merge when the slice's tests are green
   (`pytest` passes for that slice, and the full suite still passes).
   ```
   git checkout main
   git merge --no-ff feature/05-votings      # --no-ff keeps a visible feature merge commit
   ```
   Then delete the merged branch:
   ```
   git branch -d feature/05-votings
   ```
5. **One feature = one branch = one merge.** Do not bundle multiple `plan_steps` docs into a single
   branch. Build order is in `plan_steps/README.md`.

### Rules
- Never commit directly to `main`; always go through a `feature/*` branch and merge.
- Only merge to `main` when tests pass — `main` must always be green.
- Prefer `git merge --no-ff` so each feature is a distinguishable merge in history.
- Commit/push only when the user asks; branching for local work is fine.

### Repo state note
The repo currently sits on branch `master` with **no commits yet** and **no `main` branch**.
Before the branch-per-feature flow can run, `main` must be established — e.g. an initial commit
(project scaffolding / `plan_steps`) on a `main` branch. Confirm with the user before creating the
initial commit or renaming `master` → `main`.

## Testing

TDD is mandatory. Order within a slice: domain unit tests → application use-case tests → API
integration tests (`httpx.AsyncClient`). Run `pytest` before every merge to `main`.

## Commit trailer

End every commit message with:
```
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```
