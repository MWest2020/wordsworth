## 1. View

- [ ] 1.1 `src/wordsworth/legible.py`: `to_legible(text) -> (text, legend)`;
  ordinal per distinct token per type; Dutch label map. Unit tests.
- [ ] 1.2 `GET /documents/{id}/anonymized?view=tokens|legible` (default tokens);
  response adds `legend` for legible.
- [ ] 1.3 `GET /export/anonymized.zip?view=legible`.

## 2. Gate

- [ ] 2.1 Test: two occurrences of one token share one ordinal; stored text
  unchanged. Suite + CI green; `openspec validate add-legible-placeholders`.
