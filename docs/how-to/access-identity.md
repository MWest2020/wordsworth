---
status: current
last_reviewed: 2026-09-20
---

# Logging in as a person instead of a keyring

With an identity provider in front of `/console`, a caller can be an
**identity** — an email address — rather than a shared API key. The audit
trail then answers "who looked", not "which key was used". Cloudflare Access
and Keycloak are both OIDC issuers underneath, checked the same way; there is
one verifier, not one per provider.

## Turning it on — Keycloak (or any other OIDC issuer)

```bash
export WORDSWORTH_OIDC_ISSUER=https://iam.westerweel.work/realms/westerweel
export WORDSWORTH_OIDC_AUDIENCE=<the client id registered for wordsworth>
```

Both are required, checked without a default. Het JWKS-adres komt standaard uit
het eigen discovery-document van de uitgever
(`<issuer>/.well-known/openid-configuration`, veld `jwks_uri`), één keer
opgehaald en daarna gecached.

**Dat ophalen gebeurt bij het eerste verzoek dat een token controleert, niet bij
het opstarten.** Een uitgever die hapert hoort geen applicatie neer te halen —
en zeker niet de routes die niets met inloggen te maken hebben. Lukt het
ophalen niet, dan levert dat "geen caller" op (fail-closed: een verzoek zonder
vastgestelde identiteit), niet een dode pod.

Op 2026-09-20 was dat andersom en kostte het de api-pod zijn start:

```
DiscoveryError: discovery unreachable for issuer '…': HTTPError
[1] [ERROR] Reason: Worker failed to boot.
```

### De sleutels intern ophalen

```bash
export WORDSWORTH_OIDC_JWKS_URL=http://keycloak.keycloak.svc.cluster.local:8080/realms/westerweel/protocol/openid-connect/certs
```

Staat dit adres gezet, dan wordt het discovery-document **niet** opgehaald en
gaat het verkeer rechtstreeks daarheen. De **uitgever blijft de publieke naam**:
dat is wat er in `iss` staat en dus wat gecontroleerd wordt. Adres en identiteit
zijn twee dingen, en ze door elkaar halen betekent dat een interne URL in de
tokencontrole belandt.

Waarom dit uitmaakt: de uitgever is publiek bereikbaar, dus zonder dit adres
gaat de pod via Cloudflare en de eigen tunnel terug het cluster in — twee extra
partijen voor iets wat één netwerkhop verderop staat. Cloudflare weigerde die
aanvraag bovendien met **403**, omdat `urllib` geen User-Agent stuurde. Dezelfde
URL gaf vanaf dezelfde pod 200 zodra er wél een User-Agent bij zat; die stuurt
wordsworth nu altijd mee, zodat ook de publieke route werkt voor wie hem toch
gebruikt.

Wordsworth itself never speaks the OIDC login dance (authorization code,
redirects, session cookies) — a reverse proxy in front of it does that and
forwards the resulting token as `Authorization: Bearer <token>`. In the
homelab that proxy is oauth2-proxy, configured against the Keycloak realm at
`iam.westerweel.work` (homelab-repo, `cluster-config/infra/keycloak/` for the
realm, oauth2-proxy's own manifest for the proxy itself). That rollout is
out of scope here — this document only covers what wordsworth-api needs once
a token arrives.

## Turning it on — Cloudflare Access

```bash
export WORDSWORTH_ACCESS_TEAM_DOMAIN=raspy-wood-e123.cloudflareaccess.com
export WORDSWORTH_ACCESS_AUD=<the application's AUD tag>
```

Both are required. One without the other yields no verifier and no identity —
fail-closed, never a warning and an accepted header. If both an OIDC issuer
and a Cloudflare team domain are set, the OIDC issuer wins; in practice an
installation configures exactly one.

**Keep at least one API key.** Not for access — the identity handles that — but
because dropping them all used to switch off the recipient binding and the
issuer scope, and this document actively pointed you at that configuration.
Fixed on 2026-09-18: "is there a caller to decide about" now follows the same
condition the middleware mounts on. The advice stands anyway: a key is the way
back in when the provider is unreachable. Without either, nothing
changes: the API key stays the way in, exactly as before. **A screen that only
opens behind one vendor is not sovereign software**, so this is opt-in and stays
that way.

## The rule this rests on

> The header is never a source. The signature is.

Cloudflare Access puts two things on a request: `Cf-Access-Authenticated-User-Email`,
which is readable, and `Cf-Access-Jwt-Assertion`, which is signed. oauth2-proxy (for
Keycloak) sends its token as `Authorization: Bearer …` instead. They arrive together
with the readable header and look equally convincing, and only the signed one cannot
be forged.

Trusting the header would turn every path that does **not** pass the provider
into a way to claim any identity — and those paths exist here: the tailnet route
(`wordsworth-api.tail8f7877.ts.net`) reaches the same origin without Access.
Verifying the signature makes that harmless by construction. No valid assertion,
no identity, fall back to the key.

Checked on every assertion: RS256 only (refusing anything else closes the
`alg: none` family), the signature against the team's published keys, the
audience (an assertion for another application of the same organisation is not
access to this one), the issuer, and the expiry.

The keys are cached for fifteen minutes because the provider rotates them. A
failed refresh **keeps the keys we have** — an assertion we can still verify is
not less trustworthy because a fetch timed out, and locking everyone out over a
network hiccup is the wrong failure. A key never seen is refused either way.

## Keeping the key route

**A credential you send beats one that rides along.** An identity provider
injects its assertion on every request through it, so with the identity first a
person behind that provider could never be anything else — and the way back to a
key would exist only on routes that bypass the provider, which may be exactly the
routes they cannot reach.

So: a valid `X-API-Key` (or the console cookie) wins; the assertion applies when
no key is presented. Not weaker — both come from the same configured sets, and a
forged header carries no valid key any more than a forged assertion carries a
valid signature.

`/console/login` stays reachable from behind the provider, and `/console/logout`
clears the cookie and hands the identity back. That is the switch, in both
directions.

That form is the one path that is reachable without a key **and** answers
differently for a right and a wrong one. It is rate-limited harder than anything
else (five attempts, then one per ten seconds): every request there is a guess.
An earlier comment claimed it already was, and it was not — twelve attempts gave
twelve 401s and no 429.

Since 2026-09-23 that bucket lives in Postgres (`rate_limit_pg.py`), shared by
every api replica. With per-process buckets two replicas would have allowed ten
attempts instead of five, and the limit would have doubled again with every
replica added.

The cookie is marked `Secure`. Its value IS the API key and `Path=/` makes it
valid for every endpoint, so it has no business travelling over plain http.

## Before you switch: what goes quiet

A grant names who may reveal, and the caller must BE that recipient. Today a
recipient is a key label (`console`, `cli`). The moment callers are identities,
nobody is called `console` and every grant issued to a label authorises nobody.

```bash
wordsworth-access-preflight
```

Reports them and changes nothing. They do not become dangerous, they become
inert — and an inert grant that still reads as "active" is a lie in the table.
The recipient binding taught this the expensive way: four grants went quiet in
August and it was noticed afterwards, by looking.

Re-issuing them to an identity is the administrator's decision. Moving an
authorisation from a shared key to a person is a judgement about who should hold
it, which is exactly what a machine should not decide on its own.
