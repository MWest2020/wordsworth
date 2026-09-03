## 1. Registry

- [ ] 1.1 `src/wordsworth/pii_categories.py`: `CATEGORIES`, `LEGAL_BASIS`,
  `PPL_MIN`, `category_of(entity_type)`, `types_for_ppl(ppl) -> set[str]`;
  unknown types → `c1`, logged once. ≤ 200 lines. Unit tests.
- [ ] 1.2 Add the NL special-category types the detector can emit
  (`GEZONDHEID`, `RELIGIE`, `ETNICITEIT`, `BIOMETRIE`, `STRAFRECHTELIJK`,
  `KENTEKEN`) to the registry, mapped per AVG article; document that detection
  of these types is the detector's job (OpenAnonymiser), not wordsworth's.

## 2. Grants + reveal

- [ ] 2.1 `POST /grants` accepts `ppl` xor `allowed_types`; 422 on both/neither.
  Stored form stays `allowed_types`; response echoes the derived `ppl` when the
  set matches a level exactly.
- [ ] 2.2 Reveal response adds `by_legal_basis: {"Art. 6": [...], ...}` for
  revealed and withheld types.
- [ ] 2.3 Reveal audit record adds `categories` (set of `c1..c3`).
- [ ] 2.4 `GET /documents/{id}` metadata adds `pii_counts_by_category`.

## 3. Gate

- [ ] 3.1 `docs/how-to/grants.md`: PPL table + one example per level.
- [ ] 3.2 Suite green; CI green; `openspec validate add-pii-categories-and-ppl`.
