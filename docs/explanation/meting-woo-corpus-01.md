---
status: accepted
last_reviewed: 2026-09-13
---

# Meting 01 — 200 gepubliceerde Woo-documenten door de straat

De eerste keer dat wordsworth op echte documenten is gemeten in plaats van op
fixtures. Bron: `open.gelderland.nl`, opgehaald met
`scripts/eval/fetch_woo_corpus.py` (herkomst per document in `herkomst.jsonl`).

## Opzet

Woo-documenten dragen hun redactiegrond in de tekst: `[5.1.2e]` is artikel 5.1.2e
Woo, de persoonlijke levenssfeer. Elke markering staat precies waar de
publicerende overheid een persoonsgegeven heeft weggehaald. Dat is een **echt
label in een echt corpus**, gratis, zonder annotatie.

Twee kanten aan elkaar geknoopt: de gepubliceerde PDF (wat de overheid weghaalde)
en de geïndexeerde tekst (wat wordsworth daarna nog vond en liet staan). De
restcontrole gebruikt alleen checks die zónder annotatie te beoordelen zijn —
een BSN met geldige elfproef, een IBAN met geldige mod-97, een e-mailadres op een
privédomein.

## Uitkomst

| | |
|---|---|
| documenten | 200 (428 MB), 15 scans |
| eindtoestanden | **203/203 `indexed`**, nul `FAILED`, nul `UNPROCESSABLE_OCR` |
| doorlooptijd | 2 u 02 min |
| markeringen `[5.1.2e]` in de bron | **519**, verspreid over 95 documenten |
| placeholders die wordsworth plaatste | **14 526** |

Placeholders per type: ORGANIZATION 5378 · PERSON 3789 · LOCATION 3213 ·
DATE_TIME 1359 · EMAIL 634 · PHONE_NUMBER 104 · BSN 41 · IBAN 8.

**Restcontrole op de index: geen enkel persoonsgegeven van de automatisch
beoordeelbare soort.** Nul e-mailadressen, nul geldige IBANs, nul mobiele
nummers. Vier negencijferige getallen met een geldige elfproef bleken bij
inspectie geen BSN: twee btw-nummers (`BTW NL810828662B01`,
`BTW NL804306837B01`), één bestandsnaam (`D252694417_1__Overzicht…`) en één
zaaknummer van de Raad van State (`201304246/1/R6`). De detector liet ze terecht
staan — dat is precies waarom hij de elfproef gebruikt en geen kale `\d{9}`:
anders was een jurisprudentieverwijzing onleesbaar gemaakt.

## Bevinding 1 — adressen overleefden met hun identificerende helft intact

**123 volledige adressen** (straat + huisnummer + postcode) stonden ongeschonden
in de index. De NER-laag haalde de **stad** weg als `LOCATION` en liet de rest
staan:

    Burgemeester de Bordesstraat 80, 1404 GZ [LOCATION:17534a19]

Dat is de verkeerde helft. In Nederland identificeert postcode plus huisnummer
een huishouden; de stad is het mínst identificerende deel van een adres. De
straat bleef staan, het nummer bleef staan, de postcode bleef staan.

In dit corpus zijn het kantooradressen uit e-mailhandtekeningen, dus er is geen
persoonsgegeven gelekt. Het **mechanisme** is de bevinding: stond hier het
huisadres van een burger, dan was het meest identificerende deel blijven staan.

Oorzaak, en die is scherp: de taxonomie kent `ADRES`, `ADDRESS` en `POSTCODE`
(`pii_categories.py`), `normalization.py` heeft een `_postcode()`-normaliseerder
die eronder geregistreerd staat, en `legible.py` kan `[ADRES 2]` renderen — maar
**niets produceerde er ooit een**. Nul `ADDRESS`- en nul `POSTCODE`-spans in het
hele corpus. Het type was end-to-end bedraad behalve aan het begin.

Opgelost: `detectors.py` heeft nu een postcode-detector. Nagemeten op dezelfde
geanonimiseerde tekst: **67 postcodes** die nu alsnog geredigeerd worden. Een
postbus houdt zijn postcode — dat is een openbaar contactgegeven van een
organisatie, en wegredigeren maakt een besluit onleesbaar zonder iemand te
beschermen.

## Bevinding 2 — een OCR-hersteld document is niet terug te vinden op zijn bronhash

Zes documenten leken te ontbreken uit de index terwijl de Job `203/203 indexed`
meldde. Ze ontbraken niet: `recover()` schrijft de ge-OCR'de PDF weg als een
**eigen content-addressed object** en verlegt `object_key` daarheen. De originele
scan blijft bestaan, maar zijn sha256 komt niet meer in de index voor.

Geen fout — content-adressering doet precies wat hij hoort te doen. Wel een
valkuil voor iedereen die een corpus tegen de index meet: de koppeling
`sha256(bestand) → object_key` gaat niet op voor herstelde scans. De afbeelding
staat in het auditspoor, stap `ocr`, veld `old_object_key`/`new_object_key`.

## Bevinding 3 — pseudonimiseren op een combinatie van gegevens bestaat niet

Gezocht in specs, changes, code en de NORA-analyse: geen enkele vermelding van
combinaties, quasi-identifiers of k-anonimiteit. Elk gegeven wordt op zichzelf
beoordeeld.

Dat betekent dat een record als *"vrouw, geboren 1978, postcode 6541 EX,
functie X"* ongemoeid door de straat komt: geen van die vier is op zichzelf een
direct identificerend gegeven, en samen wijzen ze vaak één persoon aan. Het is
geen gap in de NORA-matrix — het staat daar niet in, want het deck noemt het ook
niet — maar het is wél een gat in de belofte.

Het raakt vooral de datasetkant (`dataset-pseudonymization`), waar kolommen per
profiel gekozen worden: precies de plek waar een combinatie ontstaat. Een eigen
change waard, niet hier binnengesmokkeld.

## Bevinding 4 — de herindexering telde haar eigen mislukkingen zonder ze aan te wijzen

De postcode-detector kwam ná de eerste meting, dus moest het corpus opnieuw door
de anonimisering. Nameting op het cluster (2026-09-14, 770 geïndexeerde
documenten): nul e-mailadressen, nul geldige IBANs, nul geldige BSN's, en **164
postcodes letterlijk in de tekst**. Daarvan staan er **56 in een
postbus-context** en blijven terecht staan; **108 moesten alsnog weg**, verspreid
over 31 documenten.

Die 56 zijn het bewijs dat de contextregel doet wat hij belooft, nu op echte
documenten in plaats van op een fixture: `Postbus 250, 6800 GD Arnhem` is het
contactadres van een overheid, geen woonadres van een mens.

Twee dingen gingen mis, en het tweede is het echte.

**De herstelactie was te duur om te draaien.** De reprocess-Job stuurde altijd
"herdraai alles": 770 documenten × ~2 min GLiNER is ruim 25 uur, voor werk van
een uur. Zo'n run wordt afgebroken — op 2026-09-13 gebeurde dat toen om 03:00 de
websocket van een `kubectl exec` wegviel. Een gate die te duur is om te draaien,
wordt niet gedraaid, en dan is het geen gate. De Job neemt nu een lijst
documenten aan.

**De gerichte run faalde, en vertelde niet waarop.** 31 documenten in 1 u 58 m:
21 gelukt, 8 retryable, 2 gefaald. De Job faalde daardoor netjes in plaats van
stil `Completed` te melden. Maar wélke tien was niet te achterhalen: het antwoord
gaf alleen tellers, en in de audit-keten stond van géén van die documenten een
regel van die dag. De keten zei dus "hier heeft nooit iemand aan gezeten" terwijl
er net tien pogingen waren gedaan. De exception werd geteld en weggegooid.

Daarmee was de enige manier om de tien terug te vinden: alle 770 opnieuw draaien
— precies de herstelactie van een dag die zojuist was weggebouwd.

Dit is dezelfde vorm als bevinding 1. Daar was een PII-type end-to-end bedraad
behalve aan het begin; hier is een run end-to-end bedraad behalve aan het eind.
De gate telt wel, maar wijst niet aan, en een mislukking zonder spoor is niet te
onderscheiden van een stap die nooit liep.

Opgelost: het antwoord noemt per document de exception-**klasse** (niet de
boodschap — die kan een fragment citeren van het document waarop hij afknapte),
en er komt een `reprocess_failed`-regel in de audit-keten met de toestand
ongewijzigd.

**Wat die reparatie meteen opleverde.** De gerichte herdraai van de acht
overgebleven documenten meldde: `retryable: 8, failed: 0`, en alle acht met
dezelfde oorzaak — `AnonymizationEngineError`. Niet de data dus, en niet de
grootte: de anonimiseringsmotor. Een antwoord dat een uur eerder nog helemaal
niet te krijgen was.

En meteen de volgende laag van hetzelfde. `AnonymizationEngineError` is de
bewuste tekstloze wikkel van de driver: hij zegt dát de motor weigerde, nooit
waarom. De oorzaak eronder — een timeout, een 503, een contractbreuk — is het
deel waar je iets mee doet, en die viel weg in de wikkel. De keten van
exception-**klassen** wordt nu meegeschreven (`AnonymizationEngineError <-
ReadTimeout`); nog steeds geen boodschappen, want een klassenaam kan niets
citeren.

Handmatig nagemeten op het cluster, ná de mislukte run: de chunks van zo'n
document slagen stuk voor stuk wél, los aangeroepen. Het gaat dus niet om een
document dat de motor niet aankan.

## Bevinding 6 — "retryable" was een verkeerd etiket, en dat verborg het echte werk

De run mét oorzaakketen gaf een leeg vervolg: alleen
`AnonymizationEngineError`, geen `<- oorzaak`. Dat is zelf het bewijs. De plek
die de fout mét `from exc` doorgeeft, was het dus niet; er zijn maar twee
plekken die hem zónder oorzaak gooien, en allebei zijn het
**invariant-controles**:

- `_score()` — de motor gaf een entiteit zonder score terug (contractbreuk);
- `pseudonymizer.py` — *"a detected entity value survived pseudonymisation"*:
  ná het vervangen staat een gedetecteerde waarde nog in de tekst, en de code
  weigert die tekst uit te geven.

Dat weigeren is goed en blijft zo. Het etiket erop was fout. `is_transient()`
gaf voor élke `AnonymizationEngineError` "tijdelijk" terug, dus werden deze acht
run na run als `retryable` gemeld. Ze waren niet tijdelijk: dezelfde invoer
ontmoet dezelfde code en faalt identiek, voor altijd. De run zag er herstelbaar
uit terwijl er een codewijziging nodig is, en elke poging kostte GLiNER-tijd om
tot dezelfde conclusie te komen.

Opgelost met `AnonymizationInvariantError`, een subklasse — zodat elke
bestaande `except AnonymizationEngineError` hem nog vangt en het fail-closed
gedrag onveranderd blijft. Alleen het etiket is nu waar: deze acht tellen
voortaan als `failed`, niet als `retryable`.

**Nog onbekend: wélke van de twee invarianten brak, en waarom.** De klasse is
voor beide dezelfde, dus er is nu een vaste `code` per plek
(`entiteit-zonder-score`, `waarde-overleefde-vervanging`) die meegeschreven
wordt naast de klassenaam. Een code uit een gesloten woordenlijst kan niets
citeren; een foutboodschap wel, en daarom blijft die eruit.

Twee pogingen om het van buitenaf te reproduceren liepen dood, en dat is zelf
informatie:

- De opgeslagen tekst van zo'n document bevat **nul** bestaande pseudoniem-
  tokens. De gedachte dat het residu van een vorige ronde zou zijn, klopt niet.
- Een nagebouwde herhaling van de detectie-en-vervangingslus op diezelfde tekst
  leverde **geen** overlever op. De nabouw is dus niet trouw genoeg: de echte
  route draait eerst de deterministische laag en chunkt op andere grenzen. Dat
  is een aanwijzing dat het aan de chunkgrenzen of aan die voorlaag ligt, en
  géén bewijs.

Wat er wél hard staat, komt uit de code en niet uit een gok: er zijn precies
twee plekken die deze fout zónder `from` gooien, en dat is waarom de keten leeg
bleef.

**De run wees het aan.** Alle acht:
`AnonymizationInvariantError[waarde-overleefde-vervanging]`, en `failed: 8,
retryable: 0`. Het is dus niet de motor die zijn contract brak — het is onze
eigen vervanging die een gedetecteerde waarde laat staan.

Waarom die waarde blijft staan, was van buitenaf niet te achterhalen: twee
nabouwen reproduceerden het niet. Daarom schrijft de controle nu zelf veilige
kenmerken van de overlever op — type, lengte, aantal woorden, hoe vaak hij vóór
en ná de vervanging voorkomt. Nooit de waarde. De audit-keten is exporteerbaar,
en een "handige" foutboodschap met de waarde erin zou document-inhoud in een
exporteerbaar spoor zetten — precies wat deze hele laag moet voorkomen.

`in_bron` tegenover `na_vervanging` is het getal dat de vraag beslecht. Zijn ze
gelijk, dan heeft de vervangings-regex de waarde nooit geraakt. Is
`na_vervanging` kleiner, dan zijn sommige voorkomens wél vervangen en andere
niet, en dan zit het in de context rond die voorkomens — niet in de waarde zelf.

## Bevinding 5 — de schema-migratie kon de hele api meetrekken

Gevonden tijdens het uitrollen van de reparatie uit bevinding 4, niet gezocht.
Het init-Job faalde bij de eerste poging en slaagde bij de retry. In het log:

    Process 272007 waits for AccessShareLock on relation 16400;
    blocked by process 272113.

`init_schema` zet een trigger en voegt kolommen toe; beide hebben ACCESS
EXCLUSIVE nodig op tabellen waar de api uit leest. Er stond geen `lock_timeout`,
in de code noch in de deploy.

Wachten is niet het probleem. Het probleem is wat een *wachtend* ACCESS
EXCLUSIVE-verzoek doet met alles wat erna komt: die parkeren er allemaal
achter, ook gewone lezers. Eén vastgelopen init stalt daarmee de complete api,
en van buiten ziet dat er niet uit als een migratie — het ziet eruit alsof de
database weg is.

Dat het deze keer goed ging, is geluk: Postgres' eigen deadlock-detectie brak
de cyclus op. Bij een gewone lock-wachtrij zónder cyclus grijpt die niet in en
wacht hij door.

Opgelost met `SET LOCAL lock_timeout = '5s'` in de migratie-transactie. Snel
falen is hier de betere helft van de afspraak: het init-Job probeert het met
backoff opnieuw, en een poging een seconde later vindt de lock meestal vrij.

## Bevinding 7 — de controle hield acht documenten tegen op twee eigen fouten

De kenmerken uit bevinding 6 wezen het aan. Acht documenten, allemaal
`waarde-overleefde-vervanging`, met per document: label, lengte, aantal
woorden, en hoe vaak de waarde vóór en ná de vervanging voorkomt.

| aantal | label | lengte | woorden | in bron | na vervanging |
|---|---|---|---|---|---|
| 5 | person / email | 5, 11, 21 | 1–4 | 0 | 1 |
| 3 | person | 3 | 1 | 15 | 1 |

`alnum: false` bij alle acht: er zitten leestekens of spaties in. Dat zijn
GLiNER-fragmenten, geen namen.

**Twee oorzaken, allebei van ons.**

De eerste: de controle vergeleek met een tekst waar de ingevoegde tokens uít
gestript waren, naar *niets*. Weghalen naar niets plakt de tekst links en
rechts aan elkaar, en zo ontstaat een woordgrens die in het origineel niet
bestond. Opgelost door naar één niet-woordteken te strippen: de reden om te
strippen (een token mag zelf geen waarde matchen) blijft overeind, de twee
kanten blijven uit elkaar.

De tweede kwam pas boven bij het schrijven van de test, en die is belangrijker.
Een entiteitswaarde komt van de dienst (`e.text`), niet uit een slice van de
tekst, en draagt de spatiëring van de span mee. Op `"Naarden "` mét spatie
matchen mist het woord — er komt een woordteken achteraan, dus de grenscontrole
slaat niet aan. Gevolg: **"Naarden" bleef leesbaar in de uitvoer** én de
fail-hard-controle verwierp het hele document. Twee fouten in één keer, en de
eerste is de ernstigste van de twee: dat is klare PII die bleef staan.

Dat verklaart ook waarom `in_bron: 0` niets bewijst op zichzelf. Dat getal telt
*woord-begrensde* voorkomens; een waarde met een spatie eraan heeft er nul,
terwijl het woord er gewoon staat. Nu wordt op de gestripte waarde gematcht.

**Wat dit zegt over de controle.** Hij stond aan de veilige kant en weigerde —
er is niets gelekt via deze weg. Maar hij weigerde op zijn eigen artefact, en
dat kostte acht documenten uit het corpus. Een controle die vals alarm slaat,
wordt uiteindelijk uitgezet; dat is geen theoretisch risico maar de normale
levensloop van zo'n controle.

**Geen van beide reparaties hielp, en dat was het beslissende gegeven.** Na de
herdraai: dezelfde acht, dezelfde kenmerken, tot op het getal. Drie ervan
lieten zien wat er werkelijk aan de hand was — een waarde van drie tekens die
**vijftien keer** woord-begrensd in de bron voorkomt, alle vijftien vervangen,
en er verschijnt er **één nieuwe**.

Dat kan maar op één manier. De vervanging maakt die grens zelf: een buurwoord
wordt een token, en een token begint met `[`. Het zestiende voorkomen stond in
de bron midden in een woord, en dat wordt bewust niet vervangen omdat het
gewone tekst zou mangelen — dezelfde reden waarom `_MIN_ENTITY_LEN` bestaat.

De kern: **de vervanging beoordeelt de woordgrenzen vóór de vervanging, de
controle beoordeelde ze erna.** Twee verschillende metingen op twee
verschillende teksten, en het verschil heet vals alarm.

Opgelost door een token te vervangen door iets met dezelfde
woord-of-niet-woord-eigenschap aan beide kanten als de waarde die er stond. Dan
ziet de controle exact de grenzen die de vervanging zag. Naar niets strippen
plakt de tekst aan elkaar; naar een vast niet-woordteken strippen maakt juist
een grens waar een woordteken hoorde — allebei fout, in tegengestelde richting.

## Wat deze meting NIET zegt

Ze meet de pijplijn, niet de kwaliteit. **Hoeveel PII er gemist is, weet ik
niet** — daarvoor is een gelabeld corpus nodig en dat is er niet. Wat hier staat
is: van de dingen die automatisch te beoordelen zijn, is er niets blijven staan;
en van de dingen die met het oog te controleren waren, is één klasse fout
gebleken (adressen).
