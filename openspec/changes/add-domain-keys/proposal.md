## Why

The target architecture separates pseudonym spaces per **domain** (department:
W&I, MO, VTH, OOV, O&A): the same BSN under a different `domain_key` yields a
different pseudonym, so datasets cannot be joined across departments without
going through a controlled step (EDPB TOM 4, "pseudonymisation domain").
wordsworth scopes keys per PII *type* only, with one implicit global scope
(`DEFAULT_SCOPE = "_global"`). Every department currently shares one pseudonym
space — fine for one corpus, wrong for a multi-department deployment.

## What Changes

- Key scope becomes `domain/type`, e.g. `wi/PERSON`. The default domain is
  `_global`, so existing key rows (`PERSON`) are read as `_global/PERSON` —
  **no migration**, no change for single-domain deployments.
- `POST /ingest` accepts an optional `domain` (also settable via
  `WORDSWORTH_DEFAULT_DOMAIN`); the domain is written to the document's audit
  record and metadata, and the pseudonymiser selects keys from that domain.
- Grants gain an optional `domain` filter; a grant without domain matches only
  `_global` (fail-safe, never "all domains").
- Rotation, escrow, recovery and the key-lifecycle audit stream already work per
  scope and therefore work per `domain/type` unchanged.
- Explicitly **not**: cross-domain linking service, TTP hand-over, per-tenant
  OpenBao KEKs (ADR-0005 D5/D6).

## Capabilities

### Modified Capabilities
- `key-lifecycle`: scopes are `domain/type`; default domain keeps today's rows
  valid.

## Impact

- CLI: `ingest --domain`, `grant issue --domain`; `grant_issued` audit event
  records the domain.
- Code: `keys.py` (scope helper), `pseudonymizer.py` (domain param),
  `api.py`/`pipeline.py` (ingest domain → audit), `grants.py` (optional
  `domain`), `config.py`. One reserved-character check (`/` not allowed in
  domain or type).
- Tests: two domains produce different tokens for the same value; `_global`
  compatibility; grant domain fail-safe.
