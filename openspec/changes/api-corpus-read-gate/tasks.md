# Tasks

Tests use three callers with their own keys: `lezer` (on the corpus-read list,
no issuer), `uitgever` (issuer, not a reader) and `derde` (logged in, on no
list). Every refusal is asserted as `derde`, and where the gate is the
grant-issue right also as `lezer`: the side that does not hold the key.

## 1. The gate
- [ ] `read_gate.py`: `corpus_read(labels)`, `grant_read(labels, issuer_labels,
      auth_enabled)`, `grant_admin(issuer_labels, auth_enabled)`,
      `gate_of(route)`. Proved by: unit tests of the truth tables (on the
      list; off the list; no caller with the list set; empty list; issuer who
      is no reader; reader who is no issuer) and of `gate_of` on a route with
      and without a gate.
- [ ] The refusal runs before validation and lookup. Proved by: a test on a
      gated route with a missing query parameter, a malformed path id and an
      unknown id, all 403 with the same body; and a test that a body that is
      not JSON answers 422 with the same body for an existing and an unknown
      id, and changes nothing.
- [ ] `api.py` loses `_guard_corpus_read` and its five body calls become the
      declared gate; `api.py` is not longer than 2009 lines and `read_gate.py`
      is under 200. Proved by: `wc -l` in the PR.

## 2. The routes
- [ ] The twelve API routes of design.md, "Corpus read, new", declare the gate
      (`GET /grants/{id}`: `grant-read`). Proved by: task 3.
- [ ] `POST /reprocess`: 403 for `derde` with no body, with a list of existing
      ids and with an unknown id, the same body each time, and no document was
      re-de-identified (no new audit record); `lezer` runs it as before.
      Proved by: tests. `deploy/k8s/45-reprocess-job.yaml` says its key has to
      be a reader. Proved by: the diff.
- [ ] `POST /datasets/pseudonymize` declares `grant-admin`. Proved by: tests
      as `derde` and as `lezer`: 403, no token in the answer, and no document
      row, no `dataset_pseudonymize` audit record and no mapping row written;
      as `uitgever`: 200 and the CSV as before.
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
      path, policy, reason). `tests/test_route_inventory.py`: the tests. Each
      file under 200 lines; split the data by API and console if it is not.
      Proved by: `wc -l` in the PR.
- [ ] Walk test: every route has a row, every row has a route, every API row
      with a declared policy declares that gate. Proved by: the test.
- [ ] The walk reaches everything. Proved by, each shown failing in the PR
      with a scratch change and passing without it:
      (a) a new optional `create_app` parameter the fixture does not pass
          (checked against `inspect.signature(create_app)`; a parameter that
          mounts no route is named in a list with its reason);
      (b) the count of route decorators and `app.mount` calls in `src/`
          differs from the rows minus the framework's four;
      (c) a route on a second included router, and a route inside a mounted
          application (the collector descends into every
          `_IncludedRouter.original_router.routes` and every `Mount`);
      (d) an object of an unknown type in a route list;
      (e) a `WebSocketRoute`;
      (f) a scratch route added without a row; the gate removed from
          `/search`; a row for a route that does not exist.
- [ ] `HEAD` is folded into the `GET` row of the same route object and
      requested by the refusal test with the same expectation; a `HEAD` route
      without `GET` needs its own row. Proved by: a test on the collector with
      one route of each kind.
- [ ] Refusal test, parametrised over every row, as `derde` with valid
      parameters and existing ids: 403 where the policy is `corpus-read`,
      `grant-read`, `grant-admin` or `delete`; neither 401 nor 403 where it is
      `any-key` or `open`. Proved by: the test; the PR lists the 55 statuses.
- [ ] Reader test, parametrised over the 28 `corpus-read` and `grant-read`
      rows, as `lezer`: the status it has on main. Proved by: the test, and
      the existing suite unchanged and green.
- [ ] Scope off: the same rows as `derde` with an empty read list answer as on
      main. Proved by: the test.
- [ ] `POST /ingest` is untouched: as `derde` it is not refused. Proved by:
      the refusal test's `any-key` row and the diff.

## 4. Who the caller is, and an empty list
- [ ] The OIDC verifier refuses a token whose `email_verified` is not `true`.
      Proved by: tests in the style of `tests/test_access_identity*.py` with a
      signed token: `true` gives the address; `false`, absent, the string
      `"true"` and `1` give no caller; the same request with a valid key is
      that key's caller; a Cloudflare Access assertion without the claim is
      accepted as before.
- [ ] A startup warning when authentication and a grant store are on and the
      read list is empty. Proved by: a log-capture test for the four
      combinations (warned once; silent with a list; silent without
      authentication; silent without a grant store), and a test that the
      answers do not change.

## 5. Docs
- [ ] `docs/how-to/api-auth.md`: what a key alone opens, what needs the read
      list, what needs the issuer list; the route that does not exist goes;
      front matter. `docs/how-to/local-demo.md`: what `gast` gets now.
      `docs/how-to/console.md`: the read list covers the API routes too, and
      what an empty list means. `docs/how-to/dataset-pseudonymisation.md`: who
      may run a dataset and why. `docs/how-to/access-identity.md`:
      `email_verified`. Proved by: docs-gates green.

## 6. Rollout
- [ ] 6.1 Before the deploy, read and report, changing nothing:
      - `WORDSWORTH_CORPUS_READ_LABELS` in the cluster is not empty;
      - the labels, and only the labels, of the keys in `wordsworth-apikeys`,
        and any that is not on the read list;
      - the callers seen on the 15 routes, if the access log names them;
      - in realm `westerweel`: whether self-registration is on, whether users
        may edit their own address, whether verify-email is on, and that the
        two listed addresses are marked verified.
      Proved by: the list in the deploy PR. An address on the list that is
      not verified stops the deploy.
- [ ] 6.2 Local check in the demo harness, as a program and as a browser, with
      the printed keys. Proved by: the statuses pasted in the PR.
      1. `gast`: each of the 15 routes 403; `/health` and `/metrics` 200.
      2. `gast`: `GET /documents/<unknown>/state` 403, not 404.
      3. `mark`: each of the 15 routes as before.
      4. After `gast`'s refused writes: no feedback record, no renamed topic,
         no declared combination by `gast` in the database.
      (The harness refuses `/reprocess` and `/datasets/…` for every caller
      before any route runs, so those two are proved by task 2 only.)
- [ ] 6.3 After the deploy, from outside, with a key or login that is no
      reader: `GET /search` 403; with the `cli` key: 200; through Keycloak as
      Mark: the console opens. Proved by: the statuses in the deploy PR.
- [ ] 6.4 `share-recipient-read` (#439) and `console-share` (#440) are not
      deployed, and no non-reader gets a key or login, before 6.1 and 6.3 are
      done. They may be built before. Proved by: the order of the deploy PRs.
- [ ] `/security-review` on the diff, clean or every finding answered in the
      PR.
