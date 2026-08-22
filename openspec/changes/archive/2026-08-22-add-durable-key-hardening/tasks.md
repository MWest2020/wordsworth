## 1. Process-lifetime provider

- [x] 1.1 `SessionFactoryKeyVaultStore` (short session per op, commits writes).
- [x] 1.2 `serve.py` builds ONE `DurableKeyProvider` over it, shared by the ingest
  anonymizer + the reveal route; no OpenBao I/O at construction.

## 2. One active key per scope

- [x] 2.1 Partial-unique index on `key_vault (scope) WHERE status='active'`.
- [x] 2.2 In-memory store mirrors it (`ActiveKeyExists`); provider re-reads and
  adopts the winner on a concurrent-mint race (`current_key`/`rotate`).

## 3. Gate

- [x] 3.1 Local tests: cache warm within one provider / cold across separate
  providers; one active after rotate; reject 2nd active; adopt-winner on race;
  serve shares one provider. Local suite green (250 passed).
- [x] 3.2 DB-integration (CI): session-factory round-trip; fresh provider resolves
  persisted keys; partial-unique index rejects a 2nd active; reveal survives
  across sessions via the singleton.
- [x] 3.3 Full suite green in CI + `openspec validate`.
