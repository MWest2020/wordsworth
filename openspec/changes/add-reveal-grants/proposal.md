## Why

Fase B's key-gated reveal needs an authorization layer that can be **shared** and
**revoked** per PII type — the sovereign key-management pillar the government
stumbled on. Per-type keys and selective `deanonymize` exist, but nothing decides
*who* may reveal *which* types for *which* document, nor lets that permission be
granted to a recipient and later revoked, with an audit trail. This cycle adds the
grant model + enforcement + audit; the HTTP reveal endpoint that consumes it comes
in a later cycle.

## What Changes

- **`grants` table + `GrantRecord`** (models.py): grant_id, recipient,
  allowed_types (upper-case PII types), nullable document_id (NULL = global),
  status (active/revoked), created_at, revoked_at, expires_at, actor. No key
  material, no clear PII.
- **`grants.py`**: a `Grant` dataclass; `GrantStore` protocol with
  `InMemoryGrantStore` + `PostgresGrantStore` (issue / get / idempotent revoke); a
  pure `authorize(grant, document_id, requested_types, now) -> set[str]` that
  returns the permitted subset (∅ when revoked, expired, or document-mismatched);
  and `issue_grant` / `revoke_grant` orchestrators that also emit an audit event.
- **Grant audit** (key_audit.py): `grant_issued` / `grant_revoked` on the existing
  append-only key-lifecycle stream (a global key-management fact, like rotation —
  not the document hash-chain), with new action constants. Never logs key material.

## Capabilities

### Added Capabilities
- `grants`: shareable, revocable, per-PII-type reveal authorization, with issue and
  revoke recorded in the key-lifecycle audit stream.

## Impact

- Code: new `grants.py`; `models.py` (+`grants` table); `key_audit.py` (+grant
  events). No pipeline/anonymizer change. Seam note: cryptographic key hand-over
  via OpenBao plugs in behind this later; the grant stays the authorization record.
- Tests: pure/local (authorize matrix — intersection, revoked, expired, doc-scope,
  global; audit-without-material; idempotent revoke) + DB-integration
  (`PostgresGrantStore` round-trip) run in CI.
