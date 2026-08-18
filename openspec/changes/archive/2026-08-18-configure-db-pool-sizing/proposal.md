## Why

The SQLAlchemy engine in `db.py` is created without pool configuration, so it
uses the library defaults (`pool_size=5`, `max_overflow=10` → 15 connections
max). Under NiFi-orchestrated concurrent `/ingest` at volume (ADR-0001), that is
both unsized-on-purpose (no explicit contract) and potentially mismatched with
the actual concurrent request count and Postgres' `max_connections`. Pool sizing
should be explicit and tuned to expected concurrency.

## What Changes

- Set explicit `pool_size` and `max_overflow` (and `pool_pre_ping`,
  `pool_recycle`) on `create_engine` in `db.py`, sourced from config with
  sensible defaults, so the connection pool is a deliberate, tunable contract.
- Config: `WORDSWORTH_DB_POOL_SIZE`, `WORDSWORTH_DB_MAX_OVERFLOW`.

## Capabilities

### Modified Capabilities
- `deployment`: the database connection pool is explicitly sized for concurrent
  request volume.

## Impact

- Code: `db.py` `make_engine` (pool args), two config accessors. No schema,
  audit-trail, or query change. Deployers size the pool to their Postgres
  `max_connections` and worker/concurrency count.
