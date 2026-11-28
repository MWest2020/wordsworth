---
status: accepted
last_reviewed: 2026-11-28
---

# ADR 0009 — A separate key-and-reveal service

- Status: accepted (Mark, 2026-10-30); amended 2026-11-26 (see
  [Amendment](#amendment-2026-11-26), from the architect's FAIL on #522)
- Date: 2026-10-30
- Context: data autonomy, least privilege, and an application layer with as
  little business logic as possible

## Context

wordsworth is a modular monolith: one image with three entrypoints (API,
schema, ingest), and every backend behind a driver seam (object store, search,
embeddings, anonymisation, key and mapping store). Around it run separate
services: OpenAnonymiser, Ollama, OpenSearch, Postgres, SeaweedFS, OpenBao,
Keycloak.

Inside that one process, today, sit three things that touch clear personal data
or the keys to it: the key provider (unwraps data keys from OpenBao), the
mapping store (the encrypted clear values behind every token) and reveal (the
decision to decrypt, and the decryption). Everything else — search, topics,
summaries, the console, the redacted PDF's layout — works on tokens. So the
whole monolith, its database credentials and its process memory are inside the
boundary that protects the clear values. A flaw anywhere in the application is
a flaw in that boundary.

## Decision

**Split out exactly one service: the key-and-reveal service.** It is the only
component that holds key material, the only one that talks to OpenBao, and the
only one that can turn a token back into a value. The rest of wordsworth sees
tokens and ciphertext only.

**It owns, in its own database** (a separate Postgres database and role that
wordsworth's database user cannot read):

- the key vault: the wrapped data keys per PII type (ADR-0002) and the wrapped
  data key per original document (ADR-0008);
- the mapping store: the encrypted clear value behind every token;
- the token registry: which tokens belong to which document, and the domain
  of every document it has seen. A token is registered for a document only
  when the service itself returned it from `pseudonymise` for that document;
  a document is known from its first `pseudonymise` or `seal`, which carries
  its domain. Reveal decides from this registry, never from a list wordsworth
  supplies;
- the authorisation facts for reveal: roles, the group → role mapping, grants;
- the reveal audit stream and the key-lifecycle stream.

wordsworth may keep its own `document_pseudonyms` copy for what is not a reveal
(type counts in the console, measurements, deletion counts): it holds no value
and can be read off wordsworth's own pseudonymised text anyway. It is never
consulted by a reveal.

**API contract** (versioned, `/v1`, mutual TLS or a service token between
wordsworth and the service; callers' identities travel as the signed assertion
from the identity provider, which the service verifies itself):

- `POST /v1/pseudonymise` — per document, a batch of (type, value) pairs in;
  tokens out. The service derives the keyed token, stores the encrypted value,
  returns only tokens. wordsworth never holds a key.
- `POST /v1/reveal/decide` and `POST /v1/reveal` — document id, grant id, the
  requested types and the caller's signed assertion (plus, for `reveal`, the
  tokens of the document's current text and the view). The service decides
  against its grants, roles and token registry; `decide` answers "covered, and
  which types" without decrypting anything, `reveal` decides afresh, decrypts
  only tokens registered for that document, audits, and returns values. Two
  calls because wordsworth must not read a document row before the grant is
  decided (reveal-authorize-first), and must not have values decrypted for a
  request it then answers 409 or 410. wordsworth can't reveal anything the
  caller isn't entitled to, even if wordsworth itself is compromised. The
  contract, with every status code, is in the change `key-service-reveal`.
- `POST /v1/originals/{document_id}/seal` and `.../open` — encrypt an original
  for storage, and decrypt it for processing (pipeline, OCR, PDF rendering).
  Every open is audited with its purpose and rate-limited.
- `DELETE /v1/originals/{document_id}` — destroy the document's data key
  (crypto-shredding, ADR-0008).
- `DELETE /v1/documents/{document_id}` — a document deletion: its data keys,
  its registry rows, every mapping no other document is registered for, and
  every grant scoped to the document (so its former recipient gets the uniform
  refusal, as today); the document's id and domain stay as a tombstone (no
  value, no token).
- `POST /v1/tokens/lookup` — a typed value in, its tokens out, for a person
  holding an unscoped grant for that type (change `search-by-value`).
- Management of roles, the group → role mapping and grants (change
  `key-service-cutover`); wordsworth's grant and role routes and the console
  call it.
- `POST /v1/export` — wrapped key export (ADR-0008 consequences; change
  `key-export-escrow`).

No route returns a clear value from the mapping store to a calling service
without a verified person: reveal is the only route that returns values.

**Authorisation is data in one place.** Which group maps to which role, which
role reveals which PII types or level, which grants exist: rows in the service,
managed through its API (and the console in front of it). The application has
no reveal rules in code.

## Threat model

| An attacker who has… | gets | does not get |
|---|---|---|
| wordsworth's database | pseudonymised text, document metadata, the audit of processing | any clear PII value, any key, any original |
| the search index | pseudonymised text and vectors | clear values |
| the object store (or a backup of it) | ciphertext | originals (no DEKs, no KEK) |
| wordsworth's process and its service credential | the ability to open any original (audited, rate-limited, counted; the alert on volume is not built yet), to pseudonymise, and to crypto-shred a document | reveal of clear PII values (needs a user's signed assertion with a matching grant, and reaches only tokens the service registered for that document) |
| the key service's database alone | wrapped keys and encrypted values | anything readable (the KEK stays in OpenBao) |
| OpenBao alone | the KEK | the wrapped keys and the ciphertext it would unwrap |

The honest residuals:

- Whoever controls wordsworth's process can read the originals it processes,
  because processing needs them, and with the service credential it can open
  any original, not only the ones it is processing. The service makes that
  visible (every open audited with a purpose) and bounded (a rate limit per
  caller, 120 a minute by default: still about 170 000 a day), not
  impossible. The opens are counted as metrics, and so are refusals, at
  `GET /v1/metrics` behind its own service token; a burst of refusals is
  audited once per caller per 60-second window, as `open_refused_summary`,
  not once per refusal -- the coarser record is what an investigation finds,
  not a flood of chained writes under the audit lock. No alert on volume is
  built in any of the key-service changes; until the homelab alert exists,
  nobody is told.
- A user's signed assertion passes through wordsworth on its way to the
  service. Whoever controls wordsworth's process can replay a live assertion
  for as long as it is valid, and reveal what that user is entitled to (the
  grant still has to cover it, and the service audits it under that user).
  Bounded by the assertion's lifetime, not prevented. The service accepts
  only Keycloak's assertions, whose access tokens live minutes; a Cloudflare
  Access session lasts up to 24 hours and is not accepted for reveal. The
  service's own audience does not narrow this as long as Keycloak adds it to
  every token wordsworth receives: it then only keeps out tokens issued to
  other clients. It narrows it only if the audience is requested at reveal
  time (an optional client scope), which is the cutover's choice.
- The service credential alone can crypto-shred any document
  (`DELETE /v1/originals`, `DELETE /v1/documents`): no person is asked. This
  is a loss of data, not a disclosure; it is audited, and recovery is only
  from a backup of the service's database taken before.
- `pseudonymise` turns any value into its token for whoever holds the service
  credential, so a compromised wordsworth can confirm whether a guessed value
  occurs in its own index. Every call is audited; ingest needs the operation,
  so it is visible, not prevented. A batch is capped
  (`KEYSERVICE_PSEUDONYMISE_MAX_ITEMS`, 1 000 by default, refused at startup
  above 5 000): the cap bounds how long the registry lock is held for one
  call, not how many guesses a caller may confirm across many calls -- the
  audit trail, not the cap, is what makes that volume visible
  (`key-service-pseudonymise`).
- The registry is copied from wordsworth once, at the cutover. A registry
  wordsworth had already corrupted before that moment carries over; after it,
  only the service registers tokens. The copy keeps its provenance
  (`copied_minted`, `copied_backfilled`): backfilled rows were read off stored
  text after the fact and were already less certain than minted ones. The
  copy aborts unless every token in every live document's current text is in
  the copied registry, so it cannot come out smaller than what reveal needs.
- `open` returns, and `seal` receives, the original in **plaintext over HTTP**
  on the link between wordsworth and the service: whoever can read that link
  reads originals in transit, which encryption at rest does not cover. Not
  prevented by `key-service-originals`; the deployment's TLS (mutual TLS or
  the service token's transport) is the mitigation.

Reading clear *PII values* out of tokens is impossible without a user entitled
to them, and then only that user's documents and types.

## Why only this service

Splitting a monolith costs operations, latency and failure modes; it pays only
where the boundary itself is the product. Here it is: the key service can run
with its own database, its own credentials, its own network policy — and, for
data autonomy, **at the organisation itself**, holding the organisation's KEK,
while wordsworth runs elsewhere. Search, topics, summaries and the console gain
nothing from being separate services; they stay in the monolith.

## Migration

1. The service ships first without traffic, in three builds:
   `key-service-skeleton` (its own process, settings, database and schema,
   service authentication), `key-service-vault` (pseudonymise with the token
   registry, seal/open/delete, its audit stream and rate limit; built as four
   changes, `key-service-pseudonymise`, `key-service-originals`,
   `key-service-open-limits` and `key-service-delete`) and
   `key-service-reveal` (the reveal contract and identity verification), all
   tested against a fake Transit.
2. Cutover (`key-service-cutover`): the key vault, mappings, the token
   registry with every document's domain, roles, grants and their audit move into the service's database with a verified copy (row
   counts, every mapping decrypts to the same value under the moved keys, a
   sample reveal before and after); wordsworth switches its key, mapping and
   reveal drivers to the service's API; the old tables are dropped only after a
   verification window, and the rollback is switching the drivers back.
3. Search on a real value (`search-by-value`), after the cutover: the service
   translates a typed value into its tokens for an authorised caller, and
   wordsworth searches on the tokens. The index still holds no value, not
   even encrypted; a refusal looks like "no hits". Follows from this ADR.

## Failure modes

- **Service down**: ingest stops (fail-hard: no un-pseudonymised text reaches
  the index), reveal and the PDF views are unavailable (fail-closed). Search,
  topics and the console's pseudonymised views keep working.
- **OpenBao sealed**: as service down, for every operation that needs a key
  not in the unwrap cache.
- **Network partition between wordsworth and the service**: as service down;
  wordsworth never falls back to holding keys.

## Amendment 2026-11-26

The first build of `key-service-skeleton` stopped at the architect (FAIL,
[#522](https://github.com/MWest2020/wordsworth/issues/522)). Three of its
findings touched this ADR:

- **The token registry was not listed.** Without it the service would reveal
  whatever tokens wordsworth put in front of it, and a compromised wordsworth
  holding one user's assertion would reach every value of that user's types in
  any document, which contradicts the threat-model row above. The registry now
  belongs to the service (Decision), so the row holds.
- **Reveal was one call.** The grant has to be decided before wordsworth reads
  any document row, and wordsworth's own answers (410 deleted, 409 superseded,
  409 not yet de-identified) must come before anything is decrypted. Hence
  `decide` then `reveal`.
- **Residuals were missing.** Opening any original at the rate limit with no
  alert built, assertion replay through wordsworth (and what the audience
  does and does not separate), `pseudonymise` as a guess-confirmation, crypto-
  shredding by the service credential alone, and the one-time registry copy
  are now written down.

Open for Mark, with defaults the builds proceed on: the residuals as written
(#525), and reveal requiring a signed identity after the cutover (#524).

Added to the contract: `DELETE /v1/documents/{document_id}`, because removing
a document's registry rows, orphaned mappings and scoped grants is now the
service's work; `POST /v1/tokens/lookup` and the management of roles, group
mappings and grants, which the later changes already assumed; and the rule
that only reveal returns a clear value.

