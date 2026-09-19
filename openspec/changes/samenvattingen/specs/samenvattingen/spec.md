## ADDED Requirements

### Requirement: Een samenvatting hoort bij het document, niet bij de vraag

The system SHALL compute at most one summary per document, on request per
dossier, and SHALL store it with the model that produced it and the moment it
was produced.

A summary does not depend on the question asked, so producing one per search is
slow work whose result differs for the same question tomorrow. The model and the
moment are stored because a summary from one model is a different thing from a
summary from another, and a reader must be able to tell which one is in front of
them.

#### Scenario: Computing twice does not redo the work

- **WHEN** summaries are computed for a dossier that already has them
- **THEN** existing summaries are left as they are and only missing ones are made

#### Scenario: The provenance travels with the text

- **WHEN** a summary is shown
- **THEN** the model that produced it and the moment it was produced are shown
  with it

### Requirement: Een samenvatting is een bewering en staat niet in de plaats van het citaat

A summary SHALL be presented as generated text, distinguishable from the
fragment quoted from the stored document, and the fragment SHALL remain
available alongside it.

Everything else this system shows can be traced back to something stored: the
pseudonymised text, the tokens, the ranking. A sentence written by a model
cannot. Presenting it as equal to a quotation invites a reader to trust it the
same way.

#### Scenario: A result carries both

- **WHEN** a document with a summary appears in a result
- **THEN** both the summary and the quoted fragment are shown, and the summary is
  marked as generated

#### Scenario: A document without a summary says so

- **WHEN** a document without a summary appears in a result
- **THEN** the fragment is shown and the absence is stated, rather than left blank

### Requirement: Een mislukte generatie levert geen samenvatting op

A generation that fails or returns nothing SHALL leave the document without a
summary and SHALL be counted in the result of the run.

A placeholder that looks like content is worse than an empty field: it is read
as a summary of a document that nobody summarised.

#### Scenario: A failure is visible and leaves nothing behind

- **WHEN** the model fails for a document
- **THEN** no summary is stored for it and the run reports how many failed

### Requirement: Een samenvatting staat achter dezelfde poort als het corpus

A summary SHALL be readable only by callers permitted to read the corpus, and
SHALL NOT appear in exports, URLs or facets.

It is derived from pseudonymised text and can therefore carry pseudonym tokens.
That is the safe form on a screen that is already behind the corpus gate; it is
not the safe form somewhere the reveal gate never looks.

#### Scenario: The corpus gate applies

- **WHEN** a caller who may not read the corpus asks for a summary
- **THEN** it is refused, exactly as the stored text is refused
