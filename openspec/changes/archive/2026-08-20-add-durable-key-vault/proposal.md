## Why

Reversible pseudonymisation keyed data by per-type data keys held **in memory
only** — they did not survive a restart, so nothing pseudonymised could be
revealed after the pod recycled. Key management is the aspect prior government
attempts stalled on: it must be durable, sovereign, and auditable with open
tooling. ADR-0002 sets the design; this change implements it.

## What Changes

- **Envelope encryption (ADR-0002).** Per-`(scope, version)` 32-byte data keys are
  WRAPPED by an OpenBao Transit KEK that never leaves OpenBao; only the wrapped
  blob is persisted, in a new durable `key_vault` table. Clear key material is
  held only transiently (unwrapped on demand, cached in memory with a short TTL),
  never written to disk or logs.
- **New `transit.py`**: a `Transit` seam (`wrap`/`unwrap`) with `FakeTransit`
  (test double) and `OpenBaoTransit` (real Transit client); a `KeyVaultStore` seam
  with `PostgresKeyVaultStore` + `InMemoryKeyVaultStore`.
- **`DurableKeyProvider`** (satisfies `KeyProvider`): active key per scope, mints
  on first use, `rotate(scope)` retires the old version (still resolvable by
  `key_id`), fail-closed on unwrap failure (no clear-key fallback).
- **Config**: `openbao_url`, `openbao_token` (scoped, never root), `transit_kek_name`,
  `key_cache_ttl`.

## Capabilities

### Modified Capabilities
- `key-lifecycle`: data keys are durably persisted as OpenBao-Transit-wrapped
  blobs and resolved by a fresh provider after a restart; clear material is never
  persisted; unwrap failure is fail-closed.

## Impact

- Code: `models.py` (`key_vault`), `transit.py` (new), `keys.py`
  (`DurableKeyProvider`), `config.py` (4 settings). Behind the existing seams, so
  `Pseudonymizer`/`deanonymize`/the reveal API are unchanged in shape.
- Tests: pure/local (durability via a fresh provider over the same vault+
  FakeTransit; rotation retire semantics; fail-closed) + DB-integration (Postgres
  vault roundtrip; reveal survives a "restart") in CI.
- `OpenBaoTransit` is live-verified against a real OpenBao in the deploy step, not
  in CI. Wiring `DurableKeyProvider` into the deployed app + reveal route follows
  once OpenBao is deployed.
