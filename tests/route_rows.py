# SPDX-License-Identifier: MIT
"""The 55-route inventory of api-corpus-read-gate (design.md, "Inventory") as
data: one row per method and path, with the policy it requires and why.

A policy names the check a route requires: ``corpus-read``, ``grant-read``,
``grant-admin`` and ``delete`` are declared or body-called guards that answer
403; ``grant`` is decided by the grant presented, not by who the caller is;
``any-key`` is any authenticated caller (or, with auth off, anybody);
``open`` needs no key at all. The walker that holds an application against
these rows is in ``route_inventory.py``.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Row:
    method: str
    path: str
    policy: str
    reason: str
    #: Whether the policy is declared on the route (`dependencies=[Depends(...)]`,
    #: visible to `read_gate.gate_of`) rather than called from the route's body.
    #: Only corpus-read, grant-read and the one declared grant-admin row are;
    #: the ten routes that keep calling `_guard_grant_admin` from their body are
    #: not, and declaration is not meaningful for any other policy.
    declared: bool = True


# --- API -------------------------------------------------------------------
_API_READ = [
    Row("GET", "/documents/{document_id}/state", "corpus-read", "which documents exist"),
    Row("GET", "/documents/{document_id}", "corpus-read", "every audit payload"),
    Row("GET", "/documents/{document_id}/anonymized", "corpus-read", "the text"),
    Row("GET", "/documents/{document_id}/redacted.pdf", "corpus-read", "the document"),
    Row("GET", "/export/anonymized.zip", "corpus-read", "every text"),
    Row("GET", "/search", "corpus-read", "ids, scores, object keys, passage"),
    Row("GET", "/hybrid", "corpus-read", "same"),
    Row("GET", "/ask", "corpus-read", "a generated answer with citations"),
    Row("GET", "/export/ranking.csv", "corpus-read", "rank, id, score, object key"),
    Row("GET", "/dossiers/{dossier_id}/topics", "corpus-read", "what a dossier is about"),
    Row("GET", "/grants/{grant_id}", "grant-read", "recipient, types, document id"),
]
_API_WRITE = [
    Row("POST", "/documents/{document_id}/feedback", "corpus-read", "writes on the audit chain"),
    Row("POST", "/dossiers/{dossier_id}/topics", "corpus-read", "replaces every topic"),
    Row("PATCH", "/topics/{topic_id}", "corpus-read", "renames what every reader sees"),
    Row("POST", "/topics/{topic_id}/label", "corpus-read", "labels one topic"),
    Row("POST", "/dossiers/{dossier_id}/summaries", "corpus-read", "makes summaries"),
    Row("POST", "/reprocess", "corpus-read", "problems keyed by document id"),
]
_API_OTHER = [
    Row("GET", "/roles", "grant-admin", "roles decide what a grant reveals",
        declared=False),
    Row("POST", "/roles", "grant-admin", "same", declared=False),
    Row("PUT", "/roles/{name}/types", "grant-admin", "same", declared=False),
    Row("POST", "/roles/{name}/deactivate", "grant-admin", "same", declared=False),
    Row("POST", "/roles/{name}/activate", "grant-admin", "same", declared=False),
    Row("GET", "/group-roles", "grant-admin", "which groups hold which roles",
        declared=False),
    Row("PUT", "/group-roles/{group}/{role}", "grant-admin", "same", declared=False),
    Row("DELETE", "/group-roles/{group}/{role}", "grant-admin", "same",
        declared=False),
    Row("POST", "/grants", "grant-admin", "mints a grant", declared=False),
    Row("POST", "/grants/{grant_id}/revoke", "grant-admin", "revokes a grant",
        declared=False),
    Row("POST", "/datasets/pseudonymize", "grant-admin", "a token lookup"),
    Row("DELETE", "/documents/{document_id}", "delete", "irreversible"),
    Row("DELETE", "/dossiers/{dossier_id}", "delete", "irreversible"),
    Row("POST", "/documents/{document_id}/reveal", "grant", "decided by the grant"),
    Row("POST", "/documents/{document_id}/reveal.pdf", "grant", "decided by the grant"),
]
_API_UNDECIDED = [
    Row("POST", "/ingest", "any-key", "issue #431; not decided here"),
]
_API_OPEN = [
    Row("GET", "/health", "open", "liveness probe"),
    Row("GET", "/metrics", "open", "ops probe, api-key-auth spec exempt"),
    Row("GET", "/", "any-key", "redirect or {'detail': 'see /docs'}"),
    Row("GET", "/openapi.json", "any-key", "describes the routes, not the corpus"),
    Row("GET", "/docs", "any-key", "same"),
    Row("GET", "/docs/oauth2-redirect", "any-key", "same"),
    Row("GET", "/redoc", "any-key", "same"),
]

# --- Console -----------------------------------------------------------------
_CONSOLE_READ = [
    Row("GET", "/console", "corpus-read", "dossier picker", declared=False),
    Row("GET", "/console/dossier", "corpus-read", "same", declared=False),
    Row("GET", "/console/documents", "corpus-read", "alle documenten", declared=False),
    Row("GET", "/console/documents/{document_id}", "corpus-read", "one document",
        declared=False),
    Row("GET", "/console/search", "corpus-read", "search page", declared=False),
    Row("GET", "/console/topics", "corpus-read", "topics page", declared=False),
    Row("GET", "/console/feedback", "corpus-read", "feedback page", declared=False),
    Row("POST", "/console/topics", "corpus-read", "recompute topics", declared=False),
    Row("POST", "/console/topics/{topic_id}/label", "corpus-read", "label a topic",
        declared=False),
    Row("GET", "/console/combinations", "corpus-read", "declared combinations + reach",
        declared=False),
    Row("POST", "/console/combinations", "corpus-read", "declares one, writes",
        declared=False),
]
_CONSOLE_OTHER = [
    Row("GET", "/console/roles", "grant-admin", "beheren", declared=False),
    Row("POST", "/console/roles", "grant-admin", "same", declared=False),
    Row("POST", "/console/roles/switch", "grant-admin", "same", declared=False),
    Row("POST", "/console/group-roles", "grant-admin", "koppel groep aan rol",
        declared=False),
    Row("POST", "/console/group-roles/delete", "grant-admin", "ontkoppel",
        declared=False),
]
_CONSOLE_OPEN = [
    Row("GET", "/console/login", "open", "nobody can bring a key here"),
    Row("POST", "/console/login", "open", "same"),
    Row("GET", "/console/static", "open", "fonts, console.js, login's own assets"),
    Row("GET", "/console/logout", "any-key", "clears the caller's own cookie"),
]

ROWS: list[Row] = (_API_READ + _API_WRITE + _API_OTHER + _API_UNDECIDED + _API_OPEN
                   + _CONSOLE_READ + _CONSOLE_OTHER + _CONSOLE_OPEN)
