"""Test harness. Runs a real PostgreSQL in Docker (honours 'PostgreSQL day one'
and reproducibility on standard iron). Set WORDSWORTH_TEST_DATABASE_URL to reuse
an existing database and skip Docker."""
from __future__ import annotations

import io
import os
import subprocess
import time

import pytest
from sqlalchemy import text

from wordsworth.db import init_schema, make_engine, make_session_factory

_PG_IMAGE = "postgres:16-alpine"
_CONTAINER = "wordsworth-test-pg"
_URL = "postgresql+psycopg://postgres:postgres@localhost:55432/wordsworth"


def _docker_ok() -> bool:
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


@pytest.fixture(scope="session")
def database_url() -> str:
    env_url = os.environ.get("WORDSWORTH_TEST_DATABASE_URL")
    if env_url:
        yield env_url
        return
    if not _docker_ok():
        pytest.skip("docker unavailable and WORDSWORTH_TEST_DATABASE_URL unset")

    subprocess.run(["docker", "rm", "-f", _CONTAINER], capture_output=True)
    subprocess.run(
        ["docker", "run", "-d", "--name", _CONTAINER,
         "-e", "POSTGRES_PASSWORD=postgres", "-e", "POSTGRES_DB=wordsworth",
         "-p", "55432:5432", _PG_IMAGE],
        check=True, capture_output=True,
    )
    engine = make_engine(_URL)
    try:
        for _ in range(60):
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                break
            except Exception:
                time.sleep(1)
        else:
            pytest.fail("postgres did not become ready")
    finally:
        engine.dispose()
    yield _URL
    subprocess.run(["docker", "rm", "-f", _CONTAINER], capture_output=True)


@pytest.fixture
def session_factory(database_url):
    engine = make_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS audit_records CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS documents CASCADE"))
    init_schema(engine)
    return make_session_factory(engine)


@pytest.fixture
def session(session_factory):
    with session_factory() as s:
        yield s


# --- PDF fixtures -----------------------------------------------------------

def _pdf(draw) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    draw(c)
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture
def born_digital_pdf() -> bytes:
    text_line = "Dit is een born-digital document met een echte tekstlaag. " * 3
    return _pdf(lambda c: c.drawString(72, 800, text_line))


@pytest.fixture
def scanned_pdf() -> bytes:
    # A shape but no text -> extract_text() empty -> unprocessable_ocr.
    return _pdf(lambda c: c.rect(72, 72, 200, 200, fill=1))


@pytest.fixture
def corrupt_pdf() -> bytes:
    return b"this is definitely not a pdf at all"
