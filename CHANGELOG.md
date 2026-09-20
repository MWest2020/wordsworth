# Changelog

## [Unreleased]

### Added

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
