# deleted-document-releases-object-key

## Why

A deleted document keeps its row (the audit trail points at it) and keeps its
`object_key` with `superseded_by` NULL. `uq_documents_live_object_key` and
`live_document_for` therefore still count it as *the* live document for its
bytes: ingesting the same PDF again adopts the deleted row, whose object is
gone, and OCR recovery's owner check treats it as an owner. The architect named
this on #306 ("a deleted document does not count as existing" cannot be built
against this index). It is an existing defect, independent of encryption, and
the encryption chain needs every existence rule to be right without a special
case for deleted documents. Second change of the chain after
`originals-cipher-and-key-store` (see its design.md §4).

## What changes

- Deleting a document **releases its object key**: in the same transaction as
  the `deleted` record, the row's `object_key` becomes `deleted/<document_id>`.
  The former key (a content hash, no personal data) is recorded in the
  `deleted` audit record as `released_object_key`.
- The object-removal check of the deletion runs against the former key, before
  the release, so a superseded copy that still claims the object keeps it, as
  today.
- `wordsworth-release-deleted-keys [--apply]`: a one-off, idempotent release for
  documents deleted before this change (dry-run by default), each with an audit
  record.
- After the release, re-ingesting the bytes of a deleted document creates a new
  document, and the deleted one stays deleted.

## Out of scope

Encryption (the other changes of the chain). Superseded copies keep their keys:
they are not live and are not in the unique index.
