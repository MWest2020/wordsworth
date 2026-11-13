# SPDX-License-Identifier: MIT
"""Labels op de onderwerpenpagina, en de knop die niet wacht (topic-labels-llm).

De knop-test praat rauw ASGI met de app in plaats van via TestClient: die
geeft een antwoord pas terug als ook de achtergrondtaak klaar is. Wat de test
bewijst is de volgorde binnen de app: de laatste bytes van de pagina komen in
`send` aan vóórdat de achtergrondtaak start, dus vóórdat het model ook maar is
aangeroepen; het slot is dan al bezet (de route nam het), dus een tweede klik
vanuit die `send` start niets. Pas daarna roept de taak het model aan en wordt
het label opgeslagen. Wat uvicorn, Cloudflare of oauth2-proxy met die bytes
doen, bewijst deze test niet.
"""
from __future__ import annotations

import json
import logging
from urllib.parse import urlencode

import anyio
from fastapi.testclient import TestClient

from topic_label_setup import Model, Wacht, dossier
from wordsworth.api import create_app
from wordsworth.models import Topic
from wordsworth.search_index import InMemoryIndex

KEY = "s3cret"


def _opzet(session_factory, generator, samenvatting="Een kapvergunning."):
    index = InMemoryIndex()
    with session_factory() as s:
        _, topics, _ = dossier(s, index, naam="zaak-console", topics=[
            ("kap · boom", [([1.0, 0.0], samenvatting)] * 2),
            ("geluid · evenement", [([0.0, 1.0], samenvatting)] * 2)])
        ids = [t.id for t in topics]
    app = create_app(session_factory=session_factory, api_keys={KEY: "mark"},
                     search_index=index, generator=generator)
    return app, ids


def _client(app):
    c = TestClient(app, base_url="https://testserver")
    c.post("/console/login", data={"key": KEY})
    return c


def test_a_labelled_topic_shows_label_description_provenance_and_terms(
        session_factory):
    app, (eerste, tweede) = _opzet(session_factory, Model())
    c = _client(app)
    c.post(f"/console/topics/{eerste}/label", data={"dossier": "zaak-console"})

    r = c.get("/console/topics?dossier=zaak-console")

    assert r.status_code == 200
    with session_factory() as s:
        t = s.get(Topic, eerste)
        datum = t.llm_at.strftime("%Y-%m-%d")
    assert "Kap van bomen in het centrum" in r.text
    assert "Aanvragen en besluiten over het kappen van bomen." in r.text
    assert f"geschreven door nep-model op {datum}" in r.text
    assert "termen: kap · boom" in r.text
    # Het andere onderwerp heeft er geen, en de pagina zegt dat, met het commando.
    assert "label ontbreekt" in r.text
    assert "1 van de\n 2 onderwerpen heeft geen label" in r.text
    assert "python -m wordsworth.onderwerpen_labelen --dossier zaak-console" in r.text
    assert r.text.count("/label\"") == 2, "een knop per onderwerp"


def test_an_unlabelled_dossier_says_every_label_is_missing(session_factory):
    app, _ = _opzet(session_factory, Model())
    r = _client(app).get("/console/topics?dossier=zaak-console")
    assert r.text.count("label ontbreekt") == 2
    assert "2 van de\n 2 onderwerpen hebben geen label" in r.text
    assert r.text.count("Label schrijven") == 2


async def _post(app, path: str, form: dict, bij_antwoord=None) -> str:
    body = urlencode(form).encode()
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "https", "path": path,
        "raw_path": path.encode(), "root_path": "", "query_string": b"",
        "headers": [(b"host", b"testserver"), (b"x-api-key", KEY.encode()),
                    (b"accept", b"text/html"),
                    (b"content-type", b"application/x-www-form-urlencoded"),
                    (b"content-length", str(len(body)).encode())],
        "client": ("127.0.0.1", 5000), "server": ("testserver", 443)}
    gelezen, delen = False, []

    async def receive():
        nonlocal gelezen
        if not gelezen:
            gelezen = True
            return {"type": "http.request", "body": body, "more_body": False}
        await anyio.sleep(60)
        return {"type": "http.disconnect"}

    async def send(bericht):
        if bericht["type"] == "http.response.body":
            delen.append(bericht.get("body", b""))
            if not bericht.get("more_body") and bij_antwoord is not None:
                await bij_antwoord(b"".join(delen).decode())

    await app(scope, receive, send)
    return b"".join(delen).decode()


def test_the_button_answers_before_the_model_and_a_second_click_starts_nothing(
        session_factory):
    model = Wacht()
    app, (eerste, tweede) = _opzet(session_factory, model)
    gezien = {}

    async def bij_antwoord(pagina):
        gezien["pagina"] = pagina
        gezien["model_al_klaar"] = model.beantwoord
        gezien["aanroepen"] = len(model.prompts)
        gezien["tweede"] = await _post(app, f"/console/topics/{tweede}/label",
                                       {"dossier": "zaak-console"})
        model.los.set()

    anyio.run(_post, app, f"/console/topics/{eerste}/label",
              {"dossier": "zaak-console"}, bij_antwoord)

    assert gezien["model_al_klaar"] is False, "de pagina wachtte op het model"
    assert gezien["aanroepen"] == 0, "het model liep al voordat de pagina weg was"
    assert "bezig, ververs over ongeveer 2 minuten" in gezien["pagina"]
    assert "er loopt al een label-opdracht" in gezien["tweede"]
    assert len(model.prompts) == 1, "de tweede klik startte toch een label"
    with session_factory() as s:
        assert s.get(Topic, eerste).llm_label == "Kap van bomen in het centrum"
        assert s.get(Topic, tweede).llm_label is None
    # Het slot is weer vrij: een volgende klik start wel.
    model.los.set()
    _client(app).post(f"/console/topics/{tweede}/label",
                      data={"dossier": "zaak-console"})
    assert len(model.prompts) == 2


def test_a_rejected_label_is_logged_without_its_text(session_factory, caplog):
    model = Model({"label": "[PERSOON] Jansen-geheim", "description": "Goed."})
    app, (eerste, _) = _opzet(session_factory, model)

    with caplog.at_level(logging.INFO, logger="wordsworth.pipeline"):
        r = _client(app).post(f"/console/topics/{eerste}/label",
                              data={"dossier": "zaak-console"})

    assert r.status_code == 200
    regels = [json.loads(rec.getMessage()) for rec in caplog.records
              if rec.name == "wordsworth.pipeline"
              and '"topic_label"' in rec.getMessage()]
    assert [(r["topic_id"], r["outcome"]) for r in regels] == [
        (str(eerste), "rejected")]
    assert "geheim" not in caplog.text and "PERSOON" not in caplog.text
    with session_factory() as s:
        assert s.get(Topic, eerste).llm_label is None


def test_a_failed_model_call_is_logged_and_releases_the_button(session_factory,
                                                               caplog):
    from topic_label_setup import Kapot

    model = Kapot()
    app, (eerste, _) = _opzet(session_factory, model)
    c = _client(app)

    with caplog.at_level(logging.INFO, logger="wordsworth.pipeline"):
        c.post(f"/console/topics/{eerste}/label", data={"dossier": "zaak-console"})
        r = c.post(f"/console/topics/{eerste}/label",
                   data={"dossier": "zaak-console"})

    assert "bezig, ververs" in r.text, "het slot bleef vast na een fout"
    assert '"error": "GenerationError"' in caplog.text
    assert '"outcome": "failed"' in caplog.text
    assert len(model.prompts) == 2


def test_an_unknown_topic_starts_nothing(session_factory):
    from uuid import uuid4

    model = Model()
    app, _ = _opzet(session_factory, model)
    r = _client(app).post(f"/console/topics/{uuid4()}/label",
                          data={"dossier": "zaak-console"})
    assert "bestaat niet" in r.text
    assert model.prompts == []
