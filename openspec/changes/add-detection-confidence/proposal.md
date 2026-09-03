## Why

The target architecture requires the audit trail to record, per detected PII,
**which detection layer** found it and **with what confidence** ("wie, wat,
wanneer, welke sleutel, detectielaag, confidence"), and wants confidence
thresholds per layer to be configurable. OpenAnonymiser already returns a
`score` per entity (`PIIEntity.score`, Presidio-derived); wordsworth's driver
drops it and keeps only type + span. The deterministic layer (BSN elfproef,
IBAN mod-97, email) has no score at all. Nothing in the audit says *how* a
value was found, so precision/recall problems cannot be traced to a layer.

## What Changes

- The detection seam returns `(entity_type, text, start, end, layer, score)`.
  Deterministic detectors report `layer="deterministic"`, `score=1.0`;
  OpenAnonymiser entities report `layer="openanonymiser"` and the service score.
- Per-document audit record for the de-identify step carries
  `detections: {layer: {entity_type: {count, min_score, max_score}}}` —
  aggregates only, never values, never offsets.
- Optional minimum score `WORDSWORTH_DETECTION_MIN_SCORE` (default `0.0` = keep
  today's behaviour). Entities below it are **not** dropped silently: they are
  still redacted (fail-safe toward the index) but counted separately as
  `below_threshold` so the operator can see what a stricter threshold would cost.
  Dropping low-score entities from redaction is explicitly *not* offered — that
  would trade privacy for readability, against the index invariant.
- `GET /documents/{id}` metadata exposes the same aggregates.

## Capabilities

### Modified Capabilities
- `openanonymiser`: driver preserves layer and score per entity.
- `audit-trail`: de-identify step records per-layer detection aggregates.

## Impact

- Code: `openanonymiser_driver.py`, `detectors.py`, `pseudonymizer.py` (entity
  tuple → small dataclass), `pipeline.py` (audit payload), `config.py`.
- No schema change (audit content is JSON). Tests for score passthrough and
  aggregate shape. No behaviour change to what gets redacted.
