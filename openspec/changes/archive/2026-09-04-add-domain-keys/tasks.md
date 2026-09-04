## 1. Scope

- [x] 1.1 `keys.py`: `scope(domain, type)`; `_global` default; legacy rows
  without `/` read as `_global/<type>`. Unit tests.
- [x] 1.2 `pseudonymizer.py`: domain threaded into key lookup and mapping put.

## 2. Surface

- [x] 2.1 `POST /ingest` optional `domain` (+ `WORDSWORTH_DEFAULT_DOMAIN`);
  recorded in the ingest audit record and `GET /documents/{id}`.
- [x] 2.2 Grants: optional `domain`; missing → `_global` only.

## 3. Gate

- [x] 3.1 Tests: same value, two domains → two tokens; rotation per
  `domain/type` audited. Suite + CI green; `openspec validate add-domain-keys`.
