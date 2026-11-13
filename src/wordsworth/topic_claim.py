# SPDX-License-Identifier: MIT
"""Wie schreef de naam die een lezer ziet? (topic-labels-llm)

`topics.display_name` geeft het label van het taalmodel als er geen naam van
een mens is. Overal waar die naam staat, hoort erbij dat het een bewering van
een model is, met model en datum, net als bij een samenvatting. Dit is die
ene zin, zodat de onderwerpenpagina, de dossierpagina en het zoekfilter hem
niet elk op hun eigen manier maken.
"""
from __future__ import annotations


def claim(topic) -> str:
    """"geschreven door <model> op <datum>" als de getoonde naam van het
    taalmodel is; anders leeg (een naam van een mens, of de termen)."""
    if topic.given_name or not topic.llm_label:
        return ""
    datum = topic.llm_at.strftime("%Y-%m-%d") if topic.llm_at else "onbekende datum"
    return f"geschreven door {topic.llm_model} op {datum}"
