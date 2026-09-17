# Change: bind-reveal-to-recipient

## Why

Een grant zegt: *"ontvanger R mag types T onthullen"*. Die ontvanger staat in het
record (`Grant.recipient`), wordt bij uitgifte gevraagd, en verschijnt in de
audit. Alleen: **`/reveal` kijkt er niet naar.**

`authorize()` toetst status, verlooptijd, documentscope en domein. De caller
wordt apart vastgelegd in het auditspoor — maar nooit vergeleken met de
recipient. Daarmee is een `grant_id` in de praktijk een bearer-capability: wie
hem heeft, onthult. Een security-review noemde dit al, en het werd toen bewust
doorgeschoven omdat het de betekenis van een grant raakt.

Dat doorschuiven is nu duur geworden. Sinds `harden-grant-issuer-scope` is het
*uitgeven* van een grant beperkt tot een expliciete kring, en sinds
`harden-grant-document-check` is de scope per document afgedwongen. Het gebruik
blijft de zwakste schakel: één gelekte grant-id — uit een logregel, een
ticketsysteem, een screenshot — en klare PII ligt open voor wie hem vindt.

## What Changes

- **`authorize()` krijgt de caller mee** en vergelijkt hem met
  `grant.recipient`. Komt hij niet overeen, dan is de uitkomst de lege
  verzameling: dezelfde weigering als bij een ingetrokken of verlopen grant, met
  dezelfde 403.
- **Alleen met caller-authenticatie aan.** Zonder auth is er geen caller om op te
  beslissen en verandert er niets — dat is de bestaande, gedocumenteerde
  tailnet-interne modus, en precies de lijn die `authorize_grant_issue` al volgt.
- **De vergelijking is exact.** Geen hoofdletterongevoeligheid, geen prefix, geen
  wildcard. Een recipient is een label uit dezelfde lijst als de caller; twee
  labels die op elkaar lijken zijn niet hetzelfde label.

## Wat hier NIET in zit

- **De cross-document-reveal en de per-document pseudonym-registratie.** Die
  vergen allebei een schemawijziging met migratie en krijgen hun eigen change;
  ze staan in dezelfde familie maar lossen een ander lek op.
- **Grants overdraagbaar maken.** Als een recipient zijn recht wil doorgeven is
  dat een nieuwe grant, geen gedeelde id.

## Impact

- `src/wordsworth/grants.py` (`authorize`), `src/wordsworth/api.py` (`/reveal`),
  `openspec/specs/reveal-api`.
- **Breaking met auth aan**: een deployment die vandaag onthult met een grant
  waarvan de recipient niet het caller-label is, krijgt 403. Dat is de bedoelde
  aanscherping, maar het is een deploy-stap: controleer dat de recipients in
  bestaande grants de caller-labels zijn die ze gebruiken.
- Zonder auth: geen gedragsverandering.
