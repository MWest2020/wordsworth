# Tasks

Tests use three callers with their own keys: `lezer` (on the corpus-read list),
`uitgever` (issuer, not a reader) and `derde` (logged in, on no list). Every
refusal is asserted as `derde`: the side that does not hold the key.

## 1. The gate
- [ ] `read_gate.py`: `corpus_read(labels)`, `grant_read(labels, issuer_labels,
      auth_enabled)`, `gate_of(route)`. Proved by: unit tests of both truth
      tables (on the list; off the list; no caller with the list set; empty
      list; issuer who is no reader) and of `gate_of` on a route with and
      without a gate.
- [ ] The refusal runs before validation and lookup. Proved by: a test on a
      gated route with a missing query parameter and with an unknown id, both
      403 with the same body.
- [ ] `api.py` loses `_guard_corpus_read` and its five body calls become the
      declared gate; `api.py` is not longer than 2009 lines and `read_gate.py`
      is under 200. Proved by: `wc -l` in the PR.

## 2. The routes
- [ ] The eleven API routes of design.md, "Corpus read, new", declare the gate
      (`GET /grants/{id}`: `grant-read`). Proved by: task 3.
- [ ] `GET` and `POST /console/combinations` call the console's read check
      before anything else. Proved by: a test as `derde`: 403 on both, no row
      in `declared_combinations`, and an existing declaration by `lezer` keeps
      its reason and `declared_by`; as `lezer`: stored, reach shown.
- [ ] A refused write leaves nothing. Proved by: tests as `derde` on
      `POST /documents/{id}/feedback` (no `detection_feedback` record; 403 for
      an existing and an unknown id), `POST /dossiers/{id}/topics` (topic rows
      unchanged) and `PATCH /topics/{id}` (name unchanged).
- [ ] `GET /grants/{id}`: 200 for `lezer` and for `uitgever`, 403 for `derde`
      on an existing and an unknown id, 404 for `lezer` on an unknown id.
      Proved by: tests.

## 3. The inventory
- [ ] `tests/route_inventory.py`: the 55 rows of design.md as data (method,
      path, policy, reason).
- [ ] Walk test: an application with every optional backend mounted; every
      route in `app.routes` (the console router included) has a row, every
      row has a route, every API row with policy `corpus-read` or `grant-read`
      declares that gate. Proved by: the test, and by showing in the PR that
      it fails (a) with a scratch route added, (b) with the gate removed from
      `/search`, (c) with a row for a route that does not exist.
- [ ] Refusal test, parametrised over every row, as `derde` with valid
      parameters and existing ids: 403 where the policy is `corpus-read`,
      `grant-read`, `grant-admin` or `delete`; neither 401 nor 403 where it is
      `any-key` or `open`. Proved by: the test; the PR lists the 55 statuses.
- [ ] Reader test, parametrised over the 27 `corpus-read` and `grant-read`
      rows, as `lezer`: the status it has on main (200, 201 or 303). Proved by:
      the test, and the existing suite unchanged and green.
- [ ] Scope off: the same rows as `derde` with an empty read list answer as on
      main. Proved by: the test.
- [ ] The write path is untouched: `POST /ingest` as `derde` is not refused.
      Proved by: the refusal test's `any-key` rows and the diff.

## 4. Docs
- [ ] `docs/how-to/api-auth.md`: what a key alone opens and what needs the
      read list; the route that does not exist goes; front matter. 
      `docs/how-to/local-demo.md`: what `gast` gets now. `docs/how-to/console.md`:
      the read list covers the API routes too. Proved by: docs-gates green.

## 5. Rollout
- [ ] 5.1 Before the deploy: print the labels, and only the labels, of the keys
      in `wordsworth-apikeys`, and the callers seen on the 13 routes if the
      access log names them. Report any label that is not on
      `WORDSWORTH_CORPUS_READ_LABELS`; add none. Proved by: the list in the
      deploy PR.
- [ ] 5.2 Local check in the demo harness, as a program and as a browser, with
      the printed keys. Proved by: the statuses pasted in the PR.
      1. `gast`: each of the 13 routes 403; `/health` and `/metrics` 200.
      2. `gast`: `GET /documents/<unknown>/state` 403, not 404.
      3. `mark`: each of the 13 routes as before.
      4. After `gast`'s refused writes: no feedback record, no renamed topic,
         no declared combination by `gast` in the database.
- [ ] 5.3 After the deploy, from outside, with a key or login that is no
      reader: `GET /search` 403; with the `cli` key: 200. Proved by: the two
      statuses in the deploy PR.
- [ ] 5.4 `share-recipient-read` (#439) and `console-share` (#440) are not
      deployed, and no non-reader gets a key or login, before 5.3 is done.
      Proved by: the order of the deploy PRs.
- [ ] `/security-review` on the diff, clean or every finding answered in the
      PR.
