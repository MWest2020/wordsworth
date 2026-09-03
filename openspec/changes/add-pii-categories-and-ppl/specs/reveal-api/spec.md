## ADDED Requirements

### Requirement: Reveal reports types per legal basis

The reveal response SHALL, in addition to `revealed_types` and
`withheld_types`, group both sets under their AVG legal basis
(`by_legal_basis: {"Art. 6": {...}, "Art. 9": {...}, "Art. 10": {...}}`). The
reveal audit record SHALL carry the set of categories touched and never a clear
value.

#### Scenario: Grouping mirrors the flat sets

- **WHEN** a reveal returns `revealed_types` and `withheld_types`
- **THEN** the union of all types in `by_legal_basis` equals the union of the two
  flat sets, each type under exactly one basis
