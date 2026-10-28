# Investigate the surviving value and build the count-by-type report

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

The first build of this change stopped at the architect check. The decision since,
in one line: split the build from the live measurement. A builder has no access to
the deployed service, and a full reprocess is about half a day of CPU GLiNER (770
documents took 14 hours on 2026-09-20), so the live run does not fit in a build.

This changes a promise (what happens when a value survives replacement, and what
the logs and reports of this work may contain), so it is an OpenSpec change.

## What changes

**Built offline, proved on synthetic input** (tasks 1 and 2):

1. **The invariant error first.** The `AnonymizationInvariantError` (code
   `waarde-overleefde-vervanging`) is investigated using only the safe features
   the error already carries (type, length, counts, word count), or one added
   feature that is a count or a class. A test proves the text is never emitted and
   that the error, its message and the audit record hold no value.
2. **A count-by-type report as code.** It groups the `value-not-located`
   `problems` of a reprocess run by PII type, with document counts and
   located-of-occurrences counts. A test proves it logs and outputs only type,
   length and counts.

**Run live, by an operator, not in the build** (task 3, "Run it live"):

3. Mark or the odin coding session runs `POST /reprocess` over the 415 documents
   on the deployed service, with the report from step 2, and answers one question
   for the real invariant document: is anonymised output outside the redacted PDF
   affected, yes or no. The result goes as a count-only comment on wordsworth#261,
   never into the build or a PR.

**Precondition of the live step, not of the build:** `pdf-redaction-match` is
deployed. Task 3 of that change (the real-artefact check) is still unchecked in
the archive (`openspec/changes/archive/2026-10-26-pdf-redaction-match/tasks.md`),
so the deploy cannot be assumed; the operator confirms it first.

The report and any new module log only type, length and counts, never a value.
Every miss keeps failing closed.

Out of this change, because they are not decided: the per-type diagnostic, the
per-cause fixes and the rebuild of the flat boxes. The live result decides
whether they get their own changes, written after it.

## Open questions

- Whether the surviving value in the invariant case also reaches anonymised
  output outside the PDF is unknown until the live step. If it does, Mark decides
  what happens to the output already produced.
- `redaction-overdetection` changes which spans get boxed and builds after this
  change; whether it shifts the counts is not known.

## Impact

- Specs: `anonymization` (ADDED), `pdf-redaction` (ADDED).
- Code: at most a count or class feature on the invariant error, and the
  count-by-type report.
- Docs: `docs/how-to/pdf-redaction.md`, `docs/how-to/reversible-backfill.md`.
