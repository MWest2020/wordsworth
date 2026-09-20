# Tasks

Gebouwd op 2026-09-19, na Marks "bouwen".

## 0. Eerst beslissen
- [x] Een samenvatting per document, op verzoek per dossier, met model en
      moment erbij.
- [x] Naast het fragment, met "geen citaat" erbij.

## 1. Opslaan
- [x] `DocumentSummary` (document, tekst, model, moment).
- [x] Alleen wat ontbreekt; het model wordt aantoonbaar niet tweemaal aangeroepen.

## 2. Maken
- [x] Over de gepseudonimiseerde tekst, via `Generator.summarise()` — een eigen
      methode, want de RAG-prompt vraagt om een ANTWOORD met bronvermeldingen.
- [x] Tokens eruit ná het genereren. Gecontroleerd met het filter eruit: dan
      falen er twee.
- [x] Mislukt, leeg, of na filteren leeg: geen rij, wel geteld.
- [x] Noemer terug, plus `without_text`.

## 3. Tonen
- [x] Op de zoekpagina boven het fragment, met model en datum.
- [x] "nog geen samenvatting" in plaats van een leeg vlak.
- [x] Achter de corpus-leespoort.

## 3b. De extractieve variant (Mark, 2026-09-19: "extractieve variant erbij bouwen en vergelijken")
- [x] De eerste regels die iets zeggen, letterlijk overgenomen. Nul
      modelaanroepen tegenover ~315s per document op deze hardware.
- [x] Beginnen bij de onderwerpregel; mailkoppen en scannerruis overslaan. Alle
      drie uit de vergelijking van 19-09 en niet verzonnen.
- [x] Een kaal `Subject:` op een eigen regel: beginnen op de regel erna.
- [x] Het scherm zegt welk van de twee het toont.
- [x] `scripts/eval/vergelijk_samenvattingen.py` zet ze naast elkaar. Geen
      score: er is geen waarheid over "een goede samenvatting" in dit corpus.

## 4. Bewijzen
- [x] `test_a_failed_generation_leaves_nothing_behind`.
- [x] `test_running_again_does_not_redo_the_work`.
- [x] `test_the_endpoint_is_behind_the_corpus_gate`.
- [x] `test_the_screen_says_it_was_generated_and_by_what`.
- [x] Een test die de extractieve uitvoer letterlijk langs de bronregels
      afloopt: overslaan mag, verzinnen niet.
- [x] Twee van mijn eerste filtertests bewaakten niets (ze gebruikten een
      document MET onderwerpregel, en dan begint het extract daar toch al).
      Herschreven zonder onderwerpregel; dan falen ze wel zonder de filters.
