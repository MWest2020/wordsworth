# Tasks

## 1. Het ontwerp overnemen
- [x] Palet, families en componenten uit `wordsworth-demo-site/index.html`:
      dezelfde variabelen voor licht én donker, `.card`, `.panel-head`, `.tok`,
      `.doc`, `.pill`. Overgenomen, niet nagemaakt — twee uiterlijken voor
      hetzelfde verhaal is precies wat we niet willen.
- [x] Vier templates herschreven. De inlogpagina laat de ingelogde balk weg
      (geen navigatie en geen afmeldlink op een pagina waar je nog niet bent).

## 2. De letters
- [x] Alleen de **latijnse** subsets opgehaald: 9 faces, 224 KB. De volledige set
      was 28 bestanden met Cyrillisch, Grieks en Vietnamees erbij.
- [x] `fonts.css` verwijst naar `/console/static/fonts/…`; geen enkel
      CDN-adres blijft over in een gerenderde pagina.
- [x] Test die de CSS ophaalt én het eerste woff2-bestand waar hij naar wijst
      volgt en op de magic bytes `wOF2` controleert. Een verpakkingsfout laat de
      CSS heel en de letters weg, en dat is precies wat je niet ziet in een
      groene testsuite die alleen de CSS opvraagt.
- [x] Wiel gebouwd en nagekeken: 9 woff2 + `fonts.css` zitten erin.

## 3. Het slot eromheen
- [x] `exempt_prefixes` in de middleware voor `/console/static/`. De inlogpagina
      is auth-vrij; zonder deze vrijstelling rendert hij zonder letters.
- [x] Subtree, geen blanket: `/console/staticky` blijft 401.

## 4. De licenties
- [x] Ik vendorde lettertypebestanden in een MIT-repo en dacht er eerst niet aan.
      Alle drie de families zijn OFL-1.1; die licentie staat verspreiding toe,
      óók gebundeld in software, zolang de tekst meereist.
- [x] Per familie de eigen OFL met eigen copyrightregel naast de fonts, plus één
      generieke `LICENSES/OFL-1.1.txt` zónder familie-copyright — een centrale
      kopie die Spectral's regel bovenaan draagt, liegt over de andere twee.
- [x] `static/fonts/README.md` met de tabel en waarom dit de MIT-invariant niet
      raakt: OFL is permissief voor de fonts en werkt niet door op de software
      die ze insluit.
- [x] De bestanden zijn ongewijzigd overgenomen, dus de Reserved Font
      Names-clausule speelt niet.

## 5. Nagemeten
- [x] 561 tests groen.
- [x] Lokaal gedraaid op 12 echte gegenereerde documenten door de echte
      pseudonimiseerder: alle vier de pagina's 200, `fonts.css` 200, geen
      `fonts.googleapis` in de uitvoer.

## Wat de demo wél heeft en dit niet
Animaties. De demo vertelt een verhaal en laat een token voor je ogen omslaan;
dit scherm toont wat er in de database staat en heeft niets te animeren. Geen
JavaScript dus.

## Aardigheid die opviel bij het nakijken
Op de documentpagina staat `(ZAAK:12ab34cd)` waar het corpus `[ZAAK:12ab34cd]`
aanleverde. Dat is `neutralise_foreign_tokens` die een tokenvormige string uit
aangeleverde tekst ontmantelt vóór de anonimisering — een garantie die tot nu toe
alleen in een test zichtbaar was, en nu op het scherm.
