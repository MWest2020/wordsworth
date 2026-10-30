# search-by-value — design

## Flow

1. The console or an API client calls wordsworth `GET /search` with `value`
   and `type` (and the usual `dossier`, `topic`).
2. wordsworth calls the key service `POST /tokens/lookup {type, value}` with
   the caller's verified identity (the same token-forwarding as reveal).
3. The key service checks the right (grant/role/group for `type`), normalises
   `value` with the ingest profile of the current `norm_version`, derives
   `HMAC(key(domain, type), label + ":" + normalised)` for EVERY active key
   version of that type (a corpus pseudonymised under an older key version
   still matches), audits, and answers `{tokens:[…]}` or 403.
4. wordsworth runs the existing search with the tokens as exact terms (BM25
   term query on the pseudonymised text field, OR over the versions), scoped
   as asked, and returns the normal result list. No vector query: a token
   carries no meaning for embeddings.

## Why the refusal looks like "no hits"

A distinguishable refusal would answer "does this person occur anywhere?" for
someone without the right to know. wordsworth maps the key service's 403 to an
empty result with the same response shape; the console shows "geen
resultaten". The 403 itself is audited in the key service.

## What never happens

- The value is not logged by wordsworth or the key service (request logging
  for this route drops the body), not written to the audit (token only), not
  sent to the search index (only tokens), not echoed in the response.
- No cache of value→token outside the key service's process memory.

## Normalisation

The same table-driven `normalize(label, value)` that ingest uses, at the same
`norm_version`; a value is accepted only for a known type label.

## Open question: partial values

A blind index of name parts (keyed hashes of each part, indexed) would allow
"Jansen" to find "Jan Jansen" and "P. Jansen", at the price of frequency
leakage and cross-document linking. Not built; Mark decides.
