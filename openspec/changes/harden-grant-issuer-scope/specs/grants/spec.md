## MODIFIED Requirements

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
