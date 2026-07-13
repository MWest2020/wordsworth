# Habitat builder — apply-docs-contract

_run_id builder-apply-docs-contract-20260712-185653 · verdict ok · 2026-07-12T18:59:03Z_

---

Done. The `apply-docs-contract` change is implemented and committed on the current branch. I stopped short of pushing/opening the PR since that's outward-facing and the Habitat runner + Mark own that step — the commit is ready.

## What I did

**`docs/` (minimum viable, per contract):**
- `docs/index.md` — short overview, status, link to README (points to it, doesn't replace), links to sections.
- `docs/reference/architecture.md` — pipeline, invariants, stack, configuration; distilled from README + the project brief (no `openspec/project.md` exists in this repo).

**Front matter** on every page: `status: draft` + `last_reviewed: 2026-07-12` (migration date, no content review yet), **no `owner` field**, English only.

**`.mcp.json`** — already present from the seed and matches the template with the `TODO-change-3` placeholder, so it's untouched (task 2.4 satisfied without a change).

**No migration/stubs** — the only loose markdown was `README.md` and `CLAUDE.md`, both of which stay in place; nothing to migrate.

## Self-check (task 3.1) — all pass
- Only allowed subdirs carry markdown (`index.md` at root + `reference/`); no stray files.
- Every page has front matter with `status` + `last_reviewed`, no `owner`.
- One language (English).

## Scope guard
Diff touches only `docs/` and the change's `tasks.md` checkboxes. **No** changes to `CLAUDE.md`, `.claude/agents/`, CI, or CODEOWNERS.

## Notes / deviations
- **Branch:** task 1.1 asked for `docs/contract`, but the Habitat runner placed me on `habitat/builder/apply-docs-contract`; I worked and committed there rather than fight the runner's convention. Noted inline in `tasks.md`.
- **Task 4.1 (PR) left unchecked:** committed but not pushed. Ready PR title: `docs: apply handbook docs contract`. Merge belongs to Mark. Let me know if you want me to push and open the PR.
