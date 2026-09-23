## ADDED Requirements

### Requirement: The API survives the loss of one node

The API SHALL run with at least two replicas on different nodes, with a
disruption budget that always keeps one running. The API SHALL mount no volume
whose storage class ties it to one node; its state SHALL live in PostgreSQL or
the object store. State that decides a request across replicas — rate-limit
buckets — SHALL be shared by every replica, not held per process.

#### Scenario: One api pod goes away

- **GIVEN** two api replicas on different nodes
- **WHEN** one of them is deleted or its node is drained
- **THEN** the console keeps answering

#### Scenario: A limit holds across replicas

- **GIVEN** a limit of N requests for one client on one endpoint
- **WHEN** that client's requests are spread over both replicas
- **THEN** no more than N are allowed in total

#### Scenario: A node-bound volume is mounted

- **GIVEN** a volume on a storage class tied to one node
- **WHEN** it is mounted into the API
- **THEN** that violates this requirement, because the second replica would
  suggest redundancy that is not there

---

### Requirement: "Highly available" appears only after a node-shutdown test

The documentation SHALL call wordsworth highly available only after a test has
shown the console keeps answering while one node is shut down. The outcome of
that test SHALL be recorded with its date and which node it was.

#### Scenario: Test run

- **WHEN** the node-shutdown test has run and passed
- **THEN** the documentation names the date, the node, and what was and was
  not reachable during the test

#### Scenario: Test not run

- **WHEN** no node-shutdown test has run
- **THEN** the documentation says which components each need one node, and
  what is lost when that node is gone
