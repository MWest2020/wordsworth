# Design

## Shared documents lose only the membership

A document is what its bytes are, and it may belong to several dossiers
(`dossiers` spec). Deleting dossier A must therefore not destroy a document that
dossier B still holds: that would let deleting one case silently empty another.
So a member is deleted only when this dossier is its last; otherwise the
membership alone goes.

Rejected: delete every member regardless. Simple, but a delete in one case
destroys content another case still relies on, with no way back.

Rejected: refuse to delete a dossier that holds shared documents. Safe, but the
caller then has to remove each membership by hand first, which is the manual
cleanup this change replaces.

## The dossier row goes

The dossier is removed together with its memberships. Keeping an empty shell
would leave the 10 empty rows that prompted this change.

## One record per document touched

`dossier-deleted` is written per document touched — deleted or only released —
holding the document id, the dossier id, the actor and what happened, never a
name or value. A document that is deleted also gets its usual `deleted` record
from `delete-documents`. The audit table is append-only and keyed by document,
so the record belongs to the document, not to the dossier.

## Same guard, same code path

The authorisation check is the one `delete-documents` already uses; a refusal
happens before anything is read or removed and writes no record. The dry run
walks the same code path as the real run and stops before the first removal, so
its report cannot drift from what the delete does. It says which documents
would be deleted and which would only lose the membership.

## Failure

A failed removal of a member document is a hard error as in `delete-documents`;
the dossier row is removed only when its members have been handled, so a rerun
finishes the work.
