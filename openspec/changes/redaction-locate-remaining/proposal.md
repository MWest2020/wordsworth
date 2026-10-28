# Investigate the surviving value, then re-measure the 51 missing box maps

## Why

The orchestrator, from the odin coding session: *"354 of 415 documents have a
box map. The 51 that don't are in wordsworth issue #259, by type, with counts
only: 26 DATE_TIME, 8 LOCATION, 6 PERSON, 5 EMAIL, 4 ORGANIZATION, 1
PHONE_NUMBER value-not-located, plus 1 AnonymizationInvariantError (a value that
survived replacement). Two documents also have flat boxes left; the render
refuses those with a 409."* And on the invariant error: *"a value that survived
replacement means clear text in anonymised output. Look at that first."*

Every miss fails closed today (no PDF rather than a half-redacted one), and that
stays. The 51 were measured before `pdf-redaction-match`; that change may already
have removed some of them, so the number is not assumed but re-measured on the
artefact the deployed service produces.

This changes a promise (what happens when a value survives replacement, and what
the logs and reports of this work may contain), so it is an OpenSpec change.

## What changes

Narrowed to one buildable unit, in this order:

1. **The invariant error first.** One document raises
   `AnonymizationInvariantError` (code `waarde-overleefde-vervanging`): a
   detected value is still in the text after replacement. Investigate it using
   the safe features the error already carries (type, length, counts, word
   count) and never the value. A test proves the text is never emitted. The
   investigation ends in a yes or no: is anonymised output outside the redacted
   PDF affected?
2. **A count-only reprocess report by type**, run on the deployed service after
   `pdf-redaction-match` is deployed. It re-measures the 51 and lists what is
   left by PII type, with counts only.

The report and any new module log only type, length and counts, never a value.
Every miss keeps failing closed.

Out of this change, because they are not decided: the per-type diagnostic, the
per-cause fixes and the rebuild of the flat boxes. The reprocess report decides
whether they get their own changes, written after it.

## Open questions

- Whether the surviving value in the invariant case also reaches anonymised
  output outside the PDF is unknown until step 1. If it does, Mark decides what
  happens to the output already produced.
- `redaction-overdetection` changes which spans get boxed and builds after this
  change; whether it shifts the counts is not known.

## Impact

- Specs: `anonymization` (ADDED), `pdf-redaction` (ADDED).
- Code: at most a count or class feature on the invariant error, and the
  count-by-type report.
- Docs: `docs/how-to/pdf-redaction.md`, `docs/how-to/reversible-backfill.md`.
