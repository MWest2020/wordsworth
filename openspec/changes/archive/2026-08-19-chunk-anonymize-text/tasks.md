## 1. Chunking

- [x] 1.1 `_chunk_text` splits on line boundaries to ≤ max chars, lossless concat.
- [x] 1.2 `_redact_one` = single anonymize call; `_openanonymiser_redact` chunks +
  reassembles + sums counts.
- [x] 1.3 Config `WORDSWORTH_ANONYMIZE_CHUNK_CHARS` (default 4000).

## 2. Gate

- [x] 2.1 Tests: lossless concat, hard-split, reassembly + count-sum.
- [x] 2.2 Full suite green + `openspec validate --all`.
