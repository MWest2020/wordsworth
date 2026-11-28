"""Composition root for ``wordsworth-keyservice``.

Importing this module performs no I/O: ``create_app`` only wires dependencies
and registers routes; the engine it builds (``make_engine``) does not connect
until first used, and the Transit factory it builds does not reach OpenBao
until first used (design.md "Settings and the Transit seam"). The
refuse-to-start checks (design.md "Refuse to start") therefore run on the
ASGI startup event, not at import time -- the same "before serving"
guarantee, without making every test that imports this module need a live,
correctly configured database or OpenBao.

Any path under ``/v1/`` is intercepted by ``ServiceTokenMiddleware`` and
answers 401 without a valid token, before FastAPI's router would otherwise
404 it.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from sqlalchemy import Engine, text
from starlette.responses import JSONResponse

from wordsworth.transit import Transit

from . import api_metrics, api_open, api_originals, api_pseudonymise
from .auth import ServiceTokenMiddleware
from .config import settings
from .db import (check_openbao_refuse_to_start,
                 check_pseudonymise_cap_refuse_to_start,
                 check_refuse_to_start, make_engine)


def create_app(engine: Engine | None = None, *,
               service_tokens: dict[str, str] | None = None,
               transit_for: Callable[[str], Transit] | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        check_refuse_to_start(settings.database_url)
        check_pseudonymise_cap_refuse_to_start(settings.pseudonymise_max_items)
        if transit_for is None:
            check_openbao_refuse_to_start(settings.openbao_url, settings.openbao_token)
        yield

    app = FastAPI(title="wordsworth-keyservice", version="0.1.0", lifespan=lifespan)
    # None means "build the real thing from settings on first use" -- kept
    # lazy so importing/constructing this app never needs a database or
    # OpenBao. Passing a FakeTransit factory here (tests) means the OpenBao
    # settings are never read.
    app.state.engine = engine
    app.state.session_factory = None
    app.state.transit_for = transit_for
    # One `DocumentKeys` per process (api_originals.py, api_open.py): its
    # unwrap cache is process-lifetime, so it is never rebuilt per request.
    app.state.doc_keys = None

    tokens = service_tokens if service_tokens is not None else settings.service_tokens
    app.add_middleware(ServiceTokenMiddleware, tokens=tokens)

    @app.exception_handler(RequestValidationError)
    async def _sanitized_validation_error(request, exc: RequestValidationError):
        # Never FastAPI's default body: that echoes each field's raw
        # ``input`` back, which for this service may be a PII value
        # (design.md "POST /v1/pseudonymise": a 422 never echoes a value).
        detail = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]}
                  for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.get("/health", summary="Liveness probe", tags=["ops"])
    def health() -> dict[str, str]:
        """No token needed. Says only that the process is up and its own
        database is reachable (design.md "Service authentication")."""
        try:
            if app.state.engine is None:
                app.state.engine = make_engine()
            with app.state.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="database unreachable") from exc
        return {"status": "ok"}

    app.include_router(api_pseudonymise.router)
    app.include_router(api_originals.router)
    app.include_router(api_open.router)
    app.include_router(api_metrics.router)
    return app


def main() -> int:
    import uvicorn

    uvicorn.run("wordsworth.keyservice.serve:app", host="0.0.0.0", port=8000)
    return 0


app = create_app()


if __name__ == "__main__":
    raise SystemExit(main())
