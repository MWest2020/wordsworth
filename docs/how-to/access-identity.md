---
status: current
last_reviewed: 2026-09-18
---

# Logging in as a person instead of a keyring

With Cloudflare Access in front of `/console`, a caller can be an **identity** —
an email address — rather than a shared API key. The audit trail then answers
"who looked", not "which key was used".

## Turning it on

```bash
export WORDSWORTH_ACCESS_TEAM_DOMAIN=raspy-wood-e123.cloudflareaccess.com
export WORDSWORTH_ACCESS_AUD=<the application's AUD tag>
```

Both are required. One without the other yields no verifier and no identity —
fail-closed, never a warning and an accepted header. Without either, nothing
changes: the API key stays the way in, exactly as before. **A screen that only
opens behind one vendor is not sovereign software**, so this is opt-in and stays
that way.

## The rule this rests on

> The header is never a source. The signature is.

Access puts two things on a request: `Cf-Access-Authenticated-User-Email`, which
is readable, and `Cf-Access-Jwt-Assertion`, which is signed. They arrive together
and look equally convincing, and only one of them cannot be forged.

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
