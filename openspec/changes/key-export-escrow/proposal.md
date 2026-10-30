# key-export-escrow

## Why

Data autonomy includes being able to leave: an organisation must be able to
take its keys (and so its data) to another installation, and to escrow them
for recovery. Keys may only ever leave wrapped.

## What changes

- `POST /v1/export` on the key service (and a CLI): export the keys of a domain
  (PII type keys and document keys), each re-wrapped under a receiving public
  key supplied by the caller (X25519, the construction the existing `Escrow`
  seam uses), as a signed bundle with a manifest (counts, key ids, kek_ref).
- Import of such a bundle into another key service.
- Only a `beheerder`; every export and import audited (who, which domain, how
  many keys, the receiving key's fingerprint) — never key material.

## Depends on

`key-service-cutover`; built after `search-by-value` (chain order).
