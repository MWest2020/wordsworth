# Tasks

A skipped test counts as failed for every reviewer. Tests use `FakeTransit`
and the in-memory store unless stated. Order per design.md "Order of work".

- [ ] 1.1 Test scaffolding, one mechanical commit: a `mem_originals` fixture in
      `tests/conftest.py`, and the positional and `store=` signature changes
      (`originals` replacing `store`) across the ~22 test files that call
      `process`, `reanonymize`, `recover`, `ingest` or `create_app`. Proved by:
      the existing suite passes unchanged in behaviour (same tests, same
      results, no skips added) and `grep -rn "store=" tests/` finds no caller
      of the changed functions.
- [ ] 2.1 One shared transit-factory helper returning `transit_for(kek_name)`
      with one cached `OpenBaoTransit` per KEK name. Proved by: a test that a
      second call for the same KEK name returns the cached instance and a
      different name returns a different one.
- [ ] 2.2 `serve.py` and the three CLI modules (`ingest_corpus.py`,
      `ingest_manifest.py`, `reprocess.py`) all use the helper; none builds a
      transit itself. Proved by: a grep test that `OpenBaoTransit(` appears in
      `src/` only inside the helper.
- [ ] 3.1 The five readers read through `get_original`, with `originals`
      replacing `store` in `process`, `reanonymize` and `recover` and in every
      caller (`api.py`, `ingest_corpus.py`, `ingest_manifest.py`,
      `reprocess.py`, `serve.py`). Proved by: an end-to-end test that ingests,
      processes, reanonymizes, and fetches the redacted and the reveal PDF of a
      sealed document; a test that OCR recovery reads a sealed scan; and a
      grep test that `.get(doc.object_key)` and `.get(document.object_key)`
      appear nowhere in `src/`.
- [ ] 3.2 Legacy documents still read: a document ingested before this change
      (plaintext object, no key row) is processed and its PDFs are served.
      Proved by: a test.
- [ ] 3.3 Wrong KEK and tampered objects at the routes: a sealed object whose
      bytes were changed, or swapped with another document's sealed object,
      gives an error at the PDF routes and never PDF bytes. Proved by: two
      API tests.
- [ ] 4.1 `pipeline.ingest` per design.md "Ingest order": register first, then
      `put_original`; delete the written object if `ingest` fails after it.
      Proved by: a test that the stored object starts with the sealed header,
      does not contain a marker string from the PDF, and opens to the PDF
      bytes; a test that the key row's `document_id` is the registered
      document; a test with a failing dossier add that no object and no row
      remain.
- [ ] 4.2 Re-ingest: the same bytes twice give one document, one key row and
      an unchanged object; the bytes of a live legacy document leave the
      plaintext object untouched; the bytes of a deleted document (after
      `deleted-document-releases-object-key`) give a new document whose
      original opens. Proved by: three tests.
- [ ] 4.3 Crash between key row and object write: with a store that raises on
      `put`, the ingest call fails, and after rollback no document, no key row
      and no object exist; with a commit that fails after the write, the next
      ingest of the same bytes yields a document whose original opens.
      Proved by: two tests.
- [ ] 5.1 Fail closed: with a Transit that raises, ingest via the API answers
      503 `key service unavailable` in reversible and in irreversible mode and
      nothing is in the store; the CLIs exit non-zero; a PDF route on a
      sealed document answers 503. Proved by: four tests, none of which finds
      a plaintext object afterwards.
- [ ] 5.2 Batch stops at the first unavailable key: a batch to `POST /ingest`
      where file 2 fails with `OriginalsKeyUnavailable` leaves file 1 stored
      and sealed, answers 503 with the fixed message `key service unavailable`
      plus the per-file report listing file 1, and stores neither file 2 nor
      any later file. Proved by: an API test with a three-file batch whose
      transit fails on the second file.
- [ ] 5.3 No plaintext or key bytes in logs: during ingest, process, both PDF
      routes and the failure cases above, the captured logs contain neither a
      marker string from the PDF nor the data key (raw, hex, base64). Proved
      by: a test.
- [ ] 6.1 `serve.py` builds one process-lifetime `OriginalsStore` in both modes,
      whose `DocumentKeys` gets the helper's `transit_for(kek_name)` factory
      (`originals-cipher-and-key-store` design.md "KEK per domain"), and
      passes it to `create_app`. Proved by: a test of `build_app` with a
      name-keyed fake factory, and a test that two documents in domains with
      different KEKs are sealed under different `kek_ref`s.
- [ ] 7.1 Docs: `docs/how-to/originals-encryption.md` (what is sealed, the
      deploy precondition from design.md, what an unreachable OpenBao does
      including the batch behaviour of task 5.2, `wordsworth-sealed-orphans`,
      the OCR gap until `originals-ocr-sealed`); `docs/reference/ingest.md`
      (the 503 body with the per-file report) and
      `docs/reference/architecture.md` updated; `docs/reference/cli.md` for
      the CLI exit on an unavailable key. Proved by: the docs gate.
