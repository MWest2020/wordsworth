# Design: particle-names-brake

## Settled here (the last architect FAIL's blocker)

The 1 Nov FAIL found a contradiction: substituting every gazetteer entry into a
sentence "followed by a particle and a capitalised word" and asserting no
`PERSON` fails by construction, because that string IS the shape the rule must
match. So the fixture does not assert "no PERSON" across the board. **Each
sentence states its own expectation**:

- `PERSON` sentences put `{naam} <particle> <Surname>` where a person is meant;
  the test asserts a `PERSON` covering exactly that full name, in the detection
  and (absent) in the anonymised output.
- `GEEN` sentences hold the entry as an ordinary word or the particle between
  ordinary words, shapes where a person is not meant; the test asserts no
  `PERSON` from the rule.
- A sentence without a stated expectation fails the test.

Line format: `PERSON<TAB>sentence` or `GEEN<TAB>sentence`, `{naam}` as the slot.

Guards against a vacuous pass:

- At least one `PERSON` sentence per particle, and those detections occur.
- **The corpus brake checks occurrence first.** Per shipped entry, it counts
  how often the entry occurs in the generated corpus as a first name before a
  particle and last name. An entry with count 0 is reported by name as not
  exercised, and the test fails. Only for exercised entries does it check that
  no false `PERSON` came from it.
- **Negative controls:** a stub gazetteer with an entry the generator never
  emits (`Zzyzx`) makes the occurrence assertion fail; a stub gazetteer holding
  `Ton` makes the exclusion check of step 1 fail.
