# Tasks: samenvatten-als-commando

## 1. Commando — run 01
- [ ] 1.1 `python -m wordsworth.samenvatten`: `--dossier <uuid>`
  (herhaalbaar) of `--ontbrekend` voor alle documenten zonder
  samenvatting. Zonder argumenten: een nette uitleg en exitcode 2.
- [ ] 1.2 Eén samenvattende regel als uitvoer (gezien / gemaakt /
  overgeslagen / mislukt / zonder tekst) plus de duur; exitcode 1 als er
  iets mislukte, 0 als alles goed ging of er niets te doen was.
- [ ] 1.3 Idempotent: een tweede run maakt niets opnieuw. Test dat met
  een generator die telt hoe vaak hij is aangeroepen.
- [ ] 1.4 Tests draaien zonder Ollama: een nep-generator, en voor de
  database de bestaande testopzet.

## 2. Documentatie
- [ ] 2.1 Hoe je het draait (lokaal en als Job), in de bestaande
  documentatie + CHANGELOG onder `[Unreleased]`.
