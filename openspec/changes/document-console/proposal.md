# Change: document-console

## Why

Je kunt vandaag niet zíen wat de straat doet.

De pijplijn is te volgen via `/documents/{id}/anonymized`, een auditrecord en een
Prometheus-teller. Dat werkt voor wie de API kent en is onbruikbaar voor het
gesprek waar dit project om draait: iemand een document laten zien, ernaast het
gepseudonimiseerde document, en vragen *"klopt dit?"*. Zonder dat scherm is elke
demo een terminal en elke beoordeling van de kwaliteit een kwestie van vertrouwen
in mijn samenvatting.

Er is een tweede gat, en dat is het belangrijkere. Een combinatie van PII-types
kan alleen worden vastgesteld door iemand die de documenten kent — dat hangt af
van de populatie, de sector en de context (identifying-combinations zegt dat, en
laat vervolgens de vaststelling in een JSON-bestand liggen). Een regel die alleen
bestaat in een profielbestand dat een ontwikkelaar bewerkt, wordt in de praktijk
door niemand vastgesteld.

## Wat deze change WEL doet

- **Een lijst van documenten** met hun toestand, welke PII-types erin zijn
  aangetroffen en hoeveel.
- **Een documentpagina** die de gepseudonimiseerde tekst toont met de tokens
  gemarkeerd, plus per token het type. Dat is het artefact dat de straat
  werkelijk produceert — niet een herdraai van de detectoren over de brontekst.
- **Combinaties vaststellen in het scherm.** Wie de documenten beoordeelt, legt
  daar vast welke types sámen identificeren, met een reden, en ziet meteen in
  hoeveel documenten die combinatie voorkomt. Vaststellen en meten in één
  handeling, want een vaststelling zonder getal is een vermoeden.

## Wat deze change NIET doet

- **De console toont geen onversleutelde PII.** Ze laat zien wat er ná
  pseudonimisatie staat. Het origineel opvragen loopt over het bestaande,
  grant-bewaakte en geauditeerde `reveal` — de console krijgt daar geen eigen,
  zachtere deur naast. Een inspectiescherm dat zelf mag onthullen is een
  achterdeur met een nette naam.
- **Geen bewerken van documenten.** Lezen, en het vastleggen van een
  combinatie. Meer niet.
- **Geen authenticatie erbij verzonnen.** De console valt onder dezelfde
  `WORDSWORTH_API_TOKEN`-bewaking als de rest en wordt alleen gemonteerd als die
  aan staat. Liever geen scherm dan een scherm zonder slot.

## Impact

- `console.py` + templates (nieuw), `models.py` (`declared_combinations`),
  `api.py` (montage), `openspec/specs/console`.
- Nieuwe afhankelijkheid: `jinja2` (BSD-3, verenigbaar met MIT). Autoescaping is
  structureel; met de hand escapen in f-strings is precies waar XSS ontstaat.
- Niets aan de pijplijn zelf.
