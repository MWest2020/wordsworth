# Habitat reviewer — apply-docs-contract

_run_id reviewer-apply-docs-contract-20260712-190221 · verdict ok · 2026-07-12T19:03:48Z_

---

Review compleet. Ik heb de diff van deze branch getoetst tegen **uitsluitend** `CLAUDE.md` + de change `apply-docs-contract`.

## Verdict: **PASS** ✅

### Hard-fail-controle
- Geen diff raakt `CLAUDE.md`, `.claude/agents/` of CI-config → geen hard-fail.

### Checks (alle gehaald)

| # | Check | Resultaat |
|---|-------|-----------|
| 1 | **Scope** | Inhoudelijke diff = `docs/index.md`, `docs/reference/architecture.md` en de `tasks.md`-afvinking. `.mcp.json` bestond al conform template (niet gewijzigd). `.habitat/*` en `run-report.json` zijn door de habitat-runner gegenereerde audit-artefacten van de run zelf, geen builder-scope. ✅ |
| 2 | **Geen klare PII naar index** | Docs-only, geen code; tekst beschrijft correct pseudonimisering vóór indexing. ✅ |
| 3 | **Geen mutabele audit-tabellen** | Docs beschrijven append-only, hash-chained, `current_state` afgeleid — consistent met invariant. ✅ |
| 4 | **Geen cloud-API's in kritiek pad** | Docs stellen expliciet lokale inferentie (Ollama/bge-m3). ✅ |
| 5 | **CLAUDE.md-invarianten** | `uv` niet `pip`, files ≤200 (19 en 64 regels), EUPL-1.2, banned deps (anonypy/MinIO/CyberArk-Conjur), driver/protocol, geen silent fallbacks — allemaal correct weergegeven. ✅ |
| 6 | **Done = green** | Docs-change; zelfcheck (taak 3.1) houdt: alleen `reference/` draagt markdown, front matter aanwezig, één taal (Engels). ✅ |

### Contract-conformiteit (Westmarch add-docs-contract)
- Minimum viable: `index.md` + één reference-pagina ✅
- Front matter `status: draft` + `last_reviewed: 2026-07-12` (migratiedatum) ✅
- **Geen** `owner`-veld ✅
- Eén taal (Engels) ✅
- README blijft; `index.md` verwijst ernaar i.p.v. te vervangen ✅
- `.mcp.json` met placeholder `TODO-change-3` intact ✅
- Eerdere reviewer-finding (gelekte `</content>`-tags) is opgelost in commits `1f4f952`/`49e3ecc`; geen resterende stray-tags in `docs/` ✅

### Opmerking (geen blocker)
Taak `4.1` (PR openen) staat terecht nog open — PR + merge zijn Marks domein; de builder/reviewer stopt hiervoor. Dat is conform de non-goals van de change.

Als reviewer ben ik read-only: ik voer geen fixes uit. De change is klaar voor Marks merge-beslissing.
