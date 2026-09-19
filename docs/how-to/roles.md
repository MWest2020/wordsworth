---
status: current
last_reviewed: 2026-09-19
---

# Rollen: wie ziet welke PII

Een rol is **een naam plus een verzameling PII-types**. Verder niets.

De **scope** — dit document of alles — zit niet in de rol maar in de grant, dus
je kiest hem bij het *toekennen*. Dezelfde rol kan aan de een gegeven worden
voor één document en aan de ander voor alles. Zat de scope in de rol, dan waren
"HR voor dit dossier" en "HR voor alles" twee rollen die morgen uit elkaar
lopen.

## Waarom een rol een ding is en geen sjabloon

Het verschil zit in wat er gebeurt als je hem uitzet.

Een **sjabloon** zou bij het toekennen de types naar de grant kopiëren. Die
grant leeft daarna zijn eigen leven. Een rol uitzetten is dan een opruimactie —
elke uitgegeven grant terugvinden en intrekken, met een tijdvenster erin,
precies op het moment dat je er geen wilt. En een rol inperken verandert niets
aan wat al is uitgegeven: je denkt dat je iets hebt dichtgezet en dat is niet zo.

Als **ding** wordt de rol opgelost op het moment dat `authorize()` beslist. Uit
is uit, onmiddellijk, en er verandert geen enkele grant. Dat laatste staat in
`test_switching_a_role_off_stops_a_reveal_that_was_working`: eerst onthult hij,
dan gaat de rol uit, dan geeft dezelfde grant 403 — en de grant staat nog op
`ACTIVE`.

## Een rol maken

In de console: **rollen** → naam invullen → types aanvinken → *Maak rol*. De
aanvinklijst komt uit het typeregister (`pii_categories`), met de AVG-grondslag
erbij — Art. 6, 9 en 10 zijn niet dezelfde beslissing.

Of over de API:

```sh
curl -XPOST $API/roles -H 'content-type: application/json' \
  -d '{"name":"HR","allowed_types":["PERSON","EMAIL"]}'
```

## Een rol toekennen

Een grant noemt **precies één** bron voor zijn types: een eigen lijst, een PPL,
of een rol. Twee bronnen voor één antwoord is hoe autorisatiefouten ontstaan.

```sh
# per document
curl -XPOST $API/grants -H 'content-type: application/json' \
  -d '{"recipient":"iemand@gemeente.nl","role":"HR","document_id":"<uuid>"}'

# globaal — alleen op naam van de beheerdersrol
curl -XPOST $API/grants -H 'content-type: application/json' \
  -d '{"recipient":"iemand@gemeente.nl","role":"beheerder"}'
```

### De ongescopete grant draagt een naam

Een grant zonder `document_id` onthult op **elk** document.
`WORDSWORTH_ALLOW_GLOBAL_GRANTS` weigert die, en dat blijft zo. De uitzondering
is de beheerdersrol: een ongescopete grant mag wanneer hij die rol noemt.

De twee alternatieven waren slechter. De vlag omzetten opent hem voor *élke*
ongescopete grant, voor iedereen — de hardening terugdraaien om hem voor één
iemand te openen. Per document een grant uitgeven is 791 stuks, en morgen meer.
Nu draagt de uitzondering de naam van wie hem krijgt, en zegt het auditspoor
achteraf dát er een uitzondering gold (`global_by_role`) en onder welke rol.

## Breakglass

```sh
curl -XPOST $API/roles/HR/deactivate -H 'content-type: application/json' \
  -d '{"reason":"sleutel gelekt"}'
```

Een reden is **verplicht**. Een noodrem zonder reden is een schakelaar waarvan
niemand later kan navertellen waarom hij overging, en dit is precies het moment
waarop dat uitmaakt. Terugzetten (`/activate`) vraagt er ook een: terugzetten is
net zo goed een besluit.

Elke wijziging aan een rol — aanmaken, inperken, uitzetten, aanzetten — komt in
het **sleutel-levensloopspoor** (`key_lifecycle`), waar grants en
sleutelrotaties ook staan. Niet in de document-hashketen: die is de
toestandsmachine van één document, en een rol raakt er duizend. De stand ná de
wijziging staat erbij, zodat uit de stroom zelf te reconstrueren is wat een rol
op enig moment toestond. De console schrijft hetzelfde record als de API — twee
wegen naar dezelfde handeling met één spoor eronder is hoe een spoor gaten
krijgt.

Wat er eerder onthuld is, verandert hierdoor niet. Dat is gebeurd en staat in
het spoor. **"Vanaf nu niet meer" is iets anders dan "is nooit gezien"** — de
console zegt dat er met zoveel woorden bij.

## De beheerdersrol

`wordsworth-init` maakt hem aan bij de installatie, met alle types die het
register kent. Mark, 2026-09-17: *"er is altijd 1 (super)admin bij het
aanmaken/installeren van de app, die bepaalt de RBAC."* Die eerste rol komt dus
niet uit het rollenstelsel — zoals een root-account niet door een
gebruikersbeheerder wordt aangemaakt.

Een bestaande beheerdersrol wordt **niet overschreven**. Zou elke uitrol hem
terugzetten op "alles", dan was een ingeperkte of uitgezette beheerdersrol één
deploy lang geldig — het tegenovergestelde van een breakglass.

"Alles zien" is daarmee een rol en geen pad langs `authorize()`. Elke onthulling
door een beheerder is een gewone, geauditeerde onthulling, en uitzetten werkt
ook op hem. Een bijzondere route voor beheerders is de tweede deur die dit
project nergens heeft — en het is de deur die het meest gebruikt wordt en het
minst bekeken.

## Wat hier niet woont

**Wie iemand is.** Dat komt uit de aanmelding: nu Cloudflare Access (het
geverifieerde e-mailadres is het callerlabel), later mogelijk Keycloak. Deze
laag kent alleen namen die daarvandaan komen, zodat de dag dat rollidmaatschap
ergens anders vandaan komt, alléén dat punt verandert en niet de beslissing.

Zie ook [grants](grants.md) en [api-auth](api-auth.md).
