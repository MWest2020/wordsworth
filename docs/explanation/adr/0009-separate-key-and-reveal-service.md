---
status: accepted
last_reviewed: 2026-10-30
---

# ADR 0009 — A separate key-and-reveal service

- Status: accepted (Mark, 2026-10-30)
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
- the authorisation facts for reveal: roles, the group → role mapping, grants;
- the reveal audit stream and the key-lifecycle stream.

**API contract** (versioned, `/v1`, mutual TLS or a service token between
wordsworth and the service; callers' identities travel as the signed assertion
from the identity provider, which the service verifies itself):

- `POST /v1/pseudonymise` — per document, a batch of (type, value) pairs in;
  tokens out. The service derives the keyed token, stores the encrypted value,
  returns only tokens. wordsworth never holds a key.
- `POST /v1/reveal` — document id, the requested types, the caller's verified
  assertion (and a grant id where one is used); the service decides against
  roles, groups and grants, decrypts what is allowed, audits, returns values.
  wordsworth can't reveal anything the caller isn't entitled to, even if
  wordsworth itself is compromised.
- `POST /v1/originals/{document_id}/seal` and `.../open` — encrypt an original
  for storage, and decrypt it for processing (pipeline, OCR, PDF rendering).
  Every open is audited with its purpose and rate-limited.
- `DELETE /v1/originals/{document_id}` — destroy the document's data key
  (crypto-shredding, ADR-0008).
- `POST /v1/export` — wrapped key export (ADR-0008 consequences; change
  `key-export-escrow`).

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
| wordsworth's process and its service credential | the ability to open originals for processing (audited, rate-limited, alerting on volume) and to pseudonymise | reveal of clear PII values (needs a user's verified assertion with a matching role or grant) |
| the key service's database alone | wrapped keys and encrypted values | anything readable (the KEK stays in OpenBao) |
| OpenBao alone | the KEK | the wrapped keys and the ciphertext it would unwrap |

The honest residual: whoever controls wordsworth's process can read the
originals it processes, because processing needs them; the service makes that
visible (every open audited with a purpose) and bounded (rate limits), not
impossible. Reading clear *PII values* out of tokens is impossible without a
user entitled to them.

## Why only this service

Splitting a monolith costs operations, latency and failure modes; it pays only
where the boundary itself is the product. Here it is: the key service can run
with its own database, its own credentials, its own network policy — and, for
data autonomy, **at the organisation itself**, holding the organisation's KEK,
while wordsworth runs elsewhere. Search, topics, summaries and the console gain
nothing from being separate services; they stay in the monolith.

## Migration

1. The service ships first without traffic (`key-service-skeleton`): its own
   database, the API contract, tests against a fake Transit.
2. Cutover (`key-service-cutover`): the key vault, mappings, roles, grants and
   their audit move into the service's database with a verified copy (row
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
