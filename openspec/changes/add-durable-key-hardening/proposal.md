## Why

The Fase-B audit flagged two follow-ups on the durable key provider (both
non-leaks): (1) `serve.py` built a NEW `DurableKeyProvider` per request, so its
in-memory unwrap cache never survived a request — every reveal/ingest re-hit
OpenBao Transit; and (2) two concurrent first-time ingests for an unseen scope
could each mint an `active` key, leaving two active rows for one scope (the
"one active per scope" invariant was code-only, unenforced).

## What Changes

- **Process-lifetime provider.** A new `SessionFactoryKeyVaultStore` opens a
  short-lived session per operation from the session factory (committing writes),
  so ONE long-lived `DurableKeyProvider` can serve every request. `serve.py`
  builds that single provider at wiring time and shares it between the ingest
  reversible-anonymizer and the reveal route — the unwrap cache now warms across
  requests. Only the mapping/grant stores stay per-request. No OpenBao I/O at
  construction (the pod still boots sealed).
- **One active key per scope, enforced by the DB.** A partial-unique index on
  `key_vault (scope) WHERE status='active'`. The provider retires the prior active
  before minting, and on a concurrent-mint race (the loser gets an `IntegrityError`
  / `ActiveKeyExists`) it re-reads and adopts the winner instead of creating a
  second active row.

## Capabilities

### Modified Capabilities
- `key-lifecycle`: at most one active key per scope is a DB-enforced invariant; a
  process-lifetime provider warms the unwrap cache across requests. Crypto/reveal
  semantics, fail-closed unwrap, and resolve-by-`key_id` are unchanged.

## Impact

- Code: `transit.py` (`ActiveKeyExists`, `SessionFactoryKeyVaultStore`, in-memory
  store enforces single-active), `keys.py` (race-safe `current_key`/`rotate`),
  `models.py` (partial-unique index — `create_all` adds it), `serve.py` (singleton
  provider). No new dep; no schema change beyond the index; no behaviour change to
  reveal/pseudonymise output.
- Tests: local (cache-warm within one provider vs cold across separate providers;
  one-active-after-rotate; store rejects a second active; adopt-winner on race;
  serve shares one provider) + DB-integration (session-factory round-trip, fresh
  provider resolves persisted keys, partial-unique index rejects a second active,
  reveal survives across sessions via the singleton).
