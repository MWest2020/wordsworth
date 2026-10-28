# Tasks

## 1. Harness and output format
- [ ] Make the measurement run on synthetic or fixture sentences only (never the
      pilot corpus), without and with the current lists
      (`python -m wordsworth.eval.pii_run gold.jsonl`, with and without
      `--lists`), reporting precision, recall, leaks and false positives per
      type, and how the five named values are typed as counts per type. Proved
      by: a test on fixture sentences that the report has the per-type table, the
      date and the five counts.
- [ ] The output file is labelled "what detection would do now on this text",
      not "what it did". Proved by: a test that the label is in the output.
- [ ] If OpenAnonymiser (`WORDSWORTH_OPENANONYMISER_URL`) is unreachable the
      report says "not run" and contains no table. Proved by: a test with an
      unreachable URL that asserts "not run" and no deterministic-only table.

## 2. Nothing logs a value
- [ ] The measurement emits counts, types and non-personal identifiers only.
      Proved by: a counts-only guard test that runs the measurement on a seeded
      fixture sentence and asserts no seeded value or surrounding text appears in
      its output or captured logs.

## 3. Docs (must change with the code)
- [ ] `docs/explanation/meting-overdetectie-07.md`: the output format, the label
      and the "not run" state (06 is taken by `meting-webadressen-06`). The
      numbers and date are filled in by the live run, not by the build. Proved
      by: the file exists with the table layout and the label.
- [ ] `docs/reference/evaluation.md`: how the baseline is run and read, with and
      without `--lists`, that it needs the service, says "not run" without it,
      and prints no values. Proved by: the section gives both commands and the
      "not run" rule.
- [ ] `openspec validate redaction-overdetection --strict` passes.

## Separate step, not a build task
The live run against OpenAnonymiser is for Mark or the coding session. It fills
the numbers and date into `meting-overdetectie-07.md`. The build does not run it.

## Follow-up changes (not tasks here)
Written once Mark has decided on the numbers: the allow entries, the DATE_TIME
judgement, the event-name judgement, the choice between allow list and score
threshold, and the reprocess run.
