## ADDED Requirements

### Requirement: Identifying combinations are declarable and checkable

A deployment SHALL be able to declare sets of PII types that identify a person
*together* while none of them identifies on its own, and each declaration SHALL
carry a reason in prose.

Every value is judged on its own today, so a record like "female, born 1978,
postcode 6541 EX, role X" passes through untouched: none of those four is a
direct identifier, and together they often name exactly one person. That is the
classic quasi-identifier, and it is why "we removed the names" has not been a
valid claim for thirty years.

A declaration SHALL name PII **types**, not column names, so the same statement
holds for documents and for datasets.

Validating a dataset profile SHALL report every declared combination that the
profile breaks nowhere — that is, no type of the combination is among the types
it pseudonymises. The report SHALL name the combination and its reason. It SHALL
be a finding, not a refusal: the controller decides what is identifying in their
context, and a tool that refuses on its own judgement teaches people to route
around it.

Breaking one member is enough, because the combination identifies only while all
its parts line up. The check is therefore a yes/no and not a score.

Note what this does not measure: whether those types actually occur in the data.
A profile knows which columns it handles, not what stands in the others. The
finding is "this profile breaks combination C nowhere", not "combination C occurs
in this file" — the first is a property of the profile and thus checkable, the
second needs the data and belongs to measurement.

The system SHALL NOT infer which combinations identify, and SHALL NOT compute a
k-anonymity figure. Answering "how many people share this combination" needs a
population reference this system does not have, and an invented k is worse than
no k.

#### Scenario: A profile that breaks a declared combination nowhere is reported

- **WHEN** a profile pseudonymises no type belonging to a declared combination
- **THEN** validation reports that combination, with its reason, and the profile
  is still usable

#### Scenario: A combination that is partly pseudonymised is not reported

- **WHEN** at least one type of a declared combination is pseudonymised in the
  profile
- **THEN** that combination is not reported, because the combination is broken

#### Scenario: A declaration without a reason is refused

- **WHEN** a combination is declared without prose explaining why those types
  identify together
- **THEN** the declaration is rejected

#### Scenario: No declarations means no change

- **WHEN** no combinations are declared
- **THEN** validation behaves exactly as before
