## 1. Grant model + store

- [x] 1.1 `grants` table + `GrantRecord` (models.py).
- [x] 1.2 `Grant` dataclass; `GrantStore` protocol; `InMemoryGrantStore` +
  `PostgresGrantStore` (issue / get / idempotent revoke).

## 2. Authorization + audit

- [x] 2.1 Pure `authorize(grant, document_id, requested_types, now)`: ∅ unless
  active, unexpired, document-matched; result = requested ∩ allowed_types.
- [x] 2.2 `grant_issued` / `grant_revoked` on the key-lifecycle audit stream
  (new action constants), never logging key material.
- [x] 2.3 `issue_grant` / `revoke_grant` orchestrators (store + audit).

## 3. Gate

- [x] 3.1 Local tests (no DB): authorize matrix (intersection, revoked, expired,
  doc-scope, global); issue+revoke audited without key material; idempotent revoke.
- [x] 3.2 DB-integration (CI): `PostgresGrantStore` issue→get→revoke round-trip and
  authorize behaviour with a real session.
- [x] 3.3 Full suite green in CI + `openspec validate`.
