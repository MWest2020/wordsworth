# originals-ocr-sealed

## Why

After `originals-encrypted-ingest`, OCR recovery is the last writer of an
original that still writes plaintext (`recovery.py:78`, a plain `put`). It
also writes **before** it checks whether another document already owns the
OCR'd bytes (`recovery.py:79`): with sealed objects that order would let a
recovery overwrite another document's sealed object. The architect named both
on #306. Fourth change of the chain, built right after
`originals-encrypted-ingest` to close the gap that change documents.

## What changes

- `recover` checks the owner of the OCR'd PDF's key **before** writing
  anything. Another live document owns it: nothing is written and the scan is
  retired as a copy of it, as today (`supersede(..., as_object=new_key)`).
- Otherwise the OCR'd PDF is written with
  `put_original(doc.id, new_key, ocr_bytes)`: sealed, under its own key row
  for the recovered document. The scan object stays as it is, with its own key
  row (one row per object, `originals-cipher-and-key-store` design.md §5).
- If `recover` fails after that write, it deletes the object it wrote.
- The ocr spec says the OCR'd PDF is stored sealed.

## Out of scope

OCR'd PDFs written as plaintext between the two changes stay legacy objects
until `originals-encrypt-existing` seals them.
