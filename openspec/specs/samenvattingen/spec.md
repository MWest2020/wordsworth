# samenvattingen Specification

## Purpose

Laten zien waaróm een document bovenaan staat, en niet alleen dát het er staat.

Een samenvatting hoort bij het **document**, niet bij de vraag: hem per
zoekopdracht maken is traag en levert morgen een andere tekst op dezelfde vraag.

Er zijn twee soorten, en het verschil is niet kwaliteit maar wat de tekst **is**:

- **extractief** — regels die letterlijk uit het opgeslagen document komen. Een
  citaat, net als het fragment ernaast. Je kunt het terugvinden.
- **gegenereerd** — een zin die een taalmodel schreef. Een bewering.

Alles wat dit systeem verder toont is terug te voeren op iets dat is opgeslagen.
Een gegenereerde samenvatting is de enige uitzondering, en daarom draagt hij
altijd zijn herkomst mee en staat hij náást het citaat in plaats van ervoor in
de plaats.

Daarom staat hier ook wat een samenvatting níet mag zijn: een tekst met een
pseudonym-token erin (een model kan er een verzinnen, en tokens lossen op via
een globale store — dan staat er een vreemde in dit document), een placeholder
waar de generatie mislukte (die wordt gelezen als inhoud), of een veld dat
buiten de corpus-leespoort belandt.

## Requirements

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

### Requirement: Er zijn twee soorten samenvatting, en het scherm zegt welke

The system SHALL support two kinds of summary for a document: an **extractive**
one, made of lines taken verbatim from the stored text, and a **generated** one,
written by a language model. Which kind a stored summary is SHALL be recorded
with it and SHALL be visible wherever it is shown.

The difference is not a matter of quality but of what the text *is*. An
extractive summary is a quotation: it can be found back in the stored document,
exactly like the fragment beside it. A generated one is a claim. Everything else
this system shows is traceable to something stored; presenting the two as the
same invites a reader to trust them the same way.

The choice SHALL be made per run, not per installation: the same corpus can
warrant one kind today and the other once different hardware is available.

#### Scenario: An extractive summary is presented as a quotation

- **WHEN** an extractive summary is shown
- **THEN** it is marked as taken verbatim from the document

#### Scenario: A generated summary is presented as a claim

- **WHEN** a generated summary is shown
- **THEN** it is marked as generated, with the model that wrote it

#### Scenario: Skipping is allowed, inventing is not

- **WHEN** an extractive summary is made
- **THEN** every part of it occurs verbatim in the stored text of that document

### Requirement: Een mislukte generatie levert geen samenvatting op

A generation that fails or returns nothing SHALL leave the document without a
summary and SHALL be counted in the result of the run.

A placeholder that looks like content is worse than an empty field: it is read
as a summary of a document that nobody summarised.

#### Scenario: A failure is visible and leaves nothing behind

- **WHEN** the model fails for a document
- **THEN** no summary is stored for it and the run reports how many failed

### Requirement: Een samenvatting draagt geen pseudonym-token

A stored summary SHALL contain no pseudonym token, and the removal SHALL happen
after generation rather than being left to the model's instruction.

A quotation cannot invent a token; generated text can. Tokens resolve through a
global mapping store, so an invented `[PERSOON:aabbccdd]` is not nonsense — it
is somebody, just not somebody in this document. A summary carrying it ties a
stranger to this document, and a reveal on that summary hands out that
stranger's clear name inside a grant scoped to this document. That is the hole
`neutralise_foreign_tokens` closes on the way in, here on the way out.

#### Scenario: A model that emits a token does not get to keep it

- **WHEN** the generated text contains a pseudonym token
- **THEN** the stored summary does not contain it

### Requirement: Een samenvatting staat achter dezelfde poort als het corpus

A summary SHALL be readable only by callers permitted to read the corpus, and
SHALL NOT appear in exports, URLs or facets.

It is derived from the corpus and says what a document is about. That is the
same kind of knowledge as the stored text, and it belongs behind the same gate.

#### Scenario: The corpus gate applies

- **WHEN** a caller who may not read the corpus asks for a summary
- **THEN** it is refused, exactly as the stored text is refused

### Requirement: Samenvatten heeft een eigen commando

Het samenvatten SHALL aan te roepen zijn als commando
(`python -m wordsworth.samenvatten`), met een of meer dossiers of met
"alles wat nog geen samenvatting heeft" als invoer. Het commando SHALL
idempotent zijn: een tweede run maakt geen bestaande samenvatting
opnieuw. Het SHALL in één regel rapporteren hoeveel documenten gezien,
gemaakt, overgeslagen en mislukt zijn, en met een exitcode ongelijk aan
nul eindigen als er iets mislukte. Een cluster-Job SHALL dit commando
aanroepen in plaats van een script mee te dragen in zijn argumenten.

#### Scenario: Tweede run doet het werk niet opnieuw

- **GIVEN** een dossier waarvan alle documenten al een samenvatting
  hebben
- **WHEN** het commando opnieuw draait
- **THEN** wordt de generator niet aangeroepen, meldt de uitvoer dat
  alles is overgeslagen, en is de exitcode 0

#### Scenario: Eén document mislukt

- **GIVEN** een dossier waarvan één document geen tekst heeft en de
  rest wel
- **WHEN** het commando draait
- **THEN** worden de overige samenvattingen gemaakt, noemt de uitvoer
  het mislukte aantal, en is de exitcode ongelijk aan nul
