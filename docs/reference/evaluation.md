---
status: draft
last_reviewed: 2026-09-03
---

# Evaluation run

wordsworth's IR evaluation (`wordsworth.eval`) computes R-Precision, Recall@10,
MAP, and NDCG@10 for the BM25 and hybrid configurations over a standard test
collection (TREC qrels + TSV queries), e.g. the thesis's 47 queries and
relevance judgments.

## Running

```
python -m wordsworth.eval.run --qrels qrels.txt --queries queries.tsv \
    --config bm25,hybrid [--k 10]
```

The report prints the four aggregate metrics per configuration.

## Precondition: id matching

The qrels reference documents by their native identifier; wordsworth assigns
its own uuid. **The evaluation corpus MUST be ingested with `object_key` equal
to the qrels' document ids.** The ranker adapters return `object_key`, so the
ranked ids and the qrels ids share one namespace. This is an operator
responsibility when loading the corpus — it is not solved in code, and a hit
without an `object_key` is a hard error (no silent fallbacks).

## Runtime requirements

- **BM25** (`--config bm25`): a running OpenSearch with the corpus indexed.
- **Hybrid** (`--config bm25,hybrid`): additionally local bge-m3 embeddings via
  Ollama. Everything runs locally — no cloud APIs in the critical path.

The run is deterministic and read-only: it writes nothing to the corpus, the
index, or the audit trail.

## Operator tooling

`scripts/eval/` holds the run scripts: `ingest_eval_corpus.py` (register a
corpus keyed on the qrels doc ids and push it through the pipeline into a
dedicated index) and `make_smoke_collection.py` (a synthetic pipe-cleaner
collection). See `scripts/eval/README.md` for the end-to-end procedure and
infrastructure notes.

## PII-detection evaluation

Separate from ranking quality: how well does the *deployed* detection seam find
PII? `wordsworth.eval.pii` scores the same `Entity` objects the pipeline uses
against a gold corpus.

```
python -m wordsworth.eval.pii_run gold.jsonl [--layers deterministic,openanonymiser] [--json]
```

- **Gold format:** JSONL, one document per line:
  `{"id": "...", "text": "...", "entities": [{"start": 10, "end": 25, "type": "PERSON"}]}`
  (character offsets, half-open, upper-case types; spans must be in range and
  non-overlapping — a malformed line is a hard error). Real gold corpora live
  outside the repo; `tests/fixtures/pii_gold_synthetic.jsonl` is a synthetic
  10-document smoke set with invented names and test BSNs.
- **Metrics:** precision / recall / F1 per type and overall, at **span** level
  (exact start/end/type) and **token** level (a whitespace token of a gold span
  counts when a same-type prediction covers it, so `van Dijk` for `Janine van
  Dijk` scores 2/3 recall); **`leaks`** = gold entities with no overlapping
  prediction of any type — the number that matters for the index invariant;
  **per layer** (`deterministic`, `openanonymiser`), each layer scored alone.
- **Runtime:** `--layers deterministic` runs offline; the `openanonymiser` layer
  needs the service at `WORDSWORTH_OPENANONYMISER_URL` (local, no cloud). A
  service failure is a hard error, never an empty result. Read-only: nothing is
  ingested, indexed or audited.

## Generating a corpus whose answer we know

Measurement 01 ran on 31 documents: enough to find a bug, too little to carry a
percentage. `scripts/eval/generate_ground_truth.py` writes ~500 documents and,
from the same run, everything needed to score them:

```bash
python scripts/eval/generate_ground_truth.py /tmp/gt --count 500
python -m wordsworth.eval.pii_run /tmp/gt/gold.jsonl --layers deterministic
```

| file | read by |
| --- | --- |
| `documents/*.txt` | ingestion |
| `gold.jsonl` | `wordsworth.eval.pii_run` |
| `queries.tsv` + `qrels.txt` | `wordsworth.eval.run` |
| `manifest.json` | what was seeded, and the caveat |

One generation, two evaluations, the same documents — two corpora give two
numbers that cannot be held next to each other.

The offsets are recorded by the step that writes the text, not by an annotation
pass over it afterwards. Two sources of truth about the same 500 documents
disagree quietly, and in the direction that flatters the score.

**Seeded on purpose**, from what measurement 01 actually met: postcodes behind
`Postbus` (in the text, *not* in the answers — an organisation's contact address
is not personal data), text arriving with a token-shaped string in it, and the
full `GENDER + DATE + POSTCODE` quasi-identifier in part of the corpus.

`GENDER` and a bare year of birth are carried but are deliberately **not gold**:
no detector emits them, and scoring a detector on what it never claimed to find
measures us rather than it.

Measured on 2026-09-17 over 500 generated documents, deterministic layer only:

```
documents=500  gold_entities=1700  leaks=500
overall/span: P=1.000 R=0.706 F1=0.828
  BSN P=1.000 R=1.000 | EMAIL P=1.000 R=1.000
  IBAN P=1.000 R=1.000 | POSTCODE P=1.000 R=1.000
  PERSON P=0.000 R=0.000  (fn=500)
```

The 500 leaks are all PERSON: the deterministic layer has no name detector, so
this is a finding about the *absence* of the GLiNER layer in that run, not about
its quality. The 123 seeded `Postbus` postcodes produced **zero** false
positives — the exception previously demonstrated on two lines of text holds at
corpus scale.

And the limit, which also travels inside `manifest.json`: this text was written
by us and is more regular than administrative reality. A score here is a lower
bound for the machinery, not a prediction for production.

## A real corpus, and what it can and cannot settle

The synthetic collections above settle the *machinery*: the state machine, the
metrics, the id matching. They cannot settle whether the straat survives a
thousand real Dutch government documents, because they were written by us.

`scripts/eval/fetch_woo_corpus.py` fetches published Woo (Freedom of
Information) documents into a directory that `ingest_eval_corpus.py` and
`ingest_corpus.py` accept. Measured 2026-09-13, the national portal
`open.overheid.nl` is closed to machines (401 plus `Disallow: /`) and so is at
least one municipal site behind a proof-of-work challenge; the provincial portal
`open.gelderland.nl` allows it and holds 848 decisions with direct PDF links.
The fetcher identifies itself, waits between requests, and records provenance
per document — a corpus whose origin is unrecorded makes every measurement on it
untraceable.

**What such a corpus settles:**

- **The pipeline.** End states, throughput, and the share that lands in
  `UNPROCESSABLE_OCR`. On a six-document sample, five were born-digital and one
  was a scan with zero extractable text, so both the ordinary path and OCR
  recovery are exercised — which the synthetic fixtures do only by construction.
- **Where PII used to be.** A Woo document carries its redaction ground in the
  text: `[5.1.2e]` is the article covering personal privacy. That is a real
  label, in a real document, marking a place where a personal detail was
  removed — and therefore a place where detection should find nothing.

**What it does not settle, and this distinction matters more than the corpus:**

- **Ranking quality, judged.** Graded relevance for real questions needs a
  person. A *derived* collection does exist since 2026-10-03, see below; it
  measures ranking without anyone judging, with a stated bias.
- **Detection precision and recall.** `pii_run` needs a gold file with character
  offsets. A real corpus has no offsets, so it cannot produce precision, recall
  or a leak count. `pii_gold_synthetic.jsonl` remains the only labelled source.

"We have a real corpus now" reads easily as "we measure everything for real
now". It does not. The corpus buys reality about the pipeline, not about
quality.

**The measurement a real corpus does unlock**, and the one worth running: point
wordsworth at a published Woo decision and look at what was *not* redacted. On
the sample above, one provincial decision still carried a direct telephone
number and two e-mail addresses alongside the names of officials acting in
function. Does our anonymisation find the personal data that the publishing
authority left in? That question is checkable against the published document,
needs no annotation, and is the reason this system exists.

## Ranking on the real Woo corpus (derived collection)

`scripts/eval/woo_ranking_eval.py herkomst.jsonl OUT` builds a collection from
what the publisher recorded and scores a ranker on it, read-only. The rules are
in `wordsworth.eval.woo_collection` and tested:

- **known-item:** each document's file name, stripped of ids, mail prefixes and
  file types, is a query; the documents whose names give the same query are
  its relevant set. Names with fewer than two subject words are skipped.
- **per decision:** the Woo decision page in `herkomst.jsonl`, its URL slug as
  the query, its documents as the relevant set.

Bias, stated before any number: title words favour keyword matching. The
collection is fair between two rankers fed the same queries; a win for a ranker
that leans on BM25 is the weaker claim.

Baseline, 2026-10-03, production index (194 of the 200 Woo documents linked;
the 6 unlinked are the OCR-recovered ones, which never got a file name; 116
known-item queries, 90 of them with a single document). Recall@8, the k `/ask`
uses, by length third of the known item:

| ranker | short (133-1303 chars) | middle (1319-3955) | long (4069-86352) | all |
|---|---|---|---|---|
| hybrid, production (RRF recall + cosine) | 0.692 | 0.103 | **0.000** | 0.219 |
| BM25 alone (reference) | 0.615 | 0.793 | 0.686 | 0.684 |

The production ranking does not find a long document by its own title, not once
in 35. BM25 has no such slope. That is the short-document bias of change
`long-documents-rank-fairly`, measured.

The runner scores hybrid search in three configurations side by side, explicitly
and not through the settings: final order `cosine` or `rrf`
(`WORDSWORTH_HYBRID_FINAL_RANK`), and the kNN half over whole documents or
passages (`WORDSWORTH_HYBRID_KNN`, candidate 2a), plus BM25 alone. Passage kNN
only sees documents that have passages, so its numbers mean something only
after `wordsworth-backfill-passages` has finished.

Outcome, 2026-10-05 (full index, all 200 Woo documents linked): the fused RRF
rank over BM25 and whole-document kNN is the default (Recall@8 by third
0.731 / 0.355 / 0.400). Passage kNN narrowed the length gap (0.538 / 0.387 /
0.514) but flipped the bias -- its top 8 for the windpark question were all
long documents -- so it is not used for search.

## The published-dossier pilot (ingest-records-source)

The MVP walking skeleton: **one published municipal publication, ingested as
one dossier**, run end to end (ingest → anonymize → rank → a person checks
both). Not a measurement of general quality — a scoped search in a dossier of
10 to 30 documents returns the one relevant document whatever the ranker
does, so the ranking step cannot fail on its own. The pilot proves the
pipeline runs on a real publication, nothing more.

Published documents only — see the non-goal below.

| part | what |
| --- | --- |
| corpus | one municipal publication (e.g. Gooise Meren) as one dossier, 10 to 30 real documents, fetched by hand; the report records who checked `robots.txt` and the terms, and when |
| ranking gate | at least 5 questions, each with its expected document, written **before** any result is seen; pass when the expected document is in the top 8 for at least 4 of 5 — gates this pilot run only |
| PII gate | a person reads the full `/anonymized` text of every pilot document against the source; any residual direct identifier of a private person (BSN, IBAN, e-mail, phone, name, home address) fails the pilot, unless that document is excluded with the reason written down |
| also reported, not gates | residual count, placeholder count, the ORGANIZATION over-redaction rate; officials' names without a public role, as a separate finding |
| a layer that did not run | counts as failed, e.g. a NER backend that is down |

**Gold set.** Offsets and hash only (`sha256, start, end, type`), no PII text
in git — this works only because a published source can be rebuilt from the
public PDF. Do not generalise the rule: unpublished documents need their own
data-handling decision.

**No recall claim from published material.** Published Woo material has
already been redacted by the municipality before wordsworth ever sees it. A
pilot on it can show residual identifiers and over-redaction, but it cannot
show what wordsworth would have missed had it been the one redacting from
the unredacted original — there is no unredacted original in this pilot to
miss anything against. **The pilot report does not use the word "recall" for
PII**, and anonymisation of *unpublished* documents remains unproven by this
pilot.

Provenance for the pilot corpus is recorded at ingest via `source_url` and
`fetched_at` (see `docs/reference/ingest.md`), not read back out of an eval
script's `herkomst.jsonl` after the fact.

**Ingest order (pilot-ingest-manifest).** `wordsworth-ingest --manifest`
proves this rather than merely promising it: the gate runs check, then
manifest, then ingest. The script refuses a manifest whose pilot report has
no completed robots/terms/Anubis check recording who, when, the quoted
`robots.txt` and terms, the Anubis status and the decision `proceed` — a
`stop` decision stops the pilot. Git order (the check committed before the
manifest) is proven by the pilot report's own commit history, not by the
script. A layer that did not run during ingest, OpenAnonymiser being down
included, fails that document and the whole run exits non-zero — it is never
reported as a success with a note (see "a layer that did not run" in the
table above).

`scripts/eval/woo_passage_eval.py herkomst.jsonl CACHE.json` measures candidate
2 (passage embeddings, `wordsworth.eval.passages`: 200-word windows every 150
words, a document scored by its best passage). Passages exist only for the Woo
documents, so it measures **every** configuration inside that one pool --
BM25 filtered to the pool's ids, kNN exact in-process -- and its absolute
numbers are not comparable with the full-index ones above; the comparison
between configurations is. The passage vectors are cached, so a dropped run
resumes.
