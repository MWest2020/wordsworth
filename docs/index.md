---
status: draft
last_reviewed: 2026-09-03
---

# wordsworth docs

wordsworth is a sovereign pipeline that turns large volumes of (mostly Dutch)
government documents into a searchable, privacy-safe corpus. This `docs/` tree
follows the handbook docs contract; the project overview lives in the
[README](../README.md), which this page points to rather than replaces.

**Status:** proof-of-concept, under construction. Design and delta specs live
under `openspec/`.

## Sections

- [reference/](reference/architecture.md) — facts: pipeline architecture,
  invariants, stack, and configuration.
  - [evaluation](reference/evaluation.md) — the IR evaluation run: CLI,
    id-matching precondition (`object_key` = qrels doc ids), runtime needs.
  - [cli](reference/cli.md) — the `wordsworth` API client: install, commands,
    ingesting a directory.
- [explanation/](explanation/nora-gap-analysis.md) — reasoning and decisions.
  - [NORA gap analysis](explanation/nora-gap-analysis.md) — wordsworth tested
    against the "Anonimiseren & Pseudonimiseren bij de Bron" target architecture;
    verdict per requirement, build order.
  - [ADR-0005](explanation/adr/0005-nora-target-architecture-alignment.md) —
    what wordsworth adopts, adapts and declines from that architecture.
  - [detection lists](how-to/detection-lists.md) — allow/deny JSON lists,
    `lists_hash` in audit, the feedback endpoint.
  - [dataset pseudonymisation](how-to/dataset-pseudonymisation.md) — CSV
    column path: profiles, per-attribute/per-record, NEN 7524-style output.
