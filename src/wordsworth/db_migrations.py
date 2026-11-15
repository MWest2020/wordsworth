"""What ``db.init_schema`` migrates an existing database to: data only.

``create_all`` never alters a table that already exists, so every column,
index and trigger added after a database was first created is listed here.
``db._missing_ddl`` asks the catalog which of them are missing and
``db.init_schema`` applies those. Adding a column to a model means adding a
line to ``_COLUMNS``; no logic lives in this module.
"""
from __future__ import annotations

# The function behind the append-only triggers. Replacing a function takes no
# lock on any table, so this one runs every time and a changed body lands.
_FORBID_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION wordsworth_forbid_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
"""

# A superseded document's pointer is set once (one-document-per-object).
_SUPERSEDED_ONCE_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION wordsworth_superseded_once() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'documents.superseded_by is set once';
END;
$$ LANGUAGE plpgsql;
"""

# Tables that are append-only at the schema level: (trigger, table).
# key_lifecycle_events is the authorisation trail (key-audit-in-postgres).
_APPEND_ONLY = [
    ("audit_no_mutation", "audit_records"),
    ("key_lifecycle_no_mutation", "key_lifecycle_events"),
]


# Additive column migrations for databases created before the column existed
# (create_all never alters existing tables): (table, column, type).
_COLUMNS = [
    ("pii_mappings", "norm_version", "VARCHAR"),
    ("grants", "domain", "VARCHAR"),
    ("documents", "filename", "VARCHAR"),
    ("grants", "role", "VARCHAR"),
    ("documents", "superseded_by", "UUID REFERENCES documents(id)"),
    ("documents", "source_url", "VARCHAR"),
    ("documents", "fetched_at", "TIMESTAMPTZ"),
    ("documents", "source_sha256", "VARCHAR"),
    ("topics", "llm_label", "VARCHAR"),
    ("topics", "llm_description", "VARCHAR"),
    ("topics", "llm_model", "VARCHAR"),
    ("topics", "llm_at", "TIMESTAMPTZ"),
]

# (trigger, table) -> its CREATE statement, for the triggers that are not the
# append-only kind.
_OTHER_TRIGGERS = {
    ("superseded_once", "documents"):
        "CREATE TRIGGER superseded_once BEFORE UPDATE OF superseded_by ON documents "
        "FOR EACH ROW WHEN (OLD.superseded_by IS NOT NULL "
        "AND NEW.superseded_by IS DISTINCT FROM OLD.superseded_by) "
        "EXECUTE FUNCTION wordsworth_superseded_once()",
}

# name -> (table, column). Reveal walks document_pseudonyms on every call;
# without its index that is a sequential scan over every pseudonym in the
# corpus. Every scoped search walks dossier_documents the other way round, from
# a dossier to its documents; the primary key covers (dossier, document), this
# covers "which dossiers is this document in".
_INDEXES = {
    "idx_document_pseudonyms_doc": ("document_pseudonyms", "document_id"),
    "idx_dossier_documents_doc": ("dossier_documents", "document_id"),
}


# Unique indexes, by name. Creating one fails while duplicates exist, and it
# should: on a database that still holds copies, run `wordsworth-dedupe` first.
# An init that quietly skipped the constraint would leave the rule unenforced
# without anyone knowing (one-document-per-object, design Decision 6).
_UNIQUE_INDEXES = {
    "uq_documents_live_object_key":
        "CREATE UNIQUE INDEX uq_documents_live_object_key ON documents (object_key) "
        "WHERE superseded_by IS NULL",
}
