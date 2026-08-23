## 1. Auth

- [x] 1.1 `config.api_keys` from `WORDSWORTH_API_KEYS` (`label:key` → {key: label}), empty = off.
- [x] 1.2 `auth.py`: `parse_api_keys` + `ApiKeyAuthMiddleware` (401 on missing/invalid, exempt `/health` `/metrics`, stash caller label; keys never logged).
- [x] 1.3 `create_app(api_keys=...)` mounts the middleware only when keys are non-empty.
- [x] 1.4 Reveal records the authenticated `caller` in the audit, alongside recipient + grant_id.

## 2. Gate

- [x] 2.1 Local tests: parse; open by default; 401 missing/wrong; valid passes; `/health` open; key not echoed.
- [x] 2.2 DB-integration (CI): reveal 401 without key, and records `caller` with no clear PII.
- [x] 2.3 Full suite green locally (266) + no regressions; `openspec validate`.
- [x] 2.4 CI green.
