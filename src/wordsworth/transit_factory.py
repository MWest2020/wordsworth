# SPDX-License-Identifier: MIT
"""One cached ``OpenBaoTransit`` per KEK name (design.md "One transit
factory"): ``serve.py`` and the CLI modules share this helper instead of each
hand-rolling its own client -- four copies that drift, and more than one
client per KEK."""
from __future__ import annotations

from typing import Callable

from .transit import OpenBaoTransit, Transit


def cached_transit_factory(url: str, token: str) -> Callable[[str], Transit]:
    """``transit_for(kek_name)``: one ``OpenBaoTransit`` per KEK name, built
    once and reused. ``OpenBaoTransit`` binds its KEK name at construction
    (OpenBao's encrypt/decrypt endpoints carry it in the path), so a factory
    -- not one shared ``Transit`` -- is the seam ``DocumentKeys`` needs."""
    cache: dict[str, Transit] = {}

    def transit_for(kek_name: str) -> Transit:
        if kek_name not in cache:
            cache[kek_name] = OpenBaoTransit(url, token, kek_name)
        return cache[kek_name]

    return transit_for
