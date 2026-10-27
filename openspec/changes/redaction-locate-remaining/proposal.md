# Find and fix why 51 documents have no box map

## Why

The orchestrator, from the odin coding session: *"354 of 415 documents have a
box map. The 51 that don't are in wordsworth issue #259, by type, with counts
only: 26 DATE_TIME, 8 LOCATION, 6 PERSON, 5 EMAIL, 4 ORGANIZATION, 1
PHONE_NUMBER value-not-located, plus 1 AnonymizationInvariantError (a value that
survived replacement). Two documents also have flat boxes left; the render
refuses those with a 409."* And on the invariant error: *"a value that survived
replacement means clear text in anonymised output. Look at that first."*

Every miss fails closed today (no PDF rather than a half-redacted one), and that
stays. What is missing is the cause of each miss. The earlier change
`pdf-redaction-match` found its three causes with a count-only diagnostic and
only then fixed them; this change uses the same method for the remaining types.

The 4 ORGANIZATION misses overlap with the ORGANIZATION case of 4d58906e (1 in
text, 0 located). That case is covered here and is not diagnosed separately.

This changes a promise (when a value counts as located, and what happens when
a value survives replacement), so it is an OpenSpec change.

## What changes

In this order:

1. **The invariant error first.** One document raises
   `AnonymizationInvariantError` (code `waarde-overleefde-vervanging`): a
   detected value is still in the text after replacement. Find out which
   document, which type and why, using the safe features the error already
   carries (type, length, counts, word count) and never the value. If anonymised
   output outside the redacted PDF is affected, that goes to Mark at once, not
   into the queue.
2. **A count-only diagnostic per type** for the value-not-located documents
   (DATE_TIME, LOCATION, PERSON, EMAIL, ORGANIZATION, PHONE_NUMBER). It reports
   per document and type the counts and a closed-vocabulary cause class, never a
   value or a page text.
3. **A fix per cause**, only after the diagnostic has named it.
4. **The two documents with flat boxes** are rebuilt so the render no longer
   answers 409 `box map unusable`.

Every miss keeps failing closed. No PII is read.

## Open questions

- Which causes the diagnostic will name is not known yet. The fixes, and the
  requirements that describe them, are added to this change once the diagnostic
  has named them; none is decided here.
- Whether the surviving value in the invariant case also reaches anonymised
  output outside the PDF is unknown until step 1. If it does, Mark decides what
  happens to the output already produced.
- `redacted-pdf-overdetection` changes which spans get boxed and builds after
  this change; whether it shifts the counts above is not known.

## Impact

- Specs: `pdf-redaction` (ADDED), `anonymization` (ADDED).
- Code: the diagnostic (counts only), the fixes it names, a rebuild of the flat
  box maps via `reanonymize`.
- Docs: `docs/how-to/pdf-redaction.md`, `docs/how-to/reversible-backfill.md`.
