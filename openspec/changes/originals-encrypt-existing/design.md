# Design

Sealed objects are written under the same object key (the plaintext hash), so
the object key, provenance and de-duplication don't change; the write replaces
the plaintext. To never be without a readable copy, the run first writes the
sealed bytes under a temporary key `sealing/<sha256>`, verifies it opens and
hashes right, then overwrites `documents/<sha256>` and verifies again, then
deletes the temporary object. A failure at any step leaves the plaintext
original in place and the document reported as failed. One commit per
document, like `wordsworth-dedupe`.

## Fixed by the split of `originals-envelope-encryption` (2026-10-31)

Two consequences of decisions in `originals-cipher-and-key-store` design.md:

- The associated data binds the **final** object key, so the bytes written to
  `sealing/<sha256>` are sealed for `documents/<sha256>` and verified at the
  temporary location by opening them for that final key.
- Per document: insert the key row with `sealed_at` NULL and commit it before
  anything is written; then the temporary object, verify, overwrite, verify;
  then set `sealed_at` and commit; then delete the temporary object. A crash
  before `sealed_at` is set leaves the plaintext readable (the downgrade guard
  only applies to rows with `sealed_at`), and the run resumes with the row it
  finds.
- `put_original` is not used here: it never replaces a legacy object. Its
  rule 4 (`originals-cipher-and-key-store` §3a, as amended 2026-10-31) covers
  exactly this run's mid-migration state: an object without a sealed header,
  with no key row or with a row whose `sealed_at` is NULL, is "legacy", not
  written. So an ingest of the same bytes while this run is between its two
  commits leaves the plaintext alone, and `get_original` returns it. Once
  `sealed_at` is set, a header-less object is a downgrade. Rule 5 then
  refuses to write over it, and `get_original` refuses to return it.
