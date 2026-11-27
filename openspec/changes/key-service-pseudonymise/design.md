# Design

All routes below sit behind the skeleton's service token (401 first, before
the body is parsed). The caller is a service (`service_caller`, the token's
label); no person is involved and no user assertion is read. Request logging
drops the body and the response of every route here: no value or key byte
reaches a log. The import rules of `key-service-skeleton` ("Reuse and
imports") apply, and this change's tests run under the fixture that makes
`config.settings` raise.

## The split of `key-service-vault`

| Change | Holds | Depends on |
|---|---|---|
| `key-service-pseudonymise` | settings to reach OpenBao, mapping store, key vault, key provider, `known_documents`, the registry, `POST /v1/pseudonymise`, `access_audit` writer, the lock-order page | skeleton |
| `key-service-originals` | the document-key store, `seal`, `open` with its purposes and its failure split | pseudonymise |
| `key-service-open-limits` | the per-caller rate limit on `open`, the coarser 429 audit, `service_state`, `/v1/metrics` | originals |
| `key-service-delete` | `DELETE /v1/originals`, `DELETE /v1/documents`, the key-lifecycle chain, the #465 twin | originals |

The line follows the architect's third verdict (values and documents apart
from originals and traffic control) and cuts each side once more, so that no
build carries two stores, two chains and a limiter at once (the skeleton, at
about 1 250 lines, is the size a build has carried). Rejected: the two-way
split of the verdict as it stands (the originals half still holds seal, open,
purposes, a limiter with lazy window summaries, a state table and metrics);
the third amendment's split (seal and both deletes stay with pseudonymise, and
`open` goes to a change nobody had written).

Nothing reaches the service from wordsworth until `key-service-cutover`, so
an `open` without a rate limit between builds 2 and 3 serves no caller.

## Settings and the Transit seam

The skeleton defined two settings. Wrapping a key needs OpenBao, so this
change adds, under `KEYSERVICE_` only (skeleton rule 2: no fallback to
wordsworth's settings):

| Setting | Default | Note |
|---|---|---|
| `KEYSERVICE_OPENBAO_URL` | none, required | |
| `KEYSERVICE_OPENBAO_TOKEN` | none, required | Transit wrap/unwrap only |
| `KEYSERVICE_TRANSIT_KEK` | `wordsworth` | the KEK that wraps the PII mapping keys. `key_vault` rows carry no KEK name, so this must be the KEK wordsworth's rows are wrapped under; the default is wordsworth's own default, so the cutover's copy unwraps unchanged |
| `KEYSERVICE_KEY_CACHE_TTL` | 300 | seconds an unwrapped mapping key stays in memory |
| `KEYSERVICE_PSEUDONYMISE_MAX_ITEMS` | 1 000 | refused at startup above 5 000 |

The service refuses to start when `KEYSERVICE_OPENBAO_URL` or
`KEYSERVICE_OPENBAO_TOKEN` is empty, in the same startup check as the
database refusal, with a message naming the setting. Rejected: wordsworth's
defaults (`http://localhost:8200` and an empty token), which are a silent
fallback (AGENTS.md) and the way a service ends up wrapping under nothing.

`create_app` gets a `transit_for` argument (`str -> Transit`) next to
`engine` and `service_tokens`. `None` builds `transit.transit_factory(url,
token)` from the settings on first use, so importing `serve.py` still does no
I/O and the refusal still runs on the startup event. When `transit_for` is
passed (the tests pass `FakeTransit`), the OpenBao settings are not required.

## Stores

`stores_pii.py` (≤ 200 lines): the service's `PostgresMappingStore` and
`KeyVaultStore` over its own `PiiMapping` and `KeyVaultRecord`, implementing
wordsworth's `MappingStore` and `KeyVaultStore` protocols. The key provider is
wordsworth's `DurableKeyProvider` (pure: it takes a vault store and a
`Transit`, reads no settings and touches no model) over the service's vault
store and `transit_for(KEYSERVICE_TRANSIT_KEK)`, with its TTL from
`KEYSERVICE_KEY_CACHE_TTL`. The token derivation, normalisation and
encryption are wordsworth's own functions (`Pseudonymizer.pseudonym`,
`normalization`, `crypto`, `keys.scope_for`), called with these stores;
nothing about how a token is made changes. Rejected: reusing
`PostgresMappingStore` and `PostgresKeyVaultStore` from wordsworth, which
query wordsworth's models (skeleton rule 3).

## Only reveal returns a clear value

No route of the service returns a clear mapping value to a calling service
without a verified person. The routes here return tokens and counts; the only
route that returns mapping values is `/v1/reveal` (`key-service-reveal`), and
it needs a person's assertion and a grant. A later need for clear values
without a person (the box map, `key-service-cutover`) is met from the values
in memory during processing, not by a new route.

## The token registry

The registry is the service's. A row (`document_id`, `token`) exists only
because the service itself returned that token from `pseudonymise` for that
document (`source = minted`), or because the cutover copied it
(`source = copied_minted` or `copied_backfilled`, keeping wordsworth's
provenance). Nothing else writes it. A reveal (`key-service-reveal`) reveals
only tokens registered for the document it is asked about.

This is what makes the registry trustworthy against a compromised wordsworth:
to bind a token to a document it must send the value, and a value it already
knows is no secret. A value it does not know cannot be registered anywhere.

Registering never removes a token: re-pseudonymising a document adds the new
tokens and keeps the old ones, as `pseudonym_registry.register` does today (a
reveal in flight must not see the registry shrink). Only
`DELETE /v1/documents/{id}` (`key-service-delete`) removes rows.

wordsworth's own `document_pseudonyms` is not touched by this change.

## `known_documents`

The service knows a document from its first `pseudonymise` (or, from
`key-service-originals`, its first `seal`), both of which carry `domain`. The
first call records (`id`, `domain`); a later call for the same id with a
different domain is refused (409), and a call for a tombstoned id is refused
(410). The domain recorded here is the one reveal judges a grant against;
wordsworth cannot change it afterwards. `known.py` holds the one function
that does this, so `seal` reuses it.

## The audit writer

`audit.py` holds `append_access(session, *, event, service_caller,
document_id, payload)`: under `pg_advisory_xact_lock(4782)`, the previous
hash, `hashing.compute_hash` over the same canonical content shape as
wordsworth's audit (`hashing.canonical_content`, genesis `GENESIS_HASH`), and
the insert. `verify_access_chain(session)` walks it. Both are pure SQL on the
service's session, so no wordsworth model is queried.

## Locks

One order inside the service's database, for every writer of the four
changes, written first on `docs/reference/lock-order.md` in its own section
(the service is another database; wordsworth's rows on that page do not
change):

1. the registry advisory lock (`pg_advisory_xact_lock(4781)`), taken by
   `pseudonymise`, `seal` and `DELETE /v1/documents`;
2. the `known_documents` row;
3. `document_keys` rows, by `object_key`, `FOR UPDATE` (originals, delete);
4. `pii_mappings` rows, by token: inserted `ON CONFLICT DO NOTHING` by
   `pseudonymise`, `FOR UPDATE` by a deletion;
5. the `key_lifecycle_events` chain lock, advisory key 4783, taken by a
   writer that records a key-lifecycle event (`key-service-delete`);
6. the `access_audit` chain lock, advisory key 4782, last: the audit is the
   terminal leaf, nothing is taken after it.

4781, 4782 and 4783 are the service's; wordsworth's 4771 and 4772 belong to
another database. The skeleton's `AccessAudit` docstring names 4772 for the
service's key-lifecycle lock; `key-service-delete`, the first writer of that
chain, corrects it to 4783. The page says that wordsworth's sentence "never
together with 4771" is about wordsworth's database. `service_state`
(`key-service-open-limits`) takes no advisory lock and is written by single
statements after lock 6 is released.

## `POST /v1/pseudonymise`

Request (JSON): `{"document_id": UUID, "domain": str, "items": [{"type": LABEL,
"value": str}, ...]}`. `items` may be empty (that registers the document and
its domain). At most `KEYSERVICE_PSEUDONYMISE_MAX_ITEMS`. The cap is there
because lock 1 (4781) is held for the whole batch: 10 000 items held it long
enough to stall every other writer. Rejected: keeping 10 000 and shortening
the lock by committing in chunks, which would break "nothing committed" on a
503 and the one-audit-record-per-call rule. A larger document sends several
calls. The time lock 1 is held at the cap is measured at cutover, and the
default revisited from it.

**Type labels.** A label is valid when it matches `[A-Za-z0-9_]+` (the token
alphabet of `pseudonymizer._PSEUDONYM_RE` once upper-cased, so every token the
service mints is still recognisable and revealable). There is no closed list:
wordsworth classifies an unknown detector type as `c1` and carries on
(`pii_categories`, "the detector's label vocabulary is not ours to fix"), and
the service does the same. Rejected: `pii_categories.known_types()` as a
closed list, which turns one new GLiNER label into a refused batch and, after
the cutover, a stopped ingest. A `domain` that is empty or contains `/` is
refused (422), as `keys.scope_for` would raise on it.

| Case | Status | Body |
|---|---|---|
| no or unknown service token | 401 | `{"detail": "invalid or missing service token"}` |
| malformed body, invalid type label or domain, too many items | 422 | validation detail, never echoing a value |
| document known in another domain | 409 | `{"detail": "document is registered in another domain"}` |
| document tombstoned | 410 | `{"detail": "document deleted"}` |
| a key is needed and Transit is unreachable or sealed | 503 | `{"detail": "key service unavailable"}`, nothing committed |
| otherwise | 200 | `{"document_id": UUID, "tokens": [str, ...]}`, one token per item, same order |

The response contains no value, no hash of a value and no key id. One
`access_audit` record per call: `event = "pseudonymise"`, the document, the
service caller, the number of items per type and the number of new registry
rows; no value, no token.

## Modules

`api_pseudonymise.py`, `stores_pii.py`, `known.py`, `audit.py`, and the
additions to `config.py` and `serve.py`. Each ≤ 200 lines.

## Residual

ADR-0009 already records that `pseudonymise` turns any value into its token
for whoever holds the service credential (guess-confirmation). This change
extends that row with the batch cap; it adds no parallel row.
