<!-- SPDX-License-Identifier: MIT -->
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

## Lange synthetische collectie (30×30, synthetic-long-corpus)

De smoke-collectie en de 500-documenten-collectie (`generate_ground_truth.py`)
zijn korte tekstdocumenten. Echte Woo-publicaties zijn lange PDF's: dekblad,
inhoudsopgave, brieven, e-mailwisselingen, notulen en tabellen, met een
pagina-header/footer op elke pagina, en soms een pagina zonder tekstlaag
(gescand). Dat genereert `generate_long_corpus.py`:

```bash
uv run python scripts/eval/generate_long_corpus.py /tmp/longcorp \
    --docs 30 --pages 30 --seed 20261106 --scanned 0.1
```

Schrijft `documents/<doc-id>.pdf`, `gold.jsonl` (één regel per
born-digital pagina, in `load_gold`'s formaat), `gold_scanned.jsonl` (dezelfde
vorm voor de gescande pagina's), `queries.tsv`/`qrels.txt` (één query per
document, met als enige antwoord een unieke zin op of na pagina 20) en
`manifest.json` (seed, opties, aantallen per PII-type, de gescande pagina's
per document, de queries en de kanttekening).

**Het te citeren getal:**

```bash
uv run python -m wordsworth.eval.pii_run /tmp/longcorp/gold.jsonl --layers deterministic
```

Gemeten op de echte 30×30-run (seed 20261106, standaard `--scanned 0.1`):
genereren duurde 10,5 s en de map beslaat 11,4 MB op schijf (30 PDF's, ~90
gescande pagina's op 200 dpi). `pii_run` zag `documents=810` (900 pagina's
minus de 90 gescande, precies zoals de proposal voorspelt) en op de
deterministische laag alleen: BSN/IBAN/EMAIL/POSTCODE P=1,000 R=1,000 —
PERSON/LOCATION/PHONE_NUMBER staan wel in de gold (voor de
openanonymiser-laag) maar hebben per definitie R=0,000 zonder die laag erbij.

**`gold_scanned.jsonl` hoort niet in dat getal.** `pii_run` detecteert over de
gold-tekst en opent nooit een PDF — scoren over de gescande pagina's zou
pagina's meetellen die de pijplijn niet kan zien, als was de extractie
perfect. Het bestaat om te laten zien *wát* er onzichtbaar verdwijnt, niet om
mee te scoren.

**IR-ranking op het lange corpus** (long-documents-rank-fairly: blijft een
lang document ranken als zijn enige antwoord diep erin verstopt zit):

```bash
uv run python -m wordsworth.eval.run \
    --qrels /tmp/longcorp/qrels.txt --queries /tmp/longcorp/queries.tsv \
    --config bm25,hybrid --k 10
```

Dat vereist een geïndexeerd corpus (zie `ingest_eval_corpus.py` hierboven) —
dit script genereert alleen de PDF's en de queries/qrels, het indexeert niets.

## Een echt corpus ophalen (Woo-documenten)

De synthetische mini-collectie bewijst de kéten; ze bewijst niet dat de straat
duizend echte Nederlandse overheidsdocumenten overleeft. Daarvoor:

    uv run python scripts/eval/fetch_woo_corpus.py --out ./corpus --max 50
    uv run python scripts/eval/ingest_eval_corpus.py --corpus-dir ./corpus --db-url …

### Waar het vandaan komt, en waarom niet ergens anders

Nagemeten 2026-09-13:

| bron | status |
|---|---|
| `open.overheid.nl` (landelijk Woo-portaal) | **dicht** — 401 voor bots, `Disallow: /` |
| `bestuur.gooisemeren.nl` | **dicht** — proof-of-work-challenge (Anubis) |
| `open.gelderland.nl` | **open** — `Allow: /`, 848 Woo-besluiten, directe PDF-links |
| `woo.arnhem.nl` | open, maar `Crawl-delay: 60` |

De fetcher gebruikt Gelderland, noemt zichzelf in de User-Agent, wacht een
seconde tussen verzoeken en schrijft per document `herkomst.jsonl` — zonder
herkomst is elke meting op het corpus onnavolgbaar.

### Wat dit corpus wél en niet meet

- **Wel: de pijplijn.** Op een steekproef van 6 PDF's: 5 born-digital en 1 scan
  (0 tekens over 2 pagina's), dus zowel het gewone pad als OCR-recovery wordt
  geraakt. Meet eindtoestanden, doorlooptijd en het aandeel `UNPROCESSABLE_OCR`.
- **Wel: waar PII stónd.** Woo-documenten dragen de redactiegrond in de tekst —
  `[5.1.2e]` is artikel 5.1.2e Woo, de persoonlijke levenssfeer. Dat is een
  gratis, echt label voor "hier is persoonsgegeven weggehaald", op een plek waar
  wordsworth dus niets meer hoort te vinden.
- **Niet: IR-kwaliteit.** `wordsworth.eval` eist qrels en queries, en die bestaan
  niet voor een Woo-corpus. Die moet iemand maken; zonder dat blijven de
  IR-metrics op de synthetische collectie.
- **Niet: PII-precisie en -recall.** Daarvoor is `pii_gold_synthetic.jsonl` nog
  steeds de enige gelabelde bron. Een echt corpus heeft geen labels.

### De meting die dit corpus wél mogelijk maakt

Draai wordsworth over een Woo-besluit en kijk naar wat er **niet** geredigeerd
is. Op de steekproef stond in een besluit van de provincie nog een direct
telefoonnummer en twee e-mailadressen, naast de namen van ambtenaren in functie.
Dat is een controleerbare vraag met echte waarde — vindt onze anonimisering de
persoonsgegevens die de publicerende overheid heeft laten staan? — en het is
precies waarvoor wordsworth bestaat.
