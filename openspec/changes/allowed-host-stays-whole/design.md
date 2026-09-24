# Design: allowed-host-stays-whole

## Host, not the whole address

The URL allow rules match the whole address including its path
(`(?:[/?#]\S*)?`), because an address on an allowed site is readable. But a
path can carry a person's name (`/raad/jan-jansen`), and today such a name is
replaced when it is detected elsewhere. Protecting the whole matched address
would make that name readable: a loss of protection, in a step whose purpose
is protection. Protecting the host alone fixes what #157 measured — the
institution's name inside its own domain — and changes nothing for the path.

Host = from the start of the match up to the first `/`, `?` or `#`.

## Subdomains

The allow patterns accept any subdomain labels (`(?:[\w-]+\.)*gooisemeren\.nl`).
A protected host therefore keeps a subdomain readable, including one that
contains a detected value. On an allowed institution's own domain the
subdomain belongs to that institution; the allow rule already said so. Noted
here so it is a decision and not an accident.

## Mechanism

`DetectionLists.allowed_spans(text, type)` returns the spans of deny matches
of that type that an allow rule of the same type fullmatches — exactly the
matches `apply` suppresses. Pure; one definition for both.

`ReversibleAnonymizer` cuts each span down to its host and hands the host
spans to the replacement step. There the hosts are swapped for placeholders
before value replacement and swapped back after the fail-hard check. So:

- no value is replaced inside a protected host;
- the fail-hard survivor check does not see the host, so an institution's name
  there does not reject the document;
- every other position, the path included, is checked exactly as before.

Placeholders instead of skipping matches: the survivor check runs on the text
after replacement, where offsets have moved. Taking the host out of the text
for the duration makes both the replacement and the check see the same thing.
