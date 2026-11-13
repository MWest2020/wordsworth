## ADDED Requirements

### Requirement: A search result shows why it matched

Each search result in the console SHALL show the passage of the document
closest to the question, cut from the stored pseudonymised text, with the query
words that occur in it marked, and a short reason stating whether the passage
matches on words, on meaning, or both. Showing the passage SHALL NOT change the
order of the results and SHALL NOT store anything in the index.

When the closest passage cannot be determined for a hit, the result SHALL show
the fragment shown before this change. When the cause is that the index cannot
be read for the passages, the page SHALL say that the passages are unavailable.

#### Scenario: The closest passage is shown

- **WHEN** a question is closest to the second passage of a document in the results
- **THEN** the result shows that passage, as it stands in the stored pseudonymised text, and the reason

#### Scenario: A semantic match is explained

- **WHEN** the closest passage shares no word with the question
- **THEN** the reason says it matched on meaning and no word is marked

#### Scenario: The order of results is unchanged

- **WHEN** the same question is asked with and without passages available
- **THEN** the results are the same documents in the same order

#### Scenario: The stored vectors do not fit the text

- **WHEN** the number of passage vectors stored for a hit differs from the number of passages its stored text splits into
- **THEN** the result shows the fragment as before, without a reason

#### Scenario: The index cannot be read for the passages

- **WHEN** the results are in but reading their passage vectors fails because the index is unreachable
- **THEN** every result shows the fragment as before and the page says the passages are unavailable
