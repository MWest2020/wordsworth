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

### Requirement: A value that survives replacement is reported without the value

When a detected value is still present after replacement, the system SHALL
refuse to emit the text and SHALL raise `AnonymizationInvariantError` with code
`waarde-overleefde-vervanging`. The error, the logs and the audit trail SHALL
carry only the PII type, the length, the counts and the word count of the value,
never the value.

#### Scenario: The text is refused

- **WHEN** a detected value is still in the text after replacement
- **THEN** the error is raised, no anonymised text is emitted, and the error
  carries type, length and counts only

#### Scenario: The error is not retried as transient

- **WHEN** the error is raised for a document
- **THEN** the document counts as `failed`, not `retryable`

### Requirement: The over-detection baseline is recorded as counts, per type

The over-detection baseline SHALL be measured on synthetic or fixture sentences,
never on the pilot corpus, with and without the current lists, and recorded with
its date in `docs/explanation/meting-overdetectie-07.md`: precision, recall,
leaks and false positives, per type. The record SHALL be labelled "what
detection would do now on this text", not "what it did". If OpenAnonymiser is
unreachable the report SHALL say "not run" and SHALL NOT show a
deterministic-only table as the baseline. How the values `statushouders`, `bewoners`,
`woningcorporaties`, `juni` and `wereldvluchtelingendag` are typed today SHALL be
recorded as counts per type. The record SHALL contain no document text.

#### Scenario: The baseline is recorded with its date

- **WHEN** the baseline measurement is taken
- **THEN** `meting-overdetectie-07.md` holds precision, recall, leaks and false
  positives per type, with and without lists, and the date

#### Scenario: OpenAnonymiser is unreachable

- **WHEN** the measurement runs and OpenAnonymiser cannot be reached
- **THEN** the report says "not run" and shows no table

#### Scenario: The five words are counted, not quoted from documents

- **WHEN** the record says how the five words are typed today
- **THEN** it gives a count per type for each word and no sentence or passage
  from any document

### Requirement: No measurement or diagnostic logs a value

Nothing that measures or diagnoses detection SHALL log, print or write a detected
value or the text around it. Output SHALL be counts, types and identifiers that
carry no personal data.

#### Scenario: A measurement run writes no value

- **WHEN** the evaluation or a diagnostic over stored runs completes
- **THEN** its output, logs and report contain counts per type and no detected
  value

### Requirement: A name with a Dutch particle is one person

In the reversible driver, detection SHALL treat a first name, a Dutch particle
(`van`, `van der`, `van den`, `de`, `ter`, `ten`) and a last name as ONE
`PERSON` span with layer `dutch_particle_name`, found by its own pattern. It
SHALL NOT turn ordinary text or an institution's name into a `PERSON`. The
irreversible `OpenAnonymiserAnonymizer` is out of scope.

#### Scenario: A name with each particle is one PERSON

- **WHEN** a synthetic name is built with each of `van`, `van der`, `van den`,
  `de`, `ter` and `ten` between a first name and a last name
- **THEN** each is detected as one `PERSON` span covering the whole name

#### Scenario: The irreversible driver is out of scope

- **WHEN** a document is de-identified by the irreversible
  `OpenAnonymiserAnonymizer`
- **THEN** this requirement does not apply and the rule does not run

#### Scenario: The detection carries its own layer name

- **WHEN** such a name is detected
- **THEN** the detection's layer is `dutch_particle_name`

#### Scenario: No part of the name stays readable

- **WHEN** a document containing such a name is de-identified
- **THEN** the full name (first name, particle and last name together) does not
  appear in the output; an unrelated `van` or `de` elsewhere in the text is
  replaced by value and may remain

#### Scenario: A lowercase particle in ordinary text is not a name

- **WHEN** a sentence contains `de` or `van` between ordinary lowercase words
- **THEN** no `PERSON` is detected

#### Scenario: Raad van State is not a name

- **WHEN** a sentence contains `Raad van State`
- **THEN** no `PERSON` is detected for it

#### Scenario: Kamer van Koophandel is not a name

- **WHEN** a sentence contains `Kamer van Koophandel`
- **THEN** no `PERSON` is detected for it

#### Scenario: Ministerie van Binnenlandse Zaken is not a name

- **WHEN** a sentence contains `Ministerie van Binnenlandse Zaken`
- **THEN** no `PERSON` is detected for it

#### Scenario: Vereniging van Eigenaren is not a name

- **WHEN** a sentence contains `Vereniging van Eigenaren`
- **THEN** no `PERSON` is detected for it

#### Scenario: Hoogheemraadschap van Rijnland is not a name

- **WHEN** a sentence contains `Hoogheemraadschap van Rijnland`
- **THEN** no `PERSON` is detected for it

### Requirement: The particle rule is anchored on a first-name gazetteer

The rule SHALL match only when the word before the particle is an entry of a
first-name gazetteer shipped inside the package. Every entry SHALL carry a
reason, and the loader SHALL refuse an entry without one. A missing or
unreadable gazetteer SHALL be a hard error, not an empty list.

#### Scenario: A word that is not a listed first name is not a name

- **WHEN** a capitalised word that is not in the gazetteer stands before a
  particle and a capitalised word
- **THEN** no `PERSON` is detected for it

#### Scenario: A gazetteer entry without a reason is refused

- **WHEN** the gazetteer is loaded with an entry that has no reason, or a blank
  one
- **THEN** loading fails and names the entry

#### Scenario: A missing gazetteer is an error

- **WHEN** the gazetteer file is absent or unreadable
- **THEN** the rule fails loudly and does not run with an empty list

#### Scenario: The gazetteer ships inside the package

- **WHEN** wordsworth is installed without any detection-lists directory
- **THEN** the gazetteer is found inside the package and the rule runs; no
  deployment needs a file of its own for it

### Requirement: The gazetteer leaves out common words and stays out of lists_hash

A first name that is also a common capitalised word at sentence start (`Ton`,
`Wil`, `Bart`) SHALL NOT be a gazetteer entry. This costs recall on purpose: of
the 14 seeded first names in `eval/synthetic.py`, `Ton` and `Bart` stay
unmatched, a known and accepted miss traded for precision. The gazetteer file
SHALL NOT be part of `lists_hash`.

#### Scenario: A first name that is a common word is excluded

- **WHEN** the shipped gazetteer is listed
- **THEN** it holds none of `Ton`, `Wil` and `Bart`

#### Scenario: The excluded names stay unmatched

- **WHEN** `Ton` or `Bart` stands before a particle and a last name
- **THEN** no `PERSON` is detected by this rule, a known and accepted miss

#### Scenario: A gazetteer change does not alter lists_hash

- **WHEN** the gazetteer file changes
- **THEN** `lists_hash` is unchanged

### Requirement: The particle rule is not a deterministic detector

The rule SHALL NOT be a row in `detectors.DETECTORS`, so the anonymizer, the
pseudonymizer, `find_deterministic()`, the PII evaluation's deterministic layer
and the dataset column validation report what they reported before.

#### Scenario: The detector table is unchanged

- **WHEN** the labels in `detectors.DETECTORS` are listed
- **THEN** they are `bsn`, `iban`, `email` and `postcode`, and no other

#### Scenario: find_deterministic ignores a name with a particle

- **WHEN** `find_deterministic()` is given a text holding a first name, a
  particle and a last name
- **THEN** it returns no hit for that name

#### Scenario: The PII evaluation's deterministic layer is unchanged

- **WHEN** the deterministic layer of the PII evaluation runs on a text holding
  such a name
- **THEN** it predicts no entity for it
