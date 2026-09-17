# Change: ground-truth-corpus

## Why

We kunnen vandaag niet zeggen hoe goed de straat is.

Beide evaluaties bestáán — `wordsworth.eval.run` voor de rangschikking,
`wordsworth.eval.pii_run` voor de detectie — en beide hebben een corpus nodig
dat we niet hebben. De thesiscollectie met 47 queries is er niet, en een gouden
PII-corpus over echte Woo-documenten is er ook niet: dat zou betekenen dat een
mens honderden documenten met de hand annoteert, en zolang dat er niet is
rapporteren we niets.

Meting 01 liep daardoor op **31 documenten**. Dat is genoeg om een fout te vinden
en te weinig om een cijfer te dragen. Elke uitspraak over precisie of recall die
we nu doen, doen we op dertig documenten.

Wat ontbreekt is geen meetinstrument maar een **meetlat**: een corpus waarvan wij
het antwoord van tevoren kennen, groot genoeg dat een percentage iets betekent.

## Wat deze change WEL doet

- **Genereert ~500 documenten met een bekend antwoord.** Per document liggen de
  PII-spans (positie, type, waarde) vast bij constructie, niet achteraf
  geannoteerd. De generator schrijft de grondwaarheid weg op hetzelfde moment
  dat hij de tekst schrijft; ze kunnen niet uit elkaar lopen.
- **Levert drie artefacten uit één bron.** `gold.jsonl` voor `pii_run`,
  `queries.tsv` + `qrels.txt` voor `eval.run`, en de documenten zelf. Eén
  generatie, twee evaluaties, dezelfde documenten — anders meet je twee corpora
  en vergelijk je appels met peren.
- **Legt de bekende rangorde vast.** Elk document krijgt bij constructie een
  onderwerp en een gradatie van relevantie per query, zodat qrels niet geraden
  maar afgeleid zijn.
- **Zaait combinaties bewust.** Een deel van de documenten draagt een volledige
  gedeclareerde quasi-identifier (identifying-combinations), een deel niet, en
  hoeveel dat er zijn staat in de grondwaarheid. Dan is `wordsworth-measure-
  combinations` óók toetsbaar in plaats van alleen uitvoerbaar.

## Wat deze change NIET doet

- **Geen echte persoonsgegevens, van niemand.** Alle namen, BSN's, IBAN's en
  adressen zijn gegenereerd. BSN's voldoen aan de elfproef en IBAN's aan mod-97
  — anders test je de detector niet — maar ze horen bij niemand.
- **Geen vervanging van een echt corpus.** Synthetische tekst is regelmatiger
  dan ambtelijke werkelijkheid; een score hierop is een ondergrens voor de
  machinerie, geen voorspelling voor productie. Dat staat in het rapport zelf,
  niet alleen in deze alinea.
- **Geen verzonnen moeilijkheidsgraad.** De generator zaait de lastige gevallen
  die meting 01 werkelijk tegenkwam (postbusadressen, tokens in aangeleverde
  tekst, spellingsvarianten van een BSN) en verzint er geen nieuwe bij om het
  cijfer interessant te laten lijken.

## Impact

- `scripts/eval/generate_ground_truth.py` (nieuw), `docs/reference/evaluation.md`,
  `openspec/specs/evaluation`.
- Niets aan de pijplijn. Dit is een meetlat, geen gedragsverandering.
