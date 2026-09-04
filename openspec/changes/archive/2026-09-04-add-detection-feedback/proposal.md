## Why

The target architecture has a feedback loop: a user marks a false positive
("Jansen BV" tagged as a person) or a false negative (missed initials), and a
rule engine (Apache Drools) adjusts detection "without code changes". Drools is
Java and a rules engine is the clever pitfall here — a mutable, hard-to-audit
layer in the critical path. wordsworth has no feedback mechanism at all, so the
same false positive recurs in every document. The boring equivalent is
git-versioned allow/deny lists applied deterministically after detection, plus
an audited way to record the feedback that produced them.

## What Changes

- `WORDSWORTH_DETECTION_LISTS` points at a directory with two JSON files (no
  new dependency): `allow.json` (`{"PERSON": ["^Jansen BV$"]}` — typed
  patterns whose full match is **not** PII of that type) and `deny.json`
  (typed patterns that **are** PII, e.g. a licence-plate shape). Lists are
  versioned in git, loaded at start, and their content hash is written into
  every de-identify audit record (`lists_hash`).
- Applied after detection in the reversible driver: deny adds detections (layer
  `list`, score 1.0); allow removes a same-type detection whose value fully
  matches a pattern (never across types). Removals are counted in the audit
  aggregates under `suppressed_by_list`. The irreversible OpenAnonymiser driver
  applies the **deny** list only (the service redacts server-side, so an allow
  rule cannot un-redact its output); it still records `lists_hash`.
- `POST /documents/{id}/feedback` records `{kind: fp|fn, type, token?}` as an
  audit access event (`detection_feedback`). Token, never a clear value — there
  is deliberately no free-text field. This creates the trail; updating the lists
  remains a reviewed git change by a human. No auto-learning.

## Capabilities

### Modified Capabilities
- `anonymization`: post-detection allow/deny lists, versioned and audited.

## Impact

- Code: `detection_lists.py` (≤ 100 lines), hooks in both drivers, one route,
  `lists_hash` on `AnonymizationResult` + audit payload + metadata, serve wiring. Tests: allow suppresses a typed FP, deny adds, list hash in audit.
- Depends on `add-detection-confidence` for the `layer`/aggregate fields.
