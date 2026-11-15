# Design

## Where groups come from

Groups come ONLY from the signed assertion (the header-is-never-a-source rule
of `access-identity.md` holds). The verifier returns the caller label and the
`groups` claim of the same verified token, or nothing at all: an expired, badly
signed or wrong-audience token yields no label AND no groups. A `groups` claim
that is missing or not a list of strings yields no groups (not a refusal of the
caller).

`ApiKeyAuthMiddleware` stashes `scope["state"]["groups"]` next to `caller`, and
sets it from the verifier ONLY on the branch where the label came from the
verifier. On the API-key and console-cookie branches (a sent credential beats
the one that rides along) `groups` is the empty tuple: the key or cookie names
a label, and a label has no groups. The service holds no group cache beyond the
request; a group removed from a user in Keycloak takes effect at that user's
next token (the assertion lifetime).

## The mapping

A `group_roles` table (`group`, `role`, `created_by`, `created_at`), one row per
pair. `GET /group-roles`, `PUT /group-roles/{group}/{role}` and
`DELETE /group-roles/{group}/{role}` sit behind the same gate as `/roles`
(today `gates.grant_admin`, the issuer labels). `PUT` for a role that does not
exist is refused with 404, like `PUT /roles/{name}/types`; `PUT` of an existing
pair and `DELETE` of an absent one are idempotent and write no event. Each real
change appends one key-lifecycle event (`group_role_mapped` /
`group_role_unmapped`) with group, role and actor (the caller label).

## Holding a role

One function decides, as today:

```python
caller_holds_role(session, caller, role, groups=()) -> bool
```

Step 2 is built first, on today's function, before groups are added (task 1);
the group path then inherits it.

1. No caller → False.
2. The role does not exist or `Role.active` is False → False. Checked first,
   for both sources: a switched-off role opens nothing (fixes the current bug
   where a grant naming a switched-off `beheerder` still opens the delete gate).
3. An active, unexpired grant with `recipient == caller` and `role == role` →
   True (unchanged).
4. A `group_roles` row whose `group` is in `groups` and whose `role == role` →
   True.
5. Otherwise False.

Callers of `caller_holds_role` today: `read_gate.build().delete` (API delete of
documents and dossiers) and `delete_cli` (no assertion, so `groups=()`). The
API delete gate passes `request.state.groups`. No other gate changes: grant
admin, `/roles`, `/group-roles` and corpus read keep deciding by their label
lists.

## Reveal does not change

`grants.authorize` keeps its one place of decision and is not touched: it
receives no groups and no held roles. A grant naming role R resolves R's types
(and R's active state) through `resolve_role`, exactly as now, and is usable
only by its recipient. Being in a group mapped to R does not make a caller the
recipient of any grant, and gives no types. So the unscoped grant naming
`beheerder` stays a key for its recipient only, and `global_by_role` keeps
naming that person.

## Audit names a person

The actor of every audit record stays the caller label from the verified
assertion (an email) or the key label — never a group name or a role name. A
delete opened by a group-held `beheerder` is recorded exactly like one opened by
a grant-held `beheerder`: the person as actor.

## Dead end said out loud

A person whose only `beheerder` comes from a group and who uses the console
login (cookie) or an API key carries no groups, so the delete gate refuses
them. That is correct by the source rule. `docs/how-to/roles.md` and
`docs/how-to/access-identity.md` say so: "no groups; use a personal grant or
label".
