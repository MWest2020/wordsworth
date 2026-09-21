# SPDX-License-Identifier: MIT
"""De rollenpagina (rollen).

"Ik maak een rol aan en selecteer welke PII's mogen" hoort een scherm te zijn en
geen curl. De aanvinklijst komt uit `pii_categories.known_types()` en niet uit
een lijst hier: een tweede plek waar types vandaan komen, is een plek waar "wat
je kunt aanvinken" op een dag stilletjes verschilt van "wat het systeem kent".
"""
from __future__ import annotations

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import roles as roles_mod
from .pii_categories import known_types, legal_basis_of


def _rows(session) -> list[dict]:
    return [
        {"name": r.name, "allowed_types": list(r.allowed_types),
         "active": r.active, "created_by": r.created_by}
        for r in roles_mod.listing(session)
    ]


def _types() -> list[dict]:
    return [{"name": t, "basis": legal_basis_of(t)} for t in known_types()]


def mount(router, session_factory, TEMPLATES, mag_beheren=None, caller=None,
          audit=None) -> None:
    def _page(request, fout=""):
        with session_factory() as session:
            rollen = _rows(session)
        return TEMPLATES.TemplateResponse(request, "roles.html", {
            "rollen": rollen, "types": _types(), "fout": fout,
            "caller": caller(request) if caller else ""})

    @router.get("/roles", response_class=HTMLResponse, include_in_schema=False)
    def roles_page(request: Request, fout: str = ""):
        if mag_beheren is not None:
            mag_beheren(request)
        return _page(request, fout)

    @router.post("/roles", include_in_schema=False)
    def create(request: Request, name: str = Form(...),
               types: list[str] = Form(default=[])):
        if mag_beheren is not None:
            mag_beheren(request)
        with session_factory() as session:
            try:
                roles_mod.create(session, name, types,
                                 actor=caller(request) if caller else "onbekend",
                                 audit=audit() if audit else None)
            except roles_mod.RoleError as exc:
                return _page(request, str(exc))
            session.commit()
        # Redirect-na-post: anders maakt een herlaad-knop dezelfde rol opnieuw,
        # en dat is bij een autorisatie-object geen onschuldige dubbele klik.
        return RedirectResponse("/console/roles", status_code=303)

    @router.post("/roles/switch", include_in_schema=False)
    def switch(request: Request, name: str = Form(...), aan: str = Form(...),
               reason: str = Form("")):
        if mag_beheren is not None:
            mag_beheren(request)
        fn = roles_mod.activate if aan == "1" else roles_mod.deactivate
        with session_factory() as session:
            try:
                fn(session, name, actor=caller(request) if caller else "onbekend",
                   reason=reason, audit=audit() if audit else None)
            except roles_mod.RoleError as exc:
                return _page(request, str(exc))
            session.commit()
        return RedirectResponse("/console/roles", status_code=303)
