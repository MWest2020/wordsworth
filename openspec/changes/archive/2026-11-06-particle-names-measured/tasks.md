# Tasks

Step 4 of 4, split from `detect-dutch-particle-names` (#285). Build after
`particle-names-rule` has merged.

## 1. The layer
- [x] `dutch_particle_name` in `_LAYERS` of `src/wordsworth/eval/pii_run.py`,
      and a `--layers` option in `src/wordsworth/eval/overdetection_run.py`
      with default `deterministic,openanonymiser`. Proved by:
      `tests/test_particle_names_eval.py`: `build_detect(["dutch_particle_name"])`
      returns a `PERSON` for a synthetic particle name;
      `build_detect(["deterministic", "openanonymiser"])` (stub client) returns
      none for it; the defaults of both `--layers` options are unchanged.

## 2. Measured
- [x] Run `python scripts/eval/generate_ground_truth.py /tmp/gt --count 500`,
      then `python -m wordsworth.eval.pii_run /tmp/gt/gold.jsonl` "before"
      (`--layers deterministic,openanonymiser`) and "after" (plus
      `dutch_particle_name`); record the PERSON numbers, the date and the exact
      layers in `docs/reference/evaluation.md`, labelled as circular. If the
      service is unreachable, record "not run".
- [x] Record full-pipeline PERSON recall with the `per_layer` breakdown on a
      constructed set of names whose first names are not in the gazetteer's
      source, saying how the set was built.
- [x] Run `python -m wordsworth.eval.overdetection_run gold.jsonl --layers
      deterministic,openanonymiser,dutch_particle_name --out
      docs/explanation/meting-overdetectie-<nn>.md`; the file names the layers
      it ran.
- [x] Both docs state in one sentence each that recall on real documents is
      unknown and that the Gooise Meren miss is not closed. Proved by: a grep
      finds both sentences, and no doc says the miss is fixed.
- [x] Reviewer finding: lines 66-70 of `docs/explanation/meting-overdetectie-08.md`
      mix unquoted English and Dutch in one paragraph. Rewrite them so the page
      keeps one language per paragraph. The disclosures "Recall on real
      documents is unknown", "The Gooise Meren miss is not closed by this
      change" and "not run" may appear only as quoted literal phrases inside
      Dutch prose, or as their own fully English paragraphs, never mixed
      mid-sentence. The phrases stay byte-exact. Proved by: a grep for each
      of the three phrases still finds it in the page; and a check on the
      page (a test, or a reviewed grep) finds no paragraph holding both
      unquoted English disclosure text and Dutch text, in particular none
      in the rewritten lines 66-70.

## 3. Docs
- [x] `docs/reference/evaluation.md` documents the opt-in layer and how to run
      before and after. Proved by: the section names the `--layers` value.

## 4. Check
- [x] `openspec validate particle-names-measured --strict` passes.
- [x] `uv run ruff check src/ tests/` is clean and the full test suite passes.
