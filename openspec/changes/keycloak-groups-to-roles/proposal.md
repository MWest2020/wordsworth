# keycloak-groups-to-roles

## Why

Rights to see PII types are granted today per person (a grant naming a role or
types). An organisation manages people in groups in its identity provider;
rights should follow group membership, managed as data in one place, with the
application deciding nothing beyond looking them up.

## What changes

- The identity verifier reads a `groups` claim from the verified assertion
  (Keycloak's group membership mapper), alongside the email.
- A mapping group → role, managed through `GET/PUT/DELETE /group-roles` and the
  console's roles page, behind the same gate as roles (`beheerder`).
- A caller holds a role when they hold a grant naming it (today) OR when one of
  their verified groups maps to it. Reveal authorisation uses the union.
- Every change to a mapping reaches the key-lifecycle/authorisation stream.

## Out of scope

Moving these tables into the key service (that is `key-service-cutover`);
nested groups.
