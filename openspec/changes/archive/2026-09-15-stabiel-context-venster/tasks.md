## 1. Onderzoek (gedaan, vóór de code)

- [x] 1.1 Positievertaling gebouwd (`source_map.SourceText`, 68 regels) en de
      detectorlus erop aangesloten.
- [x] 1.2 Nagemeten op het corpus of het antwoord ooit verschilt tussen bron en
      werktekst: **1016 voorkomens in 627 documenten, nul verschillen**.
- [x] 1.3 Machinerie weer verwijderd. Een abstractie zonder tweede geval is
      geen abstractie maar onderhoud.
- [x] 1.4 De aanleiding herzien: de "vier onterecht bewaarde" postcodes waren
      een meetfout — vergeleken op waarde in plaats van op positie.

## 2. Borging

- [x] 2.1 Test die vastlegt dat `_POSTBUS_RE` de markering pál vóór de postcode
      eist (verankering op `$`), mét de redenering waarom dat de stabiliteit
      draagt.
- [x] 2.2 Test op het gedrag: dezelfde postbusregel met en zonder een
      e-mailadres ervóór geeft hetzelfde antwoord, via beide pijplijnen.
- [x] 2.3 Nameten dat 2.1 faalt als de verankering wordt losgemaakt.
- [x] 2.4 Volledige suite groen.
- [x] 2.5 `openspec validate --strict` + CI groen.

## 3. Documentatie

- [x] 3.1 `docs/explanation/meting-woo-corpus-01.md`: het open punt over het
      venster afsluiten met wat er gemeten is en waarom er geen code bij hoort.
