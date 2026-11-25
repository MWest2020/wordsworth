## ADDED Requirements

### Requirement: Topics carry a readable label written by the in-cluster model

Labelling SHALL give a topic a label of at most six words and a one-line
description, written by the configured in-cluster language model from the
summaries of the topic's most central documents and its terms. The label SHALL
be stored and shown as a model's claim, with model and date, alongside the
TF-IDF terms. A label or description that contains a pseudonym token, a
bracketed placeholder or a URL, or a label of more than six words, SHALL be
rejected, and the topic SHALL keep the name it had. A name given by a person SHALL take precedence over a label.

#### Scenario: A topic gets a label

- **WHEN** a topic is labelled and the model answers with a valid label
- **THEN** the topic shows that label, a description, the model and the date, and the TF-IDF terms as subtitle

#### Scenario: An invalid answer is rejected

- **WHEN** the model answers with a label that contains a pseudonym token or a URL
- **THEN** the topic keeps the name it had and the answer says the label was rejected

#### Scenario: A person's name wins

- **WHEN** a topic has both a name given by a person and a label
- **THEN** the name given by the person is shown

### Requirement: Labelling a dossier is a command and the API labels one topic

Labelling every topic of a dossier SHALL be a command
(`python -m wordsworth.onderwerpen_labelen --dossier <name>`) that reports in
one line how many topics it saw, labelled, rejected, skipped, found without
summaries and failed, and ends with a non-zero exit code when a model call failed or the search index
was unreachable. The API SHALL label one topic per call and SHALL NOT offer a
call that labels a whole dossier. A topic computation SHALL NOT call the model.

Labelling SHALL never be silent about what it did not do: when the model is
unreachable no topic loses its name and the result says how many were
labelled, and when the search index is unreachable nothing is labelled and the
result says so.

#### Scenario: The command labels a dossier

- **WHEN** the command runs for a dossier with three topics without a label and the model answers validly
- **THEN** the three topics have a label and the result line says three were labelled

#### Scenario: A second run does not repeat the work

- **WHEN** the command runs again for a dossier whose topics all have a label
- **THEN** the model is not called, the result line says all were skipped, and the exit code is 0

#### Scenario: One topic is labelled through the API

- **WHEN** a caller who may read the corpus asks to label one topic
- **THEN** that topic is labelled and no other topic changes

#### Scenario: A caller who may not read the corpus

- **WHEN** a caller who may not read the corpus asks to label a topic
- **THEN** the call is refused and the model is not called

#### Scenario: The console button does not wait for the model

- **WHEN** a reader presses the label button of a topic in the console
- **THEN** the page returns at once saying the label is being written, and the label is stored when the model has answered

#### Scenario: A topic without summaries

- **WHEN** none of a topic's central documents has a summary
- **THEN** the model is not called, the topic keeps its name and the result says it had no summaries

#### Scenario: The model is down

- **WHEN** labelling runs while the model is unreachable
- **THEN** no topic loses its name and the result says how many were labelled

#### Scenario: The search index is down

- **WHEN** labelling runs while the search index is unreachable
- **THEN** no topic is labelled, no name changes and the result says the index was unreachable
