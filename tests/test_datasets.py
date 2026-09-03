"""add-dataset-pseudonymisation: profile-driven column pseudonymisation; same
token as the document path; per-record; advisory validation; audited run."""
import csv
import io
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth.api import create_app
from wordsworth.datasets import DatasetRun, Profile, load_profile, render, validate_unselected
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import InMemoryMappingStore, PostgresMappingStore
from wordsworth.models import AuditRecord
from wordsworth.pseudonymizer import Pseudonymizer, _reveal

PII_BSN = "123456782"
ROWS = [
    {"bsn": "1234.56.782", "naam": "Janine van Dijk", "uitkering": "bijstand"},
    {"bsn": PII_BSN, "naam": "janine van dijk", "uitkering": "wajong"},
    {"bsn": "", "naam": "Piet", "uitkering": "geen"},
]


def _run(profile, rows=ROWS, kp=None, store=None):
    kp, store = kp or InMemoryKeyProvider(), store or InMemoryMappingStore()
    run = DatasetRun(profile, Pseudonymizer(kp, store, domain=profile.domain))
    return list(run.transform(rows)), run, kp, store


def test_selected_columns_replaced_others_byte_identical():
    prof = Profile(domain="wi", columns={"bsn": "BSN", "naam": "PERSON"})
    out, run, _, _ = _run(prof)
    assert [r["uitkering"] for r in out] == ["bijstand", "wajong", "geen"]
    assert all(r["bsn"].startswith("[BSN:") for r in out[:2]) and out[2]["bsn"] == ""
    assert PII_BSN not in json.dumps(out) and "Janine" not in json.dumps(out)
    # normalisation: 1234.56.782 == 123456782, Janine == janine → one token each
    assert out[0]["bsn"] == out[1]["bsn"] and out[0]["naam"] == out[1]["naam"]
    assert run.stats()["unique_pseudonyms"] == 3 and run.stats()["rows"] == 3


def test_dataset_and_document_pseudonyms_coincide():
    kp, store = InMemoryKeyProvider(), InMemoryMappingStore()
    prof = Profile(domain="wi", columns={"bsn": "BSN"})
    out, _, _, _ = _run(prof, kp=kp, store=store)
    doc_text = Pseudonymizer(kp, store, domain="wi").anonymize(f"BSN {PII_BSN}").text
    assert doc_text.split()[-1] == out[1]["bsn"]
    other, _, _, _ = _run(Profile(domain="mo", columns={"bsn": "BSN"}), kp=kp, store=store)
    assert other[1]["bsn"] != out[1]["bsn"]                   # domain separation


def test_per_record_same_identity_same_pseudonym_and_nen_format():
    prof = Profile(domain="wi", columns={"bsn": "BSN", "naam": "PERSON"},
                   mode="per_record", record_key=["bsn"], format="nen7524")
    out, run, kp, store = _run(prof)
    assert out[0]["bsn"] == out[0]["naam"] == out[1]["bsn"] == out[1]["naam"]
    assert out[0]["bsn"].startswith("01-0001-PR|")
    assert out[2]["bsn"] == "" and out[2]["naam"].startswith("01-0001-PR|")
    assert run.stats()["unique_pseudonyms"] == 2
    tok = next(iter(run.unique))
    assert render(tok, "nen7524", "0001") in {out[0]["bsn"], out[2]["naam"]}
    assert render("[BSN:0011aabb]", "nen7524", "0002") == "01-0002-PB|ABGquw=="
    assert render("[BSN:0011aabb]", "token", "x") == "[BSN:0011aabb]"


def test_missing_column_is_hard_error_and_profile_validation():
    with pytest.raises(KeyError):
        _run(Profile(domain="wi", columns={"nope": "BSN"}))
    with pytest.raises(ValueError):
        Profile(domain="a/b", columns={"bsn": "BSN"})
    with pytest.raises(ValueError):
        Profile(columns={"bsn": "BSN"}, mode="per_record")
    with pytest.raises(ValueError):
        Profile(columns={})


def test_validate_unselected_warns_but_never_transforms():
    prof = Profile(domain="wi", columns={"naam": "PERSON"})
    rows = [{"naam": "Jan", "bsn": PII_BSN, "mail": "a@b.nl", "code": "x1"}]
    warnings = validate_unselected(rows, prof)
    assert {w["column"] for w in warnings} == {"bsn", "mail"}
    out, _, _, _ = _run(prof, rows)
    assert out[0]["bsn"] == PII_BSN and out[0]["mail"] == "a@b.nl"   # untouched


def test_load_profile_from_versioned_dir(tmp_path):
    (tmp_path / "p.json").write_text('{"domain":"wi","columns":{"bsn":"BSN"}}')
    assert load_profile("p", tmp_path).domain == "wi"
    with pytest.raises(FileNotFoundError):
        load_profile("zz", tmp_path)
    with pytest.raises(ValueError):
        load_profile("../p", tmp_path)
    assert load_profile("example-wi", "profiles").validate_pii is True
    assert load_profile("example-wi-record", "profiles").mode == "per_record"


def _csv(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
    return buf.getvalue().encode()


def test_endpoint_transforms_audits_and_reveals(session_factory):
    kp = InMemoryKeyProvider()
    c = TestClient(create_app(session_factory=session_factory, key_provider=kp))
    prof = {"domain": "wi", "columns": {"bsn": "BSN", "naam": "PERSON"}, "validate_pii": True}
    rows = ROWS + [{"bsn": "", "naam": "", "uitkering": "x"}]
    rows = [dict(r, mail="jan@x.nl") for r in rows]
    r = c.post("/datasets/pseudonymize", files={"file": ("in.csv", _csv(rows), "text/csv")},
               data={"profile": json.dumps(prof)})
    assert r.status_code == 200, r.text
    body = r.json()
    out = list(csv.DictReader(io.StringIO(body["csv"])))
    assert [o["uitkering"] for o in out] == ["bijstand", "wajong", "geen", "x"]
    assert PII_BSN not in body["csv"] and "Janine" not in body["csv"]
    assert body["rows"] == 4 and body["unique_pseudonyms"] == 3 and body["domain"] == "wi"
    assert [w["column"] for w in body["warnings"]] == ["mail"]
    with session_factory() as s:
        rec = s.execute(select(AuditRecord).where(
            AuditRecord.step == "dataset_pseudonymize")).scalar_one()
        assert rec.payload["rows"] == 4 and rec.payload["warnings"] == ["mail"]
        assert PII_BSN not in json.dumps(rec.payload) and "Janine" not in json.dumps(rec.payload)
        assert rec.seq == body["audit_seq"]
        # the token reveals through the shared mapping store with the wi key
        restored, _ = _reveal(out[1]["bsn"], None, PostgresMappingStore(s).get, kp.key)
        assert restored == "1234.56.782"        # first-seen spelling (spec)
    # same file again → same dataset artefact, second run record
    r2 = c.post("/datasets/pseudonymize", files={"file": ("in.csv", _csv(rows), "text/csv")},
                data={"profile": json.dumps(prof)})
    assert r2.json()["dataset_id"] == body["dataset_id"]
    # errors: both/neither profile forms, bad profile, missing column, unknown name
    assert c.post("/datasets/pseudonymize", files={"file": ("in.csv", _csv(rows), "text/csv")}
                  ).status_code == 400
    assert c.post("/datasets/pseudonymize", files={"file": ("in.csv", _csv(rows), "text/csv")},
                  data={"profile": '{"domain":"a/b","columns":{"bsn":"BSN"}}'}).status_code == 400
    assert c.post("/datasets/pseudonymize", files={"file": ("in.csv", _csv(rows), "text/csv")},
                  data={"profile": '{"columns":{"zz":"BSN"}}'}).status_code == 400
    assert c.post("/datasets/pseudonymize", files={"file": ("in.csv", _csv(rows), "text/csv")},
                  data={"profile_name": "does-not-exist"}).status_code == 400


def test_route_absent_without_key_provider(session_factory):
    c = TestClient(create_app(session_factory=session_factory))
    assert c.post("/datasets/pseudonymize").status_code in (404, 405)


def test_cli_posts_multipart(monkeypatch, tmp_path, capsys):
    from wordsworth import client
    seen = {}

    def fake(base, path, profile, profile_name, timeout=600):
        seen.update(base=base, name=path.name, profile=profile, profile_name=profile_name)
        return {"csv": "a,b\n1,2\n", "rows": 1}

    monkeypatch.setattr(client, "_post_dataset", fake)
    f = tmp_path / "in.csv"; f.write_text("a,b\n1,2\n")
    assert client.main(["--url", "http://api", "pseudonymize-dataset", str(f),
                        "--profile-name", "example-wi"]) == 0
    out = capsys.readouterr()
    assert out.out == "a,b\n1,2\n" and '"rows": 1' in out.err
    assert seen["profile_name"] == "example-wi" and seen["profile"] is None
