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

The rule, written as a property instead of a threshold: a candidate replaces
the current ranking only if it is better on the long third **and** no third is
worse than in the baseline. A candidate that buys long documents at the cost
of short ones moves the bias rather than removing it. If neither candidate
meets that, nothing changes, and the measurement is the result.

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
