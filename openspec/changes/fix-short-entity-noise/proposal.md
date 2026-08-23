## Why

The reversible driver's defense-in-depth post-check (a detected entity value that
survives substitution → `AnonymizationEngineError`, refuse to emit) fired on ~13%
of the real Dutch government corpus during the reversible backfill. Root cause:
GLiNER emits spurious 1-2 char spans on OCR-noisy text (e.g. "ik", "re"). Such a
fragment recurs throughout ordinary text, so it can never be fully removed and
ALWAYS trips the survivor check — rejecting the whole document (fail-closed: the
doc kept its prior irreversible index entry, so no leak, but it could not be
backfilled to reversible).

## What Changes

- `_pseudonymize_entities` skips GLiNER entity values shorter than
  `_MIN_ENTITY_LEN` (3): they are model/OCR noise, not PII. They are neither
  redacted (which would mangle common substrings) nor considered by the survivor
  check. Structured PII (BSN/IBAN/email) is handled by the deterministic pass
  regardless, and real entity PII (names/places/orgs) is >= 3 chars — so this
  cannot leak, and the fail-hard still fires for a genuine >=3-char survivor.

## Capabilities

### Modified Capabilities
- `pseudonymization`: reversible entity redaction ignores sub-3-char detector
  noise, so noisy documents backfill instead of being falsely rejected.

## Impact

- Code: `pseudonymizer.py` (`_MIN_ENTITY_LEN`, one filter condition). Test added.
- Unblocks the reversible backfill of the ~54 noisy documents.
