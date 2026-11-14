---
status: draft
last_reviewed: 2026-11-13
---

# Runbook: detection allow/deny lists and feedback

Detection is refined by two **git-versioned JSON files** — no rules engine, no
auto-learning. Their content hash lands in every de-identify audit record
(`lists_hash`) so you can always tell which rule version produced a document.

```
WORDSWORTH_DETECTION_LISTS=/etc/wordsworth/lists   # directory with the two files
```

`allow.json` — typed patterns whose **full match** is *not* PII of that type. A
detection is dropped only when its type matches the key (never across types).
**Elke regel draagt een reden**, en het laden weigert een regel zonder:

```json
{"LOCATION": [
  {"patroon": "(?i)^locatie$",
   "reden": "Zelfstandig naamwoord, geen plaats. 41 van 198 documenten."}
]}
```

Dit is de enige plek in dit systeem waar een wijziging stilletjes tot **minder**
pseudonimisering leidt. Een kale lijst woorden is een lijst die niemand kan
nakijken: een lezer ziet het verschil niet tussen `^gemeente$` en een regel die
ongemerkt een achternaam vrijstelt. Geweigerd en niet overgeslagen, want half
een lijst toepassen is erger dan geen — dan denkt iedereen dat de regel geldt.

Een sleutel die met `_` begint is commentaar en wordt overgeslagen. JSON kent
geen commentaar, en een lijst die kan uitleggen waarom hij bestaat is meer waard
dan een lijst die dat niet kan.

**Getypeerd betekent echt getypeerd.** `gemeente Gooise Meren` wordt door de
detector soms als `LOCATION` en soms als `ORGANIZATION` gemeld; een regel onder
één van beide werkt dan maar de helft van de tijd. Gemeten op 2026-09-20: de
regel stond alleen onder ORGANIZATION en 159 voorkomens als LOCATION bleven
staan.
`deny.json` — typed patterns that *are* PII; each match becomes a detection
(layer `list`, score 1.0) on top of what the detectors found:
```json
{"KENTEKEN": ["\\b[A-Z]{2}-\\d{3}-[A-Z]\\b"]}
```

Een kale string mag hier, want een deny-regel voegt bescherming tóé. In de repo
draagt elke regel er toch een reden bij: een patroon zonder uitleg is over een
half jaar niet te beoordelen.

**Wat er nu in staat: het straatadres.** `Kerkstraat 12` kwam de pijplijn uit
als `[LOCATION:…] 12` — de detector levert de straatnaam soms wél en het
huisnummer nooit, dus het nummer bleef staan. De regel matcht een woord op een
straatachtervoegsel gevolgd door een huisnummer. Achtervoegsels die óók gewone
woorden eindigen (`ring`, `baan`, `pad`, `hof`, `park`) staan er **bewust niet**
bij: "Verandering 3" is geen adres. Getoetst op `Artikel 5`, `bijlage 3`,
`Postbus 1234` en een straatnaam zonder nummer.

Let op wat dit kost: het evalcorpus zaait het woonadres als gewone tekst en niet
als PII, dus op dát corpus telt deze regel als precisieverlies. Of een woonadres
PII is, is een uitspraak over de zaak en niet iets wat uit een regex volgt — die
vraag ligt bij de eigenaar van het corpus.

## De particle-naamregel en zijn gazetteer

Een naam als `Hendrik ter Braak` is één persoon, niet een los woord "ter"
tussen twee andere: `src/wordsworth/particle_names.py` herkent de vorm
`<voornaam> <partikel> <achternaam>` (`van`, `van der`, `van den`, `de`,
`ter`, `ten`) als ÉÉN `PERSON`-span met laag `dutch_particle_name`, vóórdat
de allow/deny-lijsten worden toegepast. Alleen in de **reversible** driver
(`ReversibleAnonymizer`); de irreversible `OpenAnonymiserAnonymizer` draait
deze regel niet.

De regel matcht alleen als het woord vóór het partikel in een eigen
gazetteer staat: `src/wordsworth/data/voornamen.json`, een lijst van
`{"naam", "reden"}`. Zonder die ankering zou `Raad van State` of `Kamer van
Koophandel` ook als persoon worden gezien — en die namen horen leesbaar te
blijven. De lader (`particle_names.load_gazetteer`) weigert een entry zonder
(of met een lege) `reden`, en een ontbrekend of onleesbaar bestand is een
harde fout, nooit een lege lijst.

**Een gemiste naam van deze vorm fix je door de voornaam hier toe te voegen,
niet via `deny.json`**: `deny.json` werkt op het hele patroon, en een
voornaam die ontbreekt in de gazetteer is precies waarom `Raad van State`
geen persoon wordt. Toevoegen is een reviewed git-wijziging van
`voornamen.json`, met een `reden`.

Een allow-regel op `PERSON` kan een particle-naam net als elke andere
`PERSON`-detectie onderdrukken: de regel voegt zijn treffers toe aan de
entiteitslaag vóórdat `DetectionLists.apply` draait, en loopt dus door
dezelfde onderdrukking.

`Ton`, `Wil` en `Bart` staan **met opzet niet** in de gazetteer: het zijn ook
gewone hoofdlettervolgorde-woorden aan het begin van een zin, en opnemen zou
precisie kosten. Van de 14 voornamen in `eval/synthetic.py` blijven `Ton` en
`Bart` daardoor gemist — een geaccepteerde, bewuste trade.

De gazetteer telt **niet mee in `lists_hash`**: die hash is alleen over
`allow.json`/`deny.json`, en de gazetteer heeft zijn eigen versiebeheer
(losstaand, zie `reanonymise-particle-name-documents`).

Zie `tests/test_particle_names.py` voor het gedrag, de gazetteer-weigeringen
en de grens tussen wat wel en niet matcht.

**De rem op de gazetteer.** `tests/test_particle_names_veiligheid.py` toetst
elke gazetteer-entry tegen het evaluatiecorpus (zoals
`test_allow_list_veiligheid.py` dat voor de allow-lijst doet): een entry die
niet vóór een partikel en achternaam voorkomt telt niet mee als geslaagd en
faalt met de naam van die entry, en alleen een geoefende entry wordt ook nog
getoetst op valse `PERSON`-treffers. Hetzelfde bestand bewaakt dat elk
partikel minstens één `PERSON`-zin heeft in de vaste zinnenlijst
`tests/fixtures/gewone_zinnen_nl.txt` — kolommen `PERSON<TAB>zin<TAB>volledige
naam` of `GEEN<TAB>zin`, met een `{naam}`-slot. `tests/test_particle_names_zinnen.py`
loopt elke gazetteer-entry over elke zin: een `PERSON`-zin verwacht precies die
volledige naam (en dat hij na anonimiseren niet meer leesbaar is), een
`GEEN`-zin verwacht geen `PERSON`. Een treffer faalt de toets en noemt de
entry; geen van beide bestanden schrijft naar `voornamen.json` — een gemiste
naam herstel je zoals hierboven, met de hand. Dit bewijst dat de regel wordt
geoefend en dat er geen `Ton`-achtige entry verscheept is, niet dat de
gazetteer compleet is.

## Waar de lijsten leven

In de repo (`lists/`), mee in het image, **niet** in een ConfigMap. De
content-hash staat in elk de-identificatie-auditrecord zodat een document terug
te voeren is op de regels die het maakten; een hash die wijst naar iets dat
iedereen ter plekke kan wijzigen, is een getal zonder herkomst.

## De rem

`tests/test_allow_list_veiligheid.py` toetst elke allow-regel tegen het
evalcorpus, waar bekend is wat er aan PII in zit. Een regel die een ingezaaide
waarde onderdrukt, faalt. Dat geldt ook voor de **losse woorden** van zo'n
waarde: het corpus zaait volledige namen ("Hendrik de Vries"), maar de detector
levert in de praktijk ook losse achternamen — en een regel `^vries$` is precies
het gevaarlijke geval. De eerste versie van die toets keek alleen naar de
volledige waarde en liet dat passeren.

Dat is de reden dat een allow-lijst hier mag bestaan. Zonder een corpus waarvan
de antwoorden bekend zijn, is elke regel een kwestie van vertrouwen.

Where it applies: the reversible driver applies both lists after detection; the
irreversible OpenAnonymiser driver applies the **deny** list only (the service
redacts server-side, so an allow rule cannot un-redact). Suppressions are
counted per type in the audit aggregates under `suppressed_by_list`.

## Feedback

**Vanaf het scherm.** Op de documentpagina is elk token aanklikbaar: klik erop
en je meldt dat het geen PII van dat type is. Eronder staat een keuzelijst voor
het omgekeerde — "hier is een ADRES gemist". Dat is de weg die een mens neemt;
de curl hieronder is dezelfde melding voor wie een script schrijft.

Er gaat **nooit een waarde** mee, en het formulier heeft daarom geen vrij
tekstveld. Dat is geen vergetelheid maar de reden dat deze meldingen veilig in
de append-only keten passen. Het eindpunt weigert bovendien een `token` dat geen
`[TYPE:hash8]` is — anders was de regel te omzeilen door een naam in dat veld te
zetten.

**Waar de meldingen samenkomen.** `/console/meldingen` — of liever
`/console/feedback` — zet ze bij elkaar: hetzelfde token door meer mensen
gemeld staat bovenaan. Het **gewicht is het aantal verschillende melders**, niet
het aantal meldingen: één iemand die tien keer klikt is geen tien mensen, en
zonder dat onderscheid is de lijst te vullen door één vasthoudende gebruiker.

Dat scherm toont **geen waarden**. Welke naam achter een token zit, zie je langs
de gewone weg: een grant, een rol, een geauditeerde onthulling. Een overzicht
dat de waarde er "even" bij zet is de tweede deur met het grootste bereik --
hij toont ze allemaal tegelijk.

Wat je meldt verandert de lijsten **niet** vanzelf. Dat blijft een git-wijziging
die iemand nakijkt; de melding is de aanleiding, niet de beslissing.

## Het bestaande corpus bijwerken

Een lijstwijziging geldt alleen voor wat er daarna binnenkomt. Wat er al in
staat, volgt met:

```sh
curl -XPOST $API/reprocess -H 'content-type: application/json' \
  -d '{"only_outdated": true}'
```

`only_outdated` slaat over wat al onder de **huidige** lijsten is verwerkt. Dat
is geen tijdstempel die je moet onthouden: de lijst-hash staat in elk
de-identificatie-auditrecord, dus verandert de lijst, dan is elk document dat
nog de oude hash draagt vanzelf achterstallig.

De lus zelf staat in `wordsworth/reprocess.py` en wordt door het eindpunt én
door een Job gebruikt. Dat is geen netheid maar een geleerde les: op
2026-09-20 bouwde ik die lus na in een Job en liet de foutregistratie weg,
waardoor een run van 250 documenten geen enkel spoor naliet van wat er misging.
Elke mislukking hoort een `reprocess_failed`-auditrecord op te leveren met de
oorzaakketen (`ObjectStoreError <- KeyError`) en veilige kenmerken — nooit een
waarde.

**Reken op uren.** Reprocess haalt de brontekst opnieuw op, laat hem langs de
detector, embedt opnieuw en schrijft de index bij. Op 2026-09-20 kostte dat
ongeveer 6 ms per teken — voor 770 documenten (8,6 miljoen tekens) veertien
uur, op één core zonder GPU. Draai het als Job, niet als HTTP-verzoek, en niet
in de pod die het verkeer bedient: een meting daar legde die pod om (OOM).

Die run moest halverwege onderbroken worden. Zónder `only_outdated` had de
vervolgrun de 200 afgeronde documenten overgedaan — dáárom bestaat de vlag.

**De redacted PDF wordt stale.** `reanonymize` herbouwt ook de box map
(pdf-redaction); zolang dat niet is gebeurd, antwoordt
`GET /documents/{id}/redacted.pdf` met 409 `stale` zodra de huidige lijsten
afwijken van de lijsten waaronder die box map is gemaakt — ook als het
document zelf nog niet opnieuw is verwerkt. Pas na deze run (of een losse
`reanonymize` op dat document) levert het eindpunt weer een PDF.

A reader who spots a false positive or a miss records it against the document:
```
curl -XPOST $API/documents/<doc>/feedback -H 'content-type: application/json' \
  -d '{"kind":"fp","type":"PERSON","token":"[PERSON:3fa9c2d1]"}'
```
`kind` is `fp` or `fn`; `token` is the `[TYPE:hash8]` pseudonym concerned (for
`fp`). There is **no free-text field**: feedback can never carry a clear value.
The call appends a `detection_feedback` access event to the document's audit
chain and changes nothing else. Turning feedback into a list entry is a
reviewed git change; after changing the lists, run `POST /reprocess` if the
already-indexed corpus should follow.

### Na een regel- of gazetteerwijziging: de ids expliciet meegeven

`only_outdated` kijkt alleen naar `lists_hash`, en die hash is alleen over
`allow.json`/`deny.json`. Een nieuwe detectieregel (zoals de particle-naamregel)
of een nieuwe entry in `voornamen.json` verandert `lists_hash` **niet** — met
opzet, anders zou elke gazetteerwijziging het hele corpus achterstallig maken.
Na zo'n wijziging selecteert `only_outdated` dus niets. Geef de documenten dan
expliciet mee als `document_ids`.

De ids van een dossier haal je uit de productiedatabase, **alleen-lezen**
(`default_transaction_read_only=on`), via de jumpy/kubectl-route en de
verbinding van de api-pod zelf. De query geeft meteen de komma-gescheiden
lijst:

```sh
ssh jumpy kubectl -n wordsworth exec -i deploy/wordsworth-api -- python3 - <<'EOF'
import os
from sqlalchemy import create_engine, text
# Alleen-lezen voor elke transactie op deze verbinding.
e = create_engine(os.environ["WORDSWORTH_DATABASE_URL"],
                  connect_args={"options": "-c default_transaction_read_only=on"})
with e.connect() as c:
    print(c.execute(text(
        "SELECT string_agg(dd.document_id::text, ',' ORDER BY dd.document_id) "
        "FROM dossier_documents dd JOIN dossiers d ON d.id = dd.dossier_id "
        "WHERE d.name = :naam"), {"naam": "<dossiernaam>"}).scalar())
EOF
```

Die lijst gaat in `WORDSWORTH_REPROCESS_IDS` van de Job
(`deploy/k8s/45-reprocess-job.yaml`), of in `wordsworth reprocess --ids …`, of
als body van het eindpunt:

```sh
curl -XPOST $API/reprocess -H 'content-type: application/json' \
  -d '{"document_ids": ["<id>", "<id>"]}'
```

### De telcontrole lezen

Elk opnieuw geanonimiseerd document levert één regel op, per type het aantal
**verschillende** pseudoniemen in de opgeslagen tekst ervóór en erná, en
hoeveel er bijkwamen en verdwenen (`wordsworth/reprocess_counts.py`):

```json
{"counts": {"BSN": {"added": 0, "after": 1, "before": 1, "removed": 0},
            "PERSON": {"added": 1, "after": 1, "before": 1, "removed": 1}},
 "document_id": "…", "event": "reprocess_counts", "level": "info"}
```

- **Verschillende pseudoniemen, geen vermeldingen.** Eén persoon die vijf keer
  genoemd wordt telt als één. `PERSON 12` is twaalf personen, niet twaalf
  vermeldingen.
- **Lees `added` en `removed`, niet alleen de totalen.** Het geval waarvoor
  dit bestaat: de voornaam was een eigen token, na de regel is de hele naam met
  partikel één token. Dan blijft het totaal gelijk (`before 1, after 1`) en
  laat alleen `added 1, removed 1` zien dat er iets veranderde.
- **Geteld uit de opgeslagen tekst**, niet uit het pseudoniemregister: dat
  krimpt nooit, dus "erna" kon daar nooit lager zijn dan "ervoor".
- **Waar je hem leest.** In het antwoord van `POST /reprocess`, veld
  `entity_counts` (document-id → type → de vier getallen); de Job print dat
  antwoord, dus de getallen staan in
  `kubectl -n wordsworth logs job/wordsworth-reprocess`.
  En als regel in de log van de service (logger `wordsworth.pipeline`). De
  regel wordt pas geschreven nadat de commit van dat document gelukt is.
- **Een overgeslagen of mislukt document heeft geen telling.** Het staat niet
  in `entity_counts` en logt geen regel; zijn uitkomst (`skipped`,
  `retryable`, `failed`, met `problems` en het `reprocess_failed`-record)
  zegt wat er gebeurde.
- **Nooit een waarde.** Geen naam, geen token, geen omringende tekst, geen
  offset: alleen het id, typenamen en getallen.

**Wat de telling niet bewijst.** Dat er geen naam meer leesbaar is. Hij telt
wat getokeniseerd werd; een naam die de regel niet herkent (een voornaam die
niet in de gazetteer staat) telt ervoor en erna niet mee. Of een document echt
schoon is, lees je in het document zelf.

**Na een wijziging van de domeinsleutel of van het normalisatieprofiel**
(`PROFILE_VERSION`) is elk token een nieuw token: `added` en `removed` zijn
dan allebei gelijk aan het hele aantal en zeggen niets over detectie.

**In irreversibele modus** zijn er geen pseudoniemtokens (alleen kale
plaatshouders als `[BSN]`), dus vindt de telling niets. `/reprocess` wordt in
die modus ook niet aangeboden.
