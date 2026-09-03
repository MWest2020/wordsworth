---
status: accepted
last_reviewed: 2026-08-18
---

# ADR-0001: NiFi as production orchestration layer, outside wordsworth

## Context

`CLAUDE.md` currently carries a loose note under banned dependencies:
`"NiFi is not a given."` That was a placeholder, not a decision. This ADR
resolves it.

wordsworth's architecture invariant already states: *"What a consumer does
with the documents afterwards is out of scope"* (see
`docs/reference/architecture.md`). wordsworth is the engine — a single
linear pipeline (`ingest → text extraction → anonymize/pseudonymize → store →
index → hybrid search → rank`) with an append-only, hash-chained audit trail
in PostgreSQL as its only orchestration state. There is no workflow engine
inside wordsworth, by design.

The organization's long-term direction is to run Apache NiFi as the
production orchestration layer across the broader document-handling
landscape (multiple municipalities, multiple source systems), once wordsworth
moves from PoC to production. Separately, wordsworth's `/ingest` endpoint
needs to handle concurrent calls reliably at volumes around 5,000 documents,
which it does not yet do safely (unconfigured DB connection pool, no bounded
concurrency against the OpenAnonymiser/Ollama backends).

## Decision

1. **NiFi orchestrates *above* wordsworth, not *inside* it.** NiFi calls
   wordsworth's existing `/ingest` HTTP API (e.g. via `InvokeHTTP`) as one
   node in a larger flow spanning multiple source systems and
   municipalities. NiFi does not replace or duplicate any pipeline step,
   state machine, or audit mechanism internal to wordsworth.

2. **wordsworth's audit trail and NiFi's provenance are different scopes,
   not competing sources of truth.** wordsworth's audit trail is the record
   of what happened to a document *inside the straat* (register → profile →
   extract → anonymize → index). NiFi's provenance is the record of how a
   document moved *between systems* before and after wordsworth touched it.
   Neither replaces the other; neither is duplicated.

3. **The NiFi flow configuration lives in its own repository/component**,
   deployed and versioned separately from wordsworth. It is not an OpenSpec
   change against this repo, and is not touched by wordsworth's builder/
   reviewer/security agents.

4. **OpenAnonymiser is unaffected.** It remains the anonymization adapter
   (Presidio + GLiNER + deterministic regex), reused as-is per the existing
   invariant. Nothing about this decision touches the anonymize step.

5. **Kafka is explicitly deferred.** NiFi's own FlowFile queues provide
   backpressure between processing steps, which covers the current need.
   Kafka becomes relevant only if/when multiple independent systems need to
   consume the same document stream concurrently — not the case today. This
   is a re-evaluation trigger, not a rejection.

6. **wordsworth's own concurrency handling is separate, scoped work**,
   tracked as individual OpenSpec changes against this repo (see
   Consequences), independent of whether the caller is NiFi, a script, or a
   human uploading via `/docs`.

## Consequences

- `CLAUDE.md`'s "NiFi is not a given" note is updated to reflect this
  decision, and records that a NiFi-orchestrated production deployment is the
  target state.
- Two OpenSpec changes follow from this ADR, scoped to wordsworth itself:
  - `add-request-concurrency-controls` — bounded concurrency (semaphore or
    equivalent) around calls to the OpenAnonymiser and Ollama backends, so
    that concurrent callers (NiFi or otherwise) cannot exceed downstream
    capacity.
  - `configure-db-pool-sizing` — explicit `pool_size`/`max_overflow` on the
    SQLAlchemy engine in `db.py`, sized for expected concurrent request
    volume.
- Scaffolding the separate NiFi component/repo is out of scope for this ADR
  and for wordsworth's OpenSpec tracking; it is a follow-up piece of work in
  its own right, once this ADR is accepted.

## Alternatives considered

- **NiFi replaces wordsworth's internal pipeline** (each step as a NiFi
  processor). Rejected: would duplicate the audit-trail-as-state-machine
  invariant with NiFi's own provenance tracking, creating two systems of
  record for the same internal transitions — the opposite of "boring and
  auditable."
- **Introduce Kafka now, ahead of need.** Rejected: no current use case
  (single consumer of the document stream); would add a second durable log
  alongside the existing Postgres audit trail without a concrete requirement
  driving it.
- **Do nothing / leave "NiFi is not a given" unresolved.** Rejected: leaves
  an open architectural question unrecorded, which is itself an audit
  finding waiting to happen.
