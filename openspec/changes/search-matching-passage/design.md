# Design: search-matching-passage

## Decisions

- **Offsets, not text, in the index.** The passage text is already the stored
  pseudonymised text; storing offsets keeps one source and nothing new to
  scrub. The fragment is cut from the stored text with them, so it stays a
  quotation.
- **Best passage from the kNN inner hit.** The nested passage kNN can return
  the matching inner hit; its offset pair names the passage.
- **Reason in plain words.** Lexical overlap (query terms present in the
  passage) and vector similarity are both known per hit; the reason states
  which applied.
- **Fallback.** A document without offsets (not yet backfilled) keeps today's
  fragment, so the page never shows less than now.
