# Locate values the way normalisation compares them

## Why

The orchestrator, from the odin coding session: *"pdf-redaction-locate is
deployed. Problems are now reported, but the same 3 documents still get no box
map (value-not-located, DATE_TIME)."* The documents are 4d58906e, 00213a91 and
006bb702. A count-only diagnostic in the pod (values never printed) found three
causes in `pdf_boxes.py`:

1. `_flatten` drops line breaks without a separator, so a value at the end of a
   line is glued to the first word of the next line (`2022Gemeente`) and fails
   the whole-word check. This was 5 of 6 misses.
2. A value can contain a newline, because it was detected across a line break.
3. The mapping store keeps the FIRST spelling of a token (`on_conflict_do_nothing`)
   while the token is the HMAC of the normalised value. A casefold type
   (PERSON, ORGANIZATION, LOCATION, EMAIL) can then have a stored spelling that
   differs in case from this page.

With all three applied in the diagnostic every token was located: 4d58906e
167/167, 00213a91 130/130, 006bb702 45/45.

A fourth, smaller bug: the `reprocess.py` problems message prints the counts
swapped. *"'1 of 0 located' means 1 in text, 0 located."*

This changes a promise (when a value counts as located, and so when a redacted
PDF can be produced), so it is an OpenSpec change.

## What changes

- `_flatten` replaces each run of `\r`/`\n` with ONE space whose rect is `None`.
- A value's words are matched with `\s*` between them, so a value spanning a line
  break is found.
- Matching follows normalisation: case-insensitive for types whose rule is
  `_casefold` (PERSON, ORGANIZATION, LOCATION, EMAIL), whitespace-insensitive for
  POSTCODE.
- The `value-not-located` problems message reads `located of in-text`.
- A test per cause.
- Documents 4d58906e, 00213a91 and 006bb702 are reprocessed and each returns 200
  on `redacted.pdf`.

## Open questions

None.
