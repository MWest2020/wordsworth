## ADDED Requirements

### Requirement: The host of an allowed web address stays whole

When an allow rule exempts a web address from URL detection, entity
replacement SHALL NOT replace any value inside that address's host (scheme,
subdomains, domain, port). Values inside the address's path, query or fragment
SHALL be replaced as anywhere else. The fail-hard survivor check SHALL NOT
count a value that appears only inside a protected host.

#### Scenario: A name found elsewhere is not replaced inside an allowed host

- **GIVEN** `https://www.gooisemeren.nl` is allowed, and `gooisemeren` is
  detected as LOCATION elsewhere in the document
- **WHEN** the document is de-identified
- **THEN** the output contains `https://www.gooisemeren.nl` unchanged
- **AND** the other occurrence of `gooisemeren` is a LOCATION token
- **AND** the document is not rejected

#### Scenario: A name in the path of an allowed address is still replaced

- **GIVEN** `https://www.gooisemeren.nl/raad/jansen` is allowed, and `jansen`
  is detected as PERSON
- **WHEN** the document is de-identified
- **THEN** the output contains `https://www.gooisemeren.nl/raad/` followed by
  a PERSON token, and `jansen` does not appear in clear

#### Scenario: An address that is not allowed is unaffected

- **GIVEN** `www.eazwind.nl` is not allowed
- **WHEN** the document is de-identified
- **THEN** it becomes a URL token, as before
