# Design decisions — fix-key-lifecycle-rotation-audit

## Separate stream, no synthetic document

The document audit table *is* the document state machine; its `document_id` is a
mandatory FK to a real document. A key rotation has no document, so the built
work-around (a sentinel `00000000-…` document row) is exactly the invariant
violation flagged in review: the document state machine now contains a phantom
document whose history is key rotations.

Fix: emit rotation events to a **separate append-only key-lifecycle audit stream**
— the reused zeef audit-JSONL pattern fits — recording `old_key_id`, `new_key_id`,
`entries_reencrypted`, and `actor`. Remove `SYSTEM_DOCUMENT_ID` and
`_ensure_system_document`. No key material is ever logged (already true; keep it).

The global document hash-chain and its verifier are untouched, and querying a real
document's history no longer returns a phantom system document.

## Not in scope

Changing the deanonymize-by-`key_id` selection, escrow, or re-encryption — all
correctly implemented already.
