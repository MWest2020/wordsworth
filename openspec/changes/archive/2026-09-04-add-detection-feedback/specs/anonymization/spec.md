## ADDED Requirements

### Requirement: Versioned allow/deny lists refine detection

After detection, wordsworth SHALL apply git-versioned allow and deny lists:
a typed allow rule SHALL remove detections of that type whose value fully
matches the pattern; a typed deny rule SHALL add detections (layer `list`,
score 1.0). Where wordsworth does not control the substitution (the
irreversible service-side driver) only the deny list applies. The lists'
content hash SHALL be recorded in the de-identify audit record, and suppressed
detections SHALL be counted.

#### Scenario: Typed false positive is suppressed

- **WHEN** `allow.json` has `{"PERSON": ["^Jansen BV$"]}` and the detector tags
  `Jansen BV` as PERSON
- **THEN** the value is not redacted and `suppressed_by_list.PERSON == 1`

#### Scenario: Allow never crosses types

- **WHEN** the same allow rule exists and `Jansen BV` is detected as
  ORGANIZATION
- **THEN** the detection is kept

### Requirement: Feedback is recorded, not auto-applied

`POST /documents/{id}/feedback` SHALL append an audit record describing a
false positive or false negative by type and token, never by clear value, and
SHALL NOT modify any list.

#### Scenario: Feedback leaves lists untouched

- **WHEN** feedback is posted
- **THEN** an audit record exists and the list hash in the next run is unchanged
