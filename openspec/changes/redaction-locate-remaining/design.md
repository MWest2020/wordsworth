# Design

## Order is part of the design

The invariant error comes first because it is a possible clear-text leak, not a
missing PDF. The value-not-located misses are fail-closed: nothing wrong is
shown. The report comes after `pdf-redaction-match` is deployed, so that the 51
is measured on what the service produces now and not carried over.

## The invariant error

The check in `pseudonymizer.py` stays as it is: it refuses to emit text that may
hold clear PII. The error already carries safe features (`label`, `lengte`,
`in_bron`, `na_vervanging`, `woorden`, `alnum`). Those are the evidence; if they
do not suffice, a feature may be added only if it cannot identify anyone (a
count, a class, a length). Two earlier attempts to reproduce it from outside
failed because the real path runs the deterministic layer first and chunks on
other boundaries, so the investigation runs inside the real path on the stored
original, not a rebuild of the loop.

## The report

The existing `POST /reprocess` `problems` list already names document, type and
counts. The report groups that by PII type, with the number of documents and the
located-of-occurrences counts. It is run on the deployed service and the result
is the measurement; it is not a re-run of logic over a fixture.

## Counts only

The report and any module added by this change log type, length and counts. A
value, a page text or a context window never enters a log line, an error, an
audit record or a PR description.

## Rejected alternatives

- **Diagnose per type and fix per cause in this change**: the causes are not
  known and the report may show that fewer remain; those become their own
  changes, written after the report.
- **Rebuild the flat boxes here**: not decided; same reason.
- **Assume the 51 still stands**: it predates `pdf-redaction-match`.
- **Fuzzy or approximate locating**: can leave part of a value unredacted.
- **Skip an unlocated value and serve the PDF**: a partly redacted PDF.
- **Print the surviving value to find it faster**: no PII read.
