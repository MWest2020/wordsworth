## ADDED Requirements

### Requirement: De API overleeft het wegvallen van één node

De API SHALL met ten minste twee replica's draaien, verspreid over
verschillende nodes, met een verstoringsbudget dat er altijd één
overeind houdt. Dit SHALL pas ingesteld worden wanneer de opslagklasse
van elk gemount volume aantoonbaar kan verhuizen tussen nodes; tot die
tijd SHALL de opzet één replica houden, omdat een tweede replica op
node-gebonden opslag redundantie suggereert die er niet is.

#### Scenario: Node valt weg

- **GIVEN** twee replica's op verschillende nodes en een opslagklasse
  die kan verhuizen
- **WHEN** één node uitvalt of wordt leeggehaald
- **THEN** blijft de console antwoorden

#### Scenario: Opslag zit nog aan een node vast

- **GIVEN** een volume op een opslagklasse die aan één node vastzit
- **WHEN** iemand het aantal replica's verhoogt
- **THEN** is dat in strijd met deze eis, en hoort de verhoging terug
  gedraaid te worden tot de opslag verhuisbaar is

---

### Requirement: "Hoogbeschikbaar" staat er pas na een uitschakel-test

De documentatie SHALL wordsworth pas hoogbeschikbaar noemen nadat een
test heeft aangetoond dat de console blijft antwoorden terwijl één node
is uitgeschakeld. De uitkomst van die test SHALL vastgelegd worden met
datum en welke node het betrof.

#### Scenario: Test gedraaid

- **WHEN** de uitschakel-test is gedraaid en geslaagd
- **THEN** noemt de documentatie de datum, de node en wat er tijdens de
  test wél en niet bereikbaar was

#### Scenario: Test niet gedraaid

- **WHEN** er geen uitschakel-test is gedraaid
- **THEN** zegt de documentatie dat wordsworth één node nodig heeft en
  wat er wegvalt als die node weg is
