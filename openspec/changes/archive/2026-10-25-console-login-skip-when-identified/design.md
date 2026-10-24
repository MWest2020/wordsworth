# Design

## Choices

- **Decide in `login_form`, with `Identity.caller`.** The same call the
  middleware makes, so "who is verified" has one definition. A verified email
  gives 303 to `/console`; `None` (no token, bad signature, wrong audience,
  expired) shows the form.
- **`?key=1` always shows the form.** A person behind the provider carries the
  assertion on every request; without an explicit way to ask for the form, the
  key route would be unreachable from there, which the console spec forbids.
  The parameter carries no secret, so it does not fall under the rule against
  keys in a query string.
- **`build_router` receives the identity.** It is built in `api.py` and today
  only the middleware holds it. `None` when no provider is configured, in which
  case the form is always shown.
- **The redirect grants nothing.** It only moves the browser to `/console`,
  where the middleware decides as for any request. A wrong guess costs a
  redirect, not access.

## Rejected

- **Protecting `/console/login`.** Then a person with neither identity nor key
  could not reach the page that asks for one.
- **Trusting the readable email header** to decide the redirect. The header is
  never a source of identity, also not for a convenience.
- **Always redirecting identified callers, no `?key=1`.** Removes the way back
  to a key.
- **Fixing it in oauth2-proxy** (a different return URL). That is outside this
  repository and does not help whoever bookmarks `/console/login`.

## Consequence

`/console/logout` hands the identity back; its redirect to `/console/login`
therefore lands on `/console` for someone the provider still identifies.
