# Design

Groups come ONLY from the signed assertion (the header-is-never-a-source rule
of `access-identity.md` holds). A `group_roles` table (`group`, `role`,
`created_by`, `created_at`); `roles.held_by(caller, groups)` returns the union
of grant-held and group-held roles; `grants.authorize` keeps its one place of
decision and receives the resolved roles. A group removed from a user in
Keycloak takes effect at that user's next token (the assertion lifetime): the
service holds no group cache beyond the request.

## Amendment: findings of the architect

**Reveal rule (safe default, pending Mark).** A group-held role never opens a
reveal by itself. A reveal needs a grant whose recipient is the caller, as in
`reveal-api/spec.md` (recipient check) and `grants.authorize`. Group-held roles
gate only role-checked actions: the delete gate and role-gated pages. Rejected:
letting a group-held role authorise a reveal. An unscoped `beheerder` grant
would become a corpus-wide key for every group member, and `global_by_role`
would stop naming a person.

**Groups reach only assertion callers.** Groups come from the signed assertion
only. Key and `ww_console` cookie callers have no groups (the
header-is-never-a-source rule), so a group-only `beheerder` must log in via the
assertion for group-gated pages.

**Inactive roles.** `grants.caller_holds_role` does not look at `Role.active`
today, so a grant naming a switched-off role still opens the delete gate. That
is fixed first, before the function is extended with groups; the group path then
applies the same rule.
