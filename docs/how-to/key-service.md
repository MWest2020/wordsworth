---
status: draft
last_reviewed: 2026-11-28
---

# Runbook — the key service

ADR-0009: one service holds the keys, the encrypted values, the token
registry and the reveal decision; the rest of wordsworth sees tokens only.
This change (`key-service-skeleton`) ships the process boundary with **no
traffic** — nothing in wordsworth calls it yet. The five changes split
from `key-service-vault` (`key-service-pseudonymise`, `key-service-originals`,
`key-service-open-limits`, `key-service-delete`, `key-service-reveal`) fill
it in. `key-service-open-limits` adds the rate limit on `open`, its 429
audit and `GET /v1/metrics`. `key-service-reveal` adds the two reveal
routes, identity verification and the service's own grants/roles — still
with no traffic from wordsworth; that is `key-service-cutover`.

## Deploying it

Same image as wordsworth, a different command (the Dockerfile is otherwise
unchanged):

```
wordsworth-keyservice-init   # once, before first start: creates the schema
wordsworth-keyservice        # serves /health and the (still empty) /v1 surface
```

It needs its own environment variables, set independently of wordsworth's:

- `KEYSERVICE_DATABASE_URL` — required, no default. The `postgresql+psycopg://`
  scheme is required, same as wordsworth's own database URL.
- `KEYSERVICE_SERVICE_TOKENS` — `label:token` comma-separated pairs, one per
  calling service. A secret: inject via SOPS+age or OpenBao, never commit it.
- `KEYSERVICE_OPENBAO_URL` — required, no default. The OpenBao base URL the
  service wraps/unwraps mapping keys against.
- `KEYSERVICE_OPENBAO_TOKEN` — required, no default. A scoped token, Transit
  wrap/unwrap only, never root. A secret: inject via SOPS+age or OpenBao,
  never commit it.
- `KEYSERVICE_TRANSIT_KEK` — default `wordsworth`. The KEK that wraps the
  service's own PII mapping keys; must be the KEK wordsworth's existing
  `key_vault` rows are wrapped under, since those rows carry no KEK name of
  their own — the default is wordsworth's own default, so the cutover's
  copy unwraps unchanged.
- `KEYSERVICE_KEY_CACHE_TTL` — default `300`. Seconds an unwrapped mapping
  key stays in memory.
- `KEYSERVICE_PSEUDONYMISE_MAX_ITEMS` — default `1000`. Max (type, value)
  items per `POST /v1/pseudonymise` call; refused at startup above `5000`
  (see "Refuses to start" below).
- `KEYSERVICE_ORIGINALS_KEK` — default the value of `KEYSERVICE_TRANSIT_KEK`.
  The KEK that wraps original-document data keys (`seal`/`open`).
- `KEYSERVICE_ORIGINALS_KEK_BY_DOMAIN` — default empty. A JSON object
  (`{"domain": "kek-name"}`) overriding the originals KEK per domain.
- `KEYSERVICE_DOCUMENT_KEY_CACHE_SIZE` — default `1024`. Max entries in the
  unwrap cache for original-document data keys.
- `KEYSERVICE_OPEN_RATE_PER_MINUTE` — default `120`. Refill rate of the
  per-calling-service token bucket on `open`.
- `KEYSERVICE_OPEN_BURST` — default `30`. Capacity of that bucket; a burst
  past it is refused with 429 and a `Retry-After` header (seconds until the
  next token).
- `KEYSERVICE_MAX_ORIGINAL_BYTES` — default `104857600` (100 MiB). `seal` and
  `open` both hold the whole request body in memory up to this bound; a
  larger body is refused with 413 — enforced only after FastAPI has already
  buffered the whole body into memory, so an oversized request still costs
  that memory before it is refused. Every caller is wordsworth behind a
  service token, and the ingress body limit is the real bound.
- `KEYSERVICE_OIDC_ISSUER` / `KEYSERVICE_OIDC_AUDIENCE` — required for
  reveal; both empty (the default) means both reveal routes answer 503
  before reading anything. See "Identity", below.
- `KEYSERVICE_OIDC_JWKS_URL` — default empty (discovered from the issuer).
  Set this to bypass discovery, e.g. to reach Keycloak at its in-cluster
  address while `KEYSERVICE_OIDC_ISSUER` stays the public realm URL.
- `KEYSERVICE_ALLOW_GLOBAL_GRANTS` — default `false`. Whether an unscoped
  grant (no `document_id`) may authorize a reveal on every document.
- `KEYSERVICE_VC_PUBLIC_KEY` / `KEYSERVICE_VC_EXPECTED_VCT` /
  `KEYSERVICE_VC_EXPECTED_ISSUER` / `KEYSERVICE_VC_REQUIRED` — the optional
  EUDI-aligned VC gate (ADR-0003), narrowing a grant further when a
  presentation is sent in a reveal request's `vc` field. The public key is
  off (and the gate inert) unless `KEYSERVICE_VC_PUBLIC_KEY` is set.
- `KEYSERVICE_REVEAL_MAX_TOKENS` — default `10000`. Max distinct tokens per
  `POST /v1/reveal` call; 413 beyond it, checked before anything else but
  the service token. A document with more distinct tokens cannot be
  revealed until this is raised.

## Identity

A reveal names a *person*, separately from the service token that names
the *calling service*: the raw Keycloak JWT wordsworth received (the
bearer behind oauth2-proxy), forwarded in the request body's `assertion`
field — never trusted from a header. The service verifies it itself, under
its own `KEYSERVICE_OIDC_*` settings, reusing wordsworth's
`access_identity.Verifier.oidc` and `email_from` unchanged and adding the
one check that module does not perform: a token whose `nbf` lies in the
future is refused too. Every refusal — missing, forged, expired,
not-yet-valid, wrong issuer, or foreign audience — is the same
`401 {"detail": "assertion not accepted"}`, so a caller cannot distinguish
them. A Cloudflare Access assertion is refused the same way: this
service's `Verifier` only ever names one OIDC issuer (Keycloak), and an
Access token simply fails that issuer/audience check like any other.

`KEYSERVICE_OIDC_AUDIENCE` (recommended `wordsworth-keyservice`) separates
differently depending on how Keycloak adds it to a token:

- with an audience mapper on wordsworth's client, every token wordsworth
  receives carries it — the audience then keeps out tokens issued to other
  clients of the realm, and nothing more: any live wordsworth session
  token is accepted by the service once it has a valid signature and a
  grant;
- with an optional client scope requested only when a person reveals, only
  tokens obtained for a reveal carry it, so a token wordsworth could replay
  exists only around a reveal. That needs a step-up request in the console
  and is the cutover's choice, not built here.

**The replay residual**: a session token forwarded for a reveal is a
bearer credential for as long as it is valid — up to Keycloak's token
lifetime with the first (mapper) choice, or until the step-up scope's
token expires with the second. Neither this service nor wordsworth
invalidates a token after one use; treat the forwarding path (wordsworth
to the service) as carrying a short-lived but replayable secret, and keep
it off any log.

There is no "authentication off" mode for reveal: the recipient is always
checked. Without `KEYSERVICE_OIDC_ISSUER` and `KEYSERVICE_OIDC_AUDIENCE`
both routes answer 503 before reading anything.

## Grants and roles

The service decides a reveal from its own `grants` and `roles` tables —
copies of wordsworth's shape, enforced by the same pure
`wordsworth.grants.authorize`/`permitted_types` and
`wordsworth.vc.apply_vc_gate`, reused unchanged. `wordsworth-keyservice-init`
ensures the admin role (`beheerder`) exists, with every known PII type,
the same way `wordsworth.bootstrap.ensure_admin_role` does on wordsworth's
own database — an existing role, active or not, is left untouched. No
management endpoint exists yet to issue a grant, revoke one, or create or
toggle a role: until `key-service-cutover`, those are rows seeded
directly (an operator task, or a test fixture).

## The wire between wordsworth and the service

`open` returns the original in plaintext over HTTP on this link, and `seal`
receives it the same way — encryption at rest does not cover it. The link's
transport (mutual TLS or a service token) is a deployment choice; the token
alone does not encrypt it. Deploy TLS on this link, or accept that whoever
can read it reads originals in transit.

## Its database and role

A **separate PostgreSQL database and role** from wordsworth's — the whole
point of the split is that wordsworth's role cannot read it. Create a
database and a role scoped to only that database before running
`wordsworth-keyservice-init`; do not reuse wordsworth's `wordsworth` role or
database.

The service's schema (`KeyServiceBase`) lives on its own `DeclarativeBase`,
disjoint from wordsworth's: no table it creates has a foreign key to a
wordsworth table, and no migration path exists yet. Until the cutover
(`key-service-cutover`) the database holds no data, so a schema change today
is made by dropping and recreating it, not by migrating.

`service_state` is the one table for state that only the service has, that
is not a copy of a wordsworth table and not derived from `access_audit`: the
open-rate bucket, the coarse 429 audit's refusal window, and every
Prometheus counter the service keeps outside the audit. A table, not
process memory, because the service runs more than one replica
(`2026-09-20-hoge-beschikbaarheid`) and a counter that restarts at zero on a
crash hides exactly the burst an investigation looks for. Written only by
`state.py`; `tests/keyservice/test_service_state_drift.py` fails and names
any other table that grows a counter or rate-limit column.

## Refuses to start

At startup, and in `wordsworth-keyservice-init`, before touching or creating
anything:

1. **No `KEYSERVICE_DATABASE_URL`** (unset or empty) — refuses.
2. **The same database as `WORDSWORTH_DATABASE_URL`** (same host, port and
   database name, read straight from the environment, never through
   wordsworth's own settings) — refuses. Catches a copy-pasted configuration.
3. **A database that already holds `audit_records` or `document_texts`**
   (tables that exist only in wordsworth's schema) — refuses. Catches the
   real thing: pointing the service at wordsworth's database however the
   rest of the environment is configured.
4. **No `KEYSERVICE_OPENBAO_URL` or no `KEYSERVICE_OPENBAO_TOKEN`** (either
   unset or empty) — refuses, naming which one. Not checked when the
   process was wired with its own `transit_for` factory directly (tests
   only); every real deployment goes through this rule.
5. **`KEYSERVICE_PSEUDONYMISE_MAX_ITEMS` above `5000`** — refuses, naming
   the configured value. The registry advisory lock (4781) is held for the
   whole batch; a cap this high would stall every other writer too long.

Each refusal is an exception naming the rule, never a warning; the process
exits non-zero. There is no override.

## The service token

Every path under `/v1/` needs `Authorization: Bearer <token>`, checked
against `KEYSERVICE_SERVICE_TOKENS` in constant time. The matching label
becomes the caller recorded in later audit records. Unlike wordsworth's
optional, open-by-default API keys: **an empty token set refuses every
`/v1` call.** There is no "auth off" mode for this service — an open key
service is the one thing the process split exists to prevent.

`/health` needs no token. It says only that the process is up and its own
database is reachable — it does not say anything about `/v1`.

## The open rate limit and its metrics

`open` is rate-limited per calling service (`KEYSERVICE_OPEN_RATE_PER_MINUTE`,
`KEYSERVICE_OPEN_BURST`, above); a burst past it is a 429 with
`Retry-After`. A refusal is audited coarsely, not once per refusal: the
first refusal of each 60-second window writes one `open_refused` record
(`reason = "rate"`), and — if a previous window existed — one
`open_refused_summary` naming that window's count. A caller never refused
again after a window leaves it without a summary; the count still shows up
in `/v1/metrics` and in the counter itself.

`GET /v1/metrics` exposes opens and refusals in Prometheus text format,
behind the same service token as every other `/v1` route, and is never
rate-limited itself — there is no limiter middleware in this app to exempt
it from. Its caller (the scraper) therefore needs its own service token in
`KEYSERVICE_SERVICE_TOKENS`; wiring that into the homelab's scrape config is
a homelab PR, not part of this change, and no alert on open or refusal
volume is built in any key-service change yet (see ADR-0009's residuals).

## Failure modes

- **Process does not start**: one of the five refuse-to-start rules fired —
  check the exception message, it names which one.
- **`/health` returns 503**: the process is up but its database is not
  reachable (network, credentials, or the database is down). This is not a
  refuse-to-start rule; it can happen after a successful start.
- **Every `/v1` call returns 401**: either no token was sent, the token does
  not match any configured pair, or `KEYSERVICE_SERVICE_TOKENS` is empty
  (every call fails-closed in that case, by design).
- **`POST /v1/pseudonymise` returns 503**: OpenBao is unreachable or sealed
  when a mapping key was needed. Nothing is committed — no mapping, no
  registry row, no `known_documents` row, no audit record.
- **`seal` returns 503**: OpenBao is unreachable or sealed when a data key
  was needed to mint or reuse. Nothing is committed.
- **`open` returns 503**: the key backend gave no answer about the wrapped
  key (connect/timeout, or an HTTP 5xx) — no audit record is written, since
  nothing was decided. A 409 instead means the backend answered and refused
  it, or the sealed object itself does not authenticate; both are audited as
  `open_failed`.
- **Both reveal routes return 503 `reveal not configured`**:
  `KEYSERVICE_OIDC_ISSUER` or `KEYSERVICE_OIDC_AUDIENCE` is unset — there is
  no override, by design.
- **A reveal returns 401 `assertion not accepted`**: the caller's identity
  provider token failed verification for one of several reasons (see
  "Identity", above) — the body never says which one.
- **`POST /v1/reveal` returns 503 `key service unavailable`**: OpenBao gave
  no answer about a mapping key needed to resolve a requested token; no
  audit record is written, since nothing was decided. A reveal that
  resolves zero tokens (a wrong grant/document combination, or tokens none
  of which are registered or authorised) is still a 200 — that silence is
  the point (design.md "Why the existence oracle stays closed").

## Not yet enforced

**The NetworkPolicy that admits only wordsworth's pods does not exist yet**
(a separate PR in `MWest2020/homelab`). Until it does, anything in the
cluster that holds a valid service token can reach this service. Treat the
token as the only boundary for now, and deploy the policy before relying on
network isolation.
