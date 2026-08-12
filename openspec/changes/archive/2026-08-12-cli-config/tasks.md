## 1. Config file

- [x] 1.1 Read `~/.config/wordsworth/config.yaml` (or `$WORDSWORTH_CONFIG`),
  flat `key: value`, stdlib-only.
- [x] 1.2 Resolution: flag > `$WORDSWORTH_API_URL` > config > default (url);
  flag > config > default (batch/timeout).
- [x] 1.3 `wordsworth config` subcommand: show / set url,batch,timeout.

## 2. Install + docs + gate

- [x] 2.1 `install-cli.sh --url` writes the config via `wordsworth config`.
- [x] 2.2 README + docs/reference/cli.md document the config file + subcommand.
- [x] 2.3 Tests (config write/resolve, env-beats-config) + full suite green.
