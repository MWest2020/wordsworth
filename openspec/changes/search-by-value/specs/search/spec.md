## ADDED Requirements

### Requirement: Search by a real value runs on its token

wordsworth SHALL accept a search for a real value of a given PII type, obtain
the value's tokens from the key service and run an exact term search on those
tokens within the requested scope. The search index SHALL never receive the
value. A refusal by the key service SHALL produce a result indistinguishable
from a search that matched nothing.

#### Scenario: A name finds the documents that mention it

- **WHEN** a caller allowed PERSON searches the value `Jan Jansen` in a dossier
  whose documents mention `Jan Jansen`
- **THEN** those documents are returned, shown pseudonymised

#### Scenario: No right looks like no hits

- **WHEN** a caller without the right searches a value that does occur
- **THEN** the response has the same shape as a search with no hits

#### Scenario: Types and domains do not cross

- **WHEN** the same value is searched as ORGANIZATION while it occurs only as
  PERSON
- **THEN** nothing matches
