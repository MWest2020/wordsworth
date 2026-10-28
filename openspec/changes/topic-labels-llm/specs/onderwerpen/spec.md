## ADDED Requirements

### Requirement: Topics carry a readable label written by the in-cluster model

After a topic computation, labelling SHALL give each topic a label of at most
six words and a one-line description, written by the configured in-cluster
language model from the summaries of the topic's most central documents and its
terms. The label SHALL be stored and shown as a model's claim, with model and
date, alongside the TF-IDF terms. An invalid or missing answer SHALL leave the
TF-IDF name in place. A name given by a person SHALL take precedence.

#### Scenario: A topic gets a label

- **WHEN** labelling runs and the model answers with a valid label
- **THEN** the topic shows that label, a description, the model and the date, and the TF-IDF terms as subtitle

#### Scenario: An invalid answer is rejected

- **WHEN** the model answers with a label that contains a token placeholder or a URL
- **THEN** the topic keeps its TF-IDF name

#### Scenario: The model is down

- **WHEN** labelling runs while the model is unreachable
- **THEN** no topic loses its name and the answer says how many were labelled
