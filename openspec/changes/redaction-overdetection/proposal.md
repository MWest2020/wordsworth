# Measure over-detection: record the baseline

## Why

The orchestrator, from the odin coding session: *"Ordinary words get redacted as
ORGANIZATION/LOCATION/DATE_TIME ('statushouders', 'bewoners',
'woningcorporaties', 'juni', 'wereldvluchtelingendag'); tie it to the existing
over-detection measurement (docs/explanation/meting-overdetectie-*) and propose
an allow-list or score threshold, measured before and after; Mark's PII read
stays a human gate."*

The architect failed the first shape of this change: it promised requirements
for allow entries and a threshold that can only be written after the numbers
exist, which breaks propose, apply, archive. So the change is cut to the part
that does not depend on a decision: the measurement.

Read against the repo, three facts frame the five words:

- `bewoners` already has an allow rule, but only under PERSON
  (`lists/allow.json`). Allow rules never cross types, so the same word typed
  ORGANIZATION or LOCATION is still redacted.
- `statushouders`, `woningcorporaties`, `juni` and `wereldvluchtelingendag` have
  no rule, and `allow.json` has no `DATE_TIME` section.
- `detection_min_score` is read only to count `below_threshold` in the audit
  aggregates; it never changes what is redacted (`config.py`).

This changes a promise only in one respect: measurement output must never carry
a value. That is the one requirement added.

## What changes

1. **Record the baseline**: precision, recall, leaks and false positives per
   type, with and without the current lists, with the date, in
   `docs/explanation/meting-overdetectie-07.md`.
2. **Record how the five words are typed today**, as counts per type, with no
   document text.
3. **Add a requirement that nothing logs a value** in the measurement or any
   diagnostic over stored runs.

## Follow-up changes (not in this change)

Each is written as its own change once Mark has decided on the numbers: the
allow entries, the DATE_TIME judgement, the event name, the threshold choice and
the reprocess run.

## Open questions

- Which of the follow-ups ship, and in what order, depends on the numbers and is
  Mark's call. Nothing here pre-empts it.
- `redacted-pdf-overdetection` changes which spans get boxed; whether it shifts
  the baseline is not known.

## Impact

- Specs: `anonymization` (ADDED, two requirements).
- Code: only what keeps the measurement from emitting values; no change to what
  is redacted.
- Docs: `docs/explanation/meting-overdetectie-07.md` (new) and
  `docs/reference/evaluation.md`.
