## ADDED Requirements

### Requirement: De sleutels van de uitgever halen mag het opstarten niet blokkeren

Het ophalen van het discovery-document of de JWKS SHALL niet tijdens het
opstarten gebeuren, maar bij het eerste verzoek dat een token
controleert, met cache. Mislukt het ophalen, dan SHALL het verzoek geen
caller opleveren en SHALL de applicatie blijven draaien. Het JWKS-adres
MAY los ingesteld worden; dan SHALL het discovery-document niet
opgehaald worden en SHALL de uitgever nog steeds tegen `iss`
gecontroleerd worden. Elke HTTP-aanroep SHALL een User-Agent meesturen.

#### Scenario: Provider onbereikbaar

- **GIVEN** een ingestelde uitgever die niet antwoordt
- **WHEN** de applicatie start en daarna een verzoek met token binnenkomt
- **THEN** draait de applicatie, levert dat verzoek geen caller op, en
  blijft de rest van de API gewoon werken

#### Scenario: Intern JWKS-adres

- **GIVEN** een ingesteld JWKS-adres op een interne Service
- **WHEN** een token gecontroleerd wordt
- **THEN** wordt dat adres gebruikt, wordt er geen discovery-document
  opgehaald, en wordt de uitgever nog steeds tegen `iss` gecontroleerd
