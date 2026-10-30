# Design

`deletion.py` gains one step after the object removal: `DocumentKeys.destroy(
document_id)` deletes the `document_keys` row and, when no other live
document references its `key_id`, the wrapped key itself. The step runs in the
same transaction as the rest of the content removal; a failure is a hard error
(the existing rule), so a document is never marked deleted with its key alive.
Legacy plaintext originals have no key; deletion behaves as today for them.
