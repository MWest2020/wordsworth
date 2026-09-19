# Tasks

Gebouwd op 2026-09-19. **#81 stond hiervóór en is klaar**: onder Cloudflare
Access is een callerlabel een geverifieerd e-mailadres, dus "HR mag dit" is niet
langer "wie de HR-sleutel heeft mag dit".

## 0. Eerst beslissen
- [ ] Sjabloon, entiteit of het voorgestelde derde (grant noemt een rol,
      `authorize()` lost hem op)? De rest van deze lijst gaat uit van het derde.
- [x] Vraag 1 beantwoord (Mark, 2026-09-17): bij het installeren bestaat er één
      (super)admin die de RBAC bepaalt. De eerste rol komt uit de installatie,
      niet uit het rollenstelsel. **Richting productie hoort hier degelijke RBAC
      te staan** — Keycloak of gelijkwaardig — dus deze change mag nergens
      aannemen dat rollen hier vandaan blijven komen.

## 0b. Hoe ver dit gaat in de PoC
- [x] Mark (2026-09-17): een beheerder mag nu alle grants hebben; het verdelen
      over rollen komt na een gebruikstest. De vorm blijft staan, het tempo
      verandert. Eén rol, hij heet beheerder, hij houdt alles.
- [ ] De ongescopete grant toestaan **op naam van de beheerdersrol**, niet door
      `WORDSWORTH_ALLOW_GLOBAL_GRANTS` om te zetten. Die vlag omzetten opent hem
      voor élke ongescopete grant om hem voor één rol te openen.
- [ ] Welke rollen er verder zijn: niet nu beantwoorden. Een rol die wij
      verzinnen vóór de gebruikstest is een aanname met een juridische staart.

## 1. Het model
- [x] `Role` (naam, types, actief, wie hem maakte) en `grants.role`.
- [x] Precies één bron: eigen lijst, PPL of rol. De API weigert twee (422) en
      nul (422).

## 2. De beslissing
- [x] `authorize()` lost de rol op bij het beslissen, via `permitted_types()`.
      Eén beslispunt, één invoer erbij.
- [x] Inactief = leeg. Geen terugval, ook niet als de grant per ongeluk
      allebei draagt — en zonder resolver levert een rol-grant niets
      (fail-closed).

## 3. Breakglass
- [x] Uitzetten en aanzetten vragen allebei een reden.
- [x] In het **sleutel-levensloopspoor**, waar grants en sleutelrotaties ook
      staan. Niet in de document-hashketen: die is de toestandsmachine van één
      document en een rol raakt er duizend — duizend kopieën van hetzelfde feit,
      of één record zonder document dat er niet in past. Dit is dezelfde
      afweging die `key_audit.py` al voor rotaties maakte.
      Aanmaken, inperken, uitzetten en aanzetten staan er allemaal in, met de
      stand ná de wijziging erbij. De console schrijft hetzelfde record als de
      API.
- [x] `/activate`, door wie de grant-beheerpoort mag passeren, met een reden.

## 4. Bewijs
- [x] `test_switching_a_role_off_stops_a_reveal_that_was_working`: onthult,
      rol uit, 403, grant nog ACTIVE. En weer aan zonder nieuwe grant.
- [x] `test_the_admin_role_is_not_a_bypass` en
      `test_the_audit_says_under_which_role_it_was_allowed`.
- [x] `test_narrowing_a_role_narrows_a_live_grant`. Let op de vorm: een
      ingeperkt type wordt INGEHOUDEN (200 + withheld_types), niet 403 —
      hetzelfde als een type dat nooit in de grant stond. Pas als de rol niets
      meer toestaat doet de grant niets, en dan is het 403.
- [x] Live op productie (2026-09-19, sha fbe612f): rol actief -> {EMAIL}, rol
      uit -> set(), grant nog ACTIVE, rol weer aan -> {EMAIL}. De typelijst van
      de grant bleef leeg: hij kopieert niet.

## Wat hier misgaan kan
Van de vier epics is dit degene waar een fout niet "iets werkt niet" betekent
maar "iemand zag iets". Elke twijfel hier hoort in het voorstel te staan en niet
in de code te worden opgelost.
