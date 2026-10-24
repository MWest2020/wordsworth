# Skip the key form for someone the identity provider already knows

## Why

After a Keycloak login, oauth2-proxy returns the browser to the URL it came
from. When that was `/console/login`, Mark sees the API-key form although he is
logged in (2026-10-24, auth proxy log 19:20:09). `/console/login` is exempt from
authentication, so the page cannot know the caller: today it always shows the
form.

The assertion does ride along on that request. The same `Identity.caller` the
middleware uses can read it, so the page can tell a person the provider has
verified from one it has not.

## What changes

- `GET /console/login` tries the identity verifier on the request. If it yields
  a verified email, the answer is a 303 to `/console`.
- With no assertion, or an invalid one, the form is shown as before.
- `?key=1` always shows the form, so the key route stays choosable
  (`docs/how-to/access-identity.md`, "Keeping the key route").
- The verifier is the one the middleware already holds; `build_router` is given
  it. No second verifier, no new configuration.
- Without an identity provider configured nothing changes.

Not changed: `POST /console/login`, the cookie, the rate limit, and the rule
that a presented key beats an injected assertion.

## Open questions

- Does oauth2-proxy pass its bearer token to `/console/login`, which is exempt
  from authentication, or only to routes it protects? The 2026-10-24 log shows
  the redirect back to that URL, not the request headers. Check with the real
  artefact behind the proxy before calling this done; if the token does not
  arrive, this change cannot fire and the proxy configuration is the fix.
- `GET /console/login?fout=…` (a form redisplayed with a reason): is it shown
  or redirected for an identified caller? Not decided; the requirement says
  nothing about it.
