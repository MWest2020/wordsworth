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

- `WORDSWORTH_DETECTION_LISTS` points at a directory with two YAML files:
  `allow.yml` (values or regexes that are **not** PII for a given type, e.g.
  `ORGANIZATION`-suffix patterns like `\bBV\b` → drop PERSON hits) and
  `deny.yml` (values or regexes that **are** PII of a given type, e.g. known
  initials patterns). Lists are versioned in git, loaded at start, hash logged.
- Applied in a post-detection step: deny adds detections (layer `list`,
  score 1.0); allow removes detections — **only** when the allow rule is typed
  and the value matches exactly or by anchored regex. Removal is counted in the
  audit aggregates as `suppressed_by_list`.
- `POST /documents/{id}/feedback` records `{kind: fp|fn, type, token?}` as an
  audit record (token, never clear value — for fn the caller supplies the type
  and an opaque description, no text). This creates the trail; updating the
  lists remains a reviewed git change by a human. No auto-learning.

## Capabilities

### Modified Capabilities
- `anonymization`: post-detection allow/deny lists, versioned and audited.

## Impact

- Code: `detection_lists.py` (≤ 150 lines), hook in the de-identify step,
  one route. Tests: allow suppresses a typed FP, deny adds, list hash in audit.
- Depends on `add-detection-confidence` for the `layer`/aggregate fields.
