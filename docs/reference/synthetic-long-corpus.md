---
status: draft
last_reviewed: 2026-11-15
---

# Synthetic long corpus

Real Woo publications are long PDFs: covers, e-mail threads, minutes, tables,
page headers and footers, and scanned pages. The ~500-document corpus
(`scripts/eval/generate_ground_truth.py`, `docs/reference/evaluation.md`)
writes short plain-text documents and cannot test page boundaries,
long-document ranking, or pages without a text layer. This generator does.

## Running

```bash
python scripts/eval/generate_long_corpus.py OUTDIR \
    --docs 30 --pages 30 --seed 20261115 [--scanned 0.1]
```

| flag | default | meaning |
| --- | --- | --- |
| `--docs` | 30 | number of documents |
| `--pages` | 30 | pages per document |
| `--seed` | 20261115 | rng seed; same seed, options and environment give byte-identical output |
| `--scanned` | 0.1 | fraction of a document's pages (rounded down) rendered as image-only pages |

## Output

| file | read by |
| --- | --- |
| `documents/<doc-id>.pdf` | ingestion, or `python -m wordsworth.pdf_text` by hand |
| `gold.jsonl` | `python -m wordsworth.eval.pii_run` |
| `gold_scanned.jsonl` | nothing that scores a number — see below |
| `queries.tsv` + `qrels.txt` | `python -m wordsworth.eval.run` |
| `manifest.json` | what was seeded, so a measurement can be checked |

Each document is a born-digital PDF built from six parts (a cover, a table of
contents, letters, e-mail threads, minutes, tables), with a header and footer
on every page: `pagina x van y`, a document number shaped `WOO-<year>-<4
digits>` (never a bare 9-digit number or a postcode shape, so it cannot be
mistaken for PII), and the word `SYNTHETISCH`.

### Gold format

One line per **born-digital** page, in the format
`wordsworth.eval.pii.load_gold` reads, plus two keys it ignores:

```json
{"id": "<doc-id>#p<NN>", "doc": "<doc-id>", "page": N,
 "text": "<that page's extracted text>",
 "entities": [{"start": 0, "end": 10, "type": "BSN"}]}
```

`text` is the page's extracted text (`wordsworth.pdf_text.page_text` over the
pypdfium2 page) — the exact string the detectors scan. The generator plants a
value, renders the page, then locates that value in the extracted text to
compute its offset; a value not found exactly once fails the generator, so
`load_gold`'s range check always holds and detection can be compared to gold
offset-exact.

Consequences for reading a number off this corpus: `pii_run` reports
`documents=<number of pages>` (about 900 for 30 x 30, minus the scanned
pages), and gold ids are not qrels ids — qrels use the PDF stem (`<doc-id>`),
the gold the page id (`<doc-id>#p<NN>`), with the document in the `doc` field.

### Scanned pages

`--scanned` is a fraction of a document's pages, rounded down, drawn from the
seed, never page 1 and never the page holding that document's planted
answer. Each chosen page is rasterised from its own text (pypdfium2, as
`wordsworth.pdf_render` does) and re-embedded as an image-only page: no text
layer. Such a page is still classified born-digital (`profile_pdf` counts
characters per document), so it never reaches OCR — **that page's text is
lost without a trace**. This does not exercise OCR; whole scanned documents
for OCR recovery are a separate change.

`gold_scanned.jsonl` holds the same per-page records for those pages, kept
apart — their `text` is the text that was rasterised, since there is no text
layer left to extract. **They are not part of the score to quote**:
`pii_run` detects over gold text and never opens a PDF, so scoring a scanned
page would count a page the pipeline cannot see as if extraction were
perfect.

### Queries

One query per document: `queries.tsv` holds the planted answer phrase
verbatim, equal to `answer_phrase` in `manifest.json`. The phrase sits on a
page at or after page 20 (or the document's last page, if shorter), and in no
other document. `qrels.txt` judges every document for every query. Because
`wordsworth.eval.run` scores whole documents and the query is the verbatim
phrase, this measures whether a long document still ranks when its one
matching passage is deep inside it (`long-documents-rank-fairly`) — a phrase
lookup, not semantic or passage search.

## What this does and does not measure

The PII score read off this corpus comes from `pii_run` reading the gold
text, not from the pipeline reading the PDFs. This generator adds page-level
localisation, the scanned-page split, and a real long corpus for
`scripts/eval/ingest_eval_corpus.py`; it does not make the PII measurement
end-to-end — that would read the generated PDFs themselves and is a separate
change.

## Personal data is synthetic and cannot be anyone's

- Names come from the existing fictional lists (`wordsworth.eval.synthetic`),
  including names with particles ("van der", "de", "ter").
- BSNs are drawn only from the published Logius test range
  999990000-999999999 (`bsn_test_range`), still passing the elfproef.
- IBANs use the bank code `ZZZZ` (`iban_fake_bank`), which no Dutch bank
  holds, still passing mod-97.
- Telephone numbers, e-mail addresses, street addresses, postcodes and dates
  of birth are generated the same way the existing 500-document corpus
  generates its values.

## Reproducibility

The same seed, options and environment give byte-identical files. The
scanned pixels come from pdfium's rasteriser (pypdfium2) and Pillow's JPEG
encoder, so a different pypdfium2 or Pillow build may change their bytes; the
gold of born-digital pages is read from the extracted text, so it follows the
pdfium build too. `gold_scanned.jsonl` does not depend on pdfium rendering
(its text is read before rasterisation).
