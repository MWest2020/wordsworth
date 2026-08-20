## 1. Transient retry

- [x] 1.1 `retry.py`: `is_transient(exc)` (httpx transport/5xx, AnonymizationEngineError,
  connection/timeout by name; permanent errors excluded) + `retry_transient(fn,
  attempts, base_delay, sleep)` with exponential backoff and injectable sleep.
- [x] 1.2 Config `WORDSWORTH_RETRY_ATTEMPTS` (3), `WORDSWORTH_RETRY_BASE_DELAY` (0.5).

## 2. Apply in the straat

- [x] 2.1 Wrap de-identify, embed, and index calls in `process()` with `retry_transient`.
- [x] 2.2 `POST /ingest` classifies a per-document failure as `retryable` (transient)
  vs `error` (permanent) and continues the batch.

## 3. Gate

- [x] 3.1 Pure tests: retry succeeds after transient blips, exhausts after N,
  never retries a permanent error, backoff uses injected sleep, classification.
- [x] 3.2 DB-integration (CI): transient-blip→INDEXED; persistent-outage→raises,
  stays REGISTERED, nothing indexed, no text persisted; permanent→not retried;
  batch continues past a failing document (one indexed, one retryable).
- [x] 3.3 Full suite green in CI + `openspec validate`.
