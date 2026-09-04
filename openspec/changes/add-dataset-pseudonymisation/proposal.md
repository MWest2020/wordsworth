## Why

Half of the target architecture is a **dataset** path that wordsworth does not
have: tabular data (CSV / API extracts from BRP, DUO, ZorgNed, BAG) where the
operator *selects columns* to pseudonymise — no PII detection needed — and the
engine emits consistent HMAC-SHA256 pseudonyms per domain key, keeps a lookup
table for controlled re-identification, and outputs a dataset a data team can
join longitudinally (PPL 0: no keys leave the domain). Use cases: W&I batch ETL
(1.5M mutations/hour, nightly window), MO chain partners, O&A research via a
TTP. wordsworth's unit of work is a PDF; CSV exists only as a ranking export.

This is a **scope extension** (documents → documents + datasets). It reuses
the key provider, mapping store, grants, audit chain and — with
`add-value-normalisation` and `add-domain-keys` — the exact same token
derivation, so pseudonyms from a document and from a dataset in the same domain
are *the same*, which is the whole point. See ADR-0005 D8 before applying.

## What Changes

- `POST /datasets/pseudonymize` (multipart CSV + inline JSON profile, or
  `profile_name` from `profiles/`): profile = `{domain, columns: {name:
  entity_type}, mode: per_attribute|per_record, record_key: [columns], format:
  token|nen7524, ttp_id, validate_pii}`. Returns JSON with the transformed
  `csv` (selected columns replaced, unselected byte-identical) plus aggregates
  and warnings.
- `per_attribute`: each cell `HMAC(key(domain,type), normalize(type, value))`
  — same derivation as documents, so the token equals the document token.
  `per_record`: one pseudonym per row derived from the concatenation
  (`|`-separated, empty = `""`, fixed column order from the profile) of the
  `record_key` columns, type `RECORD`.
- Optional **PII validation**: unselected columns are sampled through the
  deterministic detectors (BSN/IBAN/email; offline, no service call); hits are
  reported as a warning list, never auto-applied (the operator decides; matches
  the "heb je kolommen gemist?" step).
- Every run is one audit record (`dataset_pseudonymize`, an access event on a
  dataset artefact registered once per content hash): profile hash, row count,
  columns, unique pseudonyms, domain, warned columns — no values. Mappings go into the existing
  encrypted `pii_mappings` store (the "lookup table"); re-identification is the
  existing grant-gated reveal on tokens.
- Output format `nen7524` renders each token as `01-<ttp>-P<T>|<base64>` per
  the deck's examples. **Conformance to NEN 7524:2019 is unverified** — the
  norm text is not in the repo; the format is labelled "NEN 7524-style" until
  someone checks it against the standard (ADR-0005 D9).
- Profiles are files under `profiles/` (versioned in git), or inline.

## Capabilities

### New Capabilities
- `dataset-pseudonymization`: column-selected, profile-driven pseudonymisation
  of tabular data with the same keys, normalisation and audit as documents.

## Impact

- Code: `datasets.py` (profile model + row transform, ≤ 200 lines),
  `api.py` one route, `client.py` one subcommand (`pseudonymize-dataset`),
  `Pseudonymizer.pseudonym()` as the shared derivation. Stdlib `csv`, no pandas.
  Not rate-limited (nor is `/ingest`).
- Depends on: `add-value-normalisation`, `add-domain-keys`.
- Out of scope: DWH/landing-zone delivery, scheduling (NiFi's job), Excel input
  (CSV only), TTP key transfer.
