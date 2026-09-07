## ADDED Requirements

### Requirement: Aangeleverde tekst kan geen bestaand pseudonym binnensmokkelen

De pseudonimisering SHALL pseudonym-vormige reeksen die al in de aangeleverde
tekst staan onschadelijk maken vóór er iets gedetecteerd of vervangen wordt, zodat
zo'n reeks later niet als sleutel naar een opgeslagen mapping kan dienen. De
inhoud SHALL leesbaar blijven — het document wordt niet geweigerd — en het aantal
geneutraliseerde reeksen SHALL in de telling van de run terugkomen, zodat het
zichtbaar is in plaats van stil.

#### Scenario: Een token uit een ander document werkt niet in het eigen document

- **WHEN** iemand een pseudonym uit een document dat hij mag inzien letterlijk in
  zijn eigen aangeleverde tekst zet
- **THEN** staat dat pseudonym niet meer als pseudonym in de opgeslagen tekst, en
  levert een reveal op dat eigen document de klare waarde van het andere document
  dus niet op

#### Scenario: Gewone tekst met haakjes blijft ongemoeid

- **WHEN** de tekst iets bevat dat op een token lijkt maar het niet is
  (`[bijlage 3]`, `[PERSON:xx]`)
- **THEN** blijft die tekst onveranderd

#### Scenario: Neutralisatie is zichtbaar

- **WHEN** er reeksen geneutraliseerd zijn
- **THEN** meldt de telling van die run hoeveel
