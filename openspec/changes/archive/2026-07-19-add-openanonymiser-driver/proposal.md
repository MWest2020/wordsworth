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

- **UNBLOCKED (2026-07-19):** depends on OpenAnonymiser via Mark's fork
  `MWest2020/OpenAnonymiser_light` (EUPL-1.2 verified; reachable from the build
  agent). Package name is **`OpenAnonymizer`** — git dep:
  `openanonymizer = { git = "https://github.com/MWest2020/OpenAnonymiser_light" }`.
- Known pitfalls for the builder (verified against the fork's pyproject):
  - `nl_core_news_lg` (spaCy model, ~500 MB) is declared there via a
    `[tool.uv.sources]` URL — **uv sources are not applied transitively for git
    deps**, so wordsworth's own `pyproject.toml` must repeat that URL source
    (`https://github.com/explosion/spacy-models/releases/download/nl_core_news_lg-3.8.0/nl_core_news_lg-3.8.0-py3-none-any.whl`).
  - Do **NOT** install the `gpu` extra (GLiNER pulls torch/CUDA ~5 GB); the CPU
    flavor (Presidio + spaCy NER + regex) is the PoC path.
  - Core logic lives in `src/api/services/text_analyzer.py` (the FastAPI app is
    a wrapper); the driver imports the analyzer as a library — no sidecar
    service, no network hop.
- Local CPU inference; nightly batch acceptable, throughput measured. No
  pipeline change (same protocol). Does not touch `CLAUDE.md`, `.claude/agents/`,
  CI.
