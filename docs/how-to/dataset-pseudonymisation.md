---
status: draft
last_reviewed: 2026-09-03
---

# Runbook: dataset (CSV) pseudonymisation

The dataset path: the operator **selects columns** (no detection), the engine
emits consistent keyed pseudonyms per **domain**, the encrypted originals go to
the same separated mapping store as documents, and re-identification is the
existing grant-gated reveal on tokens. Same derivation as free text, so a BSN in
a document and the same BSN in a dataset cell of the same domain get the **same
token** — that is the whole point. Reversible mode only.

## Profile

`profiles/<name>.json` (versioned in git) or inline:
```json
{"domain": "wi",
 "columns": {"bsn": "BSN", "naam": "PERSON", "geboortedatum": "DATE"},
 "mode": "per_attribute",            // or "per_record"
 "record_key": ["bsn"],              // per_record: identity columns, in order
 "format": "token",                  // or "nen7524"
 "ttp_id": "0001",
 "validate_pii": true}
```
- `per_attribute`: each selected cell → `HMAC(key(domain, type), normalize(type, value))`
  — exactly the document derivation. `per_record`: one pseudonym per row from the
  `record_key` columns joined with `|` (profile order, empty cell = `""`, each
  component normalised per its declared type), under type `RECORD`; every selected
  column of that row carries it.
- `nen7524` renders a token as `01-<ttp_id>-P<letter>|<base64>` (B=BSN, N=name,
  A=address, D=date, C=postcode, R=record). **Conformance to NEN 7524:2019 is
  unverified** (ADR-0005 D9): this is the deck's format, labelled "NEN 7524-style"
  until someone checks it against the standard.
- `validate_pii`: unselected columns are sampled through the deterministic
  detectors (BSN/IBAN/email); hits come back as *warnings* — nothing is ever
  transformed that the profile did not select.

## Run

```sh
wordsworth pseudonymize-dataset in.csv --profile-name example-wi > out.csv   # stats on stderr
wordsworth pseudonymize-dataset in.csv --profile ./my-profile.json > out.csv
```
HTTP: `POST /datasets/pseudonymize` multipart `file` (CSV, header row) + exactly
one of `profile` (inline JSON) / `profile_name`. Response: `csv`, `rows`,
`columns`, `unique_pseudonyms`, `warnings`, `dataset_id`, `audit_seq`.

## Audit

Each run appends one `dataset_pseudonymize` record to the audit chain of the
dataset artefact (registered once per content hash, `object_key` =
`datasets/<sha256>`): profile hash, domain, row count, columns, unique
pseudonyms, warned columns — never a cell value. Re-identify a token with a
grant in the same domain via `POST /documents/{dataset_id}/reveal`... no: reveal
works on stored *document* text; for datasets, reveal the tokens through any
document in that domain or via the mapping store tooling (follow-up).
