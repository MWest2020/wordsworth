## ADDED Requirements

### Requirement: A deleted document releases its object key

Deleting a document SHALL, in the same transaction as its `deleted` record,
replace its `object_key` by the placeholder `deleted/<document id>` and record
the former key in that record. The check whether the stored object may be
removed SHALL use the former key. A deleted document SHALL NOT count as the
live document for its former bytes.

#### Scenario: The key is released

- **WHEN** a document is deleted
- **THEN** its row carries `deleted/<document id>` and its `deleted` record
  carries the former key

#### Scenario: The same bytes can be ingested again

- **WHEN** the bytes of a deleted document are ingested again
- **THEN** a new document is registered and the deleted one stays deleted with
  its trail unchanged

#### Scenario: A failed deletion keeps the key

- **WHEN** a deletion fails before it completes
- **THEN** the row keeps its former key, no `deleted` record exists, and a rerun
  completes the deletion and releases the key

### Requirement: Documents deleted earlier can be released

`wordsworth-release-deleted-keys` SHALL list deleted documents that still carry
a content key and, with `--apply`, release each as a deletion does, writing one
audit record per document. It SHALL NOT touch a document that is not deleted.

#### Scenario: One-off release

- **WHEN** the command runs with `--apply` and then again
- **THEN** the first run releases every such document with one audit record each
  and the second finds none
