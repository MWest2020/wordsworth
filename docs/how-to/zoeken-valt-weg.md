---
status: current
last_reviewed: 2026-09-26
---

# Als zoeken wegvalt

Since 2026-09-26 wordsworth searches a **three-node** OpenSearch cluster, one
node per worker, with every shard on two of them (change
`2026-09-20-hoge-beschikbaarheid`, task 3.1a). Losing one node no longer
interrupts search: evicting the cluster manager under a probe of three searches
a second left 360 of 360 answered. Query embeddings come from two Ollama
instances, and a query that reaches one as it goes away retries on the other.

Search can still drop out: two of the three OpenSearch nodes down at once, or
the whole cluster. Then this page still describes what happens. It is a known
limit, not an outage somebody has to come and fix, and the console says so
instead of hiding it or making it look like the reader did something wrong.

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
