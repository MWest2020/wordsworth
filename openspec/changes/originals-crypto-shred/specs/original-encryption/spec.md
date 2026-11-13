## ADDED Requirements

### Requirement: A cached key is used only while its key row exists

Before using an unwrapped data key from its cache, the key store SHALL confirm
that the key row for that object still exists and names the same key. When it
does not, the cached key SHALL be dropped and SHALL NOT be used. The check
SHALL NOT call the key service.

#### Scenario: The row was destroyed by another process

- **WHEN** a process holds an unwrapped key in its cache and another process
  destroys that key's row
- **THEN** the first process's next unwrap for that object raises
  `OriginalsKeyUnavailable` and returns no key

#### Scenario: The key was destroyed and minted again

- **WHEN** a key is destroyed and a new key is minted for the same object key
  while a process still caches the old one
- **THEN** that process's next unwrap returns the new key

#### Scenario: A cached key that still has its row

- **WHEN** a key is unwrapped twice within the cache TTL and its row is
  unchanged
- **THEN** the key service is called once
