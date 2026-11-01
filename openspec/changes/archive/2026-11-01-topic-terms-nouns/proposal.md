# topic-terms-nouns

## Why

Mark, 2026-10-31, on the topics of the 415-document pilot dossier: *"the
keywords in topics are too general. 'concentraties' can be a good word.
'iedereen' not. 'duurzaamheid' yes, 'harte' not."* The names he saw included
`iedereen · ruil · steunt`, `overeen · recente · volgen`, `besloot · harte ·
nabijheid`. They also showed `zaal · vergadertijd · rondvraag` twice, for two
different topics.

TF-IDF picks terms that are frequent in a group and rare in the dossier. It
does not know what kind of word it picks, so pronouns, verbs, adjectives and
the noun half of a fixed expression ("van harte") get in.

Measured on the 33 words in Mark's list, 2026-10-31:
- **A general-Dutch frequency cut-off (wordfreq Zipf) does not separate
  them.** "harte" (4.42) is more common than "duurzaamheid" (4.14), but
  "veiligheid" (4.96) is more common than both.
- **Tagging single words is wrong.** spaCy `nl_core_news_sm` tags
  "vergadertijd" as ADJ and "rondvraag" as ADV.
- **Tagged in their sentence, nouns that aren't part of a fixed expression
  match every judgment Mark gave.**
  - Out: "iedereen" (PRON), "volgen" (VERB), "recente" (ADJ), "harte" (NOUN
    with dependency `fixed` in "van harte").
  - In: "duurzaamheid", "concentraties", "lood", "rondvraag",
    "vergadertijd", "zaaknummer" (NOUN).

## What changes

- **Only nouns name a topic.** A term counts for naming only where it occurs
  as a noun (`NOUN` or `PROPN`) in its sentence, and not as part of a fixed
  expression (dependency `fixed`). The tagging runs on the document text with
  the pseudonym tokens already removed (`without_tokens`). Pseudonym tokens
  never reach a name; that rule stays as it is.
- **The existing thresholds stay:** the group share, the corpus floor and the
  digit and stopword filter. Only the candidate terms change.
- **No two topics in a dossier show the same name.** When two topics would
  get the same three terms, the later one in display order takes its next
  distinguishing noun instead of the third term.
- **The model is the Dutch spaCy pipeline `nl_core_news_sm`**, pinned by
  version and installed in the image. The cluster pulls nothing at runtime.

## Out of scope

- The clustering, and how many documents end up in a topic.
- The language-model label: that is `topic-labels-llm`, which builds on these
  terms as its subtitle.
