# pseudonymization Specification

## Purpose
TBD - created by archiving change add-pseudonymization. Update Purpose after archive.
## Requirements
### Requirement: Key provider protocol

Encryption keys SHALL be obtained through a `KeyProvider` protocol so the key
source is swappable. The PoC ships a stub provider deriving a single key from a
user-supplied passphrase; production key lifecycle (rotation, escrow, recovery)
is out of scope for the PoC.

#### Scenario: Stub key is deterministic for a passphrase

- **WHEN** the stub provider is asked for the current key twice with the same
  passphrase
- **THEN** it returns the same key bytes and key id

### Requirement: Separated encrypted mapping store

Pseudonym-to-original mappings SHALL be held in a separated store as AES-GCM
ciphertext, never in the document and never as clear PII. The store SHALL be
reached through a `MappingStore` protocol, and storing a pseudonym SHALL be
idempotent.

#### Scenario: Mapping is stored as ciphertext

- **WHEN** a pseudonym and its original value are stored
- **THEN** only ciphertext (with nonce and key id) is persisted, not the original

#### Scenario: Storing the same pseudonym twice is idempotent

- **WHEN** the same pseudonym is stored a second time
- **THEN** the store keeps a single mapping for that pseudonym

### Requirement: Stable keyed pseudonyms

The `Pseudonymizer` SHALL reuse the deterministic detectors and replace each PII
value with a stable, keyed pseudonym, such that the same value yields the same
pseudonym (searchable/linkable) while the pseudonym is not reversible without the
mapping store. The search index SHALL see only pseudonyms, never clear PII.

#### Scenario: Same value yields the same pseudonym

- **WHEN** a value appears more than once (in one or more documents)
- **THEN** every occurrence is replaced by the identical pseudonym

#### Scenario: A pseudonymized document is reversible via the store

- **WHEN** deanonymization is applied with the key and mapping store
- **THEN** the original values are recovered from the store

### Requirement: Pseudonymizer is a de-identify driver

The `Pseudonymizer` SHALL satisfy the `Anonymizer` protocol so it can be injected
into the pipeline's de-identify step without pipeline changes. The pipeline
default SHALL remain irreversible anonymization.

#### Scenario: Injected pseudonymizer produces pseudonymized index text

- **WHEN** the pipeline runs with the pseudonymizer injected
- **THEN** the persisted (index-bound) text contains pseudonyms and the mapping
  store holds the reversible encrypted originals

### Requirement: Deanonymization is audit-logged

Every deanonymization SHALL append a record to the append-only, hash-chained
audit trail, recording the pseudonyms and the actor. It SHALL NOT log the
recovered clear values.

#### Scenario: Deanonymization writes a chained audit record

- **WHEN** a document's text is deanonymized
- **THEN** a `deanonymize` audit record is appended for that document, the chain
  still verifies, and the payload holds pseudonyms and actor but no clear values

### Requirement: Per-type keyed pseudonyms

Each PII type SHALL be pseudonymised under its own type-scoped key, so that the
token and the encrypted mapping for a value of type T depend on T's active key.
Possession of T's key SHALL be necessary and sufficient to decrypt T's mappings,
and SHALL NOT decrypt another type's mappings. The search index SHALL still see
only pseudonyms.

#### Scenario: Different types use different keys

- **WHEN** values of two different PII types are pseudonymised
- **THEN** each type's mapping is encrypted under that type's own key, and the key
  for one type does not decrypt the other type's mappings

### Requirement: Selective reveal by type

Deanonymisation SHALL accept an optional set of allowed PII types. A token SHALL be
revealed only when its type is allowed AND the caller can resolve that mapping's
key; otherwise the token SHALL remain in place, unrevealed. When no allowed set is
given, all resolvable tokens SHALL be revealed (unchanged behaviour). The
deanonymisation audit record SHALL additionally record which types were revealed,
and SHALL NOT record any clear value.

#### Scenario: Only allowed types are revealed

- **WHEN** a document containing two PII types is deanonymised with only one type
  allowed
- **THEN** tokens of the allowed type are replaced by their originals and tokens of
  the other type remain pseudonymised

#### Scenario: A type whose key is unavailable stays pseudonymised

- **WHEN** a type is allowed but the caller cannot resolve that type's key
- **THEN** that type's tokens remain pseudonymised (no partial or failed decrypt)

### Requirement: Reversible entity pseudonymisation

Entity PII detected by the entity engine (e.g. PERSON, LOCATION) SHALL be replaced
with stable, per-type keyed pseudonyms and a separated encrypted mapping, exactly
as deterministic PII is, so that entity values are reversible via the mapping store
and revealable selectively by their type's key. A single driver SHALL apply both
the deterministic detectors and the entity engine, and the search-index text SHALL
contain only pseudonyms, never clear entity values.

#### Scenario: A detected name becomes a reversible keyed token

- **WHEN** text containing a personal name is pseudonymised by the reversible
  driver
- **THEN** the name is replaced by a `[PERSON:…]` keyed token, the clear name is
  absent from the output, and deanonymisation with PERSON allowed recovers it

#### Scenario: Entity and deterministic PII compose

- **WHEN** text contains both a name and a BSN
- **THEN** both are replaced by their respective keyed tokens under their own
  type keys, and each is independently revealable by its type

### Requirement: Entity detection failure is fail-hard

If the entity detection engine fails, the reversible driver SHALL raise and SHALL
NOT emit text containing un-pseudonymised entities (no silent fallback). The raised
error SHALL carry no document text.

#### Scenario: Detection error raises without leaking

- **WHEN** the detection engine raises during pseudonymisation
- **THEN** the driver raises an engine error and no text with clear entities is
  returned

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

