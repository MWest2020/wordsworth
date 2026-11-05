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

Line format: `PERSON<TAB>sentence<TAB>full name` or `GEEN<TAB>sentence`, with
`{naam}` as the slot in the sentence and in the full name.

## Amended

- **The expected full name is data, not derived.** The third column of a
  `PERSON` line holds the full name the detection must cover. Rejected: having
  the test find the full name with a particle scan, because that scan mirrors the
  rule and a bug in one would be copied into the other.
- **A brake hit fails and names the entry; it never edits `voornamen.json`.**
  Rejected: a removal branch that deletes the entry from the gazetteer when the
  brake catches it. A test that rewrites shipped data hides the finding it
  reports. The accepted misses `Ton` and `Bart` stay as the applied step 1
  requirement fixes them.
- **Two test files**, to stay under 200 lines:
  `tests/test_particle_names_veiligheid.py` (corpus brake and the coverage guard)
  and `tests/test_particle_names_zinnen.py` (fixture cross-product and the
  negative controls).

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
