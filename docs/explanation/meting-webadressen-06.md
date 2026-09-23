---
status: current
last_reviewed: 2026-09-23
---

# Meting 06 — webadressen

Uitgevoerd op 2026-09-23, bij het voorstel `urls-are-detected` en issue #124.
Tegen de draaiende OpenAnonymiser, het evalcorpus en de 770 opgeslagen
documenten. Alleen tellingen; geen domeinnamen van partijen, want die kúnnen
het lek zijn.

## Waarom webadressen bleven staan

Niets in de keten detecteerde ze. De service levert geen `URL`-entiteit (in
geen enkele proef), wordsworth vraagt er niet om, de deterministische laag kent
BSN, IBAN, e-mail en postcode, en `deny.json` had geen regel. `URL` stond in
`pii_categories` als type dat geen detector opleverde.

Een naam ín een adres werd alleen via de context gevonden. Rechtstreeks aan de
service gevraagd:

| invoer | gevonden |
|---|---|
| briefhoofd met de naam als kop, dan `www.eazwind.nl` | `eazwind` als ORGANIZATION, 0,60 |
| `www.eazwind.nl` los | niets |
| `Meer informatie op www.eazwind.nl.` | niets |
| `https://www.eazwind.nl` | niets |

In het echte document uit #124 werd de kop nooit als naam gevonden (het waren
OCR-fragmenten van een logo, zie meting 03). Context had het dus ook daar niet
gered.

## Evalcorpus

De URL's zijn nieuw geseed (`generate_ground_truth.py`), uit een eigen generator
per document, zodat geen enkele bestaande waarde veranderde. Nagemeten: over
500 documenten 0 bestaande waarden anders. 145 webadressen van een partij als
`URL`-gold, 123 overheidsadressen als tegencase in de platte tekst.

Deterministische laag met de lijsten:

| | vóór | ná |
|---|---|---|
| URL recall | 0,000 (0 van 145) | **1,000** (145 van 145) |
| URL fout-positief | 0 | **0** — geen van de 123 overheidsadressen geraakt |
| overige typen | | ongewijzigd |

## Opgeslagen corpus (770 documenten, alleen lezen)

De nieuwe lijsten gesimuleerd over de opgeslagen tekst:

- **249** webadressen worden een token, in **152** documenten.
- **258** blijven leesbaar, door een uitzondering in `allow.json`.
- Van de hosts die in precies één document voorkomen — de vorm van een
  partij-eigen site — worden **alle 38 niet-publieke** vervangen. De overige 5
  zijn subdomeinen van `overheid.nl` en blijven terecht staan.

Een simulatie over opgeslagen tekst is niet hetzelfde als herverwerken. 107
treffers eindigden op `https://www`: daar had GLiNER de naam in het adres al
vervangen (`https://www.[ORGANIZATION:…].nl`), en de regel ziet dan alleen het
begin. Nagemeten met de echte `ReversibleAnonymizer` en de draaiende service op
een briefhoofd: de oude lijsten geven `www.[ORGANIZATION:c47ab01c].nl`, de
nieuwe `[URL:8021618e]`. Bij het herverwerken ziet de regel het adres dus
heel, vóór de vervanging.

## Na het herverwerken (2026-09-23)

De 151 documenten waarin de simulatie iets zag veranderen, zijn herverwerkt
(150 in de eerste Job; één verloor een deadlock tegen een init-Job van een
andere uitrol en is daarna los gedaan). Geteld over alle 770 documenten, binnen
één run en met dezelfde lijsten als de dienst:

- **0** hele, leesbare webadressen buiten `allow.json`. Dat is de eigenschap
  waar #124 om ging: een partijnaam in een adres blijft niet meer staan.
- **262** `[URL:…]`-tokens, in **119** documenten.
- **258** adressen blijven leesbaar via een uitzondering, precies het getal
  uit de simulatie.

De simulatie zat op één punt ernaast. Bij het herverwerken wint de URL-regel
niet altijd: 76 treffers in de 151 documenten eindigen nog op
`https://www.[PERSON:…]` of `[LOCATION:…]`, `[ORGANIZATION:…]`, `[EMAIL:…]`.
Dat gebeurt als het adres zelf op de uitzonderingslijst staat en er dus geen
URL-detectie is. De naam die elders in het document gevonden is, wordt dan óók
binnen het adres vervangen, want vervangen gaat op waarde en niet op positie.
Nagemeten op een briefhoofd met de draaiende service: een toegestaan adres
blijft heel staan en een ander adres wordt `[URL:…]`. De half vervangen vorm
ontstaat dus alleen waar een naam uit de rest van de tekst ook in een
toegestaan adres staat.

De naam is in die gevallen altijd een token. Wat erachter staat, is niet
altijd leeg: over het hele corpus komt `www.[TOKEN]` 189 keer voor, in 102
documenten. 174 keer volgt er alleen een topleveldomein of niets. 15 keer
volgt er een leesbaar pad (alleen de vorm bekeken, zoals `.nl/a/a/a-a`), soms
met nog een token erin. Dat is de rest die overblijft: klein, en niet de
vorm uit #124, maar ook niet nul.

## Wat het kost

Het echte probleem uit meting 04 en 05 is te véél vervangen. Deze wijziging
voegt tokens toe: ongeveer 249 over het corpus. De uitzonderingen houden de 258
institutionele adressen leesbaar. Wat buiten de lijst valt, wordt een token —
ook bedrijven en platforms die geen partij zijn. Dat is de richting die de
lijsten al kiezen: een regel te veel verbergt iets wat geen PII was, een regel
te weinig laat PII staan.

## Reproduceren

    python scripts/eval/generate_ground_truth.py <map>
    python -m wordsworth.eval.pii_run <map>/gold.jsonl --layers deterministic --lists lists
