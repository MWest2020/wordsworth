# Proposal: samenvatten is een commando, geen Job met een script erin

## Why

De samenvattingen worden gemaakt door een Job in het cluster die een
script van dertig regels meedraagt in zijn eigen `args` — een
`python -c` met daarin de sessie, de generator, de dossier-UUID uit een
omgevingsvariabele en het printen van de uitkomst. Die Job staat in
geen enkele repo. Hij is één keer met de hand aangemaakt en leeft nu
alleen nog in de cluster-API.

Dat is dezelfde fout als een realm dat alleen in een database bestaat:
niemand kan zien waarom het er zo uitziet, een wijziging is
onnavolgbaar, en na een herinstallatie is het weg.

Er is ook echt iets misgegaan dat hierdoor moeilijk te zien was. Op
2026-09-19 viel een run om op

```
duplicate key value violates unique constraint "document_summaries_pkey"
```

na dertien minuten werk. De oorzaak — twee runs die elkaar inhalen — is
inmiddels in de code opgelost met een upsert in `_bewaar`, en de
volgende poging van diezelfde Job slaagde. Maar het beeld in het
cluster bleef een Job met `Error` ernaast, zonder dat ergens staat wat
die Job doet of met welke versie hij draaide.

## What Changes

- Een echt commando: `python -m wordsworth.samenvatten`, met een
  dossier-UUID of "alles wat nog geen samenvatting heeft" als invoer, en
  een regel uitvoer die zegt hoeveel er gezien, gemaakt, overgeslagen
  en mislukt zijn.
- Het commando is idempotent: opnieuw draaien maakt niets opnieuw. Dat
  was al zo in `compute()`, en blijft expliciet zo getest.
- Het script uit de Job-args verdwijnt; de homelab-repo krijgt een
  CronJob die dit commando aanroept (aparte wijziging in die repo).

## Scope / Not in scope

**In:** het commando, zijn tests, en de documentatie eromheen.

**Out:** de samenvattingslogica zelf (`compute`, `_bewaar`,
`for_document` blijven zoals ze zijn), het model, en het manifest in de
homelab-repo.
