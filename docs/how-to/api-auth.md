---
status: draft
last_reviewed: 2026-11-17
---

# Runbook — optional API-key authentication

The Wordsworth API is tailnet-internal and open by default. You can optionally
require a per-caller API key. It is **off unless configured**. A key says who the
caller is; what that caller may then do is decided by two label lists, the
corpus-read list and the grant-issuer list (see [Effect](#effect)).

## Enable

Set `WORDSWORTH_API_KEYS` (a secret — inject via a k8s Secret / env, never commit)
to comma-separated `label:key` pairs:

```
WORDSWORTH_API_KEYS="acceptance:sk_live_aaaaaaaa,mark:sk_live_bbbbbbbb"
```

- `label` is the caller identity recorded in the audit; `key` is the secret the
  caller sends.
- Callers then send the header `X-API-Key: sk_live_aaaaaaaa` on every request
  except `/health` and `/metrics` (which stay open for probes).
- A missing or unknown key returns **401**. Keys are never logged.
- The `wordsworth` CLI sends its key from `$WORDSWORTH_API_KEY` (or `api_key`
  in its config file) — see [the CLI reference](../reference/cli.md#api-key).
  It has no flag for the key, so the key stays out of shell history.

## Effect

With auth on, every route except `/health`, `/metrics`, `/console/login` and
`/console/static/*` needs a valid key (or a verified identity, see
[access-identity](access-identity.md)). A key on its own is not enough for most
of them: what a caller may do depends on whether its label is on
`WORDSWORTH_CORPUS_READ_LABELS` (the read list) or
`WORDSWORTH_GRANT_ISSUER_LABELS` (the issuer list).

**A key alone opens:**

- `POST /ingest` (whether ingest needs its own label is issue #431);
- `/`, `/openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/redoc`: they
  describe the routes, not the corpus;
- `/console/logout`;
- `POST /documents/{id}/reveal` and `/reveal.pdf`, which are then decided by the
  grant presented (recipient, types, scope, expiry), not by the lists — the
  grant is decided before anything about the document is read, and every
  refusal to a caller it does not cover is the same 403 (see
  [grants: a refusal says nothing](grants.md#a-refusal-says-nothing)).

**The read list** (corpus read) guards every route that returns corpus content
or corpus metadata, or changes what a reader sees:

- reads: `GET /search`, `/hybrid`, `/ask`, `/export/ranking.csv`,
  `/export/anonymized.zip`, `/documents/{id}`, `/documents/{id}/state`,
  `/documents/{id}/anonymized`, `/documents/{id}/redacted.pdf`,
  `/dossiers/{id}/topics`;
- writes: `POST /documents/{id}/feedback`, `POST /dossiers/{id}/topics`,
  `PATCH /topics/{id}`, `POST /topics/{id}/label`,
  `POST /dossiers/{id}/summaries`, `POST /reprocess`;
- every console page that shows the corpus, `/console/combinations` included.

On the API routes the check is declared on the route, so it runs **before**
parameter validation and before any lookup: a caller without corpus read gets
the same `403 caller not authorized for corpus read` for an id that exists, one
that does not, and a request with a parameter missing. (A body that is not JSON
still answers 422 first, to anyone; that says nothing about the corpus.)

**The issuer list** guards `GET/POST /roles` and the role changes,
`POST /grants`, `POST /grants/{id}/revoke`, `POST /datasets/pseudonymize` (a
dataset run is a token lookup, see
[dataset pseudonymisation](dataset-pseudonymisation.md)) and the console's role
pages. `DELETE /documents/{id}` and `/dossiers/{id}` take an issuer label or the
admin role.

`GET /grants/{id}` admits a reader **or** an issuer; the recipient of a grant is
not admitted for being its recipient.

**An empty read list** switches the corpus-read scope off: every authenticated
caller reads everything, as before this list existed. With authentication and a
grant store both on, the API logs one `empty_corpus_read_scope` warning at
startup, because there the empty list is more likely forgotten than chosen. An
empty issuer list with auth on admits nobody to the issuer routes.

**A read list with auth off** has no caller to admit: every corpus-read route
answers 403, to everybody. (`GET /grants/{id}` stays reachable then, because
without auth the issuer check admits everyone, as it always has; the console is
not mounted without auth.) Set a read list only together with keys or an
identity provider.

On a reveal, the authenticated caller's `label` is written to the `deanonymize`
audit record as `caller`, alongside the grant recipient and `grant_id`, so
"who accessed this PII" is attributable to the real caller, not only the grant.

## Rotate / revoke a key

Edit `WORDSWORTH_API_KEYS` (drop or change the pair) and restart the API. There
is no per-key expiry yet.

## Not this (future)

This is a minimal shared-secret layer. Stronger schemes — OIDC/JWT via an
identity provider, or mTLS client certificates — are the heavier future option
when the straat grows a real multi-user UI; they are not implemented here.
