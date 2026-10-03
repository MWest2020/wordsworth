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
- [ ] 4.1 Offline, on the 200 Woo documents: passages, one embedding each,
      a document scored by its best passage. Measured on both sets.

## 5. Decide
- [ ] 5.1 Apply the rule in design.md, Decision 2. Write down which candidate
      meets it, or that neither does.
- [ ] 5.2 Build the winner for production (if any), make it the default,
      deploy, and run the windpark question through `/ask`.
