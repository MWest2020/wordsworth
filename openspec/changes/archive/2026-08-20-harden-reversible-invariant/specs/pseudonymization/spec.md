## ADDED Requirements

### Requirement: Entity redaction is offset-independent and fail-hard

Reversible pseudonymisation of detected entities SHALL replace the detected
values themselves (every occurrence), independent of any character offsets the
detection engine reports, so that an offset that does not align with the text
cannot leave a clear value in the emitted text. After substitution the driver
SHALL verify that no detected value remains outside an inserted token, and SHALL
fail hard (raising, emitting no text) if one does. The emitted (index-bound) text
SHALL therefore never contain a detected clear PII value.

#### Scenario: Misreported offsets do not leak

- **WHEN** the detection engine reports an entity with correct text but offsets
  that do not match the document's character positions
- **THEN** the value is still replaced by its keyed token and no clear value
  appears in the emitted text

#### Scenario: A surviving detected value fails hard

- **WHEN** any detected entity value would remain in the emitted text after
  substitution
- **THEN** the driver raises and emits no text, rather than index possibly-clear
  PII

### Requirement: Reveal access is attributed to its grant

Every reveal SHALL record, in the append-only audit access event, the identifier
of the grant that authorised it, alongside the actor and the revealed types, and
SHALL NOT record any clear value.

#### Scenario: The reveal audit names the grant

- **WHEN** a document is revealed through a grant
- **THEN** the `deanonymize` audit record carries that grant's id and the revealed
  types, and contains no clear PII value
