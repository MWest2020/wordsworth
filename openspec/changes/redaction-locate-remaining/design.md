# Design

## Order is part of the design

The invariant error comes first because it is a possible clear-text leak, not a
missing PDF. The value-not-located misses are fail-closed: nothing wrong is
shown. A fix is written only after a diagnostic has named its cause; the
earlier changes (`pdf-redaction-locate`, `pdf-redaction-match`) show that a
plausible guess about the cause was wrong more than once.

## The invariant error

The check in `pseudonymizer.py` stays as it is: it refuses to emit text that may
hold clear PII. The error already carries safe features (`label`, `lengte`,
`in_bron`, `na_vervanging`, `woorden`, `alnum`). Those are the evidence; if they
do not suffice, a feature may be added only if it cannot identify anyone (a
count, a class, a length). Two earlier attempts to reproduce it from outside
failed because the real path runs the deterministic layer first and chunks on
other boundaries, so the diagnostic runs inside the real path on the stored
original, not a rebuild of the loop.

## The diagnostic

Per document and PII type it reports: occurrences in the anonymised text,
whole-word matches in the positioned text, and a cause class from a closed
list (for example: split by the extractor, differs in case, differs in
whitespace, absent from the positioned text). A closed list cannot quote a
document. It does not print a value, a page text or a context window, and it is
run against the stored data in the deployed environment.

ORGANIZATION is covered by the same run, including 4d58906e.

## Fixes

Each fix keeps the count check intact: a token that occurs more often in the
anonymised text than its value is located stays `value-not-located` and 409.

## Flat boxes

The two documents are rebuilt with `reanonymize`, which regenerates the box map
with `char_box`: the tight box, or the loose box when the tight one is empty.
The render keeps refusing boxes without surface.

## Rejected alternatives

- **Fix by guess, then measure**: earlier guesses about the cause were wrong.
- **Fuzzy or approximate locating**: can leave part of a value unredacted;
  rejected by `pdf-redaction-locate` and again here.
- **Skip an unlocated value and serve the PDF**: a partly redacted PDF.
- **Diagnose ORGANIZATION in a separate change**: the 4 misses overlap with
  4d58906e; doing it twice costs a second run.
- **Print the surviving value to find it faster**: no PII read.
