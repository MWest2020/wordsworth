# Proposal: wordsworth overleeft het wegvallen van één node

## Why

Mark, 2026-09-20: *"is wordsworth btw High Availability?"* Nee. En dat
bleek dezelfde middag, toen de cluster-VM's één voor één opnieuw
opgestart moesten worden: bij node-03 is wordsworth een paar minuten
onbereikbaar, en daar is met de huidige opzet niets aan te doen.

Drie dingen maken het kwetsbaar, en ze hangen samen:

1. **De API draait op één replica** (`wordsworth-api`, `replicas: 1`).
2. **Het corpusvolume ligt op één node.** De opslagklasse is
   `local-path`; `wordsworth-corpus` staat vast op node-03, OpenSearch
   op node-02, Ollama op node-03. Een pod met zo'n volume kan alleen
   dáár draaien.
3. Daardoor is een tweede replica **schijnveiligheid**: hij zou het
   volume niet kunnen aankoppelen. Meer replica's zonder gedeelde
   opslag lossen niets op; ze maken het beeld alleen geruststellender
   dan de werkelijkheid.

Wat wél overleeft: Postgres draait met drie CNPG-instances verspreid
over de nodes, met failover. Dat deel is goed, en het laat zien hoe de
rest eruit zou moeten zien.

## What Changes

Deze change beschrijft de doeltoestand en de volgorde. Uitvoeren kan
pas als de opslaglaag er is — daarom is dit een spec die we opleveren
als het kan, en niet een run die we vandaag starten.

**Stap 1 — gedeelde opslag.** Een opslagklasse die niet aan een node
vastzit (`ReadWriteMany`, of ten minste een `ReadWriteOnce` die kan
verhuizen). SeaweedFS draait al in dit cluster; die is de eerste
kandidaat, met NFS of Ceph als alternatief. Zonder deze stap heeft de
rest geen zin.

**Stap 2 — de API op twee replica's**, met anti-affinity per node, en
een PodDisruptionBudget die zegt dat er altijd één overeind blijft. Dan
haalt `kubectl drain` niet per ongeluk de laatste weg.

**Stap 3 — de afhankelijkheden.** OpenSearch met meer dan één node, en
Ollama als gedeelde dienst of met een volume dat mee kan verhuizen.
Beide zijn zwaarder dan de API zelf; daarom komen ze na de API.

**Stap 4 — meten wat we beloven.** Eén test die één node uitschakelt en
controleert dat de console blijft antwoorden. Zonder die test is
"hoogbeschikbaar" een woord in een document.

## Scope / Not in scope

**In:** de doeltoestand van wordsworth zelf: replica's, verstoringsbudget,
plaatsing, en de eis dat een opslagklasse niet aan een node vastzit.

**Out:** de opslaglaag inrichten (dat is homelab-werk, geen
wordsworth-code), en hoogbeschikbaarheid van Postgres — dat is er al.

## Wat dit eerlijk houdt

Een tweede replica bovenop node-gebonden opslag is erger dan één
replica: het ziet eruit als redundantie en is het niet. De spec eist
daarom dat de opslagklasse eerst aantoonbaar kan verhuizen, en dat de
uitschakel-test draait voordat we het woord "hoogbeschikbaar" ergens
opschrijven.
