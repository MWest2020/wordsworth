# Stop ordinary words being redacted, and measure it before and after

## Why

The orchestrator, from the odin coding session: *"Ordinary words get redacted as
ORGANIZATION/LOCATION/DATE_TIME ('statushouders', 'bewoners',
'woningcorporaties', 'juni', 'wereldvluchtelingendag'); tie it to the existing
over-detection measurement (docs/explanation/meting-overdetectie-*) and propose
an allow-list or score threshold, measured before and after; Mark's PII read
stays a human gate."*

Over-detection is already a measured problem here. `meting-overdetectie-04` and
`-05` showed what a typed allow list wins back and what it costs in recall, and
the rule that came out of it is that an effect is measured on the evaluation
corpus and, across a reprocess, from `suppressed_by_list` of the run itself.
What is new is the five values above. Read against the repo, three facts frame
them:

- `bewoners` already has an allow rule, but only under PERSON
  (`lists/allow.json`). Allow rules never cross types, so the same word typed
  ORGANIZATION or LOCATION is still redacted.
- `statushouders`, `woningcorporaties`, `juni` and `wereldvluchtelingendag` have
  no rule at all, and `allow.json` has no `DATE_TIME` section.
- `detection_min_score` is read only to count `below_threshold` in the audit
  aggregates; it never changes what is redacted (`config.py`). A score threshold
  would therefore be a new behaviour, not a setting that is switched on.

This changes a promise (what is redacted before indexing, and so what search
can find), so it is an OpenSpec change.

## What changes

1. **Measure first.** Run the existing evaluation (`python -m
   wordsworth.eval.pii_run gold.jsonl`, with and without `--lists`) and the
   `suppressed_by_list` counts, and record the baseline with its date next to
   `meting-overdetectie-05`. Precision, recall and leaks, per type.
2. **Reduce over-detection** with whichever of the two mechanisms the
   measurement supports: typed allow rules, or a score threshold that actually
   suppresses (see the open questions).
3. **Measure again** on the same corpus and the same instrument, and record the
   difference. Recall on seeded PII and leaks must not move.
4. **Mark's PII read stays a human gate.** Nobody on the build side reads
   documents to find more candidate words. Allow entries are reviewed by a
   human, with the reason in the file, as today.

## Open questions

- **Allow list or score threshold, or both.** Not decided. A typed allow rule is
  exact, reviewed and already guarded by the corpus check; a threshold is
  general but cuts below a score regardless of word, so it can remove a real
  name that scored low. Which one to ship is decided from the before/after
  numbers, by Mark if the choice is a threshold, since that changes what is
  redacted without a per-word review.
- **Which words go on the list.** Only the five named above are known. Whether
  they are one type each or several (the detector types a word inconsistently,
  as `gemeente Gooise Meren` showed) is found by the measurement, not assumed.
  Further candidates need Mark's read.
- **`wereldvluchtelingendag` is a name of an event.** Whether an event name is
  PII at all is Mark's call; it may be better left redacted.
- **`DATE_TIME`.** `juni` alone is a month, but a full date can identify (a
  birth date is in `pii_categories.py` as a date type). Whether any DATE_TIME
  allow rule is acceptable, and which, is Mark's call.
- **Reprocess.** A list or threshold change only applies to new documents until
  `POST /reprocess` runs; whether to run it, and when, is not decided here.
- `redacted-pdf-overdetection` changes which spans get boxed and builds after
  this change; whether it shifts the numbers above is not known.

## Impact

- Specs: `anonymization` (ADDED).
- Code: the entries or threshold the measurement supports, and nothing else.
- Data: `lists/allow.json` if the allow list is chosen.
- Docs: `docs/how-to/detection-lists.md`, `docs/reference/evaluation.md`, and a
  new `docs/explanation/meting-overdetectie-07.md` for the before/after
  numbers (06 is taken by `meting-webadressen-06`).
