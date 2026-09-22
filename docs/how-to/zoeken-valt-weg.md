---
status: current
last_reviewed: 2026-09-22
---

# Als zoeken wegvalt

Wordsworth draait op **één** OpenSearch-node. Valt die weg — een herstart van
de node waar hij staat is genoeg — dan kan er een paar minuten niet gezocht
worden. Dat is een bekende beperking, geen storing die iemand moet komen
oplossen, en de console hoort dat te zeggen in plaats van het te verbergen of te
laten lijken alsof de lezer iets fout deed.

De structurele oplossing staat in de change
`2026-09-20-hoge-beschikbaarheid` (taak 3.1). Die wacht op een opslaglaag die
niet aan één node vastzit; zolang die er niet is, is dít wat er gebeurt.

## Wat blijft werken

Alles wat uit de database komt:

| | |
|---|---|
| een document openen, de tekst lezen | ja |
| eerder berekende **onderwerpen** | ja — die staan in de database |
| **samenvattingen** | ja |
| dossiers, rollen, grants, het auditspoor | ja |
| **zoeken** (BM25, hybride, een vraag stellen) | nee |
| onderwerpen **berekenen** | nee — dat leest het hele dossier uit de index |
| **ingest** | nee, en met opzet hard |

Die laatste is geen vergissing. Een document mag nooit de staat `indexed`
bereiken zonder echt geïndexeerd te zijn, dus een schrijfpad dat de index niet
kan bereiken faalt hard en houdt het document tegen. Alleen de **leespaden**
worden zachter; de schrijfpaden niet.

## Wat de console toont

Twee meldingen, en het verschil ertussen is het punt.

**De index is onbereikbaar** — niets aan te doen door de lezer:

> Zoeken kan nu niet: de zoekindex is onbereikbaar. Dit ligt niet aan je
> zoekopdracht. Documenten, eerder berekende onderwerpen en samenvattingen
> blijven gewoon te openen; probeer het zoeken later opnieuw.

**De vraag werd afgewezen** — de index staat er wel:

> De zoekopdracht werd afgewezen: `<type>`

Tot 2026-09-22 gaven beide gevallen dezelfde regel, met de klassenaam van de
uitzondering erin (`De zoekindex gaf een fout: ConnectionError`). Dat vertelt
niet of je iets moet veranderen of moet wachten, en een storing las daardoor als
een fout van degene die zocht.

## Hoe het onderscheid gemaakt wordt

In de **driver**, niet in de console. `search_index.SearchUnavailable` hoort bij
de naad: een aanroeper moet "de index is weg" van "je vraag is afgewezen" kunnen
onderscheiden zonder te weten wélke index eronder zit. De OpenSearch-driver
vertaalt een transportfout naar die uitzondering (`_reads`, alleen op de
leespaden); alles wat geen transportfout is, gaat ongewijzigd door.

## Nagaan of het hieraan ligt

```bash
kubectl get pods -n opensearch
kubectl logs -n wordsworth deploy/wordsworth-api --tail=20 | grep -i unreachable
```

Eén OpenSearch-pod die niet `Running` is, verklaart het volledig. Staat hij er
wel en blijft het zoeken falen, dan is het de tweede melding en zit het probleem
in de vraag, niet in de dienst.
