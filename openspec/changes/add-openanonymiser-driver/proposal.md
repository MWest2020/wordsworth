## Why

The interim `DeterministicAnonymizer` covers only high-precision structured PII
(BSN, IBAN, email). OpenAnonymiser (Presidio + GLiNER + regex) is the intended
engine for names and other entities. It plugs into the existing `Anonymizer`
protocol as a second driver — no pipeline change.

## What Changes

- Add an **`OpenAnonymiserAnonymizer`** implementing the `Anonymizer` protocol,
  delegating to OpenAnonymiser. Same `AnonymizationResult` (text + per-type
  counts), same irreversible-replacement contract.
- Local inference (GLiNER/Presidio on CPU for the PoC); no cloud. A failed
  anonymization is a hard error — never pass-through of un-redacted text.

## Capabilities

### New Capabilities
- `openanonymiser`: the OpenAnonymiser-backed anonymization driver behind the
  existing seam.

## Impact

- Depends on OpenAnonymiser (`ConductionNL/openanonymiser_light`), currently
  **unreachable from the build agent** (org hook; not on PyPI). Mark makes it
  reachable (vendor / publish / unblock) before this can be built. Local CPU
  inference; nightly batch acceptable, throughput measured. No pipeline change
  (same protocol). Does not touch `CLAUDE.md`, `.claude/agents/`, CI.
