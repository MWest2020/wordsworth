# Tasks

## 1. De bouwer
- [x] `eval/synthetic.py`: `Document.lit` / `.pii` / `.unlabelled` / `.check`.
      Eén primitief schrijft de waarde én noteert waar hij belandde, zodat er
      geen tweede bron van waarheid ontstaat die er stilletjes naast gaat zitten.
- [x] `bsn()` haalt de elfproef, `iban()` mod-97 — getoetst met de echte
      validators uit `detectors.py`, duizend keer per validator. Een ongeldig
      nummer toetst niets: de detector wijst het af en het corpus bewijst alleen
      dat afwijzen werkt.
- [x] Eerste `iban()` faalde mod-97 (verkeerd omgezette landcode in de
      herschikte vorm). Gevonden doordat ik hem tegen `is_valid_iban` hield in
      plaats van tegen mijn eigen verwachting.

## 2. De generator
- [x] `scripts/eval/generate_ground_truth.py`: 500 documenten, 10 onderwerpen,
      `gold.jsonl` + `queries.tsv` + `qrels.txt` + `manifest.json` uit één run.
- [x] Élk document wordt beoordeeld voor élke query. Een document dat in qrels
      ontbreekt is niet te onderscheiden van een document dat irrelevant is
      verklaard, en de metrieken verschillen.
- [x] De lastige gevallen uit meting 01 gezaaid, niet verzonnen: postbusadressen
      (wel in de tekst, níet in de grondwaarheid), tekst met iets tokenvormigs
      erin, en de volledige quasi-identifier in een deel van de documenten.
- [x] `GENDER` en een kaal geboortejaar worden gedrágen maar zijn geen goud.
      Geen detector geeft ze uit; een detector afrekenen op wat hij nooit
      beweerd heeft te vinden is een meting over ons, niet over hem.
- [x] Deterministisch onder een seed.

## 3. Gemeten, niet beweerd
- [x] 500 documenten gegenereerd en door `wordsworth.eval.pii_run --layers
      deterministic` gehaald. Uitkomst: **P=1.000 R=0.706 F1=0.828** over alles,
      met **P=R=1.000 voor BSN, IBAN, EMAIL én POSTCODE** en 500 `leaks` — de
      500 PERSON-spans, want de deterministische laag heeft geen naamdetector.
      Dat is precies wat er hoort te staan, en het cijfer zegt het nu hardop.
- [x] **123 postbusadressen, nul false positives op POSTCODE.** De uitzondering
      die ik eerder op twee regels tekst "bewees", houdt nu stand op schaal.
- [x] 76 documenten met een tokenvormige string erin: geen enkele als PII
      aangezien.
- [x] Test die `find_deterministic` over 120 documenten exact gelijkstelt aan de
      grondwaarheid — niet "ongeveer goed" maar spanidentiek.

## 4. Documentatie
- [x] `docs/reference/evaluation.md`: het commando, de artefacten, en wat een
      score hierop wél en niet zegt.

## Wat dit corpus niet kan
- **Het is door ons geschreven.** Synthetische ambtelijke tekst is regelmatiger
  dan de werkelijkheid. Een score hierop is een ondergrens voor de machinerie,
  geen voorspelling voor productie. Die zin staat in `manifest.json`, zodat hij
  meereist met het corpus in plaats van in een changelog achter te blijven.
- **Het zegt niets over de naamherkenning.** Die zit in de GLiNER-laag, die hier
  niet draaide. De 500 `leaks` zijn geen bevinding over die laag maar over de
  afwezigheid ervan.
