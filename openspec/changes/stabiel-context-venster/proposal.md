# Change: stabiel-context-venster

## Why

De postbus-uitzondering ("een postbus houdt zijn postcode") kijkt veertig tekens
terug vanaf de postcode en zoekt daar `Postbus <nummer>`. Dat venster wordt
gemeten op tekst die **al half herschreven is**: de detectoren draaien op
volgorde (bsn, iban, e-mail, postcode), dus tegen de tijd dat de postcode aan de
beurt is, staan er op de plek van e-mailadressen al tokens. Een token is korter
of langer dan de waarde die het verving, en dus schuift de reikwijdte van de
regel mee met wat er toevallig vóór staat.

Gemeten op het Woo-corpus (2026-09-15, 770 documenten): van de 420 leesbare
postcodes waren er vier waar de brontekst `Postbus 16005` respectievelijk
`Postbus 20301` op een eerdere regel heeft, met een KvK-regel ertussen. In de
ruwe tekst valt dat buiten de veertig tekens; ná het vervangen van die KvK-regel
viel het erbinnen. Ze zijn bewaard, en dat was ook juist — het zíjn postbussen.
Maar de regel kwam tot het goede antwoord via een toevalligheid, niet via zijn
eigen logica.

Dat is de kern: **niet de uitkomst is fout, de grond is instabiel.** Dezelfde
regel op dezelfde brontekst geeft een ander antwoord al naar gelang hoeveel
e-mailadressen ervóór stonden. Zo'n regel is niet te beredeneren en niet te
testen op wat hij belooft, en de volgende keer valt het toeval de andere kant op:
dan wordt een woonadres-postcode bewaard omdat er toevallig "Postbus" binnen
bereik kwam.

Dit is geen lek en het haalt de huidige meting niet onderuit. Het is een regel
die om de verkeerde reden werkt, en dat is precies het soort ding dat later een
incident heet.

## What changes

- **Contextregels krijgen de brontekst te zien**, niet de gedeeltelijk
  herschreven tekst. De detectorlus houdt de oorspronkelijke tekst vast en geeft
  die, met de bijbehorende positie, aan de contextfunctie door.
- **`substitute()` krijgt daarvoor een expliciete `bron`-parameter.** Zonder die
  parameter blijft het gedrag zoals het is — de aanroepers die geen contextregel
  hebben (bsn, iban, e-mail) merken er niets van.
- **Positie-afbeelding van bron naar werktekst.** De detectorlus weet per
  vervanging hoeveel tekens er zijn bijgekomen of afgegaan; daarmee is de positie
  in de werktekst terug te rekenen naar de positie in de bron.

## Wat hier NIET in zit

- **Het venster van veertig tekens zelf.** Dat getal is een aparte vraag (een
  postbusregel met een KvK-nummer ertussen valt er nog steeds buiten). Eerst de
  grond stabiel, dan pas praten over de reikwijdte — anders verander je twee
  dingen tegelijk en weet je achteraf niet welke hielp.
- **Andere contextregels.** Er is er vandaag precies één. De parameter maakt het
  mogelijk dat er meer komen; dit voorstel voegt er geen toe.

## Impact

- `src/wordsworth/detectors.py` (de lus en `substitute`), `anonymizer.py` en
  `pseudonymizer.py` (die de lus draaien).
- Gedrag verandert alleen daar waar het vandaag van toeval afhing. Op het
  Woo-corpus zijn dat vier voorkomens; die blijven bewaard, nu omdat de regel het
  zegt en niet omdat een e-mailadres toevallig kort was.
- Een herindexering is **niet** nodig om dit uit te rollen: het raakt geen
  bestaande tekst. Wie de vier voorkomens opnieuw wil laten beoordelen, draait de
  betreffende documenten door `/reprocess`.
