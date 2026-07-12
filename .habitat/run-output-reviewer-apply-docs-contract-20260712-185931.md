# Habitat reviewer — apply-docs-contract

_run_id reviewer-apply-docs-contract-20260712-185931 · verdict ok · 2026-07-12T19:01:04Z_

---

Review compleet. Ik heb de diff van change `apply-docs-contract` beoordeeld tegen `CLAUDE.md` + de change zelf. Verdict volgt.

---

## Reviewer-verdict: **FAIL**

### Hard-fail check — clean
De diff raakt **geen** `CLAUDE.md`, `.claude/agents/`, of CI-config. Geen out-of-bounds wijziging aan Mark's bestanden.

### Blocking defect
Beide gemigreerde docs-pagina's eindigen op een verdwaalde `</content>`-tag — een gelekt template/tool-wrapper-artefact dat in de bestandsinhoud terecht is gekomen:

- `docs/index.md:20` → `</content>`
- `docs/reference/architecture.md:65` → `</content>`

Dit is niet cosmetisch. De hele bestaansreden van deze change is een **schoon** docs-contract dat de handbook-hub *at build time* importeert (zie proposal "Why"). Twee malformatte markdown-pagina's leveren rauwe HTML-rommel op in de geaggregeerde output, en het spreekt de builder's eigen zelfcheck-claim bij taak 3.1 tegen ("elke pagina … één taal"). Dit blokkeert PASS.

### Wat wél klopt (ter info, geen blockers)
- **Scope** — `docs/` bevat exact minimum-viable per contract: `index.md` + één `reference/`-pagina; geen lege mappen, geen stray files (`find` bevestigt: alleen die twee). `.mcp.json` aanwezig en conform template met `TODO-change-3`-placeholder. `tasks.md`-checkboxes bijgewerkt. De `.habitat/*`- en `run-report.json`-bestanden zijn runner-infrastructuur uit een aparte commit (860ccc0), geen builder-scope.
- **Front matter** — beide pagina's: `status: draft` + `last_reviewed: 2026-07-12`, **geen** `owner`-veld. Correct per contract (gemigreerd-zonder-review).
- **Taal** — Engels, één taal. Correct.
- **Files ≤ 200 lines** — 20 en 65 regels. OK.
- **Invariant-nauwkeurigheid** — de inhoud van `architecture.md` weerspiegelt CLAUDE.md correct (append-only hash-chained audit, `current_state` afgeleid, geen silent fallbacks, lokale inference, driver/protocol, EUPL-1.2, banned deps). Geen PII-richting-index-, mutable-audit-, of cloud-API-probleem — dit is docs-only en de beschreven invarianten zijn juist.

### Vereist voor PASS
Verwijder de trailing `</content>`-regel uit `docs/index.md` en `docs/reference/architecture.md`. Dat is de enige blocker; verder is de change contractconform. Ik fix niet zelf (reviewer is read-only) — terug naar de builder.
