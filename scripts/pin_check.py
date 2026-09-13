#!/usr/bin/env python3
"""Every wordsworth image reference is pinned by DIGEST.

A convention nobody checks is a wish. Same reasoning as ratatoskr's
`pin_check.py`, and here it carries more weight: wordsworth processes personal
data, so "which code has seen this document" is an audit question and not
curiosity.

A tag is not a pin. `:latest` obviously moves, but `sha-<commit>` moves too —
nothing stops a re-push of that tag to different bytes. Only `@sha256:…`
addresses the image itself.

    python3 scripts/pin_check.py

Scope: the deployment manifests in `deploy/k8s/`. The placeholder
`@sha256:<digest>` is allowed — those files are templates and must NOT carry a
digest from somebody else's cluster; the operator fills it in. What is refused
is a tag, because a tag silently works.
"""
from __future__ import annotations

import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HIER)
MAP = os.path.join(ROOT, "deploy", "k8s")

# Alleen onze eigen images. busybox:1.37 in de loader-pod is een
# wegwerp-hulpcontainer die niets van de straat aanraakt; die eisen we niet op
# digest, en dat is een keuze met een reden en geen vergetelheid.
EIGEN = re.compile(r"^\s*image:\s*(ghcr\.io/[^\s]*wordsworth[^\s]*)\s*$", re.M)
PLAATSHOUDER = "@sha256:<digest>"


def main() -> int:
    fout = []
    for naam in sorted(os.listdir(MAP)):
        if not naam.endswith((".yaml", ".yml")):
            continue
        pad = os.path.join(MAP, naam)
        with open(pad) as f:
            for nr, regel in enumerate(f, 1):
                m = EIGEN.match(regel)
                if not m:
                    continue
                ref = m.group(1)
                if ref.endswith(PLAATSHOUDER):
                    continue
                if "@sha256:" not in ref:
                    fout.append(f"{naam}:{nr}  {ref}  — tag, geen digest")
    for f in fout:
        print("  NIET GEPIND ", f)
    print(f"pins: {'ROOD — ' + str(len(fout)) + ' referentie(s) op een tag' if fout else 'groen'}")
    return 1 if fout else 0


if __name__ == "__main__":
    sys.exit(main())
