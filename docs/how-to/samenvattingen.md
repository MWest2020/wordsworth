---
status: current
last_reviewed: 2026-09-19
---

# Samenvattingen per document

Een korte samenvatting naast elk zoekresultaat, zodat je ziet wáárom een
document bovenaan staat en niet alleen dát het er staat.

## Wat een samenvatting is, en wat niet

Alles wat wordsworth verder toont is terug te voeren op iets dat is opgeslagen:
de gepseudonimiseerde tekst, de tokens, de ranking, de onderwerpnamen. Het
fragment op de zoekpagina is een **citaat** — je kunt het letterlijk terugvinden.

Een samenvatting is dat niet. Hij is geschreven door een taalmodel en is dus een
**bewering**. Daarom:

- staat hij **naast** het citaat en niet ervoor in de plaats;
- draagt hij zijn herkomst mee: welk model, welke datum;
- zegt het scherm er met zoveel woorden bij dat het geen citaat is.

## Twee varianten

| | extractief | model |
| --- | --- | --- |
| wat het is | de eerste regels van het document, letterlijk | een zin die een taalmodel schreef |
| soort tekst | **citaat** — terug te vinden in de opgeslagen tekst | **bewering** |
| kosten | nul | ~123 s per document op deze hardware |
| hardware | geen | één core, geen GPU → 588 documenten ≈ 20 uur |

Bij bestuurlijke post staat juist in de eerste regels wat je wilt weten:
afzender, kenmerk, datum, onderwerp. Dat is precies wat een model van 3b op
OCR-ruis het slechtst navertelt. Vergelijk ze op je eigen corpus voor je kiest:

```sh
python -m scripts.eval.vergelijk_samenvattingen --dossier <uuid> --aantal 5
```

Dat levert geen score op, en dat is opzettelijk: er is geen waarheid over "een
goede samenvatting" in dit corpus, en een getal verzinnen is erger dan er geen
hebben. Het levert de twee teksten naast elkaar met de tijd erbij.

## Maken

```sh
# extractief: de eerste regels, nul modelaanroepen
curl -XPOST "$API/dossiers/<dossier-uuid>/summaries?extractief=true" -H "x-api-key: $KEY"

# met het taalmodel
curl -XPOST "$API/dossiers/<dossier-uuid>/summaries" -H "x-api-key: $KEY"
```

Maakt wat er nog niet is; bestaande blijven staan. Opnieuw draaien doet het werk
dus niet opnieuw — bij een taalmodel is dat geen optimalisatie maar het verschil
tussen een knop die je durft in te drukken en een die je vermijdt.

Op verzoek en niet bij ingest, om dezelfde reden als bij de onderwerpen: anders
wacht de straat op het taalmodel, voor een tekst die op dat moment niemand
leest.

Het wegschrijven is een **upsert**, geen lezen-dan-schrijven. `compute()` kijkt
aan het begin één keer wat er al is, en bij een taalmodel zit daar een kwartier
tussen dat moment en het schrijven. Op 2026-09-19 liepen een handmatige run en
een Job elkaar zo in de weg: de Job viel om op `duplicate key` ná dertien
minuten werk.

**Reken op minuten per document.** Tien documenten uit een Woo-dossier kostten
op productie meer dan een kwartier met `llama3.2:3b`. Voor een groot dossier is
dit werk voor een Job, niet voor een HTTP-verzoek — en de berekening **commit
per document**, zodat een afgekapte run houdt wat af is en geen uren een
leeslock vasthoudt. Dat laatste is geen theorie: een lange leestransactie hield
op 2026-09-18 een `ALTER TABLE` uit de init-job tegen en daarmee de hele uitrol.

Het antwoord draagt de noemer:

```json
{"dossier_id":"…","model":"llama3.2:3b",
 "seen":30,"made":24,"skipped":3,"failed":1,"without_text":2}
```

| veld | betekenis |
| --- | --- |
| `seen` | documenten in het dossier |
| `made` | nieuw gemaakt |
| `skipped` | had er al een |
| `failed` | het model gaf niets bruikbaars |
| `without_text` | nooit door de straat gekomen |

Zonder die vijf leest "24 gemaakt" als een uitspraak over het hele dossier.

## Tokens gaan eruit — en waarom dat geen detail is

De samenvatting wordt gemaakt over de gepseudonimiseerde tekst, want een andere
is er niet. **De pseudonym-tokens worden er daarna deterministisch uitgehaald.**

Dat stond eerst andersom in het voorstel: "hij mag tokens bevatten, dat is de
veilige vorm die het scherm toch al toont." Dat klopt voor een citaat. Voor
gegenereerde tekst niet.

Een taalmodel kan een token **verzinnen**. `[PERSOON:aabbccdd]` ziet eruit als
elk ander token, en de mappingstore is globaal: als dat token bestaat hoort het
bij iemand — alleen niet bij dit document. Een samenvatting die beweert dat die
persoon hier iets deed, koppelt een vreemde aan dit stuk, en een onthulling op
die samenvatting levert diens klare naam binnen een grant die op dít document
gescoped is. Dat is precies het gat dat `neutralise_foreign_tokens` aan de
invoerkant dichtzet, nu aan de uitvoerkant.

De prompt vraagt het model óók geen tokens over te nemen. Dat is een verzoek;
het filteren is de garantie, en alleen op die tweede staat een test
(`test_a_token_never_survives_into_a_summary`).

Ook een **kale** pseudonym-id gaat eruit. Gemeten op 2026-09-19 schreef het
model *"op locatie 9e9d0346, met hulp van organisatie a4e276dd"*: het had de
tokens geparafraseerd en de haken laten vallen, en het filter zocht de volledige
vorm. Die acht tekens zíjn de sleutel — stabiel over documenten heen, dus ze
koppelen "dit stuk en dat stuk gaan over dezelfde persoon" zonder dat er ooit
iets onthuld wordt, en tussen haken teruggezet accepteert de reveal ze.

Waar een token stond komt een **zichtbaar weglatingsteken** (`…`), geen lege
plek. De eerste productierun gaf zinnen als *"de effecten van de aanzanding op
het  en geeft aanbevelingen"*: dat leest als een taalfout in plaats van als een
weglating, en dan gaat de lezer twijfelen aan het model terwijl er gewoon iets
is weggehaald.

Blijft er na het filteren niets over, dan is er **geen** samenvatting. Een
placeholder die eruitziet als inhoud is erger dan een leeg veld: hij wordt
gelezen als de samenvatting van een document dat niemand heeft samengevat.

## De poort

Achter `WORDSWORTH_CORPUS_READ_LABELS`, net als de opgeslagen tekst. Een
samenvatting zegt waar een document over gaat; dat is dezelfde soort kennis.

Niet in exports, niet in URL's, niet in facetten.

## Wat dit niet is

Geen antwoord op je vraag. Dat is `/ask` (RAG): één antwoord over meerdere
bronnen, met een grounding-guard die verzonnen citaties laat vallen. De twee
door elkaar halen levert een tekst op die noch een documentsamenvatting noch een
antwoord is.

Zie ook [console](console.md) en [onderwerpen](topics.md).
