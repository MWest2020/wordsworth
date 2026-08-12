## Why

The CLI's API URL had to be passed as `--url` (or an env var) on every call —
easy to forget, and `wordsworth ingest <dir>` silently fell back to
`localhost:8000`. The URL (and other defaults) should be set once, persistently.

## What Changes

- The CLI reads a **config file** (default `~/.config/wordsworth/config.yaml`,
  overridable via `$WORDSWORTH_CONFIG`) — a flat `key: value` file (`url`,
  `batch`, `timeout`) parsed with the standard library (still no dependencies,
  so it stays copy-runnable; not full YAML).
- New `wordsworth config` subcommand shows the config or sets keys
  (`wordsworth config --url … [--batch N] [--timeout S]`, `--show`).
- Resolution order per value: command-line flag > `$WORDSWORTH_API_URL` (URL
  only) > config file > built-in default.
- `install-cli.sh --url` now writes the config (via `wordsworth config`) instead
  of rewriting the installed file, so the setting is a plain editable file.

## Capabilities

### Modified Capabilities
- `deployment`: the client CLI gains persistent configuration.

## Impact

- Code: `src/wordsworth/client.py` (config load/resolve + `config` subcommand),
  `scripts/install-cli.sh`. Docs updated (README + `docs/reference/cli.md`). No
  API or pipeline change.
