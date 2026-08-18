## 1. Limiter

- [x] 1.1 `concurrency.py`: named `BoundedSemaphore`s sized from config, as
  context managers.
- [x] 1.2 Config: `WORDSWORTH_ANONYMIZE_CONCURRENCY`, `WORDSWORTH_EMBED_CONCURRENCY`.

## 2. Apply

- [x] 2.1 Gate the anonymize HTTP call in `openanonymiser_driver`.
- [x] 2.2 Gate the embed HTTP call in `OllamaEmbedder`.

## 3. Gate

- [x] 3.1 Tests: limiter bounds concurrent entries; calls still succeed.
- [x] 3.2 Full suite green + `openspec validate --all`.
