## ADDED Requirements

### Requirement: Explicit database connection pool sizing

The SQLAlchemy engine SHALL configure its connection pool explicitly
(`pool_size` and `max_overflow`) from configuration rather than relying on
library defaults, so the pool is a deliberate contract sized to the expected
concurrent request volume. The engine SHALL also guard against stale
connections (pre-ping / recycle).

#### Scenario: Pool size is configurable

- **WHEN** the pool size is configured and the engine is created
- **THEN** the engine's pool reflects the configured size rather than the library
  default

#### Scenario: Stale connections do not surface as request errors

- **WHEN** a pooled connection has gone stale between requests
- **THEN** it is validated/recycled before use rather than failing the request
