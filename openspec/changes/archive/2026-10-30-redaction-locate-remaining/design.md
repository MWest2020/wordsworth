# Design

## Build and live run are separate

A builder works offline on synthetic input; it cannot reach the deployed service
and a full reprocess is about half a day of CPU GLiNER. So the build delivers
code and tests, and the measurement on the real corpus is a documented operator
step (task 3) whose result is a count-only comment on wordsworth#261. Nothing the
live step produces enters the build or a PR.

## Order is part of the design

The invariant error comes first because it is a possible clear-text leak, not a
missing PDF. The value-not-located misses are fail-closed: nothing wrong is
shown. The live step needs `pdf-redaction-match` deployed, so that the 51 is
measured on what the service produces now and not carried over. That deploy is a
precondition of the live step only; the archived change still has its real-
artefact task unchecked, so the operator confirms it.

## The invariant error

The check in `pseudonymizer.py` stays as it is: it refuses to emit text that may
hold clear PII. The error already carries safe features (`label`, `lengte`,
`in_bron`, `na_vervanging`, `woorden`, `alnum`). Those are the evidence; if they
do not suffice, a feature may be added only if it cannot identify anyone (a
count, a class, a length). Two earlier attempts to reproduce it from outside
failed because the real path runs the deterministic layer first and chunks on
other boundaries, so the investigation runs inside the real path, not a rebuild
of the loop. In the build this is proved on synthetic input; on the real stored
original it is part of the live step.

## The report

The existing `POST /reprocess` `problems` list already names document, type and
counts. The report groups that by PII type, with the number of documents and the
located-of-occurrences counts. It is a function over the `problems` list, so it
is testable offline; the same code is what the operator runs live. The live
result is the measurement; a run over a fixture is not.

## Run it live: access path

The operator runs it on the host where the service is deployed, through the
service's own reprocess entry points (`wordsworth reprocess --all` or `POST
/reprocess`, see `docs/how-to/reversible-backfill.md`). Credentials, API key
(`X-API-Key`, `docs/how-to/api-auth.md`) and the OpenBao token, come from SOPS or
OpenBao, never from the PR or the repo. The same counts-only rule applies: the
operator keeps only type, length and counts and posts that on wordsworth#261.

## Counts only

The report and any module added by this change log type, length and counts. A
value, a page text or a context window never enters a log line, an error, an
audit record or a PR description.

## Rejected alternatives

- **Run the 415-document reprocess inside the build**: no access to the deployed
  service, about half a day of CPU, and the result would be a PR artefact.
- **Diagnose per type and fix per cause in this change**: the causes are not
  known and the live result may show that fewer remain; those become their own
  changes, written after it.
- **Rebuild the flat boxes here**: not decided; same reason.
- **Assume the 51 still stands**: it predates `pdf-redaction-match`.
- **Fuzzy or approximate locating**: can leave part of a value unredacted.
- **Skip an unlocated value and serve the PDF**: a partly redacted PDF.
- **Print the surviving value to find it faster**: no PII read.
