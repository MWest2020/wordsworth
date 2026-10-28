# Design: console-share

## Decisions

- **No second door.** The console calls the same issue function the API
  uses, with the same issuer check and audit; refusing is the same 403.
- **A share is a batch of grants.** A share id groups the grants it issued, so
  listing and revoking a share is one action; the grants themselves don't
  change.
- **Least by default.** The level defaults to PPL 0 (placeholders only) and the
  expiry to 30 days; raising either is a choice the sharer makes.
