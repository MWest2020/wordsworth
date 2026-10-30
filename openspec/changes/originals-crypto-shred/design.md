# Design

`deletion.py` gains one step after the object removal: `DocumentKeys.destroy(
document_id)` deletes the `document_keys` row and the wrapped key itself. The
step is unconditional: `uq_documents_live_object_key` allows only one live
document per object key, so no other live document can reference the key.
The step runs in the same transaction as the rest of the content removal; a
failure is a hard error (the existing rule), so a document is never marked
deleted with its key alive. Legacy plaintext originals have no key; deletion
behaves as today for them.

## Rejected

- Keeping the key while another live document references the same key (a
  reference count): the uniqueness constraint makes that case impossible, and
  the branch would be dead code that can only hide a mistake.
