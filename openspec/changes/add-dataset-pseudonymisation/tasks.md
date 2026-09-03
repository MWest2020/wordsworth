## 0. Gate before apply

- [x] 0.1 ADR-0005 D8 (datasets in scope) accepted by Mark (2026-09-03).

## 1. Engine

- [ ] 1.1 `datasets.py`: `Profile` (pydantic), `pseudonymize_rows(rows, profile,
  pseudonymizer)` streaming; per_attribute + per_record; `|` join, `""` empty.
- [ ] 1.2 `nen7524` renderer `01-<ttp>-P<T>|<base64(token bytes)>`; type letters
  B/N/A/D/C/R; labelled NEN 7524-style in docs.
- [ ] 1.3 PII validation of unselected columns → warnings list.

## 2. Surface + audit

- [ ] 2.1 `POST /datasets/pseudonymize` (CSV in/out, profile inline or by name
  from `profiles/`); rate-limited like `/ingest`.
- [ ] 2.2 One audit record per run (aggregates, profile hash, no values).
- [ ] 2.3 CLI `wordsworth pseudonymize-dataset --profile x in.csv > out.csv`.

## 3. Gate

- [ ] 3.1 Test: same BSN in a document and a dataset (same domain) → same
  token; per_record consistency; warnings for missed column. Suite + CI green;
  `openspec validate add-dataset-pseudonymisation`.
