## ADDED Requirements

### Requirement: Identiteit komt uit een instelbare OIDC-uitgever

De API SHALL de caller kunnen vaststellen uit een ondertekend
OIDC-token van een ingestelde uitgever, met controle op handtekening,
uitgever, publiek en vervaltijd. Cloudflare Access SHALL één mogelijke
invulling van die instelling blijven. Het token SHALL gelezen worden
uit `Authorization: Bearer …` of uit `cf-access-jwt-assertion`; een
e-mailadres uit een kop SHALL nooit vertrouwd worden. Zonder geldig
token en zonder geldige API-sleutel SHALL er geen caller zijn.

#### Scenario: Geldig Keycloak-token

- **GIVEN** een uitgever `https://iam.westerweel.work/realms/westerweel`
  en publiek `wordsworth`
- **WHEN** een verzoek binnenkomt met een geldig token van die uitgever
- **THEN** is de caller het geverifieerde e-mailadres uit het token

#### Scenario: Token van een andere uitgever

- **GIVEN** dezelfde instelling
- **WHEN** het token van een andere uitgever komt, of een ander publiek
  noemt, of verlopen is
- **THEN** is er geen caller, en mag de aanvraag geen grant uitgeven of
  volledige tekst lezen

#### Scenario: Alleen een e-mailkop

- **WHEN** een verzoek alleen een e-mailadres in een kop meestuurt,
  zonder ondertekend token
- **THEN** is er geen caller
