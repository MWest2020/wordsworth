## 1. Metrics

- [ ] 1.1 `eval/pii.py`: span-level and token-level P/R/F1 per type + overall;
  `leaks` count. Pure functions, hand-checked tests.
- [ ] 1.2 Gold JSONL loader with validation (spans in range, non-overlapping).
- [ ] 1.3 Per-layer attribution when detections carry `layer`.

## 2. Runner

- [ ] 2.1 `python -m wordsworth.eval.pii gold.jsonl` → table + `--json`.
- [ ] 2.2 Synthetic 10-doc fixture (no real PII) under `tests/fixtures/`.

## 3. Gate

- [ ] 3.1 `docs/reference/evaluation.md` PII section. Suite + CI green;
  `openspec validate add-pii-detection-eval`.
