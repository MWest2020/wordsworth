# Tasks

Step 4 of 4, split from `detect-dutch-particle-names` (#285). Build after
`particle-names-rule` has merged.

## 1. The layer
- [ ] `dutch_particle_name` in `_LAYERS` of `src/wordsworth/eval/pii_run.py`,
      and a `--layers` option in `src/wordsworth/eval/overdetection_run.py`
      with default `deterministic,openanonymiser`. Proved by:
      `tests/test_particle_names_eval.py`: `build_detect(["dutch_particle_name"])`
      returns a `PERSON` for a synthetic particle name;
      `build_detect(["deterministic", "openanonymiser"])` (stub client) returns
      none for it; the defaults of both `--layers` options are unchanged.

## 2. Measured
- [ ] Run `python scripts/eval/generate_ground_truth.py /tmp/gt --count 500`,
      then `python -m wordsworth.eval.pii_run /tmp/gt/gold.jsonl` "before"
      (`--layers deterministic,openanonymiser`) and "after" (plus
      `dutch_particle_name`); record the PERSON numbers, the date and the exact
      layers in `docs/reference/evaluation.md`, labelled as circular. If the
      service is unreachable, record "not run".
- [ ] Record full-pipeline PERSON recall with the `per_layer` breakdown on a
      constructed set of names whose first names are not in the gazetteer's
      source, saying how the set was built.
- [ ] Run `python -m wordsworth.eval.overdetection_run gold.jsonl --layers
      deterministic,openanonymiser,dutch_particle_name --out
      docs/explanation/meting-overdetectie-<nn>.md`; the file names the layers
      it ran.
- [ ] Both docs state in one sentence each that recall on real documents is
      unknown and that the Gooise Meren miss is not closed. Proved by: a grep
      finds both sentences, and no doc says the miss is fixed.

## 3. Docs
- [ ] `docs/reference/evaluation.md` documents the opt-in layer and how to run
      before and after. Proved by: the section names the `--layers` value.

## 4. Check
- [ ] `openspec validate particle-names-measured --strict` passes.
- [ ] `uv run ruff check src/ tests/` is clean and the full test suite passes.
