# Design: person-aggregate-dedupe

## Settled here (open in the 1 Nov architect FAIL)

- **Containment by value, not by offset.** `pseudonymizer.py` records that the
  service's offsets do not line up with Python slicing and was deliberately
  made offset-independent; the aggregate is keyed by value too. So: a `PERSON`
  value A is absorbed into a `PERSON` value B of the same document when A is
  shorter and A's words occur, in order and as whole words, in B
  (`"Janine"` in `"Janine van Dijk"`; not `"Jan"` in `"Janine van Dijk"`).
  Only `PERSON` is deduplicated; other labels are untouched.
- **Two people with one first name.** `"Janine"`, `"Janine van Dijk"` and
  `"Janine de Groot"`: the bare first name is absorbed (into either), leaving
  two people. Equal values count once, as today.
- **Aggregate only.** The helper returns the entity list for the aggregate;
  `_pseudonymize_entities` keeps receiving the full list, so the anonymised
  text is identical with and without the helper.
