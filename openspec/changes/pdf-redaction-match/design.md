# Design

## Line breaks are a separator

`_flatten` currently drops `\r`/`\n`. Each run of them becomes ONE space with
rect `None`, like the spaces `page_chars` inserts: nothing is drawn for it, and
the last word of a line no longer fuses with the first word of the next. The
per-line rectangle split (`_line_groups`) is unchanged.

## Words are joined by `\s*`

The value is split on whitespace and its escaped words are joined with `\s*`,
inside the existing whole-word guards. A value detected across a line break then
matches the flattened text, where the break is a single space or nothing.

## Match the way normalisation compares

The token is the HMAC of `normalize(type, value)`; the mapping store keeps the
first spelling seen. The stored value can therefore differ from the page in the
ways normalisation ignores. The locator uses the same rule per type:

- `_casefold` types (PERSON, ORGANIZATION, LOCATION, EMAIL): `re.IGNORECASE`.
- POSTCODE: whitespace-insensitive.
- Every other type: unchanged.

## Rejected alternatives

- **Case-insensitive for every type.** Looser than normalisation; it could box
  text whose token would differ.
- **Store every spelling in the mapping store.** Changes what the store keeps, a
  separate promise, and does not fix causes 1 and 2.
- **Relax the count check.** The fail-hard rule stays: no partly redacted PDF.

## Gate

The count check stays as is. The three documents return 200 on `redacted.pdf`
after reprocess.
