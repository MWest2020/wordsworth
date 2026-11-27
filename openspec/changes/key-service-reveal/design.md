# Design

## Who decides what

| Fact | Decided by | Read from |
|---|---|---|
| the calling service is wordsworth | key service | service token (skeleton) |
| who the person is | key service | the signed assertion in the request body |
| the grant: exists, status, expiry, recipient, scope, global gate, role | key service | its `grants`, `roles` |
| the document's domain, and whether the grant covers it | key service | its `known_documents` |
| the credential gate (VC), where configured | key service | the `vc` field in the request body |
| the document is deleted (for a covered caller) | key service (tombstone) and wordsworth (its state), either answers 410 | `known_documents.deleted_at`; wordsworth's audit state |
| superseded, no box map, not yet de-identified | wordsworth | its own tables, and only after the key service said "covered" |
| which tokens are the document's | key service | its `document_tokens` |
| which tokens wordsworth wants shown | wordsworth | the tokens in the document's current text, sent in the request |
| what is revealed | key service | requested ∩ registered ∩ authorised type ∩ mapping present ∩ key resolves |

Nothing wordsworth sends can widen a reveal: the assertion is verified, the
grant and the domain are the service's rows, the tokens are intersected with
the registry and the types with the authorisation.

## Identity

The person's assertion is the raw JWT wordsworth received from Keycloak (the
bearer behind oauth2-proxy), forwarded in the body field `assertion`. The
service accepts one issuer, `KEYSERVICE_OIDC_ISSUER`; in this installation
that is Keycloak (realm `westerweel`). Cloudflare Access assertions are not
accepted for reveal: an Access session lasts up to 24 hours, and that would be
the replay window (ADR-0009 residuals).

Verification wraps wordsworth's code rather than changing it:
`access_identity.Verifier.oidc(issuer, audience)` (with
`KEYSERVICE_OIDC_JWKS_URL` when discovery must be bypassed, as in the
cluster) and `access_identity.email_from` check signature, algorithm, issuer,
audience, `exp`, a usable `email` and `email_verified: true`. `email_from`
does not check `nbf`; the service's wrapper then reads the payload of the
token it has just verified and refuses one whose `nbf` lies in the future.
wordsworth's `Verifier` is not changed. The caller label is the verified email,
the label wordsworth uses, so grant recipients keep matching. Groups in the
assertion are not used by a reveal (the default of #495: a group role never
authorises a reveal).

Audience: the service accepts only tokens whose `aud` holds
`KEYSERVICE_OIDC_AUDIENCE`, recommended `wordsworth-keyservice`. What that
separates depends on how Keycloak adds it, and the how-to says so plainly:

- with an audience mapper on wordsworth's client, every token wordsworth
  receives carries it. The audience then keeps out tokens issued to other
  clients of the realm, and nothing more: any live wordsworth session token
  is accepted by the service (it still needs a valid signature and a grant);
- with an optional client scope requested only when a person reveals, only
  tokens obtained for a reveal carry it, so a token wordsworth could replay
  exists only around a reveal. That needs a step-up request in the console
  and is the cutover's choice, not built here.

The service checks the audience either way; this change does not decide the
Keycloak side.

The service has no "authentication off" mode for reveal: the recipient is
always checked (`authorize(..., auth_enabled=True)`). Without
`KEYSERVICE_OIDC_ISSUER` and `KEYSERVICE_OIDC_AUDIENCE` both reveal routes
answer 503 `{"detail": "reveal not configured"}` before reading anything.

The service token (skeleton) and the assertion are two separate credentials:
the token says which service calls (`service_caller`), the assertion which
person (`caller`). A valid token with no valid assertion reveals nothing; a
valid assertion without a token is refused at the door.

The decision parameters that are configuration in wordsworth come from the
service's settings: `KEYSERVICE_ALLOW_GLOBAL_GRANTS` (default false), the
global role `roles.ADMIN` (ensured by `wordsworth-keyservice-init`, as
`bootstrap.ensure_admin_role` does today), and `KEYSERVICE_VC_PUBLIC_KEY`,
`KEYSERVICE_VC_EXPECTED_VCT`, `KEYSERVICE_VC_EXPECTED_ISSUER`,
`KEYSERVICE_VC_REQUIRED`. `grants.authorize`, `grants.permitted_types` and
`vc.apply_vc_gate` are reused unchanged; role resolution has the semantics of
`roles.resolve` (an inactive role permits nothing) over the service's `roles`
table.

## Why two calls

wordsworth must not read a document row before the grant is decided (the
existence oracle of #487), and the service must not decrypt values for a
request wordsworth then answers 409 or 410 (an audit record of a reveal that
never reached anyone). One call cannot do both: the service does not know
supersession, box maps or de-identification, and wordsworth may not look
before the grant is judged. So: `decide` (judge, decrypt nothing), wordsworth
checks its own facts, then `reveal` (judge again, decrypt). `reveal` trusts
nothing from `decide`: there is no decision id and no state between the calls.

## Requests

Both endpoints take JSON:

```json
{
  "document_id": "UUID",
  "grant_id": "string",
  "types": ["PERSON", "..."],
  "assertion": "the raw JWT",
  "vc": "the raw SD-JWT VC, or null"
}
```

`types` null or absent means "everything the grant permits". `/v1/reveal`
adds `"tokens": [...]` (the distinct tokens in the document's current text,
each matching the token shape) and `"view": "text" | "pdf"`. At most
`KEYSERVICE_REVEAL_MAX_TOKENS` tokens (default 10 000); more is answered 413
`{"detail": "too many tokens (limit N)"}` before anything else is checked
except the service token. One reveal is one call and one audit record, so
wordsworth does not split a request: a document with more distinct tokens than
the limit cannot be revealed until the limit is raised, and wordsworth tells a
covered caller so (409, below). The how-to names the limit and how to raise
it.

## Order inside the service (both endpoints)

1. Service token, else 401. Body, else 422.
2. Reveal configured, else 503 `reveal not configured`.
3. Verify the assertion, else 401 `{"detail": "assertion not accepted"}`, the
   same body for every reason (missing, forged, expired, not yet valid, wrong
   issuer, foreign audience). Nothing is read from the database.
4. Read the grant; unknown → 403 refusal. Compute the permitted types and run
   `authorize()` on the grant's own domain with the verified label as caller;
   nothing permitted → 403 refusal. Up to here no statement reads
   `known_documents`, `document_tokens`, `pii_mappings` or `key_vault`.
5. Read `known_documents` for the id; absent → 403 refusal. `authorize()`
   again with the recorded domain; nothing → 403 refusal.
6. The VC gate (pure); rejected → 403 `{"detail": "vc rejected: <reason>"}`.
7. Tombstoned → 410 `{"detail": "document deleted"}`.
8. `authorized` = `authorize()` over the requested types (or the permitted
   ones), intersected with the VC gate's types; `withheld` = requested
   (upper-cased) minus `authorized`.

The 403 refusal is exactly `{"detail": "grant not applicable"}`, the constant
`reveal_gate.REFUSAL` uses today.

`/v1/reveal/decide` then answers 200
`{"document_id", "authorized_types": [...], "withheld_types": [...]}`. It
writes no record.

`/v1/reveal` continues:

9. For each distinct requested token, in sorted order: reveal it only when it
   is registered for this document, its type is in `authorized`, its mapping
   exists and its key resolves (a missing key version leaves the token as it
   is, as `_reveal` does today). Transit unreachable or sealed → 503
   `{"detail": "key service unavailable"}`, no record.
10. Append one `access_audit` record, `event = "reveal"`: document,
    `service_caller`, `caller`, `actor` (the grant's recipient), `grant_id`,
    `role` and `global_by_role` where the grant has a role, `view`,
    `requested_types` (a list, empty when all were asked), `requested_all`,
    `authorized_types`, `pseudonyms` (the resolved tokens), `types`,
    `categories`, and the VC gate's audit fields. No value.
11. Answer 200:

```json
{
  "document_id": "UUID",
  "authorized_types": ["..."],
  "withheld_types": ["..."],
  "resolved_tokens": ["..."],
  "resolved_types": ["..."],
  "values": {"[PERSON:1a2b3c4d]": "clear value"},
  "audit": {"seq": 0, "hash": "...", "actor": "...", "grant_id": "...",
            "caller": "...", "role": "...", "global_by_role": true}
}
```

`values` is present only for `view = "text"`; the PDF view gets no value, as
the PDF is drawn from the original page. `resolved_types` is copied from the
record written in step 10, not derived again. A requested token that was not
revealed is not named, so the answer does not say whether it exists
elsewhere.

A refusal (steps 3 to 7) writes no record, and no log line names its cause, the
document's existence or its state: the reveal-api promise "a refused reveal
leaves no trace of its cause" holds in the service too.

## Status codes, key service

| Case | `decide` | `reveal` |
|---|---|---|
| no or unknown service token | 401 `invalid or missing service token` | same |
| malformed body | 422 | same |
| more tokens than the limit | (no tokens) | 413 `too many tokens (limit N)` |
| identity not configured | 503 `reveal not configured` | same |
| assertion missing, forged, expired, not yet valid, wrong issuer, foreign audience | 401 `assertion not accepted` | same |
| unknown grant, revoked, expired, other recipient, other document, global grant not allowed, inactive role, unknown document, other domain | 403 `grant not applicable` | same |
| covered, VC rejected | 403 `vc rejected: <reason>` | same |
| covered, document tombstoned | 410 `document deleted` | same |
| covered, Transit unreachable | (not reached) | 503 `key service unavailable` |
| covered | 200, decision | 200, values or tokens |

The service never answers 404 or 409 on these routes.

## Order on wordsworth's side (built in `key-service-cutover`)

For `POST /documents/{id}/reveal` and `.../reveal.pdf` with the service
driver:

1. wordsworth's own authentication (401) and validation (422), as today.
2. If the caller has no Keycloak assertion to forward (an API key, the
   console cookie, authentication off, or only a Cloudflare Access
   assertion): 403 `{"detail": "reveal needs a signed
   identity"}`, before any read and the same whatever the grant or document.
   This is the default of a question to Mark (#524).
3. Call `/v1/reveal/decide`. No row about the document is read before its
   answer.
4. Only after a 200: read the state (none → 403 refusal; deleted → 410),
   supersession (409 naming the survivor), for the PDF the box map (409), the
   anonymized text (none → 409), in that order: today's order and bodies.
   A document registered in wordsworth that the service has not seen yet (no
   `seal` or `pseudonymise` reached it, for instance because the seal failed)
   never gets here: the service answered the uniform 403 in step 3, also to a
   caller whose grant would cover it. Today such a caller gets 409 "not yet
   de-identified"; afterwards 403. Nothing can be revealed from such a
   document either way, and the 403 tells nobody that it exists.
5. Call `/v1/reveal` with the distinct tokens of the current text and the
   view.
6. Text: put each returned value in place of its token; every other token
   stays. PDF: draw the resolved tokens in clear from the original (opened
   with purpose `reveal_pdf`). Append wordsworth's `deanonymize` record to the
   document chain with the service's audit fields and
   `key_service_audit: {seq, hash}`; `resolved_types` in the response is the
   service's.

Mapping the service's answers, for both calls:

| Service answer | wordsworth answers |
|---|---|
| 200 | continues |
| 403 `grant not applicable` | 403 `grant not applicable` |
| 403 `vc rejected: …` | the same |
| 410 | 410 `document deleted` |
| 413 (`reveal` only) | 409 `{"detail": "document has more distinct tokens than one reveal allows (limit N)"}` |
| 401 `assertion not accepted` | 401 `assertion not accepted` |
| anything else (401 service token, 422, 503, 5xx, timeout, refused connection) | 503 `{"detail": "reveal unavailable"}`; never a fallback to an in-process reveal |

A grant revoked, or a document deleted, between the two calls makes the second
call answer 403 or 410, which wordsworth passes on; the caller learns nothing
it would not have learned a moment later.

## Why the existence oracle stays closed

Every cause a caller is not covered for (unknown grant, unknown document,
another domain, another recipient, …) is one 403 with one body from the
service, passed on unchanged; wordsworth reads no document row before the
service says "covered", so neither its answer nor its timing depends on the
document. The service decides "unknown document" and "document outside the
scope" with the same reads (grant, then `known_documents`), as `reveal_gate`
does today. 410 and 409 reach only covered callers, in today's order. A
document the service has not seen is, to everyone, the uniform 403. A grant
scoped to a document is deleted with it (`key-service-delete`), so its former
recipient gets 403, not 410. An outage (503) happens before any document read
and does not depend on the document either.
