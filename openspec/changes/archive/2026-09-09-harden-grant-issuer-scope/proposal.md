# Change: harden-grant-issuer-scope

## Why

Een onafhankelijke security-review (2026-09-06) noemde dit CRITICAL, en de
docstring van het endpoint erkende het al: *"no caller auth yet"*.

`POST /grants` en `/grants/{id}/revoke` hadden **geen eigen autorisatie**. Twee
paden:

- **Auth uit (de default):** elke host die de API bereikt mint zijn eigen grant met
  `allowed_types: [PERSON, BSN, EMAIL, …]` en onthult daarmee klare PII.
- **Auth aan, mét corpus-read-scope:** een caller die 403 krijgt op
  `/documents/{id}/anonymized` mag nog steeds een grant slaan en `/reveal` doen.
  De least-privilege-scope was dus omzeilbaar via het zwaardere endpoint.

Een grant is de sleutel tot klare PII. Wie er een mag maken, mag alles onthullen —
dat hoort een kleinere kring te zijn dan "iedereen met een api-key".

## What changes

- **`WORDSWORTH_GRANT_ISSUER_LABELS`**: de callers die een grant mogen uitgeven of
  intrekken.
- **`authorize_grant_issue(caller, issuer_labels, auth_enabled)`** — puur, zonder
  HTTP: zonder auth ongewijzigd; met auth alleen labels uit de lijst.
- Beide grant-admin-routes gaan door `_guard_grant_admin`, vóór enige write.

## Waarom leeg hier "niemand" betekent

Bij `WORDSWORTH_CORPUS_READ_LABELS` betekent leeg "scope uit, iedereen mag lezen" —
non-breaking, want lezen van gepseudonimiseerde tekst is niet het zwaarste recht.
Bij het uitgeven van grants is die keuze verkeerd om: wie vergeet de kring te
benoemen zou anders precies het gat openlaten dat de review vond. Met auth aan en
een lege lijst mint dus niemand. Zonder auth verandert er niets — dat is de
bestaande, gedocumenteerde tailnet-interne modus, en die niet-breken is bewust.

## Wat hier NIET in zit

- **Recipient-binding op `/reveal`.** De review merkte terecht op dat een
  `grant_id` een bearer-capability is: `/reveal` controleert niet dat de caller de
  recipient is. Dat is een eigen change (het raakt de betekenis van een grant en
  de console-flow), niet iets om hier stilletjes in mee te nemen.
- **De cross-document-reveal** (mapping-store zoekt op pseudonym zonder
  document-id) — aparte change, want die vergt een schemawijziging.

## Impact

- Non-breaking zonder auth; met auth moet een deployment de kring benoemen.
- Live-deployment: `WORDSWORTH_API_KEYS` staat gezet, dus na deze change moet
  `WORDSWORTH_GRANT_ISSUER_LABELS` in de configmap staan — anders mint niemand
  meer. Dat is de bedoelde fail-closed, maar het is wel een deploy-stap.
- 445 tests groen, inclusief vier nieuwe voor deze scope.
