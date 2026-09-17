# pii-categories Specification

## Purpose

The vocabulary: every PII type has a category and a legal basis, and a PPL level
expands to a set of types.

This looks like a taxonomy and is really the seam between the law and the code.
Without it, "what may this person see" is a decision spread across handlers and
config; with it, that decision is one lookup, and the reason for it is written
next to the type.

**Every type carries a legal basis** because in a Woo context the question is
never "can we technically reveal this" but "on what ground". A system that cannot
answer the second question forces a human to reconstruct it per request.

## Requirements

### Requirement: Every PII type has a category and a legal basis

wordsworth SHALL hold a static, versioned registry that maps every PII entity
type to exactly one category — `c1` (AVG Art. 6, ordinary personal data), `c2`
(AVG Art. 9, special categories) or `c3` (AVG Art. 10, criminal data) — and a
minimum Privacy Protection Level (PPL) at which that category may be revealed:
`c1 → 1`, `c2 → 2`, `c3 → 3`. An entity type unknown to the registry SHALL be
treated as `c1` and logged once per process.

#### Scenario: Known type resolves to its category

- **WHEN** the registry is asked for the category of `GEZONDHEID`
- **THEN** it returns `c2`, legal basis `Art. 9`, PPL minimum 2

#### Scenario: Unknown type is fail-safe

- **WHEN** the registry is asked for a type it does not know
- **THEN** it returns `c1` (never revealed at PPL 0) and emits one warning

### Requirement: PPL level expands to a type set

The registry SHALL expand a PPL level `n` in `0..3` to the set of all entity
types whose category has PPL minimum `≤ n`. PPL 0 SHALL expand to the empty set.

#### Scenario: PPL 2 covers Art. 6 and Art. 9

- **WHEN** PPL 2 is expanded
- **THEN** the set contains every `c1` and `c2` type and no `c3` type

#### Scenario: PPL 0 reveals nothing

- **WHEN** PPL 0 is expanded
- **THEN** the set is empty

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
