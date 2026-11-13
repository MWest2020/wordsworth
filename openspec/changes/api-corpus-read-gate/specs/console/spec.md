## ADDED Requirements

### Requirement: Declared combinations stand behind corpus read

The console page that lists the declared combinations and the action that
records one SHALL require corpus read, as every other console page that shows
the corpus does. The page shows in how many documents a combination occurs,
and a recorded combination appears on every document page. A caller who is not
on the corpus-read list SHALL get the 403 page, and his submission SHALL store
nothing and change no existing declaration.

#### Scenario: A caller on no list does not see the combinations

- **WHEN** an authenticated caller who is not on the corpus-read list opens
  `/console/combinations`
- **THEN** the answer is 403

#### Scenario: A caller on no list cannot declare or overwrite one

- **WHEN** that caller submits a combination, new or with the types of an
  existing declaration
- **THEN** the answer is 403, nothing is stored, and the existing declaration
  keeps its reason and the name of who declared it

#### Scenario: A reader declares as before

- **WHEN** a caller on the corpus-read list records a combination with a reason
- **THEN** it is stored and the page shows its reach
