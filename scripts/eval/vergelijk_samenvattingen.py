# SPDX-License-Identifier: MIT
"""Zet de twee samenvattingsvarianten naast elkaar op échte documenten.

Er is geen waarheid over "een goede samenvatting" in dit corpus, dus dit levert
geen score op. Wat het wel levert is het enige dat hier telt: de twee teksten
naast elkaar, met de tijd erbij, zodat een mens kan zien of een taalmodel van
3b op OCR-ruis iets toevoegt boven de eerste regels van het document zelf.

    python -m scripts.eval.vergelijk_samenvattingen --dossier <uuid> --aantal 5

Draait tegen de ingestelde database en Ollama; bedoeld om in het cluster te
draaien, want daar staan ze.
"""
from __future__ import annotations

import argparse
import time
from uuid import UUID

from wordsworth.config import settings
from wordsworth.db import make_engine, make_session_factory
from wordsworth.dossiers import documents_in
from wordsworth.generator import GenerationError, OllamaGenerator
from wordsworth.pipeline import get_anonymized_text
from wordsworth.summaries import clean, extractive


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dossier", required=True)
    ap.add_argument("--aantal", type=int, default=5)
    ap.add_argument("--knip", type=int, default=2000,
                    help="hoeveel tekens het model te zien krijgt")
    args = ap.parse_args(argv)

    session = make_session_factory(make_engine())()
    gen = OllamaGenerator.from_config()
    ids = sorted(documents_in(session, [UUID(args.dossier)]))

    model_tijd = 0.0
    gedaan = 0
    for doc_id in ids:
        if gedaan >= args.aantal:
            break
        tekst = get_anonymized_text(session, doc_id)
        if not tekst or len(tekst) < 500:
            continue
        gedaan += 1
        print("=" * 72)
        print(f"{doc_id}  ({len(tekst)} tekens)")

        begin = time.time()
        uit = extractive(tekst)
        print(f"\nEXTRACTIEF ({time.time() - begin:.2f}s, een citaat):")
        print(f"  {uit or '(niets bruikbaars)'}")

        begin = time.time()
        try:
            uit = clean(gen.summarise(tekst[:args.knip]))
        except GenerationError as exc:
            uit = f"(mislukt: {exc})"
        duur = time.time() - begin
        model_tijd += duur
        print(f"\nMODEL {settings.llm_model} ({duur:.0f}s, een bewering):")
        print(f"  {uit or '(niets bruikbaars)'}")

    print("=" * 72)
    print(f"{gedaan} documenten | extractief ~0s | model {model_tijd:.0f}s "
          f"({model_tijd / max(gedaan, 1):.0f}s per document)")
    print(f"Over een dossier van 588: extractief seconden, model "
          f"{model_tijd / max(gedaan, 1) * 588 / 3600:.1f} uur.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
