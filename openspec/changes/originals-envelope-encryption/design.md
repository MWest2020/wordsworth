# Design

- **Format**: `WWENC` magic, 1-byte version, 16-byte DEK `key_id`, 12-byte
  nonce, then the GCM ciphertext + tag. AAD: `document_id || sha256(plaintext)`.
- **Seam**: `EncryptingObjectStore(inner: ObjectStore, keys: DocumentKeys)`
  wraps the S3 driver; callers keep calling `get`/`put`. The document id is
  needed for AAD: `put_original(document_id, key, data)` / `get_original(
  document_id, key)`; plain `get`/`put` stay for non-original objects (redacted
  cache, exports) and are unchanged.
- **Keys**: `DocumentKeys` mints a random 32-byte DEK, wraps it via the
  existing `Transit` seam (FakeTransit in tests), stores the wrapped blob, and
  unwraps with the ADR-0002 unwrap cache. Clear DEK material is never logged,
  never written, never part of an exception message.
- **Document id before the write** (amended after architect FAIL on #305):
  `pipeline.ingest` assigns the document id (or derives it from the content
  hash) BEFORE the store write. `put_original(document_id, key, data)` seals
  under a fresh DEK only for a new document. When `register_live` returns an
  existing document for identical bytes, ingest does not re-seal and does not
  overwrite: it reuses the existing ciphertext and wrapped key. A re-ingest
  therefore leaves one wrapped key and the original ciphertext intact.
- **One live document per object key** (replaces the earlier "shared DEK"
  idea): `uq_documents_live_object_key` allows one live document per object
  key, so there is no shared-key case. Each DEK belongs to exactly one live
  document, and the shred path (`originals-crypto-shred`) may assume that.
- **Unwrap cache is bounded**: `DocumentKeys` keeps unwrapped DEKs in an LRU
  cache with a fixed maximum size; it never grows toward the size of the
  corpus. `DurableKeyProvider._cache` (pseudonymisation keys) is left alone: it
  is keyed per domain, not per document, so it is already bounded by the number
  of domains, and changing it is outside this change.
- **Availability** (decided as a default, pending Mark): ingest fails closed
  with a clear, named error when OpenBao is unreachable. There is no plaintext
  fallback. Irreversible-mode ingest, which needed no key service before, now
  needs it; the how-to and the deploy notes say so.
- **Every original write is sealed, OCR recovery included** (amended after
  architect FAIL on #306): `recovery.py:78` (`store.put(new_key, ocr_bytes)`,
  reached from `api.py:1119`) goes through `put_original` like ingest, and
  `object_key` is repointed to the ciphertext object. The OCR'd PDF gets its
  own DEK for its own document id. Rejected: leaving recovery in clear until
  `originals-encrypt-existing`; that would keep writing new plaintext originals
  after this change.
- **Backup and escrow are a deploy precondition** (amended): `document_keys`
  must be in the database backup and the KEK escrowed before this change is
  deployed. Rejected: leaving this to `key-export-escrow`, which comes last in
  the chain, after originals are already sealed.
- **Irreversible mode fails closed too** (working default, Mark can overrule):
  with OpenBao unreachable, ingest in irreversible mode raises the named error,
  with no plaintext fallback.
- **Existence rules exclude DELETED**: `deletion.py` never removes the row or
  sets `superseded_by`, so `live_document_for` alone still returns a deleted
  document. The re-ingest rule ("Re-ingest does not re-seal") and every other
  rule that asks whether a document already exists use `live_document_for`
  and additionally treat state DELETED as "does not exist". Re-ingesting bytes
  of a deleted document therefore creates a new document with a new DEK.
- **Fourth guess-point of the #306 architect finding**: not settled; see the
  proposal's open questions. Nothing is designed for it here.
