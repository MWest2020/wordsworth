# key-service-pseudonymise

## Why

ADR-0009, build B, first of four. `key-service-vault` failed the architect
three times on 26 Nov 2026 (wordsworth#532, #534) and the factory's circuit
breaker stopped it: too big for one build, and each verdict named points a
builder would have to guess. It is split into four changes, each buildable
and reviewable alone:

1. `key-service-pseudonymise` (this change): values to tokens, the token
   registry, `known_documents`, the service's audit stream, and the settings
   the service needs to reach OpenBao at all.
2. `key-service-originals`: seal and open, the service's document-key store.
3. `key-service-open-limits`: the rate limit on open, `service_state`,
   `/v1/metrics`.
4. `key-service-delete`: the two deletions, the key-lifecycle chain, the #465
   twin.

Every requirement of `key-service-vault` (as of #537) and of the open
requirements its third amendment moved to a `key-service-open` that was never
written is carried by exactly one of the four, with its wording. Where the
three verdicts left a point open, the change that owns it settles it in its
`design.md` with a rejected alternative.

This change turns values into tokens and fills the registry, so that a later
reveal decides from the service's own record of which tokens belong to which
document, not from a list wordsworth supplies (ADR-0009, amended 2026-11-26).

## What changes

- `POST /v1/pseudonymise`: per document, with its domain, a batch of
  (type, value) in; tokens out. The service stores the encrypted value,
  registers each token for that document (`document_tokens`) and records the
  document's domain (`known_documents`) on first sight. Capped at 1 000 items
  by default.
- The service's own mapping store, key vault and key provider over
  `KeyServiceBase` (`stores_pii.py`).
- The settings to reach OpenBao (`KEYSERVICE_OPENBAO_URL`,
  `KEYSERVICE_OPENBAO_TOKEN`, `KEYSERVICE_TRANSIT_KEK`,
  `KEYSERVICE_KEY_CACHE_TTL`), a `transit_for` seam on `create_app`, and a
  refusal to start without the first two.
- The service's audit stream (`access_audit`) gets its writer (`audit.py`).
- The lock order of the service's database, written on
  `docs/reference/lock-order.md` first, for all four changes.
- No route here returns a clear value: only reveal does, and it needs a
  person (`key-service-reveal`).
- ADR-0009: the `pseudonymise` residual extended with the batch cap.
- Docs: the endpoint in `docs/reference/key-service-api.md`, the settings in
  `docs/how-to/key-service.md`.

## Out of scope

Seal and open (`key-service-originals`), the rate limit and metrics
(`key-service-open-limits`), deletion (`key-service-delete`), reveal and
identity (`key-service-reveal`), traffic from wordsworth and moving data
(`key-service-cutover`), export (`key-export-escrow`).

## Next

`key-service-originals`

## Depends on

`key-service-skeleton` (process, settings, schema, service token).
