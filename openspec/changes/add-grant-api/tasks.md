## 1. HTTP

- [x] 1.1 `POST /grants` issue (tz-aware expiry required; 400 on naive/malformed).
- [x] 1.2 `GET /grants/{id}` inspect (404 unknown).
- [x] 1.3 `POST /grants/{id}/revoke` (idempotent; 404 unknown).
- [x] 1.4 Mount only when a grant store is configured; responses carry no key
  material; issue/revoke audited via `issue_grant`/`revoke_grant`.

## 2. CLI + config

- [x] 2.1 `wordsworth grant issue|show|revoke`.
- [x] 2.2 Config `WORDSWORTH_KEY_LIFECYCLE_AUDIT_PATH`; `create_app(key_audit=...)`.

## 3. Gate

- [x] 3.1 Local tests: CRUD lifecycle, idempotent revoke, 404s, 400s, no key
  material, routes absent without a store; CLI arg/payload shaping. Suite green.
- [ ] 3.2 DB-integration (CI): issue→revoke gates the reveal endpoint (403).
- [ ] 3.3 `openspec validate` + full CI suite green.
