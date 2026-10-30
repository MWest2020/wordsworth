# Tasks

- [ ] Key service: `POST /tokens/lookup {type, value}` returns the tokens for
      every active key version of the type, for an authorised caller only.
      Proved by: tests (authorised → tokens equal to what ingest produced for
      the same value; several key versions → all returned).
- [ ] Refusal: no grant/role/group for the type → 403 from the key service;
      wordsworth returns an empty result with the same shape as "no hits".
      Proved by: a test comparing the two responses field by field.
- [ ] A revoked group or an expired grant no longer translates. Proved by:
      tests.
- [ ] Normalisation equivalences: `Jansen`/`jansen`/` Jansen `, BSN with
      dots and without, a date in two notations yield the same tokens; an
      unknown type label is refused. Proved by: tests.
- [ ] A token from another domain or another type never matches: the same
      value under PERSON and ORGANIZATION, or in two domains, gives different
      tokens and no cross hits. Proved by: tests.
- [ ] The value never appears: not in wordsworth's or the key service's logs,
      not in the audit stream (only the token and the hit count), not in the
      index or the response. Proved by: a log- and audit-capture test with a
      sentinel value, and a search of the index for it.
- [ ] wordsworth `GET /search` accepts `value` + `type`, combined with
      `dossier` and `topic`, and runs a term query on the tokens (no vector
      part). Proved by: tests with a synthetic corpus.
- [ ] Console: a "zoek op persoon / organisatie / …" field on the search page,
      shown only to a caller who holds at least one type. Proved by: a
      template test.
- [ ] Docs: `docs/how-to/search-by-value.md` (what it does, who may, why the
      index holds no values, the open question on partial values),
      `docs/reference/architecture.md` (the route through the key service),
      `docs/how-to/key-service.md` (the lookup endpoint).
