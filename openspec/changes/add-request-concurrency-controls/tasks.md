## 1. Limiter

- [ ] 1.1 `concurrency.py`: named `BoundedSemaphore`s sized from config, as
  context managers.
- [ ] 1.2 Config: `WORDSWORTH_ANONYMIZE_CONCURRENCY`, `WORDSWORTH_EMBED_CONCURRENCY`.

## 2. Apply

- [ ] 2.1 Gate the anonymize HTTP call in `openanonymiser_driver`.
- [ ] 2.2 Gate the embed HTTP call in `OllamaEmbedder`.

## 3. Gate

- [ ] 3.1 Tests: limiter bounds concurrent entries; calls still succeed.
- [ ] 3.2 Full suite green + `openspec validate --all`.
