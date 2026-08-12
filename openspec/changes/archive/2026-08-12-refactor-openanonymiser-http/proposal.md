## Why

The `OpenAnonymiserAnonymizer` driver ran OpenAnonymiser **in-process** (importing
`src.api.services`, loading torch + spaCy-lg + GLiNER into the Wordsworth
process). Two problems:

- **It broke.** OpenAnonymiser went GLiNER-only and removed `plugins.classic.yaml`,
  which the in-process driver pinned via `PLUGINS_CONFIG`. The driver could no
  longer configure the engine.
- **It doesn't fit the deploy topology.** GLiNER needs ~3–4 GiB resident and is
  slow on CPU. Baking torch/spaCy/GLiNER into every Wordsworth process (API,
  workers) is wasteful and couples Wordsworth's runtime to a heavy ML stack.
  OpenAnonymiser is already a deployable FastAPI **service** (its own image,
  health/analyze/anonymize endpoints, sized deployment on alma).

Architecture A (Mark, 2026-08): keep Wordsworth's deterministic regex pass local,
and make the OpenAnonymiser engine an **HTTP client** to the co-located
OpenAnonymiser service. The heavy ML runs once, where it's provisioned.

## What Changes

- The default engine `_openanonymiser_redact` becomes an **HTTP POST** to
  `{WORDSWORTH_OPENANONYMISER_URL}/api/v1/anonymize` (strategy `replace`,
  `language=nl`), reading `anonymized_text` + `entities_found` from the response.
- Composition is unchanged: `DeterministicAnonymizer` runs FIRST (BSN/IBAN/email),
  then the service redacts entity PII (names); counts merge per type.
- **Fail-hard preserved and strengthened**: any transport error / non-2xx / an
  unreachable service raises `AnonymizationEngineError` — never a pass-through of
  un-redacted text. Empty text (nothing left after the deterministic pass) short-
  circuits without calling the service.
- Wordsworth drops the in-process `openanonymizer` git dependency and the
  `nl-core-news-lg` spaCy model — **no torch/spaCy/presidio/GLiNER in Wordsworth**.
  `httpx` becomes a runtime dependency.
- Config gains `WORDSWORTH_OPENANONYMISER_URL` (default `http://localhost:8080`;
  on alma the in-cluster svc-DNS) and `WORDSWORTH_OPENANONYMISER_TIMEOUT`.
- The driver's real-inference tests become service-integration tests that SKIP
  unless the service answers its health check (like the docker/DB skips). The
  protocol, composition-order and fail-hard tests stay offline via the `engine`
  seam.

## Capabilities

### Modified Capabilities
- `openanonymiser`: the driver reaches OpenAnonymiser over HTTP (a self-hosted,
  co-located service) instead of in-process; "local inference" is clarified as
  **sovereign** inference (no third-party cloud), which an in-cluster service
  satisfies. Unreachable-service is an explicit hard failure.

## Impact

- Code: `src/wordsworth/openanonymiser_driver.py` (rewritten to HTTP client),
  `config.py` (URL + timeout), `pyproject.toml` + `uv.lock` (drop
  openanonymizer/nl-core-news-lg, add httpx), `tests/test_openanonymiser_driver.py`
  (service-gated integration skip). No change to the `Anonymizer` seam,
  `DeterministicAnonymizer` (the default), the pipeline, or other capabilities.
- Deploy: Wordsworth on alma sets `WORDSWORTH_OPENANONYMISER_URL` to the
  OpenAnonymiser service svc-DNS. No banned deps introduced; no cloud in the
  critical path.
