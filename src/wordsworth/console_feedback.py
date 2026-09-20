# SPDX-License-Identifier: MIT
"""Het meldingenscherm (overdetectie).

Achter dezelfde poort als de rest van het corpus: welke tokens er in welke
documenten staan is corpuskennis, ook zonder de waarden erbij.
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from . import feedback as feedback_mod


def _rijen(session, meldingen) -> list[dict]:
    namen = feedback_mod.documentnamen(
        session, {d for m in meldingen for d in m.documenten})
    return [
        {"token": m.token, "type": m.type, "aantal": m.aantal,
         "melders": sorted(m.melders),
         "documenten": [{"id": str(d), "naam": namen.get(d, str(d)[:8])}
                        for d in sorted(m.documenten, key=str)],
         "laatst": m.laatst.strftime("%Y-%m-%d %H:%M") if m.laatst else ""}
        for m in meldingen
    ]


def mount(router, session_factory, TEMPLATES, mag_lezen=None, caller=None) -> None:
    @router.get("/feedback", response_class=HTMLResponse, include_in_schema=False)
    def meldingen(request: Request):
        if mag_lezen is not None:
            mag_lezen(request)
        with session_factory() as session:
            alles = feedback_mod.verzamel(session)
            fp = _rijen(session, [m for m in alles if m.kind == "fp"])
            fn = _rijen(session, [m for m in alles if m.kind == "fn"])
        return TEMPLATES.TemplateResponse(request, "feedback.html", {
            "fp": fp, "fn": fn,
            "caller": caller(request) if caller else ""})
