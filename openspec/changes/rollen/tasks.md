# Tasks

Nog niet gebouwd, en dit is de change die het langst op antwoorden mag wachten.
**#81 hoort hiervóór**: een rolmodel bovenop gedeelde api-sleutels is er een op
papier.

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
- [ ] `Role` (naam, types, actief) en de koppeling grant → rol.
- [ ] Een grant heeft óf types óf een rol, niet allebei. Twee bronnen voor één
      antwoord is precies hoe autorisatiefouten ontstaan.

## 2. De beslissing
- [ ] `authorize()` lost een rol op bij het beslissen. Eén beslispunt, één
      invoer erbij — geen tweede functie en geen pad eromheen.
- [ ] Inactief = lege verzameling. Geen terugval op de grant, op een vorige
      versie van de rol, of op wat dan ook.

## 3. Breakglass
- [ ] Uitzetten met reden; zonder reden een weigering.
- [ ] In hetzelfde append-only spoor als de rest.
- [ ] En terug: hoe komt een rol weer aan? Door wie?

## 4. Bewijs
- [ ] Een test die bewijst dat uitzetten werkt **zonder dat er een grant
      verandert**. Dat is het verschil met de sjabloonvariant en de reden voor
      deze vorm.
- [ ] Een test dat een beheerder langs dezelfde `authorize()` gaat en hetzelfde
      auditrecord oplevert.
- [ ] Een test dat een rol inperken meteen doorwerkt in een bestaande grant.
- [ ] Live: een rol uitzetten terwijl er een geldige grant op staat, en zien dat
      de onthulling 403 geeft.

## Wat hier misgaan kan
Van de vier epics is dit degene waar een fout niet "iets werkt niet" betekent
maar "iemand zag iets". Elke twijfel hier hoort in het voorstel te staan en niet
in de code te worden opgelost.
