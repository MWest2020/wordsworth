# keycloak-groups-to-roles

## Why

An organisation manages people in groups in its identity provider. Rights that
work by role should follow group membership, managed as data in one place, with
the application deciding nothing beyond looking them up.

Reveal is not one of those rights. A reveal is authorised by a grant that names
the person who may use it (`reveal-api`: the caller must be the grant's
recipient), and that stays so. If a group-held role could open a reveal, the
unscoped grant naming `beheerder` that `docs/how-to/roles.md` recommends would
become a corpus-wide key for everyone in a mapped group, and the audit line
`global_by_role` would stop naming a person.

This scope is the default of #495 (the architect stopped build #490 on this
question). It is a promise change with an open question, so it waits for Mark's
merge; if he decides that a group role may authorise a reveal after all, that
is a new amendment, not a builder's call.

## What changes

- The identity verifier reads a `groups` claim from the verified assertion
  (Keycloak's group membership mapper), alongside the email. Only from there.
- A mapping group → role, managed through `GET/PUT/DELETE /group-roles` and the
  console's roles page, behind the same gate as `/roles`.
- `caller_holds_role` answers yes when the caller holds an active, unexpired
  grant naming the role (today) OR one of the caller's verified groups maps to
  it — and in both cases ONLY while the role is active. Today it ignores
  `Role.active`, so a switched-off `beheerder` still opens the delete gate;
  that is a bug and this change fixes it.
- A group-held role counts only where the system already decides by holding a
  role (`caller_holds_role`). It NEVER authorises a reveal: `authorize()` is
  unchanged, and a reveal still needs a grant naming the person as recipient.
- A caller authenticated by API key or console cookie carries no groups (the
  header-is-never-a-source rule: only a verified assertion is a source). This
  is documented: "no groups; use a personal grant or label".
- Every change to a mapping reaches the key-lifecycle stream, naming the person
  who made it. Every decision a group-held role opens is audited with the
  person as actor, never the group.

## Out of scope

- Any reveal through a group or a group-held role (see Why; #495).
- Making the label-list gates (grant admin and `/roles`, corpus read) accept a
  role. They decide by configured labels today; turning them into role gates is
  a separate promise change.
- Moving these tables into the key service (that is `key-service-cutover`);
  nested groups.

## Open questions

- Should a group-held role ever authorise a reveal? (#495) Default, pending
  Mark: no. A reveal needs a grant naming the caller. The default stays until
  he answers.
- The #495 default names "role and grant admin, the corpus-read list" among
  the gates that work by role; in code they decide by label lists. Default:
  they stay label gates (see Out of scope).

## Relation to the earlier amendment (#493)

This amendment supersedes the first one. It keeps its reveal rule, its
key/cookie rule and its fix-`Role.active`-first ordering, and replaces three
points a builder would otherwise have to invent: "role-gated pages" (there are
none; only `caller_holds_role` gates by role), "behind the same gate as roles
(`beheerder`)" (`/roles` is gated by issuer labels), and "`grants.authorize`
receives the resolved roles" (it receives nothing new).
