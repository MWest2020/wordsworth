## ADDED Requirements

### Requirement: A web address is personal data unless it is a known public host

Detection SHALL treat a web address — `http://`, `https://` or `www.` followed
by a host — as a `URL`, unless its host is on the installation's list of public
hosts. Trailing punctuation SHALL NOT be part of the value.

A party's own website identifies the party as surely as its name does: in a Woo
file, `www.jansen-bv.nl` is the company, and the company can be a person. A
government reference such as `wetten.overheid.nl` is not personal data, and
replacing it makes a decision unreadable without protecting anyone. The line
between the two is not a pattern but a list, and every entry on it SHALL carry
a reason.

The detection SHALL NOT depend on the name inside the address being detected
elsewhere. That dependency is what failed here: the heading carrying the name
was never detected, so nothing tied the address to it.

#### Scenario: A company website is detected

- **WHEN** a document contains `www.eazwind.nl`, on its own or in a sentence
- **THEN** it is detected as `URL`

#### Scenario: A listed public host is left alone

- **WHEN** a document contains `https://wetten.overheid.nl/BWBR0045754`
- **THEN** it is not detected

#### Scenario: Sentence punctuation stays outside the value

- **WHEN** a document contains `Zie www.eazwind.nl.`
- **THEN** the detected value is `www.eazwind.nl`, without the full stop

#### Scenario: An e-mail address is not also a web address

- **WHEN** a document contains `info@eazwind.nl`
- **THEN** it is detected once, as `EMAIL`

## MODIFIED Requirements

### Requirement: Versioned allow/deny lists refine detection

After detection, wordsworth SHALL apply git-versioned allow and deny lists:
a typed deny rule SHALL add detections (layer `list`, score 1.0), and a typed
allow rule SHALL then remove detections of that type whose value fully matches
the pattern — whether a detector found them or a deny rule added them. Allow
SHALL win over deny for the same type, so an exception can be stated next to
the rule it is an exception to. Where wordsworth does not control the
substitution (the irreversible service-side driver) only the deny list applies.
The lists' content hash SHALL be recorded in the de-identify audit record, and
suppressed detections SHALL be counted.

#### Scenario: Typed false positive is suppressed

- **WHEN** `allow.json` has `{"PERSON": ["^Jansen BV$"]}` and the detector tags
  `Jansen BV` as PERSON
- **THEN** the value is not redacted and `suppressed_by_list.PERSON == 1`

#### Scenario: Allow never crosses types

- **WHEN** the same allow rule exists and `Jansen BV` is detected as
  ORGANIZATION
- **THEN** the detection is kept

#### Scenario: An allow rule exempts a deny match of its own type

- **WHEN** `deny.json` matches every web address as `URL` and `allow.json`
  lists `wetten.overheid.nl` for `URL`
- **THEN** `https://wetten.overheid.nl/BWBR0045754` is not redacted, and
  `www.eazwind.nl` in the same text still is
