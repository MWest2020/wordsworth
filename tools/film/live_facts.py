"""Live facts for the film, run INSIDE the wordsworth api pod (piped to `python -`, see
docs/reference/film-claims.yml). Prints one JSON line of counts and yes/no flags:
never a value, a name, a document id or a secret."""
import json
import os
import urllib.parse
import urllib.request

from sqlalchemy import create_engine, text

# The pilot corpus the film's numbers describe (docs/explanation/pilot-report-gooise-meren-2022.md).
DOSSIER = "Gooise Meren Woo-publicatie 2022"
e = create_engine(os.environ["WORDSWORTH_DATABASE_URL"])
OS, IX = os.environ["WORDSWORTH_OPENSEARCH_URL"], os.environ["WORDSWORTH_OPENSEARCH_INDEX"]


def q(sql, **kw):
    with e.connect() as c:
        return c.execute(text(sql), kw).scalar() or 0


def os_count(query):
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(f"{OS}/{IX}/_count", data=body, headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())["count"]


def internal(url):
    host = urllib.parse.urlsplit(url).hostname or ""
    return host.endswith(".svc.cluster.local")


did = str(q("select id from dossiers where name = :n", n=DOSSIER))
LIVE = """select dd.document_id from dossier_documents dd join documents d on d.id = dd.document_id
  where dd.dossier_id = :d and d.superseded_by is null and coalesce((select a.to_state from audit_records a
  where a.document_id = d.id order by a.seq desc limit 1), '') <> 'deleted'"""
in_dossier = {"term": {"dossiers": did}}
facts = {
    "documents": q(f"select count(*) from ({LIVE}) x", d=did),
    "indexed_docs": os_count(in_dossier),
    "vectors": os_count({"bool": {"filter": [in_dossier, {"exists": {"field": "vector"}}]}}),
    "topics": q("select count(*) from topics where dossier_id = :d", d=did),
    "topic_docs": os_count({"bool": {"filter": [in_dossier, {"exists": {"field": "topics"}}]}}),
    "box_maps": q(f"""select count(*) from box_maps b where b.document_id in ({LIVE}) and not exists (
        select 1 from jsonb_array_elements(b.boxes::jsonb) x
        where abs((x->'rect'->>3)::float - (x->'rect'->>1)::float) < 0.5)""", d=did),
    "persons": q(f"select count(distinct pseudonym) from document_pseudonyms where pseudonym like '[PERSON:%%' and document_id in ({LIVE})", d=did),
    "phones": q(f"select count(distinct pseudonym) from document_pseudonyms where pseudonym like '[PHONE_NUMBER:%%' and document_id in ({LIVE})", d=did),
    "model_detections": q(f"select count(*) from audit_records where document_id in ({LIVE}) and payload->'detections' ? 'openanonymiser'", d=did),
    "keys": q("select count(*) from key_vault"),
    "audit_records": q("select count(*) from audit_records"),
    "vault_internal": int(internal(os.environ.get("WORDSWORTH_OPENBAO_URL", ""))),
    "internal_services": int(all(internal(os.environ.get(k, "")) for k in (
        "WORDSWORTH_DATABASE_URL", "WORDSWORTH_OPENSEARCH_URL", "WORDSWORTH_OLLAMA_URL",
        "WORDSWORTH_OPENANONYMISER_URL", "WORDSWORTH_S3_ENDPOINT_URL", "WORDSWORTH_OPENBAO_URL"))),
}
print(json.dumps(facts))
