# Tasks

## 1. Sealing new originals
- [ ] `EncryptingObjectStore` + `DocumentKeys` behind the `ObjectStore` seam;
      ingest stores originals sealed. Proved by: a round-trip test (put, get,
      bytes equal) against FakeTransit.
- [ ] A tampered wrapped key is refused: a changed `wrapped_material` fails to
      unwrap, with an error and no plaintext. Proved by: a negative test.
- [ ] Plaintext never reaches the search index. Proved by: a test that ingests
      a PDF with a known marker and asserts the marker is absent from the
      indexed documents.
- [ ] The stored object contains no plaintext. Proved by: a test that the raw
      bytes in the inner store don't contain a known marker string from the
      PDF and start with the header.
- [ ] Tampering is refused: a flipped ciphertext byte, a swapped header
      `key_id`, and an object copied to another document's id each fail with
      an error and no plaintext. Proved by: three negative tests.
- [ ] A wrong or unavailable KEK fails closed (no plaintext, no fallback to the
      legacy path for a sealed object). Proved by: a test with a FakeTransit
      under another KEK and one that raises.
- [ ] Legacy plaintext objects are still read; nothing is ever written in
      clear. Proved by: a test with a header-less object, and one asserting
      `put_original` never writes without the header.
- [ ] De-duplication by plaintext hash still works, and a re-ingest neither
      re-seals nor overwrites: `pipeline.ingest` assigns the document id before
      the store write, and when `register_live` returns an existing document it
      reuses the existing ciphertext and wrapped key. Proved by: a test that
      re-ingest of identical bytes leaves one wrapped key and the original
      ciphertext intact (byte-equal before and after).
- [ ] `DocumentKeys` uses a bounded LRU unwrap cache. Proved by: a test that
      opens more documents than the maximum size and asserts the cache size
      stays at the maximum and an evicted key is unwrapped again via Transit.
- [ ] One live document per object key is relied on, not worked around. Proved
      by: a test that a second live document on the same object key is refused
      (`uq_documents_live_object_key`) and that no `document_keys` row is
      shared between documents.
- [ ] Ingest fails closed when OpenBao is unreachable (default pending Mark).
      Proved by: a test with a Transit that raises: ingest raises the named
      error, nothing is written to the object store, no `document_keys` row is
      left, and no plaintext fallback is used.
- [ ] OCR recovery seals too: `recovery.py` writes the OCR'd PDF through
      `put_original` and repoints `object_key` to the ciphertext. Proved by:
      a test that runs the recovery path (also via the `api.py:1119` caller)
      and reads back the OCR'd PDF through the encrypting store.
- [ ] No plaintext original is written after this change. Proved by: a test
      that ingests and OCR-recovers documents with a marker and asserts that
      no `put` on the inner store carries bytes without the header, plus a
      check that no other `store.put` of original bytes exists in `src/`.
- [ ] Irreversible-mode ingest fails closed when OpenBao is unreachable, with a
      clear error and no plaintext fallback (working default, Mark can
      overrule). Proved by: a test in irreversible mode with a raising Transit.
- [ ] Existence rules exclude state DELETED. Proved by: tests with a DELETED
      document (row kept, `superseded_by` unset): re-ingest of its bytes
      creates a new document with a new DEK and does not reuse the deleted
      one's ciphertext; and each other rule using `live_document_for` for
      "already exists" (including `recovery.py:79` and `api.py:1072`) has a
      test with a DELETED document.
- [ ] Backup of `document_keys` and escrow of the KEK are a precondition of
      deploy. Proved by: the deploy task and the runbook (see section 3) state
      it, and the backup procedure is shown to include `document_keys`.
- [ ] The fourth guess-point of the #306 architect finding is read and settled
      before the build. Proved by: it is removed from the proposal's open
      questions and recorded in design.md with a test named here.
- [ ] Clear key material never reaches logs or exceptions. Proved by: a test
      capturing logs during seal/open/failure and asserting the DEK bytes (hex
      and base64) are absent.
## 2. Configuration
- [ ] KEK name and OpenBao address per domain, defaulting to the current KEK.
      Proved by: a config test; docs.
## 3. Docs
- [ ] `docs/reference/architecture.md` (storage section) and a how-to
      `docs/how-to/originals-encryption.md` (what is encrypted, where the keys
      are, what a sealed OpenBao means). ADR-0008 linked. Both state that
      irreversible-mode ingest now needs the key service and fails closed with
      the named error when OpenBao is unreachable. Proved by: the docs
      contain that statement (grep in review).
- [ ] Deploy notes (the how-to's deployment section; no separate deploy doc
      exists under `docs/`) say that OpenBao must be reachable by the ingest
      path before this change is deployed, and that `document_keys` is backed
      up and the KEK escrowed first (deploy precondition, not left to
      `key-export-escrow`). The runbook says the same. Proved by: grep in
      review.
- [ ] `docs/how-to/deleting-documents.md` and the OCR recovery description in
      `docs/reference/architecture.md` say OCR'd originals are sealed too, and
      that a deleted document does not count as existing for re-ingest.

## 4. Negative and security tests (required)
A skipped test counts as failed for every reviewer.
- [ ] Wrong key, tampered wrapped key, and plaintext never in logs or index
      each have a test that runs, not skips. Proved by: the pytest run shows
      zero skips among them (check the skip list, not only the exit code).
