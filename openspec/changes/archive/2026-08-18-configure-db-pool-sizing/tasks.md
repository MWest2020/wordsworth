## 1. Pool config

- [x] 1.1 Config: `WORDSWORTH_DB_POOL_SIZE`, `WORDSWORTH_DB_MAX_OVERFLOW`.
- [x] 1.2 `make_engine` sets explicit `pool_size`, `max_overflow`,
  `pool_pre_ping`, `pool_recycle`.

## 2. Gate

- [x] 2.1 Test: engine reflects the configured pool size.
- [x] 2.2 Full suite green + `openspec validate --all`.
