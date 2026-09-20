# Tasks

Nog niet gebouwd. Eerst de vraag uit `proposal.md` die ik niet zelf kan
beantwoorden.

## 0. Eerst beslissen
- [ ] **Telt een overheidsorgaan als persoonsgegeven?** `gemeente Gooise Meren`,
      `college`, `coa`, `ofgv` — organisaties, geen personen, en in een
      Woo-publicatie bij wet genoemd. Maar `ORGANIZATION` is ook waar een
      eenmanszaak zich verstopt.
- [ ] De lijst in de repo en mee in het image (mijn voorstel), of in een
      ConfigMap (los te wijzigen, maar dan is de auditsleutel zonder herkomst)?

## 1. De lijst
- [ ] `allow.json` met een reden per regel; het laden weigert een regel zonder.
- [ ] Kandidaten uit de meting: de vaakst vervangen waarden met een kleine
      letter. Generator, geen beslisser — een mens loopt de lijst langs.
- [ ] `WORDSWORTH_DETECTION_LISTS` aanzetten in de configmap.

## 2. De rem
- [ ] Toets in CI: geen allow-regel mag een waarde onderdrukken die het
      evalcorpus als PII heeft ingezaaid.
- [ ] Meet de recall op het evalcorpus mét en zónder lijsten; hij mag niet
      dalen.

## 3. Meten
- [ ] Vóór: 39% van de entiteit-tokens begint met een kleine letter (gemeten
      2026-09-20, 198 documenten).
- [ ] Ná: hetzelfde getal, met de recall ernaast.
- [ ] Allebei met datum in `docs/explanation/`.

## 4. Daarna pas
- [ ] Het bestaande corpus herverwerken (`POST /reprocess`) is een APARTE
      beslissing met een eigen prijs.
