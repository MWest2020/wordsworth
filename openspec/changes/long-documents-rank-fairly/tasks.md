# Tasks: long-documents-rank-fairly

## 1. The measurement collection
- [ ] 1.1 `scripts/eval/woo_known_items.py`: known-item queries from the file
      names of the documents in `herkomst.jsonl`, per-decision queries from
      the decision slugs, written as `queries.tsv` + `qrels.txt` keyed on
      `object_key`. The skip rule for names without subject words is in the
      script, with its count reported.
- [ ] 1.2 Document lengths in the collection, split in thirds.

## 2. Baseline
- [ ] 2.1 The current ranking on both sets: Recall@8, MRR, nDCG@10, overall
      and per length third. Written down before any change.

## 3. Candidate 1: rank by the fused RRF rank
- [ ] 3.1 Behind a setting, measured on both sets.
- [ ] 3.2 The windpark question as smoke test.

## 4. Candidate 2: passage embeddings
- [ ] 4.1 Offline, on the 200 Woo documents: passages, one embedding each,
      a document scored by its best passage. Measured on both sets.

## 5. Decide
- [ ] 5.1 Apply the rule in design.md, Decision 2. Write down which candidate
      meets it, or that neither does.
- [ ] 5.2 Build the winner for production (if any), make it the default,
      deploy, and run the windpark question through `/ask`.
