## 1. Seam

- [ ] 1.1 `Detection` dataclass (`entity_type, text, start, end, layer, score`);
  deterministic detectors emit `layer="deterministic", score=1.0`.
- [ ] 1.2 OpenAnonymiser driver keeps `score` from `entities_found`; missing
  score → hard error (no silent default), per the no-silent-fallback rule.

## 2. Audit + metadata

- [ ] 2.1 De-identify audit record: `detections` aggregates per layer/type
  (count, min/max score, `below_threshold` count). Never values/offsets.
- [ ] 2.2 `WORDSWORTH_DETECTION_MIN_SCORE` (default 0.0); below-threshold
  entities still redacted, counted separately.
- [ ] 2.3 `GET /documents/{id}` exposes the aggregates.

## 3. Gate

- [ ] 3.1 Tests: passthrough, aggregates, threshold counting does not change
  redaction. Suite + CI green; `openspec validate add-detection-confidence`.
