# Tasks

## 1. Baseline
- [ ] Run the evaluation without and with the current lists
      (`python -m wordsworth.eval.pii_run gold.jsonl`, with and without
      `--lists`) and record precision, recall, leaks and false positives per
      type, with the date. Proved by: the numbers in
      `docs/explanation/meting-overdetectie-07.md`.
- [ ] Record, per type, how the five named values are typed today, on the
      evaluation corpus and in `suppressed_by_list` of the latest run. Proved
      by: counts per type in the same file; a check over the file finds no
      document text in it.

## 2. Nothing logs a value
- [ ] The measurement and any diagnostic over stored runs emit counts, types and
      non-personal identifiers only. Proved by: a test that runs the measurement
      on a seeded document and asserts no seeded value appears in its output or
      captured logs.

## 3. Docs (must change with the code)
- [ ] `docs/explanation/meting-overdetectie-07.md`: the baseline and its date
      (06 is taken by `meting-webadressen-06`). Proved by: the file exists with
      the table and the date.
- [ ] `docs/reference/evaluation.md`: how the baseline is run and read, with
      and without `--lists`, and that it prints no values. Proved by: the
      section gives both commands.
- [ ] `openspec validate redaction-overdetection --strict` passes.

## Follow-up changes (not tasks here)
Written once Mark has decided on the numbers: the allow entries, the DATE_TIME
judgement, the event-name judgement, the choice between allow list and score
threshold, and the reprocess run.
