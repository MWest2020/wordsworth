# Design: long-documents-rank-fairly

## Decision 1 — a collection derived from what the publisher recorded

No qrels exist for the Woo corpus, and judging relevance by hand is a person's
work. Two sets can be derived from facts the publisher recorded, without anyone
judging:

- **Known-item, per document.** Each document's file name is its publisher's
  label for it (`RE_WP_Echteld_Lienden_Verweerschrift_natuur_PRDF..._msg`).
  Stripped of ids, extensions and mail prefixes, it becomes the query, and the
  one relevant document is that document. Names without subject words
  (`Image_3_jpg`) are skipped by a stated rule, not by choice per case.
- **Per decision.** `herkomst.jsonl` records each document's Woo decision
  page. The decision's title, from its URL slug, is the query; the documents of
  that decision are the relevant set. Seven decisions, of 2 to 118 documents:
  too coarse alone, a check on the first set.

**Its bias, said before any number:** queries made of title words favour
keyword matching, and so favour any candidate that leans on BM25 — candidate
1 more than candidate 2. The comparison is still fair *between* two rankers fed
the same queries, but a win for candidate 1 is a weaker claim than a win for
candidate 2. A hand-judged set of real questions is the step after this one if
the two candidates come out close.

## Decision 2 — what is measured, and how a winner is chosen

Metrics: Recall@8 (the k `/ask` uses), MRR and nDCG@10, each overall and per
length third (short, middle, long).

~~The rule: a candidate replaces the current ranking only if it is better on
the long third **and** no third is worse than in the baseline.~~

**Corrected 2026-10-04, decided by Mark: the spec's goal decides** -- Recall@8
for the longest third at least that of the shortest. The struck rule measured
against the baseline, whose short third is high *because* of the bias it was
meant to remove, so any ranker that removes the bias lowers it, and the rule
and the goal excluded each other (tasks.md 4.1). A candidate is measured
against a length-neutral reference instead: the goal itself, and alongside it
BM25 alone, which has no length slope on this collection. A candidate that
meets the goal but loses more overall than it gains on long documents is
still reported, not quietly accepted.

The windpark question that started this is the smoke test, not the measure: one
question proves nothing about a ranker, but a ranker that still misses it has
not fixed what was reported.

## Decision 3 — candidate 1 first

The fused RRF rank already exists: the recall stage computes it and the cosine
stage throws it away. Ranking by it is a change of one sort key and costs
nothing at query time. Passage embeddings (candidate 2) mean re-embedding the
corpus in passages: hours on CPU, a new index layout, and query-time work that
grows with the number of passages. It is measured even if candidate 1 meets the
rule, because the comparison is the point; it is only built for production if
it wins.

## Decision 4 — the spec states the property

`hybrid-search` now names the mechanism ("Zeef cosine is the final selector").
Whatever wins, the requirement becomes the property the measurement checks: the
final ranking does not favour a document for being short. The mechanism moves to
this design, where a later measurement can change it without the spec claiming
something that stopped being true.

## Decision 5 — candidate 2a in production: nested passages on the document

Decided by the measurement and Mark's choice of the spec's goal (Decision 2,
corrected). How it is built:

- **Where the vectors live: a nested field `passages` on each document**, not a
  separate index. Probed on the running OpenSearch 2.19 before relying on it
  (throwaway index, 2026-10-04): nested k-NN with `score_mode: max` ranks a
  document by its best passage, and the dossier filter works *inside* the knn
  clause on the parent's fields -- the same placement `_scoped_knn` needs to
  keep small dossiers from coming back empty. A separate index would need every
  dossier and topic change mirrored onto its passages.
- **Passages are part of indexing**, whatever the search setting: both paths
  that index a document (ingest, re-anonymize) compute them from the text they
  write. `index()` replaces the whole document, so passages left out would be
  dropped -- the shape of the 2026-09-18 loss of 770 document vectors.
  Cost: one embedding per passage, ~6.9 s each on CPU as measured, so a long
  document takes minutes longer to ingest.
- **The backfill is a partial update** (`set_passages`), resumable, and ends
  even when a document cannot be done.
- **Search switches separately** (`WORDSWORTH_HYBRID_KNN`, default `document`)
  and only after the backfill: a document without passages is invisible to the
  passage kNN half. Final order stays `rrf` (candidate 1 is already live).
