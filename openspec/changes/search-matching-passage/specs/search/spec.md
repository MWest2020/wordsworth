## ADDED Requirements

### Requirement: A search result shows why it matched

Each search result SHALL show the passage that ranked the document, cut from
the stored pseudonymised text, with the query terms that occur in it marked,
and a short reason stating whether it matched on words, on meaning, or both. A
document whose passages have no offsets yet SHALL show the fragment shown
before this change.

#### Scenario: The winning passage is shown

- **WHEN** a question matches a document best on its second passage
- **THEN** the result shows that passage and the reason

#### Scenario: A semantic match is explained

- **WHEN** the passage shares no word with the question
- **THEN** the reason says it matched on meaning and no term is marked

#### Scenario: Not yet backfilled

- **WHEN** a hit's document has passages without offsets
- **THEN** the result shows the fragment as before
