## Why

The pipeline skeleton stubs `extract` and `anonymize`. To make it end-to-end we
need real text and real anonymization: PII irreversibly replaced in the text
before anything downstream can index it. OpenAnonymiser is the intended engine,
but it is unreachable from this build agent (ConductionNL repo, not on PyPI), so
we introduce the seam now with a deterministic interim driver, and OpenAnonymiser
plugs into the same seam later without touching the pipeline.

## What Changes

- Introduce an **`Anonymizer` protocol** (driver/protocol pattern). The pipeline
  depends on the protocol, never on a concrete engine.
- Add a **`DeterministicAnonymizer`** interim driver: high-precision, fully
  deterministic detection of BSN (elfproef), IBAN (mod-97), and email, replaced
  irreversibly with typed placeholders. No ML, no OpenAnonymiser reimplementation.
- Make the **`extract` transition real**: pull the document's text with pypdf.
- Make the **`anonymize` transition real**: run the injected `Anonymizer` over
  the extracted text, persist ONLY the anonymized text, and record the
  replacement counts in the audit payload. **BREAKING** to the stub behaviour.
- **Clear text is never persisted.** Extraction is in-memory and re-derivable
  from the source PDF; only anonymized text is stored (`document_texts`).
- `index` remains a stub (change (d)).

## Capabilities

### New Capabilities
- `anonymization`: the `Anonymizer` seam, the deterministic interim driver, and
  the irreversible-replacement + audit-summary contract.

### Modified Capabilities
- `document-lifecycle`: `extract` and `anonymize` become real transitions;
  anonymized text is persisted and clear text is not; only `index` stays a stub.

## Impact

- New module surface: `extraction`, `detectors`, `anonymizer`; new
  `document_texts` table (anonymized text only — not append-only, it is derived
  working data, never PII).
- `pipeline.process()` gains an injected `anonymizer` parameter (defaults to the
  deterministic driver).
- No cloud, no OpenAnonymiser dependency yet. OpenAnonymiser becomes a second
  driver behind the same protocol in a follow-up, once reachable.
- Does not touch `CLAUDE.md`, `.claude/agents/`, or CI.
