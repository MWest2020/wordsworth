# Change: rollen

## Why

Een gebruiker hoort aan een **rol** te hangen, en die rol bepaalt welke PII-types
zichtbaar zijn. Een beheerder ziet alles, want die moet kunnen kiezen wat bij
welke rol hoort. En een rol moet met een breakglass-procedure te deactiveren
zijn.

Wat er nu is: een grant noemt een `recipient` en een lijst types, per document of
globaal, en sinds vandaag moet de beller de recipient zíjn. Dat is de bouwsteen.
Wat er niet is, is een rol: "HR" bestaat alleen doordat iemand toevallig een
sleutel met dat label heeft.

## De beslissing waar deze change om draait

Is een rol een **sjabloon** of een **entiteit**?

**Sjabloon.** Een rol is een naam voor een verzameling types. Iemand die rol geven
is een grant uitgeven met die types. `authorize()` verandert niet, grants blijven
de enige waarheid. Saai, en dat is meestal het goede antwoord.

Het breekt op breakglass. Een rol uitzetten betekent dan: elke grant terugvinden
die uit die rol is voortgekomen en hem intrekken. Dat is een uitwaaiering met een
tijdvenster erin, en breakglass is precies het moment waarop je geen tijdvenster
wilt. Bovendien verandert het aanpassen van een rol niets aan wat er al is
uitgegeven — je denkt dat je iets hebt ingeperkt en dat is niet zo.

**Entiteit.** `authorize()` kijkt bij elke onthulling naar de rol. Een rol
uitzetten werkt onmiddellijk en exact. Maar het verplaatst de beslissing naar een
nieuwe laag, en dat is precies wat dit project nergens doet.

**Wat ik voorstel is het derde ding:** een grant mág een rol noemen in plaats van
een typelijst, en `authorize()` lost die rol op het moment van beslissen op. De
grant blijft het autorisatierecord — wie, welke scope, wanneer verlopen, wanneer
ingetrokken. De rol levert alleen de typeverzameling. Er komt geen tweede
beslispunt bij; er komt één invoer bij op het punt dat er al is.

Breakglass is dan geen opruimactie maar een feit: de rol is uit, de
typeverzameling is leeg, elke grant die hem noemt autoriseert niets. Eén plek,
geen venster.

## Hoe ver dit gaat in de PoC

Mark, 2026-09-17: *"console en grant [zijn] voor nu nog echt in PoC-fase. Dat
komt meestal met een gebruikstest wat meer naar voren. Voor mij mag een admin nu
alle grants hebben en later toewijzen aan rollen."*

Dat verandert het tempo en niet de vorm. Wat nú nodig is, is dat één beheerder
alles kan zien; het verdelen over rollen komt zodra een gebruikstest laat zien
wélke rollen er zijn. Rollen bedenken vóór die test is precies het soort werk dat
er af moet als de werkelijkheid binnenkomt.

De vorm blijft dus staan — een grant mag een rol noemen, `authorize()` lost hem
op — want daar bouw je later op verder. Maar in de PoC is er één rol, hij heet
beheerder, en hij houdt alles.

**En dat botst op iets dat we in augustus bewust hebben dichtgezet.** "Alles"
betekent alle types én alle documenten, en dat laatste is een ongescopete grant.
`harden-global-grant-gate` weigert die: `WORDSWORTH_ALLOW_GLOBAL_GRANTS` staat op
false, staat niet in de productie-configmap, en een ongescopete grant wordt bij
uitgifte geweigerd én autoriseert niets.

Drie manieren eruit, en twee ervan zijn fout:

1. **De vlag omzetten.** Dan mag élke ongescopete grant weer alles — niet alleen
   die van de beheerder. Dat draait de hardening terug voor iedereen om hem voor
   één iemand te openen.
2. **Per document een grant.** 791 stuks, en morgen meer. Geen.
3. **De poort op de rol zetten in plaats van op een vlag.** Een ongescopete grant
   is toegestaan wanneer hij de beheerdersrol noemt, en anders niet. De
   hardening blijft voor alle andere grants staan, en de uitzondering draagt de
   naam van wie hem krijgt in plaats van te schuilen achter een boolean.

Ik stel 3 voor. Het is ook de enige van de drie waarbij het auditspoor achteraf
kan laten zien dát er een uitzondering gold en voor wie.

## Wat deze change WEL doet

- **Rollen als benoemde typeverzamelingen**, met een actief/inactief-stand.
- **Een grant mag een rol noemen** in plaats van een typelijst. Beide vormen
  blijven bestaan; bestaande grants veranderen niet.
- **`authorize()` lost de rol op** bij elke beslissing — hetzelfde punt, één
  invoer erbij. Een inactieve rol levert een lege verzameling, en dat weigert al.
- **Breakglass: een rol uitzetten**, met wie het deed en waarom, in het
  auditspoor. Onmiddellijk, en zichtbaar.
- **Een beheerdersrol met alle types.** "Alles zien" is een rol en geen pad langs
  `authorize()`. Elke onthulling door een beheerder is een gewone, geauditeerde
  onthulling — anders is de beheerder de tweede deur die dit project nergens
  heeft.
- **De ongescopete grant wordt toegestaan op naam van die rol**, niet op een
  vlag. De hardening uit `harden-global-grant-gate` blijft staan voor elke andere
  grant.

## Wat deze change NIET doet

- **Geen eigen identiteiten.** Wie iemand ís komt uit #81. Een rolmodel bovenop
  gedeelde api-sleutels is er een op papier: "HR mag dit" wordt dan "wie de
  HR-sleutel heeft mag dit". **#81 hoort hiervóór.**
- **Geen rollen per dossier.** Dat vergt #78 en is een eigen vraag.
- **Geen zelfbediening.** Een beheerder wijst toe; niemand geeft zichzelf een
  rol. De uitzondering is de installatie, waar de eerste beheerder per definitie
  niet door een beheerder is aangewezen.
- **Geen eigen identiteitsbeheer.** Richting productie komt daar een echte
  oplossing voor (Keycloak of gelijkwaardig). Deze change moet daar ruimte voor
  laten en er niet omheen groeien: waar een rol vandaan komt, is straks niet
  meer hier.

## Open vragen die deze change moet beantwoorden

1. ~~Mag een beheerder zichzelf de beheerdersrol geven? Wie geeft de eerste?~~
   **Beantwoord door Mark (2026-09-17): bij het installeren van de applicatie
   bestaat er één (super)admin, en die bepaalt de RBAC.** De eerste rol komt dus
   niet uit het rollenstelsel maar uit de installatie — precies zoals een
   root-account niet door een gebruikersbeheerder wordt aangemaakt. Dat maakt de
   bootstrap een expliciet moment in plaats van een gat, en het betekent ook dat
   die ene identiteit vanaf dag één iets is om zuinig op te zijn.

   Mark tekende erbij aan dat dit een MVP-antwoord is: **richting productie moet
   er degelijke RBAC staan**, te zijner tijd met Keycloak of iets gelijkwaardigs.
   Deze change bouwt dus niet het eindmodel maar de vorm die daarnaartoe kan
   groeien — en moet daarom nergens aannemen dat rollen hier vandaan blijven
   komen.
2. **Wat betekent een rol veranderen voor wat er al is onthuld?** Niets — dat is
   gebeurd en staat in het spoor. Maar het scherm moet dat zeggen, anders leest
   iemand een ingeperkte rol als "die gegevens zijn nooit gezien".
3. **Welke rollen zijn er eigenlijk, naast beheerder?** Niet beantwoorden vóór
   de gebruikstest. Dit voorstel levert de vorm; de inhoud komt uit wat mensen
   werkelijk blijken te doen, en een rol die wij nu verzinnen is een aanname met
   een juridische staart.
4. **Wat gebeurt er met de bestaande grants op losse labels?** Ze blijven
   werken. Maar zolang beide vormen bestaan, is "wie mag wat" op twee plaatsen
   te lezen, en dat is precies hoe autorisatiefouten ontstaan. Is er een pad
   waarop de losse vorm verdwijnt?
5. **Breakglass: wie mag hem overhalen, en hoe komt de rol terug?** Een noodrem
   die iedereen kan indrukken is een schakelaar; een die niemand kan overhalen is
   een versiering.

## Impact

- `grants.py` (`authorize()` krijgt de rol-resolutie), `models.py` (rollen,
  lidmaatschap), `api.py` (rollen uitgeven, toewijzen, uitzetten), de console,
  `openspec/specs/rollen` en een MODIFIED op de bestaande grant-spec.

Dit is de autorisatiekern. Van de vier epics is dit degene waar een fout niet
"iets werkt niet" betekent maar "iemand zag iets".
