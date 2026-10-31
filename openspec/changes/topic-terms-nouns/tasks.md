# Tasks

## 1. Nouns only
- [ ] Add `spacy` and the pinned `nl_core_news_sm` 3.8.0 wheel (direct URL) to
      `pyproject.toml`/`uv.lock`; `NOTICE` gets the CC BY-SA 4.0 attribution.
      Proved by: the image builds and `python -c "import spacy;
      spacy.load('nl_core_news_sm')"` runs in it.
- [ ] `terms_of(text, nlp)` keeps only NOUN/PROPN tokens whose dependency is
      not `fixed`, after `without_tokens` and with `usable_name`. Proved by a
      test on synthetic sentences: "Iedereen steunt de duurzaamheid van het
      plan." yields "duurzaamheid" and "plan" but not "iedereen"/"steunt";
      "Wij feliciteren u van harte." yields no "harte"; "De concentraties lood
      zijn te hoog volgens de recente meting." yields "concentraties", "lood",
      "meting" and not "recente".
- [ ] The pipeline loads once per `compute` call, without NER. Proved by: a
      test that counts loads.
- [ ] At most 20,000 characters per document are tagged. Proved by: a test
      with a long text.
## 2. Unique names
- [ ] Two topics in one dossier never show the same computed name. Proved by:
      a test with two groups that share their top three terms.
## 3. Docs
- [ ] `docs/how-to/topics.md`: why only nouns, the measurement in the
      proposal, the model and its licence.
