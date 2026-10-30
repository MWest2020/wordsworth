# originals-envelope-encryption

## Why

ADR-0008 (accepted 2026-10-30): the original PDFs sit in the object store in
clear (`pipeline.py`, `store.put(key, pdf_bytes)`), next to an index that holds
only tokens and a mapping store that holds only ciphertext. Data autonomy means
the organisation that owns the documents holds the keys to them. This change
encrypts every **new** original; the existing corpus follows in
`originals-encrypt-existing`, deletion in `originals-crypto-shred`.

## What changes

- An encrypting object store behind the existing `ObjectStore` seam: `put`
  seals with a fresh per-document data key (AES-256-GCM, versioned header,
  associated data = document id + plaintext SHA-256); `get` opens. Legacy
  objects without the header are read as plaintext and never written as such.
- The data key is stored only wrapped by the domain's KEK (OpenBao Transit),
  in a `document_keys` table (`document_id`, `key_id`, `wrapped_material`,
  `kek_ref`, `created_at`). The object key stays `documents/<sha256 of the
  plaintext>`, so de-duplication still works.
- Configuration: the KEK name (and OpenBao address) per pseudonymisation
  domain, so a domain can later point at an organisation's own key service.

- Amended after the architect FAIL on #305: the document id exists before the
  store write; a re-ingest of identical bytes reuses the existing ciphertext
  and wrapped key; the unwrap cache is a bounded LRU; there is one live
  document per object key, so no DEK is shared.
- Availability: ingest fails closed, with a named error, when OpenBao is
  unreachable. Irreversible-mode ingest now needs the key service.

## Open questions

- **Availability default, for Mark**: is fail-closed ingest acceptable when
  OpenBao is down? Default: yes, fail closed, no plaintext fallback; ingest
  waits for the key service.
- The full architect verdict on #305 was not readable when this amendment was
  written. The builder resolves any further guess-points in it and records
  them in design.md (see tasks.md section 1).

## Out of scope

Migrating existing objects; deletion; moving keys to a separate service
(ADR-0009, later changes).
