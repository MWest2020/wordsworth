## Why

The reveal / grant / reprocess / ingest endpoints have no caller authentication —
the API is tailnet-internal and a `grant_id` is a bearer capability. The Fase-B
audit flagged this: reveal access is attributed to the grant recipient, not to
the actual caller. We want an optional per-caller identity that is enforceable
and lands in the audit, WITHOUT breaking the current open, tailnet-internal
deployment.

## What Changes

- **Opt-in, default-off API-key auth.** `WORDSWORTH_API_KEYS` holds comma-
  separated `label:key` pairs (→ {key: label}). When empty (the default) nothing
  changes: the API stays open. When set, an `ApiKeyAuthMiddleware` requires a
  valid `X-API-Key` header on every route except the ops probes (`/health`,
  `/metrics`); missing/invalid → 401. Keys are never logged.
- **Caller attribution.** On a successful request the caller's label is stashed
  in the request scope; the reveal route records it in the `deanonymize` audit as
  `caller`, alongside (not replacing) the grant recipient and `grant_id`. No clear
  PII in the audit (unchanged).
- Minimal by design — key→label only, no user/role model. OIDC / mTLS is the
  heavier future option (documented in the runbook).

## Capabilities

### Added Capabilities
- `api-key-auth`: optional per-caller API-key authentication that is inert when
  unconfigured and records the authenticated caller on reveal when enabled.

## Impact

- Code: new `auth.py` (`parse_api_keys`, `ApiKeyAuthMiddleware`); `config.py`
  (`api_keys`); `api.py` (`create_app(api_keys=...)`, conditional middleware,
  reveal caller attribution). No new dependency. No schema change.
- Non-breaking: with no keys configured every existing test and the live
  deployment behave identically (266 local tests green, no new 401s).
- Tests: local (parse, off-by-default open, 401 without/with wrong key, valid
  passes, /health open) + DB-integration (reveal requires a key and records the
  caller).
