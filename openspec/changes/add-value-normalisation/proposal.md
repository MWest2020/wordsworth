## Why

Pseudonyms must be *consistent*: the same person must yield the same pseudonym
so records stay linkable ("Zelfde waarde + key → zelfde pseudoniem"). The target
architecture defines `pseudoniem = HMAC(domain_key, normalize(id))` with typed
normalisation (BSN: strip dots, left-pad to 9; names/addresses: trim, NFC,
lowercase; postcode: strip space, uppercase; dates: ISO 8601; default: trim,
NFC). wordsworth HMACs the raw `f"{label}:{value}"`: `Jansen`, `jansen` and
`1234.56.789` vs `123456789` all get different tokens. That silently breaks
linkability across documents and is the single biggest correctness gap on the
pseudonymisation side.

## What Changes

- `normalize(entity_type, value) -> str` in a new `normalization.py`: typed
  rules as above, `NFC` + trim as the default, pure function, table-driven.
- Token derivation uses `HMAC(key, f"{label}:{normalize(label, value)}")`.
- **Versioned**: the normalisation profile has a version (`n1`), recorded per
  mapping row alongside `key_id`, so a future rule change can be rolled out via
  the existing reprocess/backfill path instead of silently forking pseudonyms.
- Existing corpora: tokens change for any value the rules touch. The migration
  is the existing `POST /reprocess` (reversible mode) — documented as a
  runbook step, not automated.
- The stored ciphertext keeps the **original** (un-normalised) value; reveal
  returns what was in the document.

## Capabilities

### Modified Capabilities
- `pseudonymization`: tokens are derived from the normalised value; the
  normalisation profile is versioned and stored per mapping.

## Impact

- Code: `normalization.py` (new, ≤ 100 lines), `pseudonymizer.py`, `models.py`
  (`pii_mappings.norm_version`, nullable = legacy `n0`), bootstrap DDL.
- Runbook: `docs/how-to/reversible-backfill.md` gains "after a normalisation
  change".
- Tests: rule table, BSN/postcode/name cases, version recorded.
