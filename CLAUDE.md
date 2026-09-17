# CLAUDE.md — wordsworth contract

This file is the single contract. Every agent reads it. The **reviewer** and
**security** agents test a change against **this file + the change only** —
never against anything else. If a rule matters, it lives here, literally.

> Values below come from the project brief and from decisions since; edit here,
> not in the agents. Maintained by Claude, sharpened by Mark.

## What wordsworth is

A sovereign pipeline turning large volumes of (mostly Dutch) government
documents into a searchable, privacy-safe corpus:

`ingest → text extraction → anonymize/pseudonymize → store → index → hybrid search → rank`

What a consumer does with the documents afterwards is out of scope. Boring and
auditable beats fast or clever — always name the "clever pitfall" when relevant.

## Hard constraints (invariants — non-negotiable)

- **MIT.** All code and dependencies must be license-compatible. Copyleft
  dependencies (EUPL, GPL) cannot be linked into an MIT work — `zeef` moved to
  MIT for exactly this reason. Reject
  AGPL where it would infect distribution (e.g. PyMuPDF — use pypdf/pdfminer).
- **No clear PII toward the search index.** Anonymization is irreversible;
  pseudonymization is controlled and reversible and sits *before* indexing.
- **Mutable audit tables do not exist.** The audit trail is append-only and
  hash-chained; PostgreSQL from day one. No UPDATE/DELETE on audit records.
- **A failed embedding is a hard error, never a silent fallback** (null-vector
  rule). The same principle applies broadly: no silent fallbacks.
- **No cloud APIs in the critical path.** Embeddings and any LLM run locally.
  Claude as a *build* agent is not the pipeline runtime — keep that distinction.
- **Secrets** via SOPS+age or OpenBao only. Never commercially licensed, never
  client-side, never hardcoded.
- **Banned dependencies:** `anonypy` (never); `MinIO` (open-source edition
  deprecated April 2026 — use Ceph RGW or SeaweedFS behind the S3 seam);
  CyberArk/Conjur. **NiFi** orchestrates *above* wordsworth (calls `/ingest`),
  never inside it — see [ADR-0001](docs/adr/0001-nifi-orchestration.md); Kafka
  is deferred.

## Architecture invariants

- **The append-only audit table is the document state machine is the
  orchestration state.** No workflow engine. Every step transition is an audit
  record. `documents.current_state` is *derived* from the latest audit record,
  never stored as a mutable column.
- **Driver/protocol pattern for every adapter** (anonymization, key/mapping
  store, object storage, search, embeddings).
- **Born-digital only for the PoC.** Scanned PDFs → status `unprocessable_ocr`
  in the audit trail. OCR is MVP-backlog.
- **Files ≤ 200 lines.**

## Stack

- Python 3.12+ managed with **`uv`** (never `pip`), FastAPI, pydantic v2.
- PostgreSQL. S3-compatible object storage (Ceph RGW target / SeaweedFS PoC).
- OpenSearch for BM25 (phase 3) and dense+hybrid/RRF (phase 4).
- Local inference: Ollama (bge-m3) for embeddings; GLiNER/Presidio via
  OpenAnonymiser for PII.

## Reused components (reuse, do not rebuild)

- **OpenAnonymiser** (`ConductionNL/openanonymiser_light`, EUPL-1.2) —
  anonymization adapter (Presidio + GLiNER + deterministic regex; BSN elfproef,
  IBAN mod-97).
- **zeef** (`MWest2020/zeef`, MIT) — ranking (local Ollama embeddings,
  cosine, UPGMA clustering, append-only audit-JSONL). clustering ≠ ranking;
  reach ≠ relevance; `--no-llm` + cosine is the proven path.

## Working method & governance

- **Does it change a promise?** That is the test, not how big the work is. A
  change to what the system guarantees — what search means, who may see what,
  what a token resolves to — follows OpenSpec: propose → apply → archive, and no
  code before the change is applied. Everything else is a GitHub issue and can
  simply be done. Labels: `spec-nodig` and `direct`.
  Size correlates with this and is the wrong test: three lines in `authorize()`
  can be the most dangerous change in the repo, and a rewritten stylesheet is
  not.
- **One change per run**, nothing outside it. "Done = green" (tests pass).
- **Green is not the same as working.** Before calling something done, run the
  real artefact: the installed binary, the deployed service, the page as a
  browser requests it. And run it from the side where you do NOT already hold
  the key — the path a newcomer takes is the one that is actually used, and it
  is the one a green suite is most likely to miss. A refusal that is correct can
  still be a dead end.
- **Measure the artefact the system produced**, not a re-run of the logic over
  the same input. Those answer different questions ("what did it do" versus
  "what would it do now"), and confusing them means reporting on the instrument
  instead of the thing.
- **Merging.** Claude merges its own PRs once the gates are green and reports
  that it did. `main` is deliberately NOT protected (Mark declined branch
  protection; the gate is CI plus the local pre-push hook). What still goes to
  Mark: anything that changes a promise and has an open question in it, and the
  agent definitions in `.claude/agents/`.
- **This file is maintained by Claude** (Mark, 2026-09-17) and records how we
  actually work. `.claude/agents/`, `CODEOWNERS` and CI config stay Mark's.
  Note that `CODEOWNERS` still lists `/CLAUDE.md` as his and says agents must
  never modify it; that line is now out of date and its correction is his call,
  not something to change from here.
