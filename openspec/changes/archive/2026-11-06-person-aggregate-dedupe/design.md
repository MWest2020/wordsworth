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
  two people. A person counts once per detection of the longer value, and the
  bare first name adds no row.
- **Equal values are not merged.** The aggregate is one row per detection
  (`stats.add` once per `Entity`), so equal values keep one row per occurrence,
  unchanged from today. The helper only drops entities whose `PERSON` value is
  absorbed into a longer `PERSON` value; it does not deduplicate anything else.
- **Aggregate only.** The helper returns the entity list for the aggregate;
  `_pseudonymize_entities` keeps receiving the full list, so the anonymised
  text is identical with and without the helper.

## Risks

- **Audit records change meaning.** Records written before and after this
  change count `PERSON` differently, so `particle-names-measured` must take its
  baseline after this change has merged.
- **`min_score` and `below_threshold` can shift.** An absorbed low-score
  detection leaves its layer's row, so those two fields can change for a layer
  even where the count of the longer value does not.
- **Case and diacritic variants stay separate, on purpose.** Matching is by
  exact whole words, like the case-sensitive `_pseudonymize_entities`; the
  aggregate must not merge what the replacement treats as different values.
