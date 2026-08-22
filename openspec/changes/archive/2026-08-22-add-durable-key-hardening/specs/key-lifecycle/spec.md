## ADDED Requirements

### Requirement: At most one active key per scope

The key vault SHALL hold at most one `active` key per scope, enforced by the
datastore (not only by code). When two writers concurrently mint a first key for
the same scope, exactly one SHALL become active and the other SHALL be rejected;
the rejected writer SHALL adopt the winning active key rather than create a second
active row. Retired versions remain resolvable by `key_id`.

#### Scenario: A concurrent second active is rejected and the winner adopted

- **WHEN** two providers concurrently mint a first active key for the same scope
- **THEN** the datastore rejects the second active insert, and the losing provider
  re-reads and returns the winning active key — never two active rows for the scope

### Requirement: Process-lifetime provider warms the unwrap cache

The durable key provider SHALL be usable as a single process-lifetime instance
backed by a session-factory vault store, so its in-memory unwrap cache persists
across requests. Repeated resolutions of the same key within the cache TTL SHALL
unwrap via the KEK at most once.

#### Scenario: Repeated resolutions unwrap once

- **WHEN** one long-lived provider resolves the same key several times within the
  cache TTL
- **THEN** the Transit unwrap is performed once and subsequent resolutions are
  served from the cache
