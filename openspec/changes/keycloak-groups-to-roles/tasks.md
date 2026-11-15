# Tasks

- [ ] Make `grants.caller_holds_role` respect `Role.active` before it is
      extended. Proved by: a test where a grant naming a switched-off
      `beheerder` no longer opens the delete gate.
- [ ] `groups` read from the verified assertion only; a `groups` header or an
      unsigned claim is ignored. Proved by: tests with a forged header and an
      unsigned token.
- [ ] Group → role mapping API and console page, gated like roles. Proved by:
      tests (beheerder may, others are refused).
- [ ] Group-held role passes a role-checked action (delete gate); refused once
      the group is removed from the assertion (revoked group); refused for a
      group mapped to a switched-off role (same inactive-role behaviour as the
      first task). Proved by: three tests.
- [ ] A group-held role never opens a reveal: a reveal still needs a grant
      whose recipient is the caller; `global_by_role` still names a person.
      Proved by: a test that a group-only caller is refused a reveal on
      someone else's grant and on no grant.
- [ ] Groups reach only assertion-authenticated callers; key and `ww_console`
      cookie callers have none. Proved by: tests for both callers on a
      group-gated action.
- [ ] Mapping changes are audited in the stream. Proved by: a test.
- [ ] Docs: `docs/how-to/roles.md` (groups, and that a group never opens a
      reveal), `docs/how-to/access-identity.md` (the Keycloak mapper to
      configure; key and cookie callers have no groups),
      `docs/how-to/deleting-documents.md` (the delete gate via a group;
      switched-off roles).
