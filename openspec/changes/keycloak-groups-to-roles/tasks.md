# Tasks

- [x] First, before adding groups: make `grants.caller_holds_role` respect
      `Role.active` (an inactive or unknown role is held by nobody). Proved by:
      a test where a grant naming a switched-off `beheerder` no longer opens the
      delete gate, and opens it again once the role is switched back on.
- [x] `groups` read from the verified assertion only; a `groups` header or an
      unsigned claim is ignored; an expired assertion yields no groups (and no
      caller). Proved by: tests with a forged header, an unsigned token and an
      expired token.
- [x] API-key and console-cookie callers carry no groups, also when a valid
      assertion with groups rides along. Proved by: two tests (key, cookie) where
      a group-only `beheerder` is refused the delete gate.
- [x] Group → role mapping API and console page, behind the same gate as
      `/roles`; `PUT` for an unknown role is 404. Proved by: tests (an issuer
      label may, others are refused; unknown role refused).
- [x] Extend to `caller_holds_role(session, caller, role, groups=())`, with the
      same inactive-role rule for the group path, and have the API delete gate
      pass the request's groups (`delete_cli` passes none). Proved by: tests — a
      delete by a group-held `beheerder` succeeds, is refused once the group
      leaves the assertion, and is refused while the role is switched off.
- [x] A group-held role never authorises a reveal; `grants.authorize` is
      unchanged. Proved by: tests — a caller in a group mapped to `beheerder`
      presenting an unscoped grant naming `beheerder` issued to someone else gets
      403 and no text; a caller in a group mapped to R with no grant naming them
      cannot reveal; the same caller with a personal grant naming R reveals, and
      the `deanonymize` record names them.
- [x] Mapping changes are audited in the key-lifecycle stream with the person
      as actor; a delete opened by a group-held role records the person as actor,
      never the group. Proved by: tests.
- [x] Docs: `docs/how-to/roles.md` (groups; reveal still needs a personal grant;
      switched-off role opens nothing; "no groups; use a personal grant or label"
      for cookie and key), `docs/how-to/access-identity.md` (the Keycloak mapper
      to configure, and the same cookie/key note),
      `docs/how-to/deleting-documents.md` (the delete gate via a group;
      switched-off roles).
