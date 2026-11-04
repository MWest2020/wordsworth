# Design

## Stop on key refusal, continue on everything else

A parse, empty or unsupported file says something about that file; the next
file may be fine. A key-service refusal says something about the service, so
every later file would fail the same way. Stopping returns the 503 early with
the completed `results` instead of N identical failures.

## "Not stored" is only promised before the write

`put_original` mints the key before it writes (rule 3), so a refusing key
service leaves nothing in the store. If a write already committed and
`process`'s read-back then raises `OriginalsKeyUnavailable`, the object stays.
The `deployment` delta and the tests claim no more than the first case.

Rejected: a compensating delete on the `process` path. It would destroy a
document that can be resumed, and `wordsworth-sealed-orphans` already sweeps a
sealed object with no usable row.

## Rejected: leave the `deployment` requirement as it is

"A file that fails SHALL NOT abort the batch" would contradict the 503 stop.
The requirement is MODIFIED with its existing scenarios kept and one added.

## Known gap, not fixed here

`client.py` `_post_batch_with_retry` retries 5xx and discards the 503 body, so
`wordsworth ingest <dir>` against a down key service does not surface
`results`. Handled in `originals-ingest-switch`'s docs or a separate issue.
