# Runbook — optional API-key authentication

The Wordsworth API is tailnet-internal and open by default. You can optionally
require a per-caller API key. It is **off unless configured** — enabling it does
not change any other behaviour.

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

## Effect

- When enabled, every mutating/PII endpoint (`/ingest`, `/reveal`, `/grants*`,
  `/reprocess`, `/ingest/nextcloud`, `/search`, `/export/*`, …) requires a valid
  key.
- On a reveal, the authenticated caller's `label` is written to the `deanonymize`
  audit record as `caller`, alongside the grant recipient and `grant_id` — so
  "who accessed this PII" is attributable to the real caller, not only the grant.

## Rotate / revoke a key

Edit `WORDSWORTH_API_KEYS` (drop or change the pair) and restart the API. There
is no per-key expiry yet.

## Not this (future)

This is a minimal shared-secret layer. Stronger schemes — OIDC/JWT via an
identity provider, or mTLS client certificates — are the heavier future option
when the straat grows a real multi-user UI; they are not implemented here.
