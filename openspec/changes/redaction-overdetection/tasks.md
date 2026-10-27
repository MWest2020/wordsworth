# Tasks

## 1. Baseline (before any change)
- [ ] Run the evaluation without and with the current lists and record
      precision, recall, leaks and false positives per type, with the date.
      Proved by: the numbers in `docs/explanation/meting-overdetectie-07.md`,
      taken before the lists or code change.
- [ ] Record, per type, how the five named values are typed today on the
      evaluation corpus and in `suppressed_by_list` of the latest run. Proved
      by: counts per type in the same file; no document text in it.

## 2. The reduction
- [ ] Allow entries for the words Mark has approved, each typed and with a
      reason (`lists/allow.json`). Proved by: the list loads, and
      `tests/test_allow_list_veiligheid.py` stays green with the new entries.
- [ ] A test per entry: the word is not redacted under its type and still is
      under another type. Proved by: the test, one per entry.
- [ ] If a score threshold is chosen instead: it suppresses only below the
      configured score, is off by default, and the suppressed count is
      recorded per type. Proved by: a test with an entity below and one above
      the threshold, and the count in the audit aggregates.

## 3. After
- [ ] Run the same evaluation on the same corpus and record the difference.
      Proved by: a second table in `meting-overdetectie-07.md` with the same
      columns; recall on seeded PII and leaks equal to the baseline.
- [ ] State the false positives removed in `suppressed_by_list` from the run
      itself, not from comparing two rounds. Proved by: the number cites the
      run that produced it.

## 4. Docs (must change with the code)
- [ ] `docs/how-to/detection-lists.md`: the new entries or threshold, and the
      typed-per-type rule for the words concerned. Proved by: the section names
      each.
- [ ] `docs/reference/evaluation.md`: how the before/after is run and read.
      Proved by: the section gives the command with and without `--lists`.
- [ ] `docs/explanation/meting-overdetectie-07.md`: the measurement. Proved by:
      the file exists with baseline, after and date.
- [ ] `openspec validate redaction-overdetection --strict` passes.
