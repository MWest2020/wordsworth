# search-by-value

## Why

A person with the right to see a type of personal data (say PERSON) wants
every document about one real value: "alle documenten over Jan Jansen".
Today search only takes words that are in the pseudonymised text, so a real
name finds nothing. The answer must not put real values into the index, not
even encrypted: the index stays a component that holds no clear value and no
key (ADR-0009's threat table), and ciphertext is not searchable anyway.

Tokens make it possible without that: a token is a keyed HMAC over the
normalised value (`pseudonymization`: "Tokens are derived from the normalised
value"), so the same value always yields the same token. The key service can
compute the token for a typed value, and the search runs on the token.

## What changes

- **The key service translates a value to its token**, for one type, for an
  authorised caller only: the caller must hold a grant or a role (directly or
  through a group) that allows that type. It normalises the value with the
  same versioned profile ingest uses, derives the token under the type's
  current key and domain, and returns only the token.
- **Refusal is indistinguishable from "no hits"** to the end user: wordsworth
  returns an empty result for an unauthorised value search, with the same
  shape and timing class as a search that matched nothing; the API caller that
  lacks the right gets 403 from the key service, and wordsworth does not pass
  on whether the value exists.
- **wordsworth searches on the token**: `GET /search?q=…&value=…&type=PERSON`
  (or the console's "zoek op persoon" field) asks the key service for the
  token and runs the existing scoped search with it; the result list is the
  ordinary pseudonymised one.
- **Every value search is audited** in the key service's own audit stream:
  who, which type, the token (never the value, never a hash of the raw value),
  how many documents matched, when.
- **Exact values only**, after normalisation (case, spaces, Unicode form, date
  formats, BSN separators). Searching on part of a name is out of scope.

## Out of scope (open question)

Partial-value search (only "Jansen", or "J. Jansen") would need a blind index
of name parts: keyed hashes of each part, stored in the index. It leaks how
often each part occurs and links documents that share a common surname. Left
as an open question for Mark; recorded in `docs/how-to/search-by-value.md`.

## Depends on

`key-service-cutover` (the key service holds the keys and the authorisation
facts). Built before `key-export-escrow`.
