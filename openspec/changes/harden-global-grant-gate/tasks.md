## 1. Gate

- [x] 1.1 `config.allow_global_grants` from `WORDSWORTH_ALLOW_GLOBAL_GRANTS` (default `false`).
- [x] 1.2 `grants.authorize()` returns the empty set for an unscoped grant while the gate is closed (pure decision, still never raises for the denied case).
- [x] 1.3 `POST /grants` without `document_id` → 400 while the gate is closed; no grant row and no audit event.
- [x] 1.4 `create_app(allow_global_grants=...)` threads the flag to the issue route and the reveal path; default comes from config.

## 2. Gate (verification)

- [x] 2.1 Unit: unscoped grant authorizes nothing when off / its types when on; scoped grant unchanged in both modes; revoked + expired precedence unchanged.
- [x] 2.2 API: 400 on unscoped issue when off; 201 when on; reveal with a pre-existing unscoped grant → refused when off, allowed when on.
- [x] 2.3 Full suite green locally + `openspec validate --strict`.
- [x] 2.4 Docs: setting + bulk-reveal recipe in the reveal/grants how-to.
- [x] 2.5 Incidental: the CLI now prints the API's ``detail`` on an HTTP error, so
      the refusal is actionable ("document_id required …") instead of a bare 400.
- [x] 2.6 Live smoke against a real uvicorn + the CLI (not TestClient): unscoped
      issue 400 with detail and NO audit event written, scoped issue 201,
      `WORDSWORTH_ALLOW_GLOBAL_GRANTS=true` → unscoped issue 201.

## 3. Deploy

- [ ] 3.1 Deploy the new image; leave `WORDSWORTH_ALLOW_GLOBAL_GRANTS` unset (closed) in `wordsworth-config`.
- [ ] 3.2 Live proof: unscoped issue → 400; scoped issue → 201 and reveal 200 on its own document, 403 on another.
- [ ] 3.3 Note the structural fix on the F3 entry in `boomhuis/handover/2026-08-30-security-review-wordsworth.md`.
