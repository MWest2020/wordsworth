---
status: draft
last_reviewed: 2026-09-03
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
