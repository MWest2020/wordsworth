# Habitat run 01 — discovery robuust (tasks 1.1–2.1)

Contract: `openspec/changes/2026-09-20-oidc-discovery-robuust/`.

Waargenomen in het cluster, 2026-09-20: de pod kreeg **403** van
Cloudflare op `https://iam.westerweel.work/realms/westerweel/.well-known/openid-configuration`
(urllib zonder User-Agent; `curl` vanaf dezelfde pod gaf 200), en de
worker stierf daarop bij het booten.

## Scope — ONLY these tasks
- [ ] 1.1 `WORDSWORTH_OIDC_JWKS_URL` (leeg = uit). Gezet → discovery
  overslaan en dit adres gebruiken. Uitgever blijft de ingestelde
  waarde en blijft tegen `iss` gecontroleerd.
- [ ] 1.2 Ophalen verplaatsen naar het eerste token-verzoek, met cache
  (ook de foutcache kort houden, zodat een hik zichzelf herstelt).
  Een fout → geen caller, geen uitzondering die de worker sloopt.
- [ ] 1.3 User-Agent op elke HTTP-aanroep.
- [ ] 1.4 Tests: gezet JWKS-adres → geen discovery-aanroep; niet gezet →
  discovery één keer en daarna uit cache; onbereikbaar → geen caller en
  de app blijft draaien; User-Agent aanwezig.
- [ ] 2.1 Deployment-documentatie + CHANGELOG.

## Done means
`uv run pytest -q` groen en `openspec validate
2026-09-20-oidc-discovery-robuust --strict` groen. Budget is $5.
