---
status: accepted
last_reviewed: 2026-09-13
---

# Gap analysis — wordsworth vs. "Anatomie van Anonimiseren & Pseudonimiseren bij de Bron"

Source: NORA Expertgroep Gegevensmanagement deck (Gemeente Haarlem & Zandvoort,
Programma Open Overheid / XENA), 15 slides. Method: every functional statement in
the deck was extracted (≈120 atomic requirements) and tested against the code
with file-level evidence. This page keeps the verdicts; the proposals under
`openspec/changes/` and ADR-0005 carry the detail.

**Herzien 2026-09-13.** De eerste versie toetste tegen `main` op `7d26cec`
(2026-09-03). De dag erna zijn zeven changes gebouwd en gearchiveerd —
`add-detection-confidence`, `add-detection-feedback`, `add-pii-categories-and-ppl`,
`add-legible-placeholders`, `add-value-normalisation`, `add-domain-keys` en
`add-dataset-pseudonymisation` — en dit document bleef staan alsof ze er niet
waren. Het meldde dus **gap** bij dertien dingen die bestaan, waaronder #17, dat
het zelf "the biggest correctness gap" noemde.

Dat is de verkeerde kant om op te falen: dit is het document waarmee je aan een
gemeente uitlegt wat wordsworth wel en niet kan, en het verzweeg wat er gebouwd
is. Elke regel hieronder is opnieuw tegen de code gehouden, met bestand en
regelnummer als bewijs. De drift-poort ving dit niet — die bewaakt `src/` en
`scripts/`, niet `docs/`.

Verdict legend: **have** = present and tested · **gap** = missing, fits the
invariants, proposal written · **decided** = conflicted with a wordsworth
invariant or ADR and was **settled in ADR-0005, accepted by Mark on 2026-09-03**
(D8 explicitly, D1–D7 and D9–D11 as recommended) · **out-of-core** = belongs in a
separate component per ADR-0001/0004.

Let op bij het lezen: **decided** betekent niet "open". Die rijen dragen een
D-nummer omdat het een besluit vergde, en dat besluit is genomen. Wie een van
deze punten opnieuw wil aankaarten, doet dat door ADR-0005 te vervangen — niet in
een PR. Op 2026-09-13 las ik ze zelf verkeerd als openstaand; vandaar deze
alinea.

## 1. Where the two designs agree

Both put pseudonymisation *before* anything downstream, both keep keys out of
the document store, both make audit tamper-evident, both are open source /
Common Ground, both use OpenBao, both run PII inference locally, both reject a
mutable "redacted copy" in favour of one source of truth. wordsworth already has
the pieces the deck calls "gedeelde kern": key vault (OpenBao transit), grants
(the deck's PPL/ABAC slot), hash-chained audit with WORM export, and a
multi-layer detector (regex + Presidio patterns + NER via OpenAnonymiser — the
deck's "Swiss Cheese", just not named that).

## 2. Verdict matrix

| # | Deck requirement (cluster) | wordsworth today | Verdict | Where |
|---|---|---|---|---|
| 1 | Multi-layer PII detection, deterministic + pattern + NER | regex (BSN elfproef, IBAN, email) + OpenAnonymiser (Presidio + NER) | **have** (2–3 layers; not named) | `detectors.py`, `openanonymiser_driver.py` |
| 2 | Anonypy as layer 2 | banned in CLAUDE.md | **decided** D4 (ADR-0005, 2026-09-03) (recommend: no; NER covers it) | ADR-0005 |
| 3 | Confidence + detection layer per PII, in audit | driver keeps `score` + layer; pipeline writes per-layer aggregates to the audit (never a value or an offset) | **have** | `openanonymiser_driver.py`, `pipeline.py:226` |
| 4 | Configurable thresholds per layer | present; counting only — a threshold never weakens redaction (spec `audit-trail`) | **have** | `detection_confidence` in `2026-09-04-add-detection-confidence` |
| 5 | FP/FN feedback → rule engine (Drools) | versioned allow/deny lists; feedback is recorded, never auto-applied | **have** (the boring variant, deliberately) | `detection_lists.py` |
| 6 | 17 PII types incl. gezondheid, religie, etniciteit, biometrie, strafrechtelijk, kenteken | registry present | **have** (registry) · detector coverage per type still depends on OpenAnonymiser | `pii_categories.py` |
| 7 | AVG Art. 6/9/10 legal basis per type | `legal_basis` per type in the registry | **have** | `pii_categories.py` |
| 8 | PPL 0–3 levels | PPL expands to a type set over the existing grants | **have** | `pii_categories.py`, spec `grants` |
| 9 | ABAC, Entra ID/SSO, roles | grant_id is a bearer capability; auth model pending | **decided** D7 (ADR-0005, 2026-09-03) | ADR-0005 |
| 10 | Legible placeholders `[PERSOON 1]` | `[PERSON:hash8]` stays the stored form; `legible.py` renders `[PERSOON 1]` + a legend as a **view** | **have** (as a view, as intended) | `legible.py` |
| 11 | Reversible via decryption, one document / many views | reversible tokens + grant-gated reveal | **have** | `pseudonymizer.py`, `api.py` reveal |
| 12 | RDFa-embedded encrypted PII inside the document | separated encrypted mapping store, deliberately | **decided** D1 (ADR-0005, 2026-09-03) (recommend: RDFa as export view referencing tokens, ciphertext stays in store) | ADR-0005 |
| 13 | Per-document keys derived from category key | random per-type keys, rotation, escrow | **decided** D2 (ADR-0005, 2026-09-03) (recommend: keep; add domain scope) | ADR-0005 |
| 14 | Algorithm per article: AES-GCM / ChaCha20 / RSA-OAEP | AES-256-GCM everywhere (ChaCha20 only in escrow) | **decided** D3 (ADR-0005, 2026-09-03) (recommend: no; one AEAD, basis as metadata) | ADR-0005 |
| 15 | Key fingerprint embedded | `key_id = sha256(material)[:12]` per mapping | **have** (different name) | `keys.py` |
| 16 | HMAC-SHA256 pseudonyms, deterministic | yes | **have** | `pseudonymizer.py` |
| 17 | `normalize()` before HMAC (BSN strip/lpad, NFC, casefold, postcode, ISO date) | `normalize()` runs before the HMAC | **have** — was the biggest correctness gap | `normalization.py` |
| 18 | Domain keys per department, cross-domain blocked | domain scope in the key derivation | **have** | `keys.py`, spec `pseudonymization` |
| 19 | Key rotation with backward compatibility | rotate → re-encrypt mappings; old key_id still decrypts | **have** | `key_lifecycle.py` |
| 20 | Master key in HSM, FIPS 140-2 L2 | OpenBao transit; HSM/auto-unseal documented as prod hardening | **out-of-core** (infra) | ADR-0002 |
| 21 | Lookup table BSN→pseudonym persistent | `pii_mappings` encrypted store | **have** | `mapping_store.py` |
| 22 | Re-identification only PPL 3, audited | reveal grant-gated + audited | **have** (PPL 3 mapping via #8) | |
| 23 | Dataset/CSV column pseudonymisation, profiles, per-attribute/per-record | column selection by profile, per record; dataset and document pseudonyms coincide | **have** | `datasets.py`, spec `dataset-pseudonymization` |
| 24 | NEN 7524 format `01-0001-PB|base64` | `format="nen7524"` output option | **have** as output format · conformance to NEN 7524:2019 remains **unverified** (D9 — nobody here has read the standard) | `datasets.py:25-54` |
| 25 | Optional PII validation of unselected columns | `validate_unselected()` — advisory, never auto-pseudonymises a column nobody chose | **have** | `datasets.py:140` |
| 26 | TTP key hand-over, PKCS#12 export | age escrow exists; no PKCS#12 | **decided** D6 (ADR-0005, 2026-09-03) (recommend: age/JSON envelope; PKCS#12 is for X.509 material) | ADR-0005 |
| 27 | Audit: who/what/when/key/layer/confidence, tamper-evident, 7 y | hash chain + WORM, 10 y default; layer/confidence now included via #3 | **have** | `audit.py`, `audit_export.py` |
| 28 | Key-lifecycle stream WORM-exported | `export_key_lifecycle_worm()` ships the stream to Object Lock, incrementally, byte-exact | **have** · one layer of tamper-evidence, not two: the stream is append-only but **not hash-chained**, so a host compromised before an export could rewrite it first (follow-up `harden-key-audit-chain`) | `key_audit_export.py` |
| 29 | Metrics precision/recall/F1 per type | `pii_run` scores precision/recall/F1 per type, span- and token-level, plus a leak count | **have** · a **real** gold corpus is still missing; only `pii_gold_synthetic.jsonl` (10 invented docs) exists | `eval/pii.py`, `eval/pii_run.py` |
| 30 | NiFi orchestration, status tracking, retry | above wordsworth by ADR-0001 | **out-of-core** | ADR-0001 |
| 31 | Word / Office / ZGW plugin, upload portal, beheerportaal, dashboards | headless core by ADR-0004; console-site partly | **out-of-core** | ADR-0004 |
| 32 | Thin-client: Web Crypto + detection in the plugin | keys never leave OpenBao | **decided** D10 (ADR-0005, 2026-09-03) (recommend: server-side only) | ADR-0005 |
| 33 | DMS new version / Woo-portaal / TMLO metadata output | text-only pipeline; no docx/pdf re-render | **decided** D11 (ADR-0005, 2026-09-03) (render service is a separate component) | ADR-0005 |
| 34 | ZGW-API / CMIS / WebDAV connectors | connector pattern exists (Nextcloud, outside core) | **out-of-core** | `connectors/` |
| 35 | CyberArk Conjur / Azure KV | banned / cloud in critical path banned | **have** (OpenBao) | CLAUDE.md |
| 36 | EDPB 01/2025 TOM 1–5 | TOM 3 have; TOM 2/4/5 via #8, #18, PPL 0 exports | mostly **have/gap** | |
| 37 | 1.5M mutations/hour batch, 3 h window | untested for datasets | measure after #23 | |

## Nieuw gat, gevonden op echte documenten (2026-09-13)

Niet uit het deck, want het deck noemt het ook niet: **pseudonimiseren op een
combinatie van gegevens bestaat niet.** Elk gegeven wordt op zichzelf beoordeeld,
dus een record als "vrouw, geboren 1978, postcode 6541 EX, functie X" komt
ongemoeid door de straat terwijl die vier samen vaak één persoon aanwijzen.
Raakt vooral `dataset-pseudonymization`, waar kolommen per profiel gekozen worden
— precies de plek waar zo'n combinatie ontstaat. Zie
[meting-woo-corpus-01](meting-woo-corpus-01.md), bevinding 3.

## Bewust niet nu (2026-09-13, akkoord Mark)

Drie dingen zijn geen gap en geen besluit maar een **keuze om te wachten**. Ze
staan hier zodat ze niet over een maand terugkomen als vergeten werk.

- **Een echte gelabelde PII-gold-set.** `pii_run` meet precision/recall/F1, maar
  alleen tegen tien verzonnen documenten. Honderd echte documenten handmatig
  labelen is dagen werk en levert één corpus op dat je niet mag delen. Goedkoper
  en echter: Woo-documenten dragen `[5.1.2e]` precies waar een persoonsgegeven
  is weggehaald — een gratis **negatieve** gold-set (daar hoort niets gevonden te
  worden), en de niet-geredigeerde delen leveren de omgekeerde vraag op: vindt
  wordsworth wat de publicerende overheid heeft laten staan? Controleerbaar
  zonder annotatie. Zie `scripts/eval/README.md`.
- **Qrels en queries voor ranking-kwaliteit.** Zelf verzinnen meet hoe goed je
  vragen kon bedenken. Wachten tot er een gebruiker is die tien echte zoekvragen
  aanlevert; dat is een halve middag voor hen en maakt het cijfer pas iets waard.
- **NEN 7524-conformiteit (#24).** De norm kost geld en de claim koop je er niet
  mee — verifiëren vraagt de tekst én iemand die hem toetst. Zolang we niet
  claimen eraan te voldoen, is "NEN 7524-style" eerlijk en compleet. Zodra een
  aanbesteding erom vraagt is het een dagtaak, geen project.

## 3. What to build, in order

1. `add-value-normalisation` — correctness; unblocks consistent pseudonyms.
2. `add-pii-categories-and-ppl` — vocabulary the deck (and the operator) uses.
3. `add-detection-confidence` — makes 4, 5 and 29 measurable.
4. `add-legible-placeholders` — cheap, visible, ADR-0004 already wants it.
5. `add-domain-keys` — needed before any multi-department use.
6. `add-pii-detection-eval` — verifies the detector claims before tuning.
7. `add-detection-feedback` — after 3.
8. `add-dataset-pseudonymisation` — only after ADR-0005 D8; depends on 1 and 5.

ADR-0005 was accepted 2026-09-03 (D8 included); items 1–5 are implemented on
this branch, 6–8 remain proposals. Everything **out-of-core** is not
wordsworth's to build.

## 4. Deck inconsistencies worth knowing before adopting it as a spec

OpenBao vs CyberArk Conjur; "derives" arrows vs an explicit "wrapping, not
derivation" note for the master key; quarterly domain-key rotation vs a stable
non-rotating key for longitudinal research (two alternatives, no choice);
`data-key-id` with and without category suffix; RSA-OAEP vs "RSA-OAEP hybrid";
Presidio server-side via NiFi vs embedded in the Word plugin. None of these
change the verdicts above, but they mean the deck is an architecture sketch,
not an acceptance spec.
