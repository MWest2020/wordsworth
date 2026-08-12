## 1. Driver → HTTP client

- [x] 1.1 Rewrite `_openanonymiser_redact` to POST `/api/v1/anonymize`
  (`replace`, `language=nl`), parse `anonymized_text` + `entities_found`.
- [x] 1.2 Keep composition (deterministic-first, count-merge) and fail-hard
  (`AnonymizationEngineError`, no un-redacted pass-through).
- [x] 1.3 Short-circuit empty text (post-deterministic) — no service call.

## 2. Config

- [x] 2.1 Add `WORDSWORTH_OPENANONYMISER_URL` (default `http://localhost:8080`).
- [x] 2.2 Add `WORDSWORTH_OPENANONYMISER_TIMEOUT` (default 120s, CPU GLiNER slow).

## 3. Dependencies

- [x] 3.1 Drop `openanonymizer` git dep and `nl-core-news-lg` from pyproject.
- [x] 3.2 Add `httpx` as a runtime dependency; regenerate `uv.lock`.
- [x] 3.3 Verify torch/spaCy/presidio/GLiNER no longer resolve into the lock.

## 4. Tests

- [x] 4.1 Real-inference tests become service-gated integration tests (skip
  unless the service health check answers).
- [x] 4.2 Protocol / composition-order / fail-hard tests stay offline via the
  `engine` seam.
- [x] 4.3 Full suite green (148 passed, 56 skipped) and `openspec validate --all`.
