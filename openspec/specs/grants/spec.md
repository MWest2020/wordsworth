# grants Specification

## Purpose
TBD - created by archiving change add-reveal-grants. Update Purpose after archive.
## Requirements
### Requirement: Per-type reveal grants

The system SHALL represent authorization to reveal PII as a grant naming a
recipient and a set of PII types, optionally scoped to a single document and/or an
expiry. A grant SHALL carry no key material and no clear PII. Grants SHALL be
issued and revoked; revocation SHALL be idempotent.

A grant without a document scope ("global") SHALL authorize any document ONLY
where the deployment explicitly allows global grants. Where it does not — the
default — such a grant SHALL authorize nothing, whenever and however it was
issued, and SHALL be refused at issue.

#### Scenario: A grant authorizes only its own types

- **WHEN** a grant for types {PERSON} is asked to authorize a reveal of
  {PERSON, BSN}
- **THEN** it authorizes exactly {PERSON}

#### Scenario: A scoped grant applies only to its own document

- **WHEN** a grant scoped to document D authorizes a reveal
- **THEN** it authorizes for D and authorizes nothing for another document,
  whether or not the deployment allows global grants

#### Scenario: An unscoped grant is inert unless global grants are allowed

- **WHEN** a grant with no document scope is asked to authorize a reveal of its
  allowed types
- **THEN** it authorizes the empty set where the deployment does not allow global
  grants, and its allowed types where it does

### Requirement: Revocation and expiry withhold authorization

A revoked grant SHALL authorize nothing. A grant past its expiry SHALL authorize
nothing. Authorization SHALL be a pure decision returning the permitted subset of
the requested types (empty when denied), never raising for the denied case.

#### Scenario: Revoked grant authorizes nothing

- **WHEN** a grant is revoked and then asked to authorize its previously allowed
  type
- **THEN** it authorizes the empty set

#### Scenario: Expired grant authorizes nothing

- **WHEN** the current time is at or past a grant's expiry
- **THEN** it authorizes the empty set, while before the expiry it authorizes its
  allowed types

### Requirement: Grant issue and revoke are audited without key material

Issuing and revoking a grant SHALL each append an event to the append-only
key-lifecycle audit stream (not the document hash-chain), recording the grant id,
recipient, allowed types, and actor. No key material SHALL ever be written.

#### Scenario: Issue and revoke each write one audit event

- **WHEN** a grant is issued and later revoked
- **THEN** the key-lifecycle stream gains one issue event and one revoke event
  naming the grant and actor, and no key material appears in the stream

### Requirement: Grant admin over HTTP

De API SHALL een operator laten uitgeven, inspecteren en intrekken van
reveal-grants over HTTP, gemount alleen wanneer een grant-store geconfigureerd is.
Uitgeven en intrekken SHALL beperkt zijn tot callers die de deployment expliciet
als uitgever aanwijst wanneer caller-authenticatie aanstaat; een caller buiten die
kring SHALL 403 krijgen, ook als hij verder geauthenticeerd is. Staat er geen
caller-authenticatie aan, dan is er geen caller om op te beslissen en blijft het
gedrag ongewijzigd. Een lege uitgeverskring SHALL met authenticatie aan **niemand**
toestaan — een grant is de sleutel tot klare PII en dat recht hoort een expliciete
keuze te zijn, geen restwaarde.

Uitgeven SHALL een recipient, een lijst PII-types, een optionele documentscope en
een optionele tijdzone-bewuste expiry accepteren (een naïeve of ongeldige expiry,
of een ongeldig document-id, SHALL met 400 geweigerd worden). Uitgeven zonder
documentscope SHALL met 400 geweigerd worden waar de deployment geen globale
grants toestaat. Inspecteren of intrekken van een onbekende grant SHALL 404 geven;
intrekken SHALL idempotent zijn. Elke uitgifte en intrekking SHALL in de
key-lifecycle-audit terechtkomen. Geen antwoord SHALL sleutelmateriaal of klare
PII bevatten.

#### Scenario: Een geauthenticeerde caller buiten de uitgeverskring mint niets

- **WHEN** caller-authenticatie aanstaat en een caller die niet als uitgever is
  aangewezen een grant probeert uit te geven of in te trekken
- **THEN** wordt het geweigerd met 403 en ontstaat er geen grant en geen
  audit-event

#### Scenario: Vergeten kring betekent niemand

- **WHEN** caller-authenticatie aanstaat maar er is geen uitgeverskring
  geconfigureerd
- **THEN** kan niemand een grant uitgeven of intrekken

#### Scenario: Zonder authenticatie ongewijzigd

- **WHEN** er geen caller-authenticatie is geconfigureerd
- **THEN** gedraagt de grant-admin zich als voorheen

#### Scenario: Issue, inspect, revoke

- **WHEN** een uitgever een grant uitgeeft, inspecteert en intrekt
- **THEN** geeft uitgifte de grant met status active, weerspiegelt inspectie dat,
  en geeft intrekken status revoked (een tweede intrekking is een no-op)

#### Scenario: Revocatie sluit reveal af

- **WHEN** een grant die een reveal toestond wordt ingetrokken en dezelfde reveal
  opnieuw wordt geprobeerd
- **THEN** wordt de reveal geweigerd

#### Scenario: Een unscoped issue wordt geweigerd zolang globale grants niet mogen

- **WHEN** een uitgever een grant zonder documentscope uitgeeft op een deployment
  die geen globale grants toestaat
- **THEN** wordt het verzoek met 400 geweigerd en ontstaat er geen grant

#### Scenario: Afwezig zonder grant-store

- **WHEN** de app zonder grant-store is geconfigureerd
- **THEN** zijn de grant-routes niet gemount

### Requirement: Grants may be issued by PPL level

`POST /grants` SHALL accept `ppl` (integer 0–3) as an alternative to
`allowed_types`. The server SHALL expand `ppl` via the PII category registry and
persist the result as `allowed_types`; the stored grant model is unchanged.
Supplying both or neither SHALL be rejected with 422.

#### Scenario: PPL shorthand is expanded on issue

- **WHEN** a grant is issued with `ppl: 1`
- **THEN** the stored `allowed_types` equals the registry's PPL 1 set and the
  response reports `ppl: 1`

#### Scenario: Both forms at once are rejected

- **WHEN** a grant request carries both `ppl` and `allowed_types`
- **THEN** the API responds 422 and no grant is created

