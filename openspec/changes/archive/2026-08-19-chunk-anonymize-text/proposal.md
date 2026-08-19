## Why

The OpenAnonymiser (GLiNER) service was OOMKilled on specific documents even at a
12Gi limit (10 restarts in one top-up run, only 1 doc indexed) → `AnonymizationEngineError`
on ~80 documents. GLiNER runs a single transformer forward pass over the whole
document text; its O(n^2) attention memory spikes on long text (docs up to ~34k
chars here). More memory does not fix this — the per-call sequence length must be
bounded.

## What Changes

- The driver splits the (deterministic-redacted) text into bounded chunks before
  the GLiNER call and redacts per chunk, then reassembles. The `replace` strategy
  leaves non-entity text unchanged, so chunks concatenate faithfully; entity
  counts are summed. Splits on line boundaries (a single over-long line is
  hard-split); pieces concatenate back to the original exactly.
- Config `WORDSWORTH_ANONYMIZE_CHUNK_CHARS` (default 4000; 0 disables). Chunking
  keeps each GLiNER call short enough that attention memory cannot OOM the service.
- Deterministic structured-PII (BSN/IBAN/email) is handled before chunking, so
  chunking only affects entity detection (names/locations); the only edge is an
  entity spanning a line-boundary split, which is rare for these types.

## Capabilities

### Modified Capabilities
- `deployment`: the ingest/anonymize path bounds GLiNER input size by chunking,
  so long documents no longer OOM the anonymization service.

## Impact

- Code: `openanonymiser_driver.py` (`_chunk_text`, `_redact_one`, chunking
  `_openanonymiser_redact`), one config accessor. No pipeline/schema change; the
  composite/fail-hard/concurrency behaviour is unchanged. Tests added.
