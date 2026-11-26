# Tasks

Callers as in `api-corpus-read-gate`: `lezer` (on the read list), `uitgever`
(issuer, no reader), `derde` (logged in, on no list). Every refusal is
asserted as `derde`, and as `uitgever` where an issuer might be assumed to
pass.

## 1. The gate
- [x] `read_gate.GateFirst`: an `APIRoute` that runs the route's declared
      `Gate`s before FastAPI reads the body, and refuses to build on a route
      without one. Proved by: `tests/test_ingest_gate.py`
      (`test_gate_first_needs_a_declared_gate`).
- [x] `POST /ingest` declares `corpus_read` and uses `GateFirst`. Proved by:
      `tests/test_ingest_gate.py` — `derde` and `uitgever` get 403 and
      `Request.form` is never called; a reader gets past the gate and the form
      is read; no key is 401 with nothing read; auth off is open as before;
      with the gate declared but without `GateFirst` the form is read before
      the 403; with no gate `derde` reaches the route.

## 2. Nothing written, a reader unaffected
- [x] A refused upload writes nothing. Proved by:
      `tests/test_read_gate_writes.py::test_an_upload_is_refused_to_a_non_reader_and_writes_nothing`
      (seeded corpus, existing dossier, `derde` and `uitgever`: every table's
      row count and the object store unchanged) and
      `tests/test_ingest_gate.py::test_a_refused_upload_writes_nothing_and_a_reader_ingests`
      (empty database: no document, no audit record, no object; then `lezer`
      uploads the same PDF and it is indexed).
- [x] A reader and the scope-off case answer as on main. Proved by:
      `tests/test_read_gate_reader.py` (now 29 reader rows; `POST /ingest`
      still 422 without a file for `lezer`, and for `derde` with the list
      empty).

## 3. The inventory
- [x] `POST /ingest` recorded as `corpus-read` (declared). Proved by:
      `tests/test_route_inventory.py::test_the_walk_on_the_real_application`,
      `::test_removing_the_gate_from_ingest_fails` and
      `tests/test_route_refusal.py` (the row is refused as `derde`;
      `::test_the_refusal_suite_fails_when_ingest_loses_its_gate`).
- [x] `ungated_writes`: a writing route recorded as any-key or open fails,
      except `POST /console/login`. Proved by:
      `tests/test_route_inventory.py::test_a_write_route_recorded_as_unrefused_fails`
      and `::test_a_new_write_route_cannot_pass_as_any_key`.

## 4. Docs and rollout
- [x] `docs/how-to/api-auth.md`: ingest under the read list, refused before
      the upload is read; a connector's key has to be on the read list.
- [ ] Deployed, and the self-scan check `ww-ingest-gate` reports `held` in
      production; then moved from the private checks into `layer2.py`.
