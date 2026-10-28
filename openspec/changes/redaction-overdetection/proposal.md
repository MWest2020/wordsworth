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

1. **Deliver the measurement harness and its output format**: precision,
   recall, leaks and false positives per type, with and without the current
   lists, and how the five words are typed, as counts per type, written to
   `docs/explanation/meting-overdetectie-07.md`. The corpus is synthetic or
   fixture sentences only, never the pilot corpus.
2. **Deliver a counts-only guard test**: the measurement emits no value and no
   document text.
3. **Add a requirement that nothing logs a value** in the measurement or any
   diagnostic.
4. **Label the output** "what detection would do now on this text", not "what
   it did" (the pitfall of meting 05).
5. **State the live run as a separate step**: running the harness against
   OpenAnonymiser (`WORDSWORTH_OPENANONYMISER_URL`) is for Mark or the coding
   session, not for the build. If the service is unreachable the report says
   "not run"; it never shows a deterministic-only table as the baseline.

Amended after the architect's FAIL on the first build: reading real documents is
a data-handling decision for Mark, not for a builder, and a live run does not
fit in a build.

## Follow-up changes (not in this change)

Each is written as its own change once Mark has decided on the numbers: the
allow entries, the DATE_TIME judgement, the event name, the threshold choice and
the reprocess run.

## Open questions

- Which of the follow-ups ship, and in what order, depends on the numbers and is
  Mark's call. Nothing here pre-empts it.
- Whether counts over the pilot corpus (including `suppressed_by_list` of stored
  runs) are ever read is Mark's data-handling decision. This change does not
  read them.
- `redacted-pdf-overdetection` changes which spans get boxed; whether it shifts
  the baseline is not known.

## Impact

- Specs: `anonymization` (ADDED, two requirements).
- Code: the measurement harness, its output format and the counts-only guard
  test; no change to what is redacted.
- Docs: `docs/explanation/meting-overdetectie-07.md` (new: format first, numbers
  after the live run) and
  `docs/reference/evaluation.md`.
