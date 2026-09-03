# Dataset profiles

Git-versioned profiles for `POST /datasets/pseudonymize` (`profile_name=<stem>`).
Fields: `domain`, `columns` (column → PII type), `mode` (`per_attribute` |
`per_record`), `record_key` (per_record identity columns, in order), `format`
(`token` | `nen7524`), `ttp_id`, `validate_pii`. See
`docs/how-to/dataset-pseudonymisation.md`. The examples are synthetic.
