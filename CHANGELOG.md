# Changelog

## [Unreleased]

### Added

- `python -m wordsworth.samenvatten`: samenvatten is nu een echt commando
  (`--dossier <uuid>`, herhaalbaar, of `--ontbrekend` voor alles wat nog geen
  samenvatting heeft), niet langer een script dat een cluster-Job meedroeg in
  zijn eigen `args`. Idempotent zoals `compute()` dat al was, met één regel
  uitvoer (de vijf tellingen plus de duur) en een exitcode ongelijk aan nul
  als er iets mislukte. Zie [samenvattingen](docs/how-to/samenvattingen.md).
- Identity from Keycloak (or any OIDC issuer), alongside Cloudflare Access.
  `access_identity.Verifier` now holds issuer, audience and JWKS address as
  plain fields; `Verifier.cloudflare(...)` and `Verifier.oidc(...)` are two
  ways to build the same verifier, not two code paths. The JWKS address for
  an OIDC issuer is resolved from its `.well-known/openid-configuration`
  document and cached. Configure via `WORDSWORTH_OIDC_ISSUER` and
  `WORDSWORTH_OIDC_AUDIENCE`; existing `WORDSWORTH_ACCESS_TEAM_DOMAIN` /
  `WORDSWORTH_ACCESS_AUD` configuration keeps working unchanged.
- The token may now also arrive as `Authorization: Bearer …` (what a reverse
  proxy such as oauth2-proxy sends), alongside the existing
  `cf-access-jwt-assertion` header. The readable
  `cf-access-authenticated-user-email` header is still never trusted.
- `WORDSWORTH_OIDC_JWKS_URL` sets the JWKS address directly, skipping OIDC
  discovery — for fetching an issuer's keys from a neighbour in the same
  cluster instead of round-tripping through the public internet. The issuer
  stays the configured public name either way, since that is what is checked
  against `iss`.

### Fixed

- OIDC discovery no longer runs at startup. An unreachable or slow issuer used
  to crash the worker before it could boot, taking down routes that have
  nothing to do with logging in; the fetch now happens on the first request
  that verifies a token, with the result cached, and a failure there yields no
  caller instead of a dead process. Every discovery/JWKS request now also
  sends a `User-Agent`: Cloudflare was answering the bare `urllib` one with a
  403 while `curl` from the same pod got a 200.
