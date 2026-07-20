<!-- SPDX-License-Identifier: EUPL-1.2 -->
# Evaluatierun — operator-tooling

Operator-scripts om een testcollectie door de wordsworth-pipeline te halen en
er de IR-metrics over te draaien. De bibliotheek zelf zit in
`src/wordsworth/eval/`; de contractuele beschrijving in
`docs/reference/evaluation.md`. Dit is het *hoe-draai-ik-het* eromheen.

De keten is end-to-end bewezen met de synthetische mini-collectie hieronder
(12 docs, 6 queries), met echte lokale bge-m3-embeddings:

```
bm25:   r_precision=0.8333  recall@10=0.8333  map=0.8333  ndcg@10=0.9201
hybrid: r_precision=0.7500  recall@10=1.0000  map=0.8819  ndcg@10=0.9634
```

## Wat de operator aanlevert

Een testcollectie in drie delen (bv. de thesis-collectie, Pilkes):

1. **`queries.tsv`** — één query per regel: `query-id<TAB>querytekst`
2. **`qrels.txt`** — TREC-formaat: `query-id 0 doc-id relevantie`
3. **corpus-PDF's** — één bestand per document, genoemd **`<doc-id>.pdf`**,
   waarbij `<doc-id>` exact het id uit de qrels is. De bestandsnaam wordt de
   `object_key`, zodat ranked ids en qrels-ids één naamruimte delen (de
   preconditie uit `docs/reference/evaluation.md`).

## Infrastructuur

- **OpenSearch** bereikbaar op `WORDSWORTH_OPENSEARCH_URL` (default
  `localhost:9200`).
- **Ollama + bge-m3** op `WORDSWORTH_OLLAMA_URL` (default `localhost:11434`)
  — nodig voor de hybrid-config. User-space installeren kan:
  download `ollama-linux-amd64.tar.zst` van de GitHub-release, uitpakken, en
  `OLLAMA_MODELS=<dir>/models <dir>/bin/ollama serve &`, dan `ollama pull bge-m3`.
- **PostgreSQL** — elke Postgres 16 volstaat (eigen eval-database, raakt
  productie niet). Zonder docker: `pgserver` (pip) geeft een embedded server;
  gebruik de socket-URL als `--db-url`.

## Draaien

Vanuit de repo-root, op actuele `main`:

```bash
# 1. Ingest — eigen index + eigen database
export WORDSWORTH_OPENSEARCH_INDEX=wordsworth-thesis-eval
uv run python scripts/eval/ingest_eval_corpus.py \
    --corpus-dir <map-met-pdfs> \
    --db-url "postgresql+psycopg://...(eval-db)..." \
    --embedder ollama

# 2. Evaluatie (read-only; schrijft niets naar corpus/index/audit)
uv run python -m wordsworth.eval.run \
    --qrels <qrels.txt> --queries <queries.tsv> \
    --config bm25,hybrid --k 10
```

`--embedder fake` gebruikt betekenisloze vectoren en is **alleen** geldig bij
`--config bm25` (BM25 negeert vectoren) — handig om zonder Ollama de
BM25-leiding te testen. Een hybrid-run op fake vectoren is misleidend.

Het ingest-script rapporteert per eindtoestand en heeft retry-rondes voor
transiente indexfouten (`process()` is hervatbaar; onder geheugendruk
time-out OpenSearch soms). Falen blijft luid: na 3 rondes staat een document
als FAILED in het rapport.

## Interpretatie — twee kanttekeningen

- **Anonimisatie vóór indexering.** wordsworth indexeert geanonimiseerde tekst
  (dat is het product); een thesis-baseline mat mogelijk op ruwe tekst.
  Geredigeerde namen/PII kunnen daarop leunende queries drukken — vergelijk
  richtinggevend, niet op de decimaal.
- **Resources.** ~1–2k documenten embedden op CPU duurt eerder uren dan
  minuten; bge-m3 + OpenSearch + Postgres samen willen comfortabel >4 GB.

## Smoke-collectie

`make_smoke_collection.py` genereert de synthetische mini-collectie opnieuw
(map `smoke/` naast het script: `corpus/*.pdf`, `queries.tsv`, `qrels.txt`).
De gegenereerde bestanden staan bewust niet in git — reproduceerbaar uit het
script, nooit binair ingecheckt.
