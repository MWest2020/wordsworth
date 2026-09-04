## Why

The target architecture demands "metrics: precision, recall, F1-score per
PII-type" and layer-level claims ("laag 1 vangt 60-70%", "laag 3 de laatste
5-10%"). wordsworth can measure ranking quality (R-Prec, MAP, NDCG) but has
**no** PII-detection benchmark: no gold corpus format, no per-type
precision/recall, no leakage count. The only runtime signal is the fail-hard
survivor check. Without this, every detection change (thresholds, new types,
a new OpenAnonymiser version) is unverifiable, and the 60/20/10 layer claims
in the deck cannot be checked against Dutch municipal text.

## What Changes

- Gold format: JSONL, one document per line, `{"id", "text", "entities":
  [{"start","end","type"}]}` — the de-facto NER format, no new invention.
  Synthetic fixtures only in the repo; real gold corpora live outside it.
- `wordsworth.eval.pii`: runs the detection seam over the gold texts and
  computes per type and overall: precision, recall, F1 at **span level**
  (exact) and **token level** (overlap), plus `leaks` = gold entities with zero
  overlap (the number that matters for the index invariant), and per-layer
  attribution using `add-detection-confidence`'s `layer` field.
- CLI: `python -m wordsworth.eval.pii gold.jsonl --openanonymiser-url …`,
  table + JSON output. Pure functions tested against hand-computed cases.

## Capabilities

### Modified Capabilities
- `evaluation`: PII detection metrics per type and per layer, plus a leak count.

## Impact

- Code: `src/wordsworth/eval/pii.py` (+ `pii_run.py` CLI), tests, one fixture.
- Docs: `docs/reference/evaluation.md` gains a PII section.
- No runtime behaviour change. Depends on `add-detection-confidence` for
  per-layer attribution (falls back to overall metrics without it).
