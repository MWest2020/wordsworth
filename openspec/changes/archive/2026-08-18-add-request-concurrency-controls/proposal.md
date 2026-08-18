## Why

`/ingest` drives each document through calls to the OpenAnonymiser (GLiNER)
service and the Ollama embedder. Nothing bounds how many of those calls are in
flight at once, so concurrent callers — NiFi in production (ADR-0001), or simply
several simultaneous API requests today — can exceed the capacity of those
single-replica, memory-heavy CPU backends. Observed in practice: the
OpenAnonymiser service was OOMKilled repeatedly (exit 137, dozens of restarts)
during ingest, surfacing as `AnonymizationEngineError` on many documents.

## What Changes

- Add a process-wide bounded concurrency limiter around the network calls to the
  backends: the anonymize call in `openanonymiser_driver` and the embed call in
  `OllamaEmbedder`. Each is gated by a `threading.BoundedSemaphore` sized from
  config, so no more than N calls hit a backend concurrently per worker process.
- Config: `WORDSWORTH_ANONYMIZE_CONCURRENCY` (default conservative, matching a
  single-replica GLiNER) and `WORDSWORTH_EMBED_CONCURRENCY`.
- **No change to the anonymize step itself** — same driver, same output, same
  fail-hard behaviour. Only *how many* calls may run at once changes.

## Capabilities

### Modified Capabilities
- `deployment`: the servable API bounds concurrency against the OpenAnonymiser
  and Ollama backends so concurrent callers cannot overwhelm them.

## Impact

- Code: a small `concurrency` helper (named bounded semaphores from config),
  applied in `openanonymiser_driver.py` and `embedder.py`; two config accessors.
  No pipeline, schema, or audit change. The limiter is per worker process; the
  multi-worker/NiFi-level total is documented (a global limit would need a
  distributed semaphore — out of scope, noted for the NiFi layer).
- Does not by itself resolve a single document that individually exceeds a
  backend's memory (that is a backend-sizing concern) — it prevents *concurrency*
  from doing so.
