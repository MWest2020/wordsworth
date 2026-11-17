# Tasks

## State at stop (for the builder)

The 2026-11-17 15:20 builder attempt (#492) ran out of budget with the work
done but not verified. Written: the `Role.active` fix, the group → role
mapping, the API and console routes, the docs and the tests. NOT re-verified:
the full-suite run. Check what is on the branch against the tasks below before
writing anything again; do not rewrite what already passes its task's proof.

## How to build

- Build in task order, one commit after each task.
- Per task run only the targeted tests that prove it. Run the full suite once,
  at the end.
- Every new API or console route is added to the route inventory registry in
  the same step as the route, with its test: a row in `tests/route_rows.py`
  (read by `tests/route_inventory.py`). A route without a row fails that test.

## Tasks

- [ ] 0. Before any change: run the full suite on `main` and record the 3
      failures that exist there (test names and the one-line cause each) in the
      PR description, so they are not diagnosed again mid-build. Use a private
      test database (`WORDSWORTH_TEST_DATABASE_URL`), and note which tests
      skipped. Proved by: the recorded list; at the end the full suite shows
      those 3 and no others.
- [ ] 1. First, before adding groups: make `grants.caller_holds_role` respect
      `Role.active` (an inactive or unknown role is held by nobody). Proved by:
      a test where a grant naming a switched-off `beheerder` no longer opens the
      delete gate, and opens it again once the role is switched back on.
- [ ] 2. `groups` read from the verified assertion only; a `groups` header or an
      unsigned claim is ignored; an expired assertion yields no groups (and no
      caller). Proved by: tests with a forged header, an unsigned token and an
      expired token.
- [ ] 3. API-key and console-cookie callers carry no groups, also when a valid
      assertion with groups rides along. Proved by: two tests (key, cookie) where
      a group-only `beheerder` is refused the delete gate.
- [ ] 4. Group → role mapping API and console page, behind the same gate as
      `/roles`; `PUT` for an unknown role is 404. The new routes get their
      route-inventory rows in this step. Proved by: tests (an issuer label may,
      others are refused; unknown role refused) and `tests/test_route_inventory.py`
      passing with the new rows.
- [ ] 5. Extend to `caller_holds_role(session, caller, role, groups=())`, with the
      same inactive-role rule for the group path, and have the API delete gate
      pass the request's groups (`delete_cli` passes none). Proved by: tests — a
      delete by a group-held `beheerder` succeeds, is refused once the group
      leaves the assertion, and is refused while the role is switched off.
- [ ] 6. A group-held role never authorises a reveal; `grants.authorize` is
      unchanged. Proved by: tests — a caller in a group mapped to `beheerder`
      presenting an unscoped grant naming `beheerder` issued to someone else gets
      403 and no text; a caller in a group mapped to R with no grant naming them
      cannot reveal; the same caller with a personal grant naming R reveals, and
      the `deanonymize` record names them.
- [ ] 7. Mapping changes are audited in the key-lifecycle stream with the person
      as actor; a delete opened by a group-held role records the person as actor,
      never the group. Proved by: tests.
- [ ] 8. Docs: `docs/how-to/roles.md` (groups; reveal still needs a personal grant;
      switched-off role opens nothing; "no groups; use a personal grant or label"
      for cookie and key), `docs/how-to/access-identity.md` (the Keycloak mapper
      to configure, and the same cookie/key note),
      `docs/how-to/deleting-documents.md` (the delete gate via a group;
      switched-off roles). Proved by: the three pages name each point above
      (checked by reading them against this list).
- [ ] 9. Last: run the full suite once, with `uv run ruff check src/ tests/`.
      Proved by: only the 3 failures recorded in task 0 remain, and the route
      inventory test passes.
