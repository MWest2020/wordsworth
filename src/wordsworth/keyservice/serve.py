"""Composition root for ``wordsworth-keyservice``.

Importing this module performs no I/O: ``create_app`` only wires dependencies
and registers routes; the engine it builds (``make_engine``) does not connect
until first used. The refuse-to-start check (design.md "Refuse to start")
therefore runs on the ASGI startup event, not at import time -- the same
"before serving" guarantee, without making every test that imports this
module need a live, correctly configured database.

No ``/v1`` route exists yet (this change is the process boundary only); any
path under ``/v1/`` is still intercepted by ``ServiceTokenMiddleware`` and
answers 401 without a valid token, before FastAPI's router would otherwise
404 it.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import Engine, text

from .auth import ServiceTokenMiddleware
from .config import settings
from .db import check_refuse_to_start, make_engine


def create_app(engine: Engine | None = None, *,
               service_tokens: dict[str, str] | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        check_refuse_to_start(settings.database_url)
        yield

    app = FastAPI(title="wordsworth-keyservice", version="0.1.0", lifespan=lifespan)
    # None means "build the real engine from settings on first /health call"
    # -- kept lazy so importing/constructing this app never needs a database.
    app.state.engine = engine

    tokens = service_tokens if service_tokens is not None else settings.service_tokens
    app.add_middleware(ServiceTokenMiddleware, tokens=tokens)

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

    return app


def main() -> int:
    import uvicorn

    uvicorn.run("wordsworth.keyservice.serve:app", host="0.0.0.0", port=8000)
    return 0


app = create_app()


if __name__ == "__main__":
    raise SystemExit(main())
