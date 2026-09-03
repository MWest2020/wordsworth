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
dataset artefact (registered once per content+profile hash, `object_key` =
`datasets/<sha256>`): profile hash, domain, row count, columns, unique
pseudonyms, `rows_without_record_key`, warned columns — never a cell value.
Dataset artefacts stay in state `registered` (they are never profiled or
extracted), so `wordsworth_documents_total{state="registered"}` includes them.

## Re-identification

Dataset tokens live in the same mapping store as document tokens. A grant in the
same domain reveals them through any document text that contains them; a
dedicated "reveal these tokens" surface for datasets (and for `RECORD` tokens,
which appear in no document) is a follow-up change.

## Caveats

- `per_record` rows whose key cells are all empty derive identity `""` and
  collapse onto one shared pseudonym; they are counted in
  `rows_without_record_key` — check it before joining.
- Empty selected cells stay empty (no pseudonym is invented for a missing value).
- `validate_pii` covers only the deterministic detectors (BSN/IBAN/email); an
  unselected name or address column is not warned about.
