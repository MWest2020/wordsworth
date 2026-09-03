## Why

The NORA/Haarlem-Zandvoort target architecture ("Anonimiseren & Pseudonimiseren
bij de Bron") groups every PII type under an AVG legal basis — Art. 6 (ordinary
personal data), Art. 9 (special categories: health, religion, ethnicity,
biometrics) or Art. 10 (criminal data) — and authorises disclosure by
**Privacy Protection Level** (PPL 0–3): 0 = placeholders only, 1 = Art. 6,
2 = Art. 6+9, 3 = everything incl. re-identification.

wordsworth has no entity taxonomy at all: three hardcoded deterministic labels
(`bsn`, `iban`, `email`) plus whatever `entity_type` string the detector returns.
It has no legal-basis field anywhere (mapping, grant, audit) and no notion of
levels. Grants are per free-form type set, which is *more* granular than PPL but
gives an operator no vocabulary for "Art. 9 data" or "level 2 access".

## What Changes

- **PII category registry** (`pii_categories.py`): a static, versioned mapping
  `entity_type → (category, legal_basis, ppl_min)` with three categories
  `c1`/`c2`/`c3` ↔ `Art. 6` / `Art. 9` / `Art. 10`. Unknown detector types map to
  `c1` by default (fail-safe: withheld at PPL 0, revealed only from PPL 1) and
  are logged once. The registry is data, not code paths.
- **Grants accept a PPL shorthand.** `POST /grants` accepts `ppl: 0..3` as an
  alternative to `allowed_types`; the server expands it to the type set of all
  categories with `ppl_min ≤ ppl`. `allowed_types` stays the canonical stored
  form — PPL is sugar over the existing capability model, not a second model.
  PPL 3 additionally sets `reidentify: true` (reserved; today a no-op flag
  because reveal *is* re-identification).
- **Category + legal basis surfaced** in `GET /documents/{id}` metadata counts
  (per category) and in reveal responses (`revealed_types` grouped per basis).
- **Audit**: reveal records carry the categories touched. No clear values.
- **Untouched:** cryptography, key scoping, token format, index invariant.

## Capabilities

### New Capabilities
- `pii-categories`: the AVG legal-basis taxonomy and PPL level table.

### Modified Capabilities
- `grants`: PPL shorthand expands to `allowed_types`.
- `reveal-api`: responses group revealed/withheld types by legal basis.

## Impact

- Code: new `pii_categories.py` (data + two pure functions), `grants.py`
  request model, `api.py` (grants + reveal + metadata), `pseudonymizer.py`
  audit record. No schema migration (categories are derived, not stored).
- Tests: registry, expansion, reveal grouping.
- Docs: `docs/how-to/grants.md` gets a PPL section.
- Not in scope: ABAC engine, IdP/Entra integration, roles. See ADR-0005 D7.
