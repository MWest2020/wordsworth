# Tasks: long-documents-rank-fairly

## 1. The measurement collection
- [x] 1.1 `scripts/eval/woo_known_items.py`: known-item queries from the file
      names of the documents in `herkomst.jsonl`, per-decision queries from
      the decision slugs, written as `queries.tsv` + `qrels.txt` keyed on
      `object_key`. The skip rule for names without subject words is in the
      script, with its count reported.
- [x] 1.2 Document lengths in the collection, split in thirds.

## 2. Baseline
- [x] 2.1 The current ranking on both sets: Recall@8, MRR, nDCG@10, overall
      and per length third. Written down before any change.

      Done 2026-10-03 on the production index (`scripts/eval/woo_ranking_eval.py`,
      read-only). Collection: 194 of 200 documents linked (the 6 unlinked are
      the OCR-recovered ones, which have no file name), 41 names skipped as
      subjectless, 116 known-item queries (90 with one document), 7 decision
      queries. Length thirds: 133-1303, 1319-3955, 4069-86352 characters.

      | | known-item short | middle | long | all | decision |
      |---|---|---|---|---|---|
      | hybrid (production) Recall@8 | 0.692 | 0.103 | **0.000** | 0.219 | 0.086 |
      | hybrid MRR | 0.429 | 0.108 | 0.022 | 0.175 | 0.491 |
      | BM25 (reference) Recall@8 | 0.615 | 0.793 | 0.686 | 0.684 | 0.473 |
      | BM25 MRR | 0.395 | 0.513 | 0.447 | 0.462 | 0.929 |

      Not one of 35 long documents reaches the top 8 for its own title in
      production; BM25 has no length slope. Title queries favour BM25 (stated
      in design Decision 1), but that cannot make a 0.69 -> 0.10 -> 0.00
      gradient inside one ranker.

## 3. Candidate 1: rank by the fused RRF rank
- [x] 3.1 Behind a setting, measured on both sets.
- [x] 3.2 The windpark question as smoke test.

      Done 2026-10-03. `WORDSWORTH_HYBRID_FINAL_RANK` = `cosine` (default) |
      `rrf` (#186, deployed as `dc95cb9` with the default unchanged; the
      evaluation ran on that image, both orders side by side):

      | | short | middle | long | all | decision |
      |---|---|---|---|---|---|
      | Recall@8 cosine (production) | 0.692 | 0.103 | 0.000 | 0.219 | 0.086 |
      | Recall@8 **rrf** | **0.731** | **0.345** | **0.400** | **0.477** | **0.315** |
      | Recall@8 BM25 (reference) | 0.615 | 0.793 | 0.686 | 0.684 | 0.473 |
      | MRR cosine / rrf | 0.429 / 0.517 | 0.108 / 0.199 | 0.022 / 0.119 | 0.175 / 0.276 | 0.491 / 0.726 |
      | nDCG@10 cosine / rrf | 0.504 / 0.574 | 0.091 / 0.241 | 0.000 / 0.212 | 0.169 / 0.330 | 0.304 / 0.519 |

      Better on every metric in every third, so it meets the design's rule
      (better on long, no third worse). It does **not** meet the spec's
      property, Recall@8 long >= short: 0.400 against 0.731. RRF fuses BM25
      with the same whole-document kNN list, which carries the bias in half
      its input.

      Smoke test: the windpark question under `rrf` puts a windpark document
      **first** (9600 characters); the top 8 run from 316 to 14039
      characters. Under `cosine`, none of the eight mention it.

      Production stays on `cosine` until task 5: candidate 2 is measured
      first, as the design says.

## 4. Candidate 2: passage embeddings
- [x] 4.1 Offline, on the 200 Woo documents: passages, one embedding each,
      a document scored by its best passage. Measured on both sets.

      Done 2026-10-03/04 (`scripts/eval/woo_passage_eval.py`, image
      `e773126`). 194 documents, 1034 passages of 200 words every 150,
      embedded in 7113 s (~6.9 s a passage on CPU). Every configuration in the
      same pool of 194, so these numbers are not the full-index ones of 2.1/3.1.

      | Recall@8 | short | middle | long | all | decision |
      |---|---|---|---|---|---|
      | cosine, whole document (production) | 0.769 | 0.103 | 0.000 | 0.241 | 0.138 |
      | rrf, whole document (candidate 1) | 0.846 | 0.345 | 0.257 | 0.450 | 0.285 |
      | rrf, passages (candidate 2a) | 0.538 | 0.448 | 0.629 | 0.521 | 0.319 |
      | best-passage cosine (candidate 2b) | 0.462 | 0.310 | 0.400 | 0.365 | 0.271 |
      | bm25 alone (reference) | 0.615 | 0.793 | 0.686 | 0.693 | 0.496 |

      | MRR / nDCG@10 | short | middle | long | all |
      |---|---|---|---|---|
      | production | 0.445 / 0.516 | 0.108 / 0.091 | 0.023 / 0.000 | 0.186 / 0.176 |
      | candidate 1 | 0.539 / 0.621 | 0.208 / 0.247 | 0.103 / 0.155 | 0.277 / 0.320 |
      | candidate 2a | 0.433 / 0.456 | 0.310 / 0.331 | 0.447 / 0.483 | 0.411 / 0.420 |
      | candidate 2b | 0.359 / 0.410 | 0.216 / 0.227 | 0.333 / 0.339 | 0.322 / 0.314 |

      **The design's two criteria exclude each other, and that is the
      finding.** Decision 2's rule -- better on long *and* no third worse than
      the baseline -- passes candidate 1 and rejects 2a (short 0.538 against
      0.769). The spec's property -- long >= short -- is met by 2a (0.629 >=
      0.538) and BM25, not by candidate 1 (0.257 against 0.846). The baseline's
      short third is high *because* of the bias, so "no third worse than the
      baseline" protects exactly what the change is meant to remove; any ranker
      that removes the bias lowers it. The rule should have been written
      against a length-neutral reference, not against the biased baseline.
      Not resolved here: which criterion holds is task 5, and Mark's.

## 5. Decide
- [x] 5.1 Apply the rule in design.md, Decision 2. Write down which candidate
      meets it, or that neither does.

      Decided 2026-10-04 by Mark: the spec's goal counts (Decision 2,
      corrected). **Candidate 2a meets it** (long 0.629 >= short 0.538 in the
      pool) and is the one built for production (5.2, issue #190).
      Candidate 1 does not (long 0.257 against short 0.846), but is better
      than production on every metric, so it went live as the interim step the
      same day: `WORDSWORTH_HYBRID_FINAL_RANK=rrf` (homelab `1ccfb51`), checked
      on both api pods through the default path -- the windpark question puts
      a windpark document first.
- [x] 5.2 Build the winner for production (if any), make it the default,
      deploy, and run the windpark question through `/ask`. Candidate 2a;
      tracked in issue #190.

      Built 2026-10-04 (design Decision 5): nested `passages` field, passages
      written at every indexing, `set_passages` + `wordsworth-backfill-passages`,
      `WORDSWORTH_HYBRID_KNN` (default `document`). Next: deploy, backfill,
      measure on the full index, switch.

      Backfill 2026-10-04/05: 611 documents, 3861 passages, 0 empty, 0 failed,
      5 h 57 min (Job `wordsworth-backfill-passages`); checked independently
      afterwards, 0 documents without passages.

      **Measured on the full production index -- not switched.** 200 Woo
      documents linked (the 6 OCR names restored, #194), 118 known-item and 7
      decision queries. Recall@8:

      | | short | middle | long | all | decision |
      |---|---|---|---|---|---|
      | cosine, document kNN | 0.692 | 0.097 | 0.000 | 0.214 | 0.076 |
      | **rrf, document kNN (candidate 1, live)** | 0.731 | 0.355 | 0.400 | 0.474 | 0.329 |
      | rrf, passage kNN (candidate 2a) | 0.538 | 0.387 | 0.514 | 0.459 | 0.227 |
      | rrf of bm25 + document + passage kNN (3, analysed) | 0.692 | 0.290 | 0.314 | 0.392 | 0.245 |
      | bm25 alone (reference) | 0.577 | 0.742 | 0.657 | 0.654 | 0.461 |

      MRR / nDCG@10 overall: candidate 1 0.274 / 0.318, 2a 0.403 / 0.389,
      3 0.266 / 0.275, bm25 0.448 / 0.493.

      - **2a misses the spec's goal on the full index**: long 0.514 against
        short 0.538 (in the 194-document pool it met it). The gap is smaller
        than one query in either third -- but the smoke test decides it:
      - **2a fails the windpark question**: none of its top 8 mention the
        windpark, and all eight are long (3719-28209 characters). Scoring a
        document by its best passage gives a long document one chance per
        passage; the bias flips instead of vanishing.
      - Fusing both kNN views with BM25 (3) is worse overall and also misses
        the windpark document.
      - **Candidate 1 stays live**: best Recall@8 overall, passes the smoke
        test. No hybrid meets the goal; BM25 alone does, and scores best on
        this title-word collection -- its stated bias. Whether the vector half
        helps real questions needs judged ones (#196).

      Per the spec delta, the requirement is not archived as if it held.
      **Decided 2026-10-05 by Mark: keep candidate 1 and revise the goal.**
      The requirement is renamed and rewritten (`The final ranking does not
      shut out long documents`): the fused rank, every third above zero and
      recorded per change, the remaining gap stated as a known limitation.
      The code default becomes `rrf` so the spec holds without the configmap. Passages stay in the index and are still
      computed at every indexing (~4.7 s a passage); switching that off is a
      one-line change if they will not be used.
