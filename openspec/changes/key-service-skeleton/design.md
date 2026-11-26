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
| 7 | `config.settings` is a `WORDSWORTH_*` singleton that `document_keys` reads | The service has its own `Settings` (`KEYSERVICE_*`); no service code path reads `config.settings`, checked by a test that makes it raise; the change that first needs a function reading it passes the value as an argument | below, "Settings" and "Reuse and imports" |
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

`keyservice.config.Settings` reads `KEYSERVICE_*`. This change needs two:
`KEYSERVICE_DATABASE_URL` (required, no default) and
`KEYSERVICE_SERVICE_TOKENS` (`label:token` pairs, the format of
`auth.parse_api_keys`). Later changes add theirs under the same prefix.

One exception, for refusing and nothing else: the refuse-to-start check reads
`WORDSWORTH_DATABASE_URL` straight from `os.environ` and compares it with
SQLAlchemy's `make_url` (host, port, database). It never imports
`wordsworth.config`, and the value is used for nothing else.

## Reuse and imports

Three rules, each checked by a test:

1. **`KeyServiceBase.metadata` contains no wordsworth table.** The set of
   `Table` objects in `KeyServiceBase.metadata` and in wordsworth's
   `Base.metadata` is disjoint (same names in two databases are fine, the
   same object is not), and the service's init creates only
   `KeyServiceBase.metadata`. Importing a wordsworth module that imports
   `.models` (`grants`, `roles`, `transit`, `pseudonymizer`, …) is allowed: it
   registers tables on wordsworth's `Base`, which the service never creates.
2. **No service code path reads wordsworth's `config.settings`.** A fixture
   replaces `settings` in `wordsworth.config` and in every loaded
   `wordsworth.*` module that bound it by name (`from .config import
   settings`) with an object whose every attribute access raises; the
   service's tests in this change and in `key-service-vault` and
   `key-service-reveal` run under it.
3. **Pure logic may be imported; stores bound to wordsworth's models are
   not used.** Imported as they are: `grants.authorize`,
   `grants.permitted_types`, `vc.apply_vc_gate`, `crypto`, `normalization`,
   `keys.scope_for`, `originals_envelope`, the `Transit` protocol with
   `FakeTransit` and `OpenBaoTransit`, `access_identity.Verifier` and
   `email_from`. Not used: `PostgresGrantStore`, `PostgresKeyVaultStore`,
   `PostgresMappingStore`, `roles.resolve` and anything else that queries a
   wordsworth model; the service has its own over `KeyServiceBase`. Where
   logic the service needs sits in a function that reads `config.settings` or
   a wordsworth model, it gets an argument or moves into a pure function, with
   wordsworth's behaviour unchanged, in the change that first needs it
   (`document_keys.kek_name_for` and the `DocumentKeys` cache defaults:
   `key-service-vault`).

This change itself imports nothing that reads `config.settings`.

## Schema

One metadata per database. `KeyServiceBase` is a separate `DeclarativeBase`;
no module of the service imports `wordsworth.models`, and `wordsworth.models`
does not import the service (rule 1 above). `wordsworth-keyservice-init` runs
`KeyServiceBase.metadata.create_all` plus the append-only trigger
(`_FORBID_FUNCTION_SQL` from `db_migrations.py`) on `access_audit` and
`key_lifecycle_events`, with the same lock-timeout-and-retry shape as
`db.init_schema`. A second run is a no-op.

The service database holds no data until the cutover. Until then a change to
a table is made by dropping and recreating the schema, without migrations; the
cutover decides how the schema changes once there is data.

Tables. "Copied" means the same column names, types and nullability as the
named wordsworth model. No column refers to a wordsworth table. Every
`document_id` is an indexed UUID column; in `document_keys` and
`document_tokens` it is a real foreign key to the service's own
`known_documents.id` (a document is recorded there before either is
written, and a deletion tombstones the row, never removes it); in `grants`
and `access_audit` it is no foreign key.

| Table | Shape | Used from |
|---|---|---|
| `key_vault` | copied from `KeyVaultRecord` | vault |
| `pii_mappings` | copied from `PiiMapping` | vault, reveal |
| `document_keys` | copied from `DocumentKeyRecord`; `document_id` refers to the service's `known_documents.id` | vault |
| `known_documents` | new: `id` UUID PK, `domain` text NOT NULL, `registered_at`, `deleted_at` NULL | vault, reveal |
| `document_tokens` | new, the token registry: `document_id` → `known_documents.id`, `token`, `source` (`minted` \| `copied_minted` \| `copied_backfilled`), `created_at`; PK (`document_id`, `token`) | vault, reveal |
| `grants` | copied from `GrantRecord`; `document_id` nullable, no foreign key (a grant may name a document the service has not seen; it then covers nothing) | reveal |
| `roles`, `group_roles` | copied from `Role`, `GroupRole` | reveal |
| `key_lifecycle_events` | copied from `KeyLifecycleEvent`, append-only | vault, reveal |
| `access_audit` | new: `seq`, `ts`, `event`, `document_id` NULL, `service_caller`, `caller` NULL, `payload` JSONB, `prev_hash` UNIQUE, `hash` UNIQUE; append-only, hash-chained under its own advisory lock (not 4771, which is wordsworth's) | vault, reveal |
| `rate_limit_buckets` | copied from `RateLimitBucket` | vault |

The cost of a separate metadata is that the copied shapes live in two places
and can drift. Two things catch that: a test in this change that compares, for
every copied table, the service's column names, types and nullability with
wordsworth's model (a difference fails the test and names the column; foreign
keys are not compared, so wordsworth's references to `documents.id` and the
service's to `known_documents.id` are ignored), and the cutover's row-count
and decryption verification.

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

`Authorization: Bearer <service token>` on every path under `/v1/`, compared in
constant time against `KEYSERVICE_SERVICE_TOKENS`; the matching label is the
`service_caller` (audit, rate limit). Missing or unknown token: 401
`{"detail": "invalid or missing service token"}`, before the body is parsed and
before any database read. That needs a pure ASGI middleware on the `/v1/`
prefix (it answers before the app reads the body), not a FastAPI dependency,
which runs after body parameters are parsed; it puts the label in
`scope["state"]["service_caller"]`. An empty token set refuses every `/v1` call; that is
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
