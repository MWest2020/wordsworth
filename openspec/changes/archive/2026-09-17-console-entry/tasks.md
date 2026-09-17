# Tasks

## 1. De weigering
- [x] `wants_html()` in `auth.py` — `text/html` in Accept. Grof, en die grofheid
      is de bedoeling: het alternatief is raden aan de User-Agent, en dat is een
      veel slechtere gok.
- [x] Middleware stuurt een HTML-navigatie door naar `/console/login` in plaats
      van 401 JSON. Op élk pad, niet alleen onder `/console` — vandaag gaven
      `/`, `/console`, `/documents` én `/docs` alle vier dezelfde JSON-401 aan
      een browser.
- [x] Een client die niet om HTML vraagt krijgt onveranderd 401 JSON. Een
      programma dat een 303 naar een formulier krijgt, parseert dat formulier.
- [x] Zonder gemonteerde console geen omleiding (`login_path=None`). Doorsturen
      naar een route die 404 geeft vervangt de muur door een cirkel.

## 2. De ingang
- [x] `/` stuurt een browser naar `/console`. Dat is wat iemand intikt.
- [x] Een onbekend pad stuurt een browser naar `/console`; een programma krijgt
      zijn 404.

## 3. Het formulier
- [x] De sleutel wordt getoetst vóór het cookie wordt gezet, tegen dezelfde
      verzameling die de middleware gebruikt. Een tikfout gaf eerst een cookie
      dat nergens toe leidde — mét de verwarring van schijnbaar ingelogd zijn.
- [x] `/console/logout` en een afmeldlink. Zonder dat is een verlopen cookie een
      val waar je alleen uitkomt via de browserinstellingen.

## 4. Nagemeten
- [x] 557 tests groen; 20 daarvan op de console.
- [x] Live door de ingress nagemeten na uitrol (zie het PR-bericht).

## De fout eronder
Ik bouwde een inlogpagina en bouwde nergens iets dat ernaartoe wees. En ik testte
de stroom vanaf de kant waar ik de sleutel al hád — nooit vanaf de kant waar
iemand nieuw binnenkomt. Mijn smoke gaf `/console/login -> 200` en `/console met
cookie -> 200` en zag de enige route die een mens werkelijk neemt, `/console`
zónder cookie, nooit als iets anders dan een correcte 401.
