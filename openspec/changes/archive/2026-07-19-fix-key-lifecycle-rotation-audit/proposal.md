## Why

The built key rotation (merged in #13) audits into the **document** hash-chain via
a synthetic system document. Fixes issue #19.

`key_lifecycle.py` defines `SYSTEM_DOCUMENT_ID = UUID("00000000-…0000")` and
`_ensure_system_document` inserts a real `Document(id=SYSTEM_DOCUMENT_ID,
object_key="__system__/key-management")` so the NOT-NULL `document_id` FK is
satisfied, then appends rotation events to the global document chain. A key
rotation is system-wide and has no document; forcing it into the document chain
pollutes the document state machine with a phantom document whose "lifecycle" is
really key rotations.

## What Changes

- Rotation events SHALL be emitted to a **separate append-only key-lifecycle audit
  stream**, NOT the document hash-chain. The synthetic system document is removed.
- The document audit table keeps its invariant: `document_id` stays NOT NULL and
  carries only real documents; no sentinel rows.
- Deanonymize-by-`key_id`, escrow, mapping re-encryption, and no-key-material
  logging are already correct and unchanged.

## Capabilities

### Modified Capabilities
- `key-lifecycle`: rotation auditing moves off the document chain to a separate
  key-lifecycle stream.

## Impact

- Corrects `src/wordsworth/key_lifecycle.py` (drop `SYSTEM_DOCUMENT_ID` /
  `_ensure_system_document`; write to the key-lifecycle stream). No document or
  document-audit schema change. Does not touch `CLAUDE.md`, `.claude/agents/`, CI.
- Archive-order: archive only after `add-key-lifecycle` is archived — the baseline
  `openspec/specs/` does not carry this capability until then.
