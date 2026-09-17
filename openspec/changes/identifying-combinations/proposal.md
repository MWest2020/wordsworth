# Change: identifying-combinations

## Why

Elk gegeven wordt op zichzelf beoordeeld. Een record als *"vrouw, geboren 1978,
postcode 6541 EX, functie X"* komt daarom ongeschonden door de straat: geen van
die vier is een direct identificerend gegeven, en samen wijzen ze vaak precies
één persoon aan.

Dat is geen theoretisch bezwaar. Het is de klassieke quasi-identifier, en het is
de reden dat "we hebben de namen weggehaald" al dertig jaar geen geldige
bewering is. Bevinding 3 van meting 01 noemde het en schoof het door: *"een eigen
change waard, niet hier binnengesmokkeld."*

De datasetkant kán het al, alleen weet niemand wanneer het nodig is:
`mode: per_record` met een `record_key` voegt kolommen samen tot één pseudonym.
Wat ontbreekt is het **vaststellen** welke combinatie identificerend is — en een
`record_key` die de operator uit zijn hoofd kiest, is een aanname met een
juridische staart.

## Wat deze change WEL doet

- **Combinaties worden benoembaar.** Een `combinations`-blok in een profiel
  benoemt verzamelingen types die sámen identificeren, met een reden erbij. Niet
  een lijst kolomnamen maar een lijst PII-types, zodat dezelfde uitspraak geldt
  voor documenten en datasets.
- **Een profiel wordt erop getoetst.** Laat een profiel een benoemde combinatie
  volledig ongepseudonimiseerd staan, dan is dat een expliciete melding bij het
  valideren — geen stille doorgang.
- **Het corpus wordt erop gemeten.** Een commando telt in welke documenten een
  benoemde combinatie voorkomt. Meten vóór beweren: zonder dat getal is elke
  uitspraak over quasi-identifiers in dit corpus een gok.

## Wat deze change NIET doet

- **Geen k-anonimiteit, geen automatische onderdrukking.** De vraag "hoeveel
  mensen delen deze combinatie" vergt een populatiebestand dat we niet hebben, en
  een antwoord dat per corpus verschilt. Een verzonnen k is erger dan geen k.
- **Geen automatisch redigeren van combinaties in documenten.** Eerst weten hoe
  vaak het voorkomt en waar; daarna pas beslissen wat de straat ermee doet. In
  die volgorde, want de omgekeerde volgorde mangelt tekst op een aanname.
- **Geen oordeel over wélke combinaties identificeren.** Dat is een keuze van de
  verwerkingsverantwoordelijke, niet van dit project. De change levert de plek om
  die keuze vast te leggen en te toetsen, niet de keuze zelf.

## Impact

- `combinations.py` (de combinatie-definitie — een eigen module en niet
  `pii_categories.py`, omdat een combinatie geen categorie is maar een uitspraak
  óver categorieën), `datasets.py` (profielvalidatie), `api.py` (de bevinding in
  het antwoord), `measure_combinations.py` (het meetcommando),
  `openspec/specs/pii-categories`.
- Non-breaking: een profiel zonder `combinations` gedraagt zich ongewijzigd.
