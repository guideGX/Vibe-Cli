# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `tests/test_windows_shell.py` — 5 cases pinning GBK output decoding, UTF-8 priority,
  the `VIBECLI_SHELL=cmd` opt-out, and bracket preservation in the approval panel.
- `docs/bugs/2026-10-26-windows-shell-and-markup.md` — post-mortem with reproduction,
  root cause, verification table, and the CI gap that let it survive 97 green tests.
- CI now runs the matrix on `ubuntu-latest` **and** `windows-latest` (`fail-fast: false`).

### Changed

- The `bash` / `execute_command` tool descriptions now state that a POSIX shell is used when
  available, so the model stops writing GNU-only pipelines against `cmd.exe`.

### Fixed

- **Windows: `bash` was unusable.** `asyncio.create_subprocess_shell` goes through `COMSPEC`,
  i.e. `cmd.exe`, so `| head`, `wc` and GNU `find` did not exist and the agent could only fall
  back to `python -c` one-liners. Spawn `bash -c` directly when a POSIX shell is on PATH,
  falling back to the old path otherwise; `VIBECLI_SHELL` overrides, `cmd`/`default` opts out.
- **Windows: every error message came back as `����`.** Console output was decoded as UTF-8 while
  `cmd.exe` emits GBK, so the model could not read why a command failed. Decoding now tries
  UTF-8, then the locale encoding, then GBK, and only then `errors="replace"`.
- **The approval panel showed a different command than the one about to run.** `_approval_prompt`
  printed the payload through `console.print(f"...")`, so rich parsed `[pathlib.Path('src')]` as
  markup and dropped it. Render it as `Text` and pretty-print the payload as indented JSON.

## [0.1.0] - 2026-10-26

First tagged release. The feature surface below is what exists in `src/vibecli` today; anything
listed as a known gap is stated as such in [docs/parity.md](docs/parity.md) rather than implied.

### Added

- **CLI** — `vibecli` REPL, `-p/--prompt` print mode, `--provider` / `--model` / `--plain` /
  `--cwd` overrides, `--version`, `doctor`, `serve`, and the `mcp list` / `mcp serve` /
  `mcp init-chrome` command group.
- **Agent core** — event-stream ReAct loop with streamed tool-call argument merging, thinking
  deltas, usage accounting, and a bounded turn count.
- **Plan-and-Execute** — Planner-generated task DAG, dependency-ordered execution, parallel
  batches for independent tasks, and explicit `completed` / `failed` / `stalled` outcomes.
- **Multi-agent orchestration** — Planner / Worker / Reviewer roles, worker pool with history
  clearing on release, reviewer rejection with per-step retry cap.
- **Tools** — 15 built-ins: `read_file`, `write_file`, `list_dir`, `glob` / `glob_files`,
  `grep` / `grep_code`, `bash` / `execute_command`, `web_search`, `web_fetch`, `save_memory`,
  `load_skill`, `search_code`, `revert_turn`. Read-only safe tools run in parallel batches;
  writes run strictly in order.
- **MCP** — stdio and Streamable HTTP client transports, dynamic `mcp__<server>__<tool>`
  registration, four virtual resource/prompt tools per server, and VibeCLI as an MCP server over
  stdio or HTTP.
- **Chrome DevTools MCP helper** — `mcp init-chrome` writes a correct config with
  `--browser-url`, `--headless`, `--slim`, and usage-statistics opt-out.
- **Runtime API** — `/v1/threads`, `/v1/threads/{id}/turns`, SSE event replay at
  `/v1/threads/{id}/events`, and a SQLite-backed durable task queue with two worker threads.
- **Memory** — SQLite long-term memory scoped per project, plus project memory files
  (`VIBE.md`, `.vibecli/VIBE.md`, and `.local.md` variants) folded into the system prompt.
- **RAG** — SQLite local code index with `/index`, `/search`, and the `search_code` tool.
- **Skills** — built-in / user / project layers, `SKILL.md` frontmatter, disabled-state store,
  and one-shot `load_skill` injection through a bounded context buffer.
- **Snapshots** — automatic `pre-turn` / `post-turn` snapshots under
  `~/.vibecli/snapshots/<project-hash>/`, `/snapshot`, `/restore`, `/snapshot clean`, and a
  `pre-restore` safety snapshot on every rollback.
- **Image input** — `@image:` for local paths, `file://`, and remote URLs; 1568px downscaling,
  JPEG re-encoding, transparent-PNG flattening, and workspace confinement.
- **Safety** — `PathGuard`, `CommandGuard` (configurable blacklist plus destructive-command
  regexes), `HITL` with `always` / `auto` / `never`, and a redacting JSONL `AuditLog`.
- **SDK** — `create_default_engine` with `ask` / `plan` / `team` and their `*_complete` and
  `*_complete_async` variants.
- **Diagnostics** — Python syntax check after `write_file`, surfaced back to the model.
- **Docs** — Chinese-primary README with English mirror, `docs/architecture.md` (turn lifecycle,
  event contract, execution model, safety layering, extension points), parity matrix, and this
  changelog.
- **Tests** — 97 offline tests covering config layering, safety policy, tool execution, the ReAct
  loop, snapshots, Runtime API, memory/index, MCP config, image input, CLI, and SDK wiring. No
  network or API key required.
- **CI** — GitHub Actions running ruff lint, format check, the test suite, CLI smoke checks, and
  `uv build`.

### Changed

- README rewritten as a Chinese-primary document with a full English mirror. The earlier English
  rewrite had dropped the usage chapters for MCP, Runtime API, image input, snapshots, SDK, and
  web tools; those are restored and re-verified against the current code.
- `parity.md` verification steps now reflect reality: `pytest` is a declared dev dependency and
  `tests/` exists.

### Fixed

- HITL rejection message read `was denyed by approval policy`; it now says `denied` / `skipped`.

### Known gaps

- Context compression is config-only (`memory.compression_threshold`); the summarisation logic is
  not wired yet.
- Snapshots are full copies, not incremental.
- The Runtime API event endpoint replays; it does not hold a live subscription.
- The private WeChat iLink channel from the Java implementation is intentionally absent.
