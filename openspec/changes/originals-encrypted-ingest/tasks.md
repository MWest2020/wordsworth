# Tasks

A skipped test counts as failed for every reviewer. Tests use `FakeTransit`
and the in-memory store unless stated.

- [ ] 1.1 `pipeline.ingest` per design.md "Ingest order": register first, then
      `put_original`; delete the written object if `ingest` fails after it.
      Proved by: a test that the stored object starts with the sealed header,
      does not contain a marker string from the PDF, and opens to the PDF
      bytes; a test that the key row's `document_id` is the registered
      document; a test with a failing dossier add that no object and no row
      remain.
- [ ] 1.2 Re-ingest: the same bytes twice give one document, one key row and
      an unchanged object; the bytes of a live legacy document leave the
      plaintext object untouched; the bytes of a deleted document (after
      `deleted-document-releases-object-key`) give a new document whose
      original opens. Proved by: three tests.
- [ ] 1.3 Crash between key row and object write: with a store that raises on
      `put`, the ingest call fails, and after rollback no document, no key row
      and no object exist; with a commit that fails after the write, the next
      ingest of the same bytes yields a document whose original opens.
      Proved by: two tests.
- [ ] 2.1 The five readers read through `get_original`, with `originals`
      replacing `store` in `process`, `reanonymize` and `recover` and in every
      caller (`api.py`, `ingest_corpus.py`, `ingest_manifest.py`,
      `reprocess.py`, `serve.py`). Proved by: an end-to-end test that ingests,
      processes, reanonymizes, and fetches the redacted and the reveal PDF of a
      sealed document; a test that OCR recovery reads a sealed scan; and a
      grep test that `.get(doc.object_key)` and `.get(document.object_key)`
      appear nowhere in `src/`.
- [ ] 2.2 Legacy documents still read: a document ingested before this change
      (plaintext object, no key row) is processed and its PDFs are served.
      Proved by: a test.
- [ ] 3.1 Fail closed: with a Transit that raises, ingest via the API answers
      503 `key service unavailable` in reversible and in irreversible mode and
      nothing is in the store; the CLIs exit non-zero; a PDF route on a
      sealed document answers 503. Proved by: four tests, none of which finds
      a plaintext object afterwards.
- [ ] 3.2 Wrong KEK and tampered objects at the routes: a sealed object whose
      bytes were changed, or swapped with another document's sealed object,
      gives an error at the PDF routes and never PDF bytes. Proved by: two
      API tests.
- [ ] 3.3 No plaintext or key bytes in logs: during ingest, process, both PDF
      routes and the failure cases above, the captured logs contain neither a
      marker string from the PDF nor the data key (raw, hex, base64). Proved
      by: a test.
- [ ] 4.1 `serve.py` builds one `OriginalsStore` over `OpenBaoTransit` in both
      modes and passes it to `create_app`. Proved by: a test of `build_app`
      with a fake Transit.
- [ ] 5.1 Docs: `docs/how-to/originals-encryption.md` (what is sealed, the
      deploy precondition from design.md, what an unreachable OpenBao does,
      `wordsworth-sealed-orphans`, the OCR gap until `originals-ocr-sealed`);
      `docs/reference/ingest.md` and `docs/reference/architecture.md` updated.
      Proved by: the docs gate.
