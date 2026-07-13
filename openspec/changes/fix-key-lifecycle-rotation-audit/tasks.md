# Tasks — fix-key-lifecycle-rotation-audit

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.
Fixes #19.

## 1. Rotation audits to a separate stream
- [ ] 1.1 Emit rotation events to a separate append-only key-lifecycle audit
      stream (old/new `key_id`, entries re-encrypted, actor; no key material) —
      not `audit.append` on the document chain
- [ ] 1.2 Remove `SYSTEM_DOCUMENT_ID` and `_ensure_system_document`; no sentinel
      document rows; `document_id` stays NOT NULL with only real documents

## 2. Tests
- [ ] 2.1 A rotation writes a key-lifecycle stream event and leaves the document
      hash-chain unchanged (no new document-audit record, no phantom document)
- [ ] 2.2 The document audit table contains no `00000000-…` sentinel document;
      deanonymize-by-`key_id` still decrypts pre/post-rotation mappings
