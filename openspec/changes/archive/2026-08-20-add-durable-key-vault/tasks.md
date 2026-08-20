## 1. Durable vault + Transit

- [x] 1.1 `key_vault` table (`KeyVaultRecord`): key_id PK, scope, wrapped_material,
  status (active/retired), created_at.
- [x] 1.2 `transit.py`: `Transit` seam + `FakeTransit` + `OpenBaoTransit`
  (encrypt/decrypt via /v1/transit, scoped token).
- [x] 1.3 `KeyVaultStore` seam + `PostgresKeyVaultStore` + `InMemoryKeyVaultStore`.

## 2. DurableKeyProvider

- [x] 2.1 `DurableKeyProvider` satisfies `KeyProvider`; mints+wraps+persists active
  keys; unwrap cached with a TTL; only wrapped material persisted.
- [x] 2.2 `rotate(scope)` retires the prior active (still resolvable by key_id),
  isolates other scopes; unknown key_id → KeyError; unwrap failure fail-closed.
- [x] 2.3 Config: openbao_url/openbao_token/transit_kek_name/key_cache_ttl.

## 3. Gate

- [x] 3.1 Local tests (no DB/server): protocol; mint persists only wrapped;
  durability via a fresh provider; rotate retire+isolation; end-to-end reveal
  survives "restart"; fail-closed on unwrap error.
- [x] 3.2 DB-integration (CI): Postgres vault roundtrip; reveal survives restart
  over the persisted vault; chain verifies.
- [x] 3.3 Full suite green in CI + `openspec validate`.
