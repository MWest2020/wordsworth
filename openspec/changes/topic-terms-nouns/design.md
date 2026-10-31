# Design: topic-terms-nouns

## Where it goes

`topics.terms_of(text)` is the one place a document's terms come from.

- It becomes `terms_of(text, nlp)`. `nlp` is a loaded spaCy pipeline, loaded
  once per `compute` call and not per document.
- It returns the lower-cased token texts that pass all three tests:
  `pos_ in {"NOUN", "PROPN"}`, `dep_ != "fixed"`, and `usable_name`.
- `name_for` does not change. It already scores whatever terms it receives.

## Model and licence

- spaCy is MIT.
- `nl_core_news_sm` 3.8.0 is CC BY-SA 4.0, trained on UD Dutch and others.
  We use it unchanged and don't redistribute a modified model. Attribution
  goes in `NOTICE`.
- Pin the model's wheel as a direct URL dependency in `pyproject.toml`, so
  `uv.lock` records its hash.
- Only the parser and tagger are needed: load with
  `exclude=["ner", "lemmatizer"]`. NER is wordsworth's own business and must
  not run here.

## Cost

The small pipeline tags in the order of 10k words per second on one core. A
dossier of 415 documents is a matter of minutes at worst, inside a
computation that already runs on request.

To keep that bounded on long scans, tag at most the first 20,000 characters
per document. Topics are named from what a group shares, so a cap per
document doesn't change which terms a group has in common.

## Duplicate names

After every topic has its `name_for` terms:
- Walk the topics in display order, keeping the names already used.
- On a clash, replace the last term with the next scored noun that isn't in
  the name yet.
- If there is none, append ` (2)`.

To make that possible, `name_for` grows an optional `skip` set; it returns
the same result as today when `skip` is empty.

## Not chosen

- **A general-language frequency cut-off:** measured and rejected (see the
  proposal).
- **A hand list of "general" words:** endless, and it bakes one person's
  judgment into code.
- **Tagging single terms out of context:** measured and wrong.
