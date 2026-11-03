# particle-names-measured (step 4 of 4)

## Why

Without a seam, the evaluation tooling cannot see the particle rule:
`eval/pii_run.py` registers only `{deterministic, openanonymiser}` and
`eval/overdetection_run.py` hardcodes both, so "before and after" would be
identical by construction (the defect three architect rounds named). Split from
`detect-dutch-particle-names` (#285). Build after `particle-names-rule` has
merged.

## What changes

- `dutch_particle_name` as an opt-in layer in `_LAYERS` of
  `src/wordsworth/eval/pii_run.py` and in `src/wordsworth/eval/overdetection_run.py`
  (a `--layers` option there, default unchanged).
- The measurements: the PII eval before and after, the overdetection run with
  the layer, recorded with the date in `docs/reference/evaluation.md` and
  `docs/explanation/meting-overdetectie-<nn>.md`.

## Impact

- Specs: `anonymization` (ADDED, one requirement).
- Code: `src/wordsworth/eval/pii_run.py`, `src/wordsworth/eval/overdetection_run.py`.
- Tests: `tests/test_particle_names_eval.py` (new).
- Docs: `docs/reference/evaluation.md`, `docs/explanation/meting-overdetectie-<nn>.md`.
