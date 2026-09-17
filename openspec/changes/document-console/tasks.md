# Tasks

## 1. Lezen
- [x] `/console` — documenten met toestand en aangetroffen PII-types, nieuwste
      activiteit eerst. `documents` heeft geen tijdstempel (de tijd zit in het
      auditspoor), dus de volgorde komt uit het laatste auditrecord — wat ook
      het nuttigere antwoord is: wat heeft de straat het laatst gedaan.
- [x] `/console/documents/{id}` — de opgeslagen gepseudonimiseerde tekst met de
      tokens gemarkeerd en per type benoemd.
- [x] Geen enkele route onthult. Re-identificatie houdt één deur: de
      grant-bewaakte, geauditeerde `reveal`. De pagina zegt dat ook, zodat
      niemand hoeft te gokken waar het origineel gebleven is.
- [x] Een document zonder opgeslagen tekst zegt dat, in plaats van een lege
      pagina te tonen.

## 2. Vaststellen
- [x] `/console/combinations` — vastleggen van types + reden, opgeslagen in
      `declared_combinations`, en meteen het aantal documenten dat élk type
      draagt. Vaststellen en meten in één handeling.
- [x] Een type waar geen detector voor bestaat krijgt per regel "niet te zien"
      in plaats van een kale nul. Die nul betekent niet "komt niet voor".
- [x] Weigering met reden bij een lege reden of één type; er wordt dan niets
      opgeslagen.

## 3. Het slot
- [x] De console wordt alléén gemonteerd mét api-key-auth. Een scherm dat elk
      document en elk aangetroffen type opsomt hoort niet aan een open poort;
      géén scherm is beter dan een scherm zonder slot.
- [x] De sleutel mag ook in het `ww_console`-cookie komen — een browser kan bij
      een navigatie geen header meesturen. Eén beslispunt (dezelfde middleware,
      dezelfde sleutelverzameling, hetzelfde label), twee enveloppen. Niet in de
      URL, want dat lekt naar logs, historie en referrers.
- [x] Alleen `/console/login` is vrijgesteld van auth — je kunt geen sleutel
      meebrengen naar de pagina die erom vraagt. Rate limiting blijft er wél op
      staan, want dat is de enige route waar raden loont.
- [x] Jinja2 met autoescaping, en een test die een `<script>` in een
      documenttekst en in een objectsleutel probeert. Met de hand escapen in
      f-strings is precies waar XSS ontstaat.

## 4. Gemeten, niet beweerd
- [x] Live gedraaid: 40 gegenereerde documenten door de échte pseudonimiseerder,
      `wordsworth.serve:app` op poort 8731, met echte sleutels.
      - zonder sleutel 401, met foute sleutel 401, loginpagina 200
      - lijst, documentpagina en combinatiepagina alle 200
      - `BSN + POSTCODE` → 14 van de 40; `DATE + GENDER + POSTCODE` → 0 met
        "niet te zien: DATE, GENDER"
- [x] Eerste poging draaide `wordsworth.api:create_app` in plaats van
      `wordsworth.serve:app`. Die kreeg geen session_factory en monteerde de
      console dus niet — en `/console` gaf tóch 401, omdat de middleware vóór de
      routering komt. De 401 leek montage te bewijzen en bewees niets.

## Wat hier niet in zit
- **Geen bewerken.** Lezen, en het vastleggen van een combinatie.
- **Geen eigen authenticatie.** Dezelfde sleutels als de API.
- **De smoke draaide zonder de GLiNER-laag**, dus namen stonden in de
  documenttekst nog gewoon in het klaar — zichtbaar op het scherm. Dat is
  dezelfde bevinding als de 500 `leaks` in de evalmeting, en het is een
  eigenschap van die opstelling, niet van de console.
