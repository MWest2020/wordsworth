# Tasks

- [ ] `groups` read from the verified assertion only; a `groups` header or an
      unsigned claim is ignored. Proved by: tests with a forged header and an
      unsigned token.
- [ ] Group → role mapping API and console page, gated like roles. Proved by:
      tests (beheerder may, others are refused).
- [ ] Reveal allowed through a group-mapped role; refused once the group is
      removed from the assertion (revoked group); refused for a group mapped to
      a switched-off role. Proved by: three tests.
- [ ] Mapping changes are audited in the stream. Proved by: a test.
- [ ] Docs: `docs/how-to/roles.md` (groups), `docs/how-to/access-identity.md`
      (the Keycloak mapper to configure).
