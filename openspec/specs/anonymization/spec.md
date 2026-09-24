# anonymization Specification

## Purpose

Removing PII irreversibly, and being deliberate about what "removing" means.

This is the step the whole privacy promise rests on, so the design refuses
several tempting shortcuts. Detection is **deterministic** — the same document
gives the same result, because an anonymiser whose output depends on the day you
ran it cannot be audited. Replacement is **irreversible**: no key, no mapping, no
"we could get it back if we had to". That is what separates this from
pseudonymisation, and blurring the line would make the legal basis unclear for
both.

**Feedback is recorded, not auto-applied.** A missed name is valuable
information, but an allow/deny list that updates itself from feedback is a
detection rule nobody reviewed acting on real documents. Lists are versioned and
changed on purpose.

## Requirements

### Requirement: Anonymizer driver protocol

Anonymization SHALL be accessed through an `Anonymizer` protocol that takes text
and returns the anonymized text plus a per-type replacement count. The pipeline
SHALL depend on the protocol, never on a concrete engine, so that a different
engine (e.g. OpenAnonymiser) can be substituted without pipeline changes.

#### Scenario: A custom driver is used when injected

- **WHEN** a caller injects an alternative object satisfying the `Anonymizer`
  protocol
- **THEN** the pipeline uses it for the anonymize step instead of the default

### Requirement: Deterministic PII detection

The interim `DeterministicAnonymizer` SHALL detect and irreversibly replace, with
typed placeholders, only high-precision deterministic PII: BSN (validated by the
elfproef), IBAN (validated by mod-97), email addresses, and Dutch postcodes. A
candidate that fails its validation SHALL be left untouched.

A detector MAY carry a **context rule** that rejects a match on the grounds of
what surrounds it, where the value alone cannot decide. The postcode detector
carries exactly one: a postcode directly preceded by `Postbus <number>` is the
contact address of an organisation, not a household, and SHALL be left readable —
redacting it makes a decision unreadable without protecting anyone. The rule SHALL
be defined once, in the shared detector table, so that every path that replaces
PII applies the same exceptions.

A context rule SHALL be written so that text rewritten by detectors running
earlier cannot change its answer. The detectors run in sequence and each replaces
values with placeholders of a different length, so a rule that merely scans a
window backwards would have a reach that shifts with whatever happened to precede
the match — the same rule, on the same source, answering differently depending on
how many email addresses came before. Requiring the marker to sit **directly**
before the match is what rules that out: if nothing stood between them in the
source, nothing was replaced there either; and an inserted placeholder can only
break such a match, never create one.

#### Scenario: Valid BSN is replaced

- **WHEN** the text contains a 9-digit number that passes the elfproef
- **THEN** it is replaced by `[BSN]` and the BSN count increments

#### Scenario: Invalid BSN is left untouched

- **WHEN** the text contains a 9-digit number that fails the elfproef
- **THEN** it is not replaced and the BSN count does not increment

#### Scenario: Valid IBAN is replaced

- **WHEN** the text contains an IBAN-shaped string that passes mod-97
- **THEN** it is replaced by `[IBAN]` and the IBAN count increments

#### Scenario: Email is replaced

- **WHEN** the text contains an email address
- **THEN** it is replaced by `[EMAIL]` and the email count increments

#### Scenario: A PO box keeps its postcode

- **WHEN** the text contains `Postbus 250, 6800 GD Arnhem`
- **THEN** the postcode is left readable and the postcode count does not increment

#### Scenario: A street address loses its postcode

- **WHEN** the text contains `Brinklaan 35, 1404 GZ Bussum`
- **THEN** the postcode is replaced and the postcode count increments

#### Scenario: An earlier replacement does not change the answer

- **WHEN** the same PO box line is de-identified twice, once with an email address
  on the line before it and once without
- **THEN** the postcode is left readable in both cases

#### Scenario: A marker that is not directly before the postcode does not count

- **WHEN** the text contains `Postbus 16005` and a line of other text before
  `3500 DA`
- **THEN** the postcode is replaced, because the rule requires the marker directly
  before the match

### Requirement: Irreversible replacement

Replacement SHALL be irreversible: placeholders SHALL carry no mapping back to
the original value. Reversible handling is out of scope (pseudonymization).

#### Scenario: Placeholders are not reversible

- **WHEN** a value is replaced
- **THEN** the output contains only the typed placeholder, with no stored mapping
  from placeholder to original value

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

### Requirement: Een allow-regel draagt een reden

Every entry in the allow list SHALL carry a human-readable reason, stored beside
the pattern in the same file.

An allow list is the one place in this system where a change quietly results in
*less* pseudonymisation. A bare list of words is a list nobody can review: a
reader cannot tell `^gemeente$` (an ordinary noun) from an entry that silently
exempts a surname. The reason is what makes review possible. A deny rule adds
protection, so there a bare pattern is enough.

#### Scenario: An entry without a reason is refused

- **WHEN** the lists are loaded and an allow entry has no reason
- **THEN** loading fails, and no list is applied

### Requirement: Een allow-regel mag geen bekende PII onderdrukken

The allow list SHALL be checked against the evaluation corpus, where the seeded
PII values are known, and an entry that suppresses a seeded value SHALL fail the
check. The check SHALL also cover the **individual words** of a seeded value.

This is the guard that makes an allow list safe to have at all. Without a corpus
whose answers are known, every entry is a matter of trust; with one, "this rule
hides real PII" is a fact that can be established before the rule ships. The
individual words matter because the corpus seeds full names (`Hendrik de
Vries`) while the detector also yields bare surnames — a rule `^vries$` is
exactly the dangerous case, and a check on the full value alone lets it through.

#### Scenario: A rule that hides a seeded value is caught

- **WHEN** an allow entry matches a value the evaluation corpus seeded as PII,
  or one of that value's individual words
- **THEN** the check fails and names the entry

#### Scenario: Recall does not drop

- **WHEN** the evaluation is run with and without the lists
- **THEN** the recall on seeded PII is unchanged

### Requirement: De lijst leeft in de repo, niet in de omgeving

The lists SHALL be versioned in the repository and shipped with the application
image, and SHALL NOT be supplied by an environment that can be changed without
review.

The lists' content hash is recorded in every de-identification record so that a
document can be traced to the rules that produced it. A hash that points at
something anyone could have edited in place is a number without provenance.

#### Scenario: A document can be traced to reviewed rules

- **WHEN** an auditor takes the lists hash from a document's record
- **THEN** it identifies a reviewed commit

### Requirement: A street with a house number is an address

Detection SHALL treat a Dutch street name followed by a house number as an
address, also when no postcode accompanies it.

In a Woo file about a building permit the building *is* the case: from an
address to an owner is one land-registry lookup. The earlier pattern found the
postcode and the place name and left `Industrieweg 23a` standing — which is the
half that identifies. A home address is personal data unless something marks it
otherwise (Mark, 2026-09-22); an organisation's `Postbus` contact address is
that exception and SHALL NOT be detected as one.

The pattern SHALL be anchored on street-like endings and SHALL NOT be a general
"capitalised word followed by a number", which would swallow `Artikel 5` and
`bijlage 3`. Street and house number SHALL form ONE span: what identifies a
person is the pair, a street alone is a place and a number alone is nothing.

#### Scenario: A street with a number is detected without a postcode

- **WHEN** a document contains `Amsterdamsestraatweg 65a` and no postcode nearby
- **THEN** it is detected as an address

#### Scenario: A legal reference is not an address

- **WHEN** a document contains `Artikel 5` or `bijlage 3`
- **THEN** neither is detected as an address

#### Scenario: A post-office box is not a home address

- **WHEN** a document contains `Postbus 1234, 1234 AB Haarlem`
- **THEN** it is not detected as an address

### Requirement: A detection change is measured before it is called fixed

The effect of a change to detection SHALL be measured on the evaluation corpus,
where the seeded values are known, and the number SHALL be recorded with its
date alongside the existing measurements.

Without a number, "detection improved" is a feeling, and this is the part of the
system where a feeling is the least useful thing to have. The measurement SHALL
be taken against the **action** — what the layer that constitutes the change did
— and not against a shape in the result that can arise without that action.

#### Scenario: The measurement is repeatable

- **WHEN** the evaluation corpus is generated and processed
- **THEN** the count of seeded values that survive into the stored text is
  reported

#### Scenario: What the corpus labels decides what can be measured

- **WHEN** a value is not seeded as PII in the evaluation corpus
- **THEN** a detector that finds it scores as a false positive, so changing what
  counts as PII is a change to the corpus first and to the detector second

### Requirement: Feedback is recorded, not auto-applied

`POST /documents/{id}/feedback` SHALL append an audit record describing a
false positive or false negative by type and token, never by clear value, and
SHALL NOT modify any list.

#### Scenario: Feedback leaves lists untouched

- **WHEN** feedback is posted
- **THEN** an audit record exists and the list hash in the next run is unchanged

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
