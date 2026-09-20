# Habitat run 01 — samenvatten als commando (tasks 1.1–2.1)

Contract: `openspec/changes/2026-09-20-samenvatten-als-commando/`.

De huidige Job draagt dit script mee in zijn `args` (uit de cluster-API
gehaald, 2026-09-20): sessie opzetten, `OllamaGenerator.from_config()`,
`documents_in(s, [dossier])`, `compute(...)`, en het printen van
`seen/made/skipped/failed/without_text` plus de duur. Dat is precies wat
het commando moet doen — inclusief de bestaande keuze dat `compute()`
per document commit.

## Scope — ONLY these tasks
- [ ] 1.1 `src/wordsworth/samenvatten.py` met een `main()` en een
  `if __name__ == "__main__"`: `--dossier <uuid>` (herhaalbaar),
  `--ontbrekend`, en zonder argumenten uitleg + exitcode 2.
- [ ] 1.2 Eén regel uitvoer met de vijf tellingen en de duur; exitcode 1
  bij mislukkingen.
- [ ] 1.3 Idempotent, met een test die telt hoe vaak de generator werd
  aangeroepen.
- [ ] 1.4 Tests met een nep-generator.
- [ ] 2.1 Documentatie + CHANGELOG.

Raak `compute`, `_bewaar` en `for_document` NIET aan: die werken, en de
upsert die de duplicate-key-fout oploste zit er al in.

## Over de testomgeving in de kooi — lees dit eerst
Er is hier GEEN Postgres en GEEN OpenSearch; de volledige suite loopt
daarop stuk of blijft hangen. Draai alleen je eigen testbestand plus
`tests/test_summaries.py` als dat zonder database kan. Lukt dat niet,
zeg dat dan in je run-rapport in plaats van een database te gaan zoeken.

## Done means
Je eigen tests groen en `openspec validate
2026-09-20-samenvatten-als-commando --strict` groen. Budget is $4.
