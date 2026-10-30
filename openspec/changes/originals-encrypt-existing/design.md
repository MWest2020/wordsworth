# Design

Sealed objects are written under the same object key (the plaintext hash), so
the object key, provenance and de-duplication don't change; the write replaces
the plaintext. To never be without a readable copy, the run first writes the
sealed bytes under a temporary key `sealing/<sha256>`, verifies it opens and
hashes right, then overwrites `documents/<sha256>` and verifies again, then
deletes the temporary object. A failure at any step leaves the plaintext
original in place and the document reported as failed. One commit per
document, like `wordsworth-dedupe`.
