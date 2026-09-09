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
of een ongeldig document-id, SHALL met 400 geweigerd worden). Uitgeven met een
documentscope die naar een onbekend document wijst SHALL met 404 geweigerd
worden, vóór enige write — dezelfde weigering als de andere document-routes
geven, en niet een databasefout die als 500 naar buiten komt. Uitgeven zonder
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

#### Scenario: Onbekend document

- **WHEN** een uitgever een grant aanvraagt met een goed gevormd `document_id`
  dat niet bestaat
- **THEN** antwoordt de API met 404 "unknown document" en ontstaat er geen
  grant en geen audit-event
