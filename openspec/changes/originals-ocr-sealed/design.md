# Design

## Order: owner check, then write

```
new_key = "documents/" + sha256(ocr_bytes)
owner = live_document_for(session, new_key)
if owner and owner.id != doc.id:
    supersede(session, doc.id, owner.id, actor="ocr", as_object=new_key)
    return SUPERSEDED                  # nothing written
wrote = originals.put_original(doc.id, new_key, ocr_bytes)
try:   repoint object_key, transition to EXTRACTABLE (as today)
except: if wrote: originals.objects.delete(new_key); raise
```

Why the owner's object needs no write: the owner is a live document, so its
object is stored already (sealed or legacy), and `put_original` must never be
called with a document id that is not the live owner of the key
(`originals-cipher-and-key-store` §3a, rule 1). Since
`deleted-document-releases-object-key`, a deleted document is never an owner.

Sub-threshold OCR output is still not stored, as today.

## What the rules of `put_original` mean here

- Recovering the same scan twice (a retry after a failed commit): the key row
  is gone with the rollback, the object opens under no row, and rule 3 writes
  it again under a new row. Nothing readable is overwritten.
- The OCR'd bytes are already stored as a legacy object with no live owner (a
  recovery from between the two changes, retried): rule 4, no write; the
  document points at the legacy object, which reads as it is.

## Two objects, two rows

The recovered document has the scan (kept, per the ocr spec) and the OCR'd
PDF; each has a key row with `document_id` = the recovered document, so
`originals-crypto-shred` destroys both when it is deleted.

## Files

`recovery.py` is 95 lines; the change replaces the write and reorders two
statements.
