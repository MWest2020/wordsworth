## 1. Grond stabiel maken

- [ ] 1.1 `substitute(text, pattern, replacer, validate, context=None, bron=None)`:
      de contextfunctie krijgt `bron` en een positie ín `bron`, niet in `text`.
- [ ] 1.2 De detectorlus in `anonymizer.py` en `pseudonymizer.py` houdt de
      oorspronkelijke tekst vast en geeft die aan elke detector door.
- [ ] 1.3 Positie-afbeelding: per vervanging de lengteverschuiving bijhouden,
      zodat een positie in de werktekst terug te rekenen is naar de bron.
      Geen herberekening van de hele tekst per match — dat maakt het kwadratisch
      op een document van 70 MB.

## 2. Gate

- [ ] 2.1 Test: een postbusregel met een e-mailadres ervóór geeft hetzelfde
      antwoord als dezelfde regel zonder dat e-mailadres. Dit is de test die
      vandaag faalt.
- [ ] 2.2 Test: hetzelfde voor een bsn en een iban ervóór (andere lengtes).
- [ ] 2.3 Test: een woonadres-postcode met "Postbus" net buiten bereik in de bron
      wordt geredigeerd, óók als een vervanging ervóór hem binnen bereik zou
      trekken. Dat is de richting waarin het toeval gevaarlijk is.
- [ ] 2.4 Nameten dat de tests niet vacuüm slagen: zonder de wijziging falen 2.1
      en 2.3.
- [ ] 2.5 Volledige suite groen.
- [ ] 2.6 `openspec validate --strict` + CI groen.

## 3. Nameten op het corpus

- [ ] 3.1 De vier bekende voorkomens (`3500 DA` ×3, `2500 EH` ×1) opnieuw
      beoordelen op de **bron** en vastleggen dat de uitkomst gelijk blijft.
- [ ] 3.2 Tellen hoeveel postcodes in het corpus van antwoord veranderen. Nul is
      het verwachte getal; een ander getal is de vondst.

## 4. Documentatie

- [ ] 4.1 `docs/explanation/meting-woo-corpus-01.md`: de fragiliteit die nu als
      open punt genoteerd staat, afsluiten met wat er is gebeurd.
