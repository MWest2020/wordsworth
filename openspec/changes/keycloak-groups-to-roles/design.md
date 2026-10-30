# Design

Groups come ONLY from the signed assertion (the header-is-never-a-source rule
of `access-identity.md` holds). A `group_roles` table (`group`, `role`,
`created_by`, `created_at`); `roles.held_by(caller, groups)` returns the union
of grant-held and group-held roles; `grants.authorize` keeps its one place of
decision and receives the resolved roles. A group removed from a user in
Keycloak takes effect at that user's next token (the assertion lifetime): the
service holds no group cache beyond the request.
