---
status: accepted
last_reviewed: 2026-10-30
---

# ADR 0008 — Envelope encryption of the original documents

- Status: accepted (Mark, 2026-10-30)
- Date: 2026-10-30
- Context: data autonomy — the organisation that owns the documents holds the
  keys to them, and can take them away

## Context

wordsworth pseudonymises before it indexes, and the clear PII values behind the
tokens are encrypted per type under envelope-wrapped keys (ADR-0002). The
**original documents are not**: ingest writes the PDF bytes to the object store
as they arrived (`pipeline.py`, `store.put(key, pdf_bytes)`, key
`documents/<sha256 of the bytes>`). Anyone with read access to the bucket, or
to a copy of it, reads every original in clear — every name the pipeline
pseudonymised, and everything it did not detect.

That contradicts the promise the rest of the design makes. The index holds
tokens, the mapping store holds ciphertext, reveal is gated and audited — and
the bucket next to it holds the plaintext originals.

## Options

**A. Storage-level encryption** (SeaweedFS SSE, or an encrypted disk).
Transparent to wordsworth; protects a stolen disk or a stolen backup medium.
It does **not** separate who may read: every client with bucket credentials
reads plaintext, an operator of the store reads plaintext, and there is no
per-document or per-organisation key, so no cryptographic deletion and no way
for an organisation to withdraw its data by withdrawing a key.

**B. Envelope encryption in the application.** Each original gets its own
random 256-bit data key (DEK); the object stored is AES-256-GCM ciphertext; the
DEK is persisted only wrapped by a key-encryption key (KEK) in OpenBao Transit,
exactly the construction ADR-0002 already uses for the PII keys. Without the
KEK the bucket and every copy of it are unreadable. Deleting the wrapped DEK
destroys the document cryptographically (crypto-shredding), including in
backups that still hold the object.

**C. B, with a KEK per organisation (BYOK / HYOK).** The KEK that wraps an
organisation's DEKs lives in *that organisation's* key service (its own
OpenBao or HSM). The operator of wordsworth cannot read the organisation's
originals without the organisation's key service answering; the organisation
can revoke its KEK and every one of its documents becomes unreadable at once.

## Decision

**B now, built so that C is a configuration choice, not a rewrite.**

- **A DEK per document**, random (not derived: ADR-0005 D2 declined derived
  per-document keys; this is "wrapping, not derivation", as the NORA deck
  itself advises). The DEK never touches disk in clear.
- **Object format**: a small versioned header (magic, format version, DEK
  `key_id`, nonce) followed by the AES-256-GCM ciphertext. The associated data
  binds the ciphertext to the document id and to the SHA-256 of the plaintext,
  so an object swapped between documents fails to decrypt.
  *Amended 2026-10-31:* the associated data is the object key (which is
  `documents/` + the SHA-256 of the plaintext) and the `key_id`, without the
  document id. One object can belong to successive documents (a superseded
  copy, a re-ingest after deletion); binding the document id would force a
  re-seal over a stored object at every change of owner. A swapped or copied
  object still fails to decrypt. Reasoning in
  `openspec/changes/originals-cipher-and-key-store/design.md` §3.
- **The object key stays `documents/<sha256 of the plaintext>`**, so
  de-duplication by content still works and the existing provenance (source
  hash) stays comparable. The hash reveals equality of content, not content.
- **The KEK is named per domain** (the pseudonymisation domain, ADR-0007's
  `add-domain-keys`), with the OpenBao address and KEK name in configuration
  per domain. One domain per organisation makes option C a matter of pointing a
  domain at the organisation's own key service.
- **Reading goes through one driver** (an encrypting object store behind the
  existing `ObjectStore` seam): every caller that reads an original (the
  pipeline, OCR, reprocess, the redacted and reveal PDF) gets plaintext through
  it and nothing else changes shape. Mixed mode while migrating: a stored
  object without the header is legacy plaintext and is read as such, never
  written as such.
- **Crypto-shredding on delete**: deleting a document destroys its wrapped DEK
  as part of the deletion (alongside removing the object), so a copy of the
  object that survives anywhere is unreadable.
- **Where the DEKs live**: first in wordsworth's key vault (the same pattern
  as `key_vault`); after ADR-0009, in the separate key-and-reveal service.

## Consequences

- **Backups**: a backup of the object store is useless without the key store;
  a backup of the key store without the KEK is useless too. Both must be backed
  up, and the KEK escrowed (ADR-0002 custody; key export in ADR-0009).
- **Key loss is data loss.** Losing the KEK, or a DEK and its escrow, loses the
  documents. That is the point of option C and the risk of it; escrow and a
  tested recovery are part of the work, not an afterthought.
- **Migration of the existing corpus**: a one-off run re-writes every legacy
  plaintext object encrypted, dry-run first, and verifies before and after: the
  object count, and per document that the decrypted bytes hash to the recorded
  source hash. The plaintext object is removed only after its encrypted
  successor verifies. Replicated copies (SeaweedFS `001`) follow the object.
  Built as the chain `originals-cipher-and-key-store` →
  `deleted-document-releases-object-key` → `originals-encrypted-ingest` →
  `originals-ocr-sealed` → `originals-crypto-shred` →
  `originals-encrypt-existing` (the migration itself). The chain replaced
  `originals-envelope-encryption` (#306), which was too large to build at
  once; its decisions are in `originals-cipher-and-key-store/design.md`.
- **WORM and Object Lock**: the audit exports (S3 Object Lock, COMPLIANCE)
  contain no originals, so nothing changes there. Should originals ever sit
  under a retention lock, crypto-shredding is the only deletion that remains
  possible during retention — which is the reason to have it.
- **Availability**: ingest and every read of an original depend on the KEK
  being reachable. A sealed OpenBao means ingest stops (fail-hard) and the
  redacted/reveal PDF is unavailable (fail-closed); search is unaffected (it
  reads only the index). The unwrap cache of ADR-0002 bounds the blast radius.
- **Cost**: AES-GCM over a PDF is negligible next to OCR and NER; one unwrap
  per document read, cached.
