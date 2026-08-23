## Why

After skipping sub-3-char detector noise, the reversible backfill still rejected
11 OCR-noisy documents. GLiNER emits >=3-char FRAGMENT spans that sit inside
larger words (e.g. "ene" in "voorzienen", "len" in "bepalen"). Substring-based
redaction both mangled ordinary words (every occurrence of the fragment became a
token) and, because such a fragment recurs everywhere, guaranteed a false
survivor that tripped the fail-hard and rejected the whole document.

## What Changes

- `_pseudonymize_entities` matches detected values only as WHOLE tokens, using
  non-word-char lookarounds `(?<!\w)…(?!\w)`, for both the redaction pass and the
  survivor fail-hard check. A fragment inside a larger word is neither redacted
  nor flagged; a real whole-word name/place/org is still redacted, and a genuine
  whole-word survivor still fails hard. Complements the sub-3-char skip.

## Capabilities

### Modified Capabilities
- `pseudonymization`: entity redaction + the survivor check are whole-word, so
  fragment noise inside words neither mangles text nor falsely rejects a document.

## Impact

- Code: `pseudonymizer.py` (`_pseudonymize_entities` — lookaround alternation +
  lookaround survivor search). Test added. Unblocks the remaining backfill docs.
