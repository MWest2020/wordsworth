# Design

## Architect FAIL #522: how each finding is answered

| # | Finding | Answer | Where |
|---|---------|--------|-------|
| 1 | `/v1/reveal` has no contract; `reveal_gate.decide()` reads document state, domain, supersession and the box map, and `deanonymize()` needs the token registry and writes the document audit chain | A two-call contract (`/v1/reveal/decide`, `/v1/reveal`) with inputs, outputs, who decides what, the order, and every status code on both sides of the boundary | `key-service-reveal/design.md` |
| 2 | ADR-0009's threat-model row only holds if the service decides which tokens belong to a document | Choice (a): the registry moves to the service (`document_tokens`, filled only by the service's own `pseudonymise`); ADR-0009 amended in this PR. wordsworth's `document_pseudonyms` may stay as a copy for non-reveal uses and is never consulted by a reveal | ADR-0009; `key-service-vault/design.md` |
| 3 | Splitting the grant decision across a process boundary brings the existence oracle back | wordsworth reads no document row until the service has answered "covered"; the service never answers 404 or 409; every non-covered cause is the same 403 on both sides; 410/409 only after "covered", in today's order | `key-service-reveal/design.md`, "Order" and "Status codes" |
| 4 | One `Base` would govern two databases; the test fixture would drop wordsworth's tables | A separate `KeyServiceBase`; its own init and its own test database; a drift test compares the duplicated column shapes | below, "Schema" |
| 5 | Foreign keys to `documents.id` (`audit_records`, `document_keys`, `grants`) block the schema; the open/reveal audit stream has no home | No foreign key to any wordsworth table; the service has its own `known_documents` (id, domain, tombstone) and its own hash-chained `access_audit` with an `event` instead of from/to state | below, "Schema" |
| 6 | Two credentials on one request (calling service and person); `ApiKeyAuthMiddleware` collapses them; the audience is unnamed | The service token authenticates the calling service (this change); the person's signed assertion travels in the request body and is verified by the service against its own issuer and audience (`key-service-reveal`). The service never mounts `ApiKeyAuthMiddleware` | below, "Service authentication"; `key-service-reveal/design.md`, "Identity" |
| 7 | `config.settings` is a `WORDSWORTH_*` singleton that `document_keys` reads | The service has its own `Settings` (`KEYSERVICE_*`); reused functions that read `config.settings` get their values as arguments in the service | below, "Settings" |
| 8 | Files ≤ 200 lines; `api.py` is 2006 | The service is a package of small modules from the start, one router per endpoint group | below, "Layout" |
| 9 | `/v1/export` is absent and belongs to `key-export-escrow` | Kept out, stated in the proposal | `proposal.md` |
| 10 | The homelab NetworkPolicy lives elsewhere | The how-to says plainly that until that policy exists, anything in the cluster holding a service token reaches the service | below, "Deployment" |
| 11 | Too big for one build | Split into three changes, the architect's builds A, B and C | `proposal.md` |

The architect's working assumptions for the refuse-to-start check, the service
token and the rate limit are taken over as decisions (below, and in
`key-service-vault`).

## Layout

`src/wordsworth/keyservice/`, every file ≤ 200 lines:

- `config.py` — `Settings` from `KEYSERVICE_*` only.
- `models.py` (split further if the rule needs it) — `KeyServiceBase` and the
  tables below.
- `db.py` — `make_engine`, `init_schema` over `KeyServiceBase.metadata`, the
  refuse-to-start check.
- `bootstrap.py` — `wordsworth-keyservice-init`: create the schema, nothing
  else (no admin role: roles arrive with `key-service-reveal`).
- `auth.py` — the service-token check.
- `serve.py` — the composition root: FastAPI app, `/health`, the service-token
  dependency on every `/v1` route, lazy backends so that importing does no I/O.

`pyproject.toml` gets the scripts `wordsworth-keyservice` (uvicorn on
`wordsworth.keyservice.serve:app`) and `wordsworth-keyservice-init`. The
Dockerfile is unchanged apart from a comment: same image, different command.

## Settings

`keyservice.config.Settings` reads `KEYSERVICE_*` and nothing else. This change
needs two: `KEYSERVICE_DATABASE_URL` (required, no default) and
`KEYSERVICE_SERVICE_TOKENS` (`label:token` pairs, the format of
`auth.parse_api_keys`). Later changes add theirs under the same prefix.

wordsworth modules the service reuses and that read `config.settings` today
(`document_keys.kek_name_for`, the cache defaults of `DocumentKeys`) get their
values as arguments from the service; wordsworth's own call sites keep their
current defaults. Proved by a test that sets conflicting `WORDSWORTH_*` values
and shows the service uses the `KEYSERVICE_*` ones.

## Schema

One metadata per database. `KeyServiceBase` is a separate `DeclarativeBase`;
no module of the service imports `wordsworth.models`, and `wordsworth.models`
does not import the service. `wordsworth-keyservice-init` runs
`KeyServiceBase.metadata.create_all` plus the append-only trigger
(`_FORBID_FUNCTION_SQL` from `db_migrations.py`) on `access_audit` and
`key_lifecycle_events`, with the same lock-timeout-and-retry shape as
`db.init_schema`. A second run is a no-op.

Tables. "Copied" means the same column names and types as the named
wordsworth model. No column refers to a wordsworth table: every `document_id`
is an indexed UUID column, referring at most to the service's own
`known_documents`.

| Table | Shape | Used from |
|---|---|---|
| `key_vault` | copied from `KeyVaultRecord` | vault |
| `pii_mappings` | copied from `PiiMapping` | vault, reveal |
| `document_keys` | copied from `DocumentKeyRecord`; `document_id` refers to the service's `known_documents.id` | vault |
| `known_documents` | new: `id` UUID PK, `domain` text NOT NULL, `registered_at`, `deleted_at` NULL | vault, reveal |
| `document_tokens` | new, the token registry: `document_id` → `known_documents.id`, `token`, `source` (`minted` \| `copied`), `created_at`; PK (`document_id`, `token`) | vault, reveal |
| `grants` | copied from `GrantRecord`; `document_id` nullable, no foreign key (a grant may name a document the service has not seen; it then covers nothing) | reveal |
| `roles`, `group_roles` | copied from `Role`, `GroupRole` | reveal |
| `key_lifecycle_events` | copied from `KeyLifecycleEvent`, append-only | vault, reveal |
| `access_audit` | new: `seq`, `ts`, `event`, `document_id` NULL, `service_caller`, `caller` NULL, `payload` JSONB, `prev_hash` UNIQUE, `hash` UNIQUE; append-only, hash-chained under its own advisory lock (not 4771, which is wordsworth's) | vault, reveal |
| `rate_limit_buckets` | copied from `RateLimitBucket` | vault |

The cost of a separate metadata is that the copied shapes live in two places
and can drift. Two things catch that: a test in this change that compares, for
every copied table, the service's column names and types with wordsworth's
model (a difference fails the test and names the column), and the cutover's
row-count and decryption verification.

## Refuse to start

At startup and in the init entrypoint, before serving or creating anything:

1. `KEYSERVICE_DATABASE_URL` unset or empty: refuse.
2. `WORDSWORTH_DATABASE_URL` is set in the process and names the same host,
   port and database: refuse (a copied configuration).
3. The database already holds `audit_records` or `document_texts`, tables
   only wordsworth has: refuse. This one catches the real thing whatever the
   environment says.

A refusal is an exception with a message naming the rule, never a warning; the
process exits non-zero.

## Service authentication

`Authorization: Bearer <service token>` on every `/v1` route, compared in
constant time against `KEYSERVICE_SERVICE_TOKENS`; the matching label is the
`service_caller` (audit, rate limit). Missing or unknown token: 401
`{"detail": "invalid or missing service token"}`, before the body is parsed and
before any database read. An empty token set refuses every `/v1` call; that is
the opposite of wordsworth's API-key default (open when no key is set) on
purpose, because an open key service is the one thing the split exists to
prevent. `/health` needs no token and says only that the process is up and its
database reachable.

The service token is not a person. Where a person matters (reveal) the person's
signed assertion travels in the body and is verified by the service itself
(`key-service-reveal`); the two are never collapsed into one caller, so the
service does not mount wordsworth's `ApiKeyAuthMiddleware`.

## Tests

A second private database for the service, next to wordsworth's: the fixture
takes `KEYSERVICE_TEST_DATABASE_URL`, or creates
`wordsworth_keyservice_test_<suffix>` through the `WORDSWORTH_TEST_DATABASE_URL`
connection, and skips on the same terms as the existing database fixture. It
drops and creates `KeyServiceBase.metadata` only; a test proves that running it
leaves every wordsworth table in wordsworth's test database untouched.

## Deployment

`docs/how-to/key-service.md`: the two variables, the init Job, a separate
Postgres database and role that wordsworth's role cannot read, and the failure
modes from ADR-0009. It says plainly that the NetworkPolicy admitting only
wordsworth's pods is a separate homelab PR, and that until it exists anything
in the cluster that holds a service token reaches the service.
