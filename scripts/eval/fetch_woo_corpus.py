# SPDX-License-Identifier: MIT
"""Haal een corpus echte Woo-documenten op, om de straat end-to-end te draaien.

Waarom dit bestaat: `ingest_corpus.py` kan al een map PDF's door de hele
pipeline halen, maar er was geen map. De synthetische fixtures (born-digital,
scan, corrupt) bewijzen de toestandsmachine; ze bewijzen niet dat de straat
duizend echte Nederlandse overheidsdocumenten overleeft.

**Wat wel en niet kan, nagemeten 2026-09-13:**

- `open.overheid.nl` — het landelijke Woo-portaal — geeft bots een 401 en zegt
  in robots.txt `Disallow: /`. Daar halen we dus niets. Dat is geen technische
  hobbel maar een uitspraak van de beheerder.
- `bestuur.gooisemeren.nl` zit achter een proof-of-work-challenge (Anubis).
  Ook dicht. De bron die als voorbeeld genoemd werd, is juist niet machinaal
  benaderbaar.
- `open.gelderland.nl` zegt `Allow: /`, heeft 848 Woo-besluiten en linkt
  rechtstreeks naar PDF's op media.gelderland.nl. Dat is de bron hieronder.
- `woo.arnhem.nl` mag ook, maar met `Crawl-delay: 60` — bruikbaar, traag.

Deze scraper doet drie dingen die een scraper hoort te doen: hij noemt zichzelf
in de User-Agent, hij wacht tussen verzoeken, en hij schrijft per document op
waar het vandaan komt. Zonder dat laatste heb je over een maand een map PDF's
zonder herkomst, en dan is elke meting erop onnavolgbaar.

    uv run python scripts/eval/fetch_woo_corpus.py --out ./corpus --max 50
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

BASIS = "https://open.gelderland.nl"
LIJST = BASIS + "/woo-documenten"
UA = "wordsworth-corpus/0.1 (+https://github.com/MWest2020/wordsworth)"
# Beleefd, niet snel. De bron stelt geen crawl-delay, maar een seconde per
# verzoek kost ons niets en houdt ons ruim binnen wat redelijk is.
PAUZE = 1.0


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def detail_urls(html: str) -> list[str]:
    """De detailpagina's uit een listing, in volgorde en zonder dubbelen."""
    gezien, uit = set(), []
    for pad in re.findall(r'href="(/woo-documenten/[^"#?]+)"', html):
        if pad not in gezien:
            gezien.add(pad)
            uit.append(urljoin(BASIS, pad))
    return uit


def pdf_urls(html: str) -> list[str]:
    """Alleen de PDF's zelf.

    De pagina linkt elke PDF twee keer: één keer rechtstreeks en één keer via
    een voorleesdienst (readspeaker) met de PDF-URL als query-parameter. Die
    tweede is hetzelfde document met een omweg, dus die valt af — anders staat
    elk bestand dubbel in je corpus en telt elke meting erop dubbel.
    """
    gezien, uit = set(), []
    for u in re.findall(r'href="(https://[^"]+?\.pdf)"', html):
        if "readspeaker" in u or u in gezien:
            continue
        gezien.add(u)
        uit.append(u)
    return uit


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True, help="doelmap voor de PDF's")
    ap.add_argument("--max", type=int, default=25, help="maximum aantal PDF's")
    ap.add_argument("--pauze", type=float, default=PAUZE, help="seconden tussen verzoeken")
    a = ap.parse_args()

    a.out.mkdir(parents=True, exist_ok=True)
    herkomst_pad = a.out / "herkomst.jsonl"

    try:
        listing = _get(LIJST).decode("utf-8", "replace")
    except Exception as e:
        print(f"[corpus] listing niet op te halen: {e}", file=sys.stderr)
        return 1

    details = detail_urls(listing)
    print(f"[corpus] {len(details)} Woo-besluiten op de eerste listing-pagina")

    gehaald, fouten = 0, 0
    with herkomst_pad.open("a") as herkomst:
        for d in details:
            if gehaald >= a.max:
                break
            time.sleep(a.pauze)
            try:
                pagina = _get(d).decode("utf-8", "replace")
            except Exception as e:
                print(f"[corpus] detail mislukt {d}: {e}", file=sys.stderr)
                fouten += 1
                continue
            for u in pdf_urls(pagina):
                if gehaald >= a.max:
                    break
                naam = u.rsplit("/", 1)[-1]
                doel = a.out / naam
                if doel.exists():
                    continue
                time.sleep(a.pauze)
                try:
                    data = _get(u)
                except Exception as e:
                    print(f"[corpus] pdf mislukt {u}: {e}", file=sys.stderr)
                    fouten += 1
                    continue
                doel.write_bytes(data)
                # Herkomst per document, meteen weggeschreven. Een corpus zonder
                # herkomst maakt elke meting erop onnavolgbaar.
                herkomst.write(json.dumps({
                    "bestand": naam, "bron": u, "besluit": d,
                    "bytes": len(data), "opgehaald": time.strftime("%FT%TZ", time.gmtime()),
                }) + "\n")
                herkomst.flush()
                gehaald += 1
                print(f"[corpus] {gehaald}/{a.max} {naam} ({len(data)} bytes)")

    print(f"[corpus] klaar: {gehaald} PDF's in {a.out}, {fouten} fout(en). "
          f"Herkomst: {herkomst_pad}")
    return 0 if gehaald else 1


if __name__ == "__main__":
    raise SystemExit(main())
