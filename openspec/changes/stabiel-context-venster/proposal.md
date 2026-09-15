# Change: stabiel-context-venster

## Why

De postbus-uitzondering ("een postbus houdt zijn postcode") kijkt veertig tekens
terug vanaf de postcode en zoekt daar `Postbus <nummer>`. Dat venster wordt
gemeten op tekst die **al half herschreven is**: de detectoren draaien op
volgorde (bsn, iban, e-mail, postcode), dus tegen de tijd dat de postcode aan de
beurt is, staan er op de plek van e-mailadressen al placeholders van een andere
lengte.

Dat rook naar een regel die van toeval afhangt. Het eerste voorstel hier was dan
ook om contextregels de brontekst te laten zien in plaats van de werktekst, met
een positievertaling erbij.

**Dat voorstel was fout, en dit is het bewijs.** Nagemeten op alle 1016
postcode-voorkomens in 627 documenten van het Woo-corpus: de contextregel geeft
op de brontekst **precies hetzelfde antwoord** als op de werktekst. Nul
verschillen.

De reden is structureel en zit al in de code. `_POSTBUS_RE` eindigt op `$`: de
markering moet pál voor de postcode staan. Staat hij daar in de bron, dan zat er
niets tussen, dus is er ook niets vervangen, dus staat hij er in de werktekst
óók. En andersom kan een vervanging de afstand nooit verkleinen — een
placeholder bevat `[`, wat niet in de scheidingstekens `[,.\s|]` zit, dus elke
tussenliggende vervanging bréékt de match in plaats van hem te maken.

Het vermoeden waar dit voorstel op begon — vier postcodes die "per ongeluk"
bewaard bleven — was een meetfout van mij: ik vergeleek op **waarde** in plaats
van op **positie**, en dezelfde postcode komt in zo'n document meerdere keren
voor. De bewaarde voorkomens stonden wel degelijk achter een postbus.

## What changes

Niet de machinerie, maar de **borging**. De stabiliteit van deze regel hangt
vandaag aan één teken — de `$` in `_POSTBUS_RE` — en dat is nergens vastgelegd.
Wie die verankering ooit losser maakt (`Postbus` ergens in het venster in plaats
van er pal voor), zet de instabiliteit aan zonder het te merken.

- **Een eis in de spec**: een contextregel moet zó geschreven zijn dat
  herschreven tekst zijn antwoord niet kan veranderen.
- **Een test die de verankering vastpint**, met de redenering erbij, zodat het
  losmaken ervan een bewuste daad wordt en geen bijvangst.
- **Een test op het gedrag zelf**: dezelfde postbusregel met en zonder een
  e-mailadres ervóór geeft hetzelfde antwoord.

## Wat hier NIET in zit

- **Positievertaling naar de brontekst.** Gebouwd, gemeten, weer weggegooid: 68
  regels machinerie voor een verschil dat in 1016 gevallen nul keer optreedt.
  Zou er ooit een contextregel bijkomen die níét verankerd kan zijn, dan is dit
  het moment om het terug te halen — en dan staat hier waarom.
- **Het venster van veertig tekens zelf.** Een postbusregel met een KvK-nummer
  ertussen valt er nog steeds buiten. Dat is een vraag over reikwijdte, niet
  over stabiliteit.

## Impact

- Geen gedragsverandering. Geen herindexering nodig.
- Twee tests en één spec-eis erbij; de code blijft zoals hij is.
