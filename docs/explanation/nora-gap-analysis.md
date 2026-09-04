---
status: accepted
last_reviewed: 2026-09-03
---

# Gap analysis — wordsworth vs. "Anatomie van Anonimiseren & Pseudonimiseren bij de Bron"

Source: NORA Expertgroep Gegevensmanagement deck (Gemeente Haarlem & Zandvoort,
Programma Open Overheid / XENA), 15 slides. Method: every functional statement in
the deck was extracted (≈120 atomic requirements) and tested against the code on
`main` at `7d26cec` with file-level evidence. This page keeps the verdicts; the
proposals under `openspec/changes/` and ADR-0005 carry the detail.

Verdict legend: **have** = present and tested · **gap** = missing, fits the
invariants, proposal written · **decision** = conflicts with a wordsworth
invariant or ADR, needs Mark (ADR-0005) · **out-of-core** = belongs in a separate
component per ADR-0001/0004.

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
| 2 | Anonypy as layer 2 | banned in CLAUDE.md | **decision** D4 (recommend: no; NER covers it) | ADR-0005 |
| 3 | Confidence + detection layer per PII, in audit | service returns `score`, driver drops it; no layer field | **gap** | `add-detection-confidence` |
| 4 | Configurable thresholds per layer | none | **gap** (counting only; never weakens redaction) | `add-detection-confidence` |
| 5 | FP/FN feedback → rule engine (Drools) | none | **gap** (boring variant: versioned allow/deny lists + audited feedback) | `add-detection-feedback` |
| 6 | 17 PII types incl. gezondheid, religie, etniciteit, biometrie, strafrechtelijk, kenteken | no taxonomy; 3 hardcoded + passthrough | **gap** (registry) + detector work in OpenAnonymiser | `add-pii-categories-and-ppl` |
| 7 | AVG Art. 6/9/10 legal basis per type | absent | **gap** | `add-pii-categories-and-ppl` |
| 8 | PPL 0–3 levels | grants per type set (finer, no vocabulary) | **gap** (PPL = shorthand over grants) | `add-pii-categories-and-ppl` |
| 9 | ABAC, Entra ID/SSO, roles | grant_id is a bearer capability; auth model pending | **decision** D7 | ADR-0005 |
| 10 | Legible placeholders `[PERSOON 1]` | `[PERSON:hash8]` stored + indexed | **gap** (as a view, not storage) | `add-legible-placeholders` |
| 11 | Reversible via decryption, one document / many views | reversible tokens + grant-gated reveal | **have** | `pseudonymizer.py`, `api.py` reveal |
| 12 | RDFa-embedded encrypted PII inside the document | separated encrypted mapping store, deliberately | **decision** D1 (recommend: RDFa as export view referencing tokens, ciphertext stays in store) | ADR-0005 |
| 13 | Per-document keys derived from category key | random per-type keys, rotation, escrow | **decision** D2 (recommend: keep; add domain scope) | ADR-0005 |
| 14 | Algorithm per article: AES-GCM / ChaCha20 / RSA-OAEP | AES-256-GCM everywhere (ChaCha20 only in escrow) | **decision** D3 (recommend: no; one AEAD, basis as metadata) | ADR-0005 |
| 15 | Key fingerprint embedded | `key_id = sha256(material)[:12]` per mapping | **have** (different name) | `keys.py` |
| 16 | HMAC-SHA256 pseudonyms, deterministic | yes | **have** | `pseudonymizer.py` |
| 17 | `normalize()` before HMAC (BSN strip/lpad, NFC, casefold, postcode, ISO date) | none — `Jansen`≠`jansen` | **gap** (biggest correctness gap) | `add-value-normalisation` |
| 18 | Domain keys per department, cross-domain blocked | one global scope per type | **gap** | `add-domain-keys` |
| 19 | Key rotation with backward compatibility | rotate → re-encrypt mappings; old key_id still decrypts | **have** | `key_lifecycle.py` |
| 20 | Master key in HSM, FIPS 140-2 L2 | OpenBao transit; HSM/auto-unseal documented as prod hardening | **out-of-core** (infra) | ADR-0002 |
| 21 | Lookup table BSN→pseudonym persistent | `pii_mappings` encrypted store | **have** | `mapping_store.py` |
| 22 | Re-identification only PPL 3, audited | reveal grant-gated + audited | **have** (PPL 3 mapping via #8) | |
| 23 | Dataset/CSV column pseudonymisation, profiles, per-attribute/per-record | absent; unit of work is PDF | **decision** D8 → **gap** | `add-dataset-pseudonymisation` |
| 24 | NEN 7524 format `01-0001-PB|base64` | absent | **gap** as output format; conformance **unverified** D9 | `add-dataset-pseudonymisation` |
| 25 | Optional PII validation of unselected columns | detectors exist | **gap** (advisory only) | `add-dataset-pseudonymisation` |
| 26 | TTP key hand-over, PKCS#12 export | age escrow exists; no PKCS#12 | **decision** D6 (recommend: age/JSON envelope; PKCS#12 is for X.509 material) | ADR-0005 |
| 27 | Audit: who/what/when/key/layer/confidence, tamper-evident, 7 y | hash chain + WORM, 10 y default; layer/confidence missing | **have** + **gap** via #3 | `audit.py`, `audit_export.py` |
| 28 | Key-lifecycle stream WORM-exported | JSONL, not WORM | **gap** (known; small) | follow-up to `add-audit-export` |
| 29 | Metrics precision/recall/F1 per type | IR eval only | **gap** | `add-pii-detection-eval` |
| 30 | NiFi orchestration, status tracking, retry | above wordsworth by ADR-0001 | **out-of-core** | ADR-0001 |
| 31 | Word / Office / ZGW plugin, upload portal, beheerportaal, dashboards | headless core by ADR-0004; console-site partly | **out-of-core** | ADR-0004 |
| 32 | Thin-client: Web Crypto + detection in the plugin | keys never leave OpenBao | **decision** D10 (recommend: server-side only) | ADR-0005 |
| 33 | DMS new version / Woo-portaal / TMLO metadata output | text-only pipeline; no docx/pdf re-render | **decision** D11 (render service is a separate component) | ADR-0005 |
| 34 | ZGW-API / CMIS / WebDAV connectors | connector pattern exists (Nextcloud, outside core) | **out-of-core** | `connectors/` |
| 35 | CyberArk Conjur / Azure KV | banned / cloud in critical path banned | **have** (OpenBao) | CLAUDE.md |
| 36 | EDPB 01/2025 TOM 1–5 | TOM 3 have; TOM 2/4/5 via #8, #18, PPL 0 exports | mostly **have/gap** | |
| 37 | 1.5M mutations/hour batch, 3 h window | untested for datasets | measure after #23 | |

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
