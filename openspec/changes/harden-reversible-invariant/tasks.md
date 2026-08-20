## 1. Fix the leak

- [x] 1.1 `_pseudonymize_entities` matches literal detected values (longest-first,
  all occurrences), not offsets.
- [x] 1.2 Defense-in-depth: strip tokens, fail hard if any detected value survives.

## 2. Hardening

- [x] 2.1 Token regex `[A-Z0-9_]+` (multi-word types revealable).
- [x] 2.2 `deanonymize` `extra_audit`; reveal route records `grant_id`.
- [x] 2.3 FAILED audit payloads record error type, not raw message.
- [x] 2.4 `authorize` treats tz-naive `expires_at` as UTC.

## 3. Gate

- [x] 3.1 Local tests: offset-independent no-leak, all-occurrences, underscored
  type revealable; local suite green.
- [ ] 3.2 DB-integration (CI): reveal audit carries grant_id; full suite green.
- [ ] 3.3 `openspec validate`.
