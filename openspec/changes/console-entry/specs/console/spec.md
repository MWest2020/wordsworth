## ADDED Requirements

### Requirement: A browser always lands on a page that works

While the console is mounted, a request that asks for HTML SHALL end on a page,
never on an API error body: a refused request goes to the login page, the root
path goes to the console, and an unknown path goes to the console.

A lock that gives no indication where the key goes is not a lock, it is a wall.

A client that did not ask for HTML SHALL keep receiving the unchanged API error.
A 303 to an HTML form is the wrong answer for a program, which will try to parse
it and report something incomprehensible.

Without the console mounted there is no page to send anyone to, and every
response SHALL stay as it is. Redirecting to a route that answers 404 replaces
the wall with a circle.

#### Scenario: A browser refused on any path lands on the login page

- **WHEN** a request with an HTML `Accept` header is refused for a missing or
  invalid key, on any path
- **THEN** it is redirected to `/console/login`

#### Scenario: The bare hostname opens the console

- **WHEN** a browser requests `/`
- **THEN** it is redirected to the console

#### Scenario: An unknown path opens the console

- **WHEN** a browser requests a path that matches no route
- **THEN** it is redirected to the console

#### Scenario: An API client still gets an API error

- **WHEN** a request without an HTML `Accept` header is refused
- **THEN** it receives the unchanged 401 with the JSON body

### Requirement: The login form refuses a wrong key

The login form SHALL check the key against the configured set before storing it,
and SHALL redisplay the form with a reason when it does not match.

Storing an unchecked key produces a cookie that leads nowhere, so a typo becomes
the same dead end as no key at all — with the added confusion of having
apparently logged in.

#### Scenario: A wrong key is rejected at the form

- **WHEN** an operator submits a key that is not in the configured set
- **THEN** the form is shown again with a reason and no cookie is set

#### Scenario: Logging out clears the cookie

- **WHEN** an operator logs out
- **THEN** the cookie is cleared and the next console request goes to the login
  page
