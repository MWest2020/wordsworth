# Tasks

A skipped test counts as failed for every reviewer.

- [ ] 1.1 `recover` checks the owner before writing, per design.md. Proved by:
      a test where the OCR'd bytes are another live document's sealed object:
      that object is byte-for-byte unchanged, no key row is added, and the
      scan's document is superseded by the owner.
- [ ] 1.2 The OCR'd PDF is written with `put_original` under the recovered
      document. Proved by: a test that the new object starts with the sealed
      header, contains no marker string from the OCR text, opens to the OCR'd
      bytes, has a key row with the document's id, and that the scan object
      and its row are unchanged; the existing test that extract then reads
      non-empty OCR text passes on the sealed object.
- [ ] 1.3 Failure after the write: with a session that fails at the
      transition, the written object is deleted and the document still points
      at its scan; a retry recovers it and its original opens. Proved by: a
      test.
- [ ] 1.4 Fail closed: with a Transit that raises, `recover` raises
      `OriginalsKeyUnavailable`, nothing is written, and the document stays
      `unprocessable_ocr`. Proved by: a test.
- [ ] 1.5 A legacy OCR'd object from before this change, recovered again, is
      left as it is and the document reads it. Proved by: a test.
- [ ] 1.6 No plaintext or key bytes in logs during recovery and its failure
      cases (marker string and data key, raw, hex, base64). Proved by: a test.
- [ ] 2.1 Docs: `docs/how-to/originals-encryption.md` drops the OCR gap note
      and says recovered PDFs are sealed. Proved by: the docs gate.
