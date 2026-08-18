## 1. Pool config

- [ ] 1.1 Config: `WORDSWORTH_DB_POOL_SIZE`, `WORDSWORTH_DB_MAX_OVERFLOW`.
- [ ] 1.2 `make_engine` sets explicit `pool_size`, `max_overflow`,
  `pool_pre_ping`, `pool_recycle`.

## 2. Gate

- [ ] 2.1 Test: engine reflects the configured pool size.
- [ ] 2.2 Full suite green + `openspec validate --all`.
