# Tasks

## 1. Code
- [ ] Pass the `Identity` (or `None`) from `api.py` into `build_router`.
      Proved by: the tests in 2 constructing the app with a verifier.
- [ ] In `console.py` `login_form`: if `?key=1` is absent and
      `identity.caller(request)` yields an email, return a 303 to `/console`.
      Proved by: the tests in 2.

## 2. Tests (`tests/test_console.py` or beside `tests/test_access_resolver.py`)
- [ ] A verified assertion on `GET /console/login` gives 303 to `/console`.
- [ ] No assertion shows the form (200).
- [ ] An invalid assertion (bad signature, other audience) shows the form.
- [ ] `?key=1` shows the form even with a verified assertion.
- [ ] Without an identity provider configured the form is shown, as before.
      Proved by: the existing `test_console.py` line 51 still passing.

## 3. Docs (CI fails on code without docs)
- [ ] `docs/how-to/console.md`: where it describes `/console/login` (the
      exemption paragraph), say an identified caller is sent on to `/console`
      and `?key=1` shows the form. Proved by: docs review in the PR.
- [ ] `docs/how-to/access-identity.md`, "Keeping the key route": the same, and
      that `?key=1` is the way to choose the key. Proved by: docs review.

## 4. The real artefact
- [ ] Open `/console/login` through oauth2-proxy logged in: lands on
      `/console`; with `?key=1`: the form. Resolves the first open question.
