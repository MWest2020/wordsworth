---
status: accepted
last_reviewed: 2026-08-27
---

# ADR-0004: Loose coupling — the core stays headless, experience/UI layers are separate consumers

## Context

wordsworth keeps growing a constellation of surrounding components:
production orchestration (NiFi, `ADR-0001`), source connectors (the
Nextcloud connector, deliberately **withdrawn from the core** and kept as a
standalone artifact that speaks only to the public `/ingest`), the
interactive demo, a planned verifiable-credential reveal verifier
(`ADR-0003`), and now a planned **UI** that develops ranking, anonymisation,
pseudonymisation and key-sharing.

The recurring risk is that presentation-, source-, or orchestration-specific
logic creeps *into* the engine. The Nextcloud episode is the cautionary tale:
a source-specific connector was built inside wordsworth and had to be pulled
back out. The explicit standing directive (Mark, 2026-08-27) is to **guard
that everything we build is microservice / loosely coupled**.

## Decision

**wordsworth core is a headless engine with a stable public API** — the
linear straat (`ingest → extract → pseudonymize → store → index → search →
rank`), grants, reveal, and export — with the append-only hash-chained audit
as its only orchestration state. Nothing else lives inside it.

Everything else is a **separate, independently-deployable consumer** that
talks to wordsworth **only through its public API / contracts**:

- Orchestration → NiFi (`ADR-0001`), above wordsworth.
- Source ingestion → connectors, each standalone, posting to `/ingest`
  (never importing from the package).
- Reveal authorization → the EUDI/VC verifier (`ADR-0003`), opt-in, gating
  reveal in front of OpenBao.
- **Experience / UI → a separate frontend service** (its own repo and
  deploy) that consumes the public API. Its modules — ranking, anonymisation
  & pseudonymisation views, key-sharing (grants) — are UI over the API, with
  **no presentation logic in the core**.

Rules that follow:
1. No source-specific, UI-specific, or orchestration-specific code in the core.
2. Each surrounding component is its own service/repo, independently
   deployable, testable, and replaceable.
3. The public API contract is the only coupling seam; components integrate
   through it, not through shared internals.
4. **Graceful degradation** (resilience invariant): any consumer — UI,
   connector, verifier, orchestrator — can fail without stopping the straat.

## Consequences

- **Positive.** Boundaries are explicit and enforceable; the core stays
  source- and UI-agnostic (the Nextcloud lesson, codified); every component
  is deployable and testable on its own; the planned UI cannot become a
  hidden dependency of the engine.
- **Cost.** The public API becomes the contract that must stay stable and
  well-versioned; some duplication at the seam (each consumer maps the API to
  its own model) is accepted as the price of decoupling.
- **Neutral.** This ADR codifies and generalises existing practice
  (`ADR-0001`, the Nextcloud withdrawal) into a governing principle; it does
  not change any current runtime behaviour.

## The planned UI (scope note, not yet an implementation)

A separate frontend, API-first, consuming wordsworth's public endpoints.
Candidate modules, each backed by an existing capability:

- **Ranking** — search over the pseudonymised index; explain the score.
- **Anonymisation / pseudonymisation** — show a document in index-form; make
  the pseudonyms legible (`Persoon 1`, `Locatie 1`, …).
- **Key-sharing** — grants per department/role; issue, share, revoke;
  key-ring per type; every reveal audited without clear values.

The current interactive demo already prototypes ranking, pseudonymisation and
key-sharing as a self-contained page; it is the seed, but the real UI is a
separate service against the API — never folded into the core.
