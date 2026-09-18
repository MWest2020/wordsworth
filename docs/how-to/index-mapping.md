---
status: current
last_reviewed: 2026-09-18
---

# Adding a field to the search index

`ensure_ready()` creates the index **only when it does not exist yet**. A field
added to `_mapping()` afterwards therefore never reaches an index that is already
there — and that is not a loud failure.

## Why this bites without an error

OpenSearch maps an undeclared field dynamically on first write. A list of strings
becomes `text` with a `.keyword` subfield, not `keyword`. A `terms` filter on the
raw field then matches **nothing**, and the search answers with zero hits and no
error.

That is the worst shape a fault can take here: the answer is wrong and looks
ordinary. It happened on 2026-09-18 with the `dossiers` field — every test was
green, because tests create the index fresh, and the scoped search returned
nothing in production while `dossier=alle` returned nine.

## What the code does now

`ensure_ready()` also **adds fields the mapping has gained** since the index was
created (`indices.put_mapping`) — additive and idempotent, the same shape as the
column migrations in `db.py`.

A field that already exists with the **wrong type** raises `MappingConflict`.
Deliberately hard: a field cannot be retyped in place, and carrying on would
leave a filter that silently matches nothing.

## Repairing an index that already has the wrong type

Reindex into a correctly mapped one. Verified first, then swapped:

```python
cl.indices.create(index="wordsworth-new", body=_mapping(dim))
cl.reindex(body={"source": {"index": "wordsworth"},
                 "dest": {"index": "wordsworth-new"}},
           params={"wait_for_completion": "true"}, request_timeout=180)
```

Check the new index answers the query the old one got wrong **before** deleting
anything — on 2026-09-18 the same search gave 0 on the old index and 9 on the
new, which is what made the diagnosis certain rather than plausible. Then delete
the old index, recreate it from `_mapping()`, reindex back, and drop the
temporary one.

`request_timeout` is the keyword the client wants; `timeout` in `params` raises
`Timeout value connect was 180s, but it must be an int, float or None`.

Search is unavailable between the delete and the reindex. That window is short
and the temporary index holds everything, but it is a window.

## Wie een nieuw veld als eerste schrijft, zorgt eerst voor de mapping

`ensure_ready()` draait in productie alleen langs de ingest-straat. Een nieuwe
schrijver van een nieuw veld — `topics.compute` bijvoorbeeld, die het
`topics`-veld zet zonder dat er een document ingelezen wordt — komt daar niet
langs. Zonder mapping schrijft hij een veld dat OpenSearch dynamisch mapt, met
het gevolg hierboven: `text` in plaats van `keyword`, en een `term`-filter dat
niets matcht zonder fout.

Dus: **roep `ensure_ready()` aan vóór de eerste schrijfactie op een nieuw veld**,
niet alleen bij ingest. Bewaakt door
`test_the_mapping_is_ensured_before_a_topic_is_ever_written`.

## Verwant: een dossierfilter hoort in de knn-clause, niet erbuiten

Dezelfde familie fout, andere plek: hij geeft antwoord, het antwoord is alleen
minder dan je denkt.

De lexicale helft van een hybride zoekopdracht krijgt het dossierfilter als
`bool.filter` naast de zoekvraag — versmallen zonder de score te raken. Zet je
datzelfde filter buiten de `knn`-clause, dan is het een **ná-filter**: kNN
levert eerst de globale top-k en het filter gooit daarna weg wat niet in het
dossier zit.

Gemeten op 18-09 tegen de draaiende index (770 documenten, zoekvector uit het
grootste dossier van 567, scope een dossier van 2):

| k | filter buiten de clause | filter binnen de clause |
|---|---|---|
| 10 | 0 treffers | 2 |
| 50 | 0 treffers | 2 |
| 200 | 1 treffer | 2 |

Een eerdere meting, toen alle vectoren nog in één groot dossier zaten, gaf
tweemaal hetzelfde en leek een weerlegging. Dat was het niet — het geval waar
het om gaat viel toen niet te maken. **Een meting die het geval niet kan maken,
weerlegt niets.**

Dit was stil omdat de zoekopdracht gewoon antwoorden gaf: de lexicale helft
werkte. Alleen de vectorhelft droeg niets bij.

De mapping gebruikt engine `lucene`; die ondersteunt filteren tijdens het
doorlopen van de graaf. Bij een andere engine (`nmslib`) bestaat die optie niet
en is dit een ander gesprek.

Zie `_scoped_knn` in `opensearch_index.py` en
`tests/test_opensearch_scoping.py`.
