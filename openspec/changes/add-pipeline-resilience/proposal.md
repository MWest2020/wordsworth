## Why

A batch run over a large corpus must not be aborted by a transient outage of one
downstream service (OpenAnonymiser, Ollama, OpenSearch) — and it must never let
resilience weaken the PII invariant. Today a brief blip mid-document raises and
leaves the document resumable, but there is no in-document retry (a one-second
network hiccup fails the document unnecessarily) and the batch result does not
distinguish a transient (retryable) failure from a permanent one.

## What Changes

- **Bounded transient retry.** A new `retry_transient(fn, attempts, base_delay,
  sleep)` retries ONLY transient errors — httpx transport errors/timeouts, HTTP
  5xx, `AnonymizationEngineError` (wraps service-unreachable), and connection/
  timeout errors from any client (matched by duck-typed status code + error name)
  — with exponential backoff. Permanent/logic errors (`ExtractionError`,
  `ProfilingError`, `ValueError`, …) raise immediately, never retried.
- The pipeline's three external calls (de-identify, embed, index) are wrapped in
  `retry_transient`, so a brief blip self-heals mid-document. After attempts are
  exhausted the error still propagates and the document stays in its resumable
  state — never indexed with clear PII (fail-hard per attempt is unchanged).
- The `POST /ingest` batch classifies a per-document failure as `retryable`
  (transient → the document stays resumable for a re-run) vs `error` (permanent),
  and continues to the next document either way. Config: `WORDSWORTH_RETRY_ATTEMPTS`
  (3), `WORDSWORTH_RETRY_BASE_DELAY` (0.5s).

## Capabilities

### Modified Capabilities
- `document-lifecycle`: transient downstream failures are retried with bounded
  backoff; a document that cannot be de-identified is never indexed and stays
  resumable; a batch continues past a failing document, reporting retryable vs
  permanent.

## Impact

- Code: new `retry.py`; `pipeline.py` wraps the external calls; `api.py`
  classifies batch outcomes; two config accessors. No schema change; the fail-hard
  and pseudonyms-only invariants are unchanged.
- Tests: pure retry-helper unit tests + DB-integration (transient-blip→indexed,
  persistent-outage→resumable-and-never-indexed, permanent→not-retried, batch
  continues past a failing document).
