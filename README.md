# VibeCLI (Python)

A terminal AI agent CLI written in Python — ReAct loop, Plan-and-Execute, multi-agent
orchestration, MCP, a durable Runtime API, long-term memory, turn snapshots, a local code
index, and image input.

This is the Python port of the VibeCLI Java / TypeScript implementations.
See [`docs/parity.md`](docs/parity.md) for the full parity matrix.

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Optional: Node.js LTS + `npm`/`npx` (only for Chrome DevTools MCP)

## Install

```bash
# with uv (recommended)
uv sync
uv sync --extra dev      # plus ruff

# or with pip
pip install -e .
```

For an editable install that exposes the `vibecli` command:

```bash
uv run vibecli --help
```

## Quick start

```bash
# 1. Provide an API key (DeepSeek is the default provider)
export VIBECLI_API_KEY="sk-..."        # macOS / Linux
set VIBECLI_API_KEY=sk-...             # Windows (cmd)
$env:VIBECLI_API_KEY="sk-..."          # Windows (PowerShell)

# 2. Check the environment
uv run vibecli doctor

# 3. Start the REPL
uv run vibecli

# 4. Or run a single prompt, non-interactive
uv run vibecli -p "summarize src/vibecli/agent/agent.py"
```

## CLI

| Command | Description |
| --- | --- |
| `vibecli` | Start the interactive REPL |
| `vibecli -p, --prompt <text>` | Print mode: run one prompt and exit |
| `vibecli -m, --model <name>` | Override the model |
| `vibecli --provider <name>` | Override the LLM provider |
| `vibecli --plain` | Plain-text rendering (no Rich UI) |
| `vibecli --cwd <path>` | Set the working directory |
| `vibecli --version` | Print the version |
| `vibecli doctor` | Print an environment / config diagnostic report |
| `vibecli serve --http --port <port>` | Start the Runtime API over HTTP |
| `vibecli mcp list` | List configured MCP servers |
| `vibecli mcp serve --transport stdio\|http` | Expose built-in tools as an MCP server |
| `vibecli mcp init-chrome` | Write a Chrome DevTools MCP config |

## Configuration

Config is resolved by layering, later sources overriding earlier ones:

1. Built-in defaults
2. User config — `~/.vibecli/config.json`
3. Project config — `<project>/.vibecli/config.json`
4. Project `.env`
5. CLI overrides (`--provider`, `--model`, `--plain`)
6. Process environment

### Environment variables

| Variable | Purpose |
| --- | --- |
| `VIBECLI_API_KEY` | Generic API key |
| `VIBECLI_PROVIDER` | Provider name (`deepseek`, `glm`, `step`, `kimi`, ...) |
| `VIBECLI_MODEL` | Model name |
| `VIBECLI_BASE_URL` | Override the API base URL |
| `VIBECLI_MAX_TOKENS` | Max output tokens |
| `VIBECLI_TEMPERATURE` | Sampling temperature |
| `VIBECLI_RENDER_MODE` / `VIBECLI_RENDERER` | `plain` or `inline` |
| `VIBECLI_MCP` / `VIBECLI_SKILL` / `VIBECLI_MEMORY` | `true` / `false` feature toggles |
| `VIBECLI_HITL` | Human-in-the-loop mode: `always`, `auto`, `never` |
| `VIBECLI_RUNTIME_API_KEY` | Required by `vibecli serve` |

Provider-specific keys are also picked up when `VIBECLI_API_KEY` is unset:
`DEEPSEEK_API_KEY`, `GLM_API_KEY`, `STEP_API_KEY`, `KIMI_API_KEY`, `FREELLMAPI_API_KEY`,
`XFYUN_API_KEY`, `AGNES_API_KEY`. Per-provider `<PROVIDER>_MODEL` and
`<PROVIDER>_BASE_URL` are honored as well.

### State files

| Path | Contents |
| --- | --- |
| `~/.vibecli/config.json` | User configuration |
| `~/.vibecli/memory.db` | SQLite long-term memory |
| `~/.vibecli/audit.jsonl` | JSONL audit log |
| `~/.vibecli/history/prompt_history.txt` | REPL input history |
| `~/.vibecli/skills.json` | Disabled-state store for skills |

## REPL slash commands

```
/help    /exit    /clear   /context  /memory  /save    /config
/tools   /hitl    /policy  /audit    /index   /search  /plan
/team    /model   /skill   /mcp      /task    /snapshot /restore
```

## Built-in tools

`read_file`, `write_file`, `list_dir`, `glob` / `glob_files`, `grep` / `grep_code`,
`bash` / `execute_command`, `web_search`, `web_fetch`, `save_memory`, `load_skill`,
`search_code`, `revert_turn`.

MCP servers add tools dynamically as `mcp__<server>__<tool>`, plus virtual resource and
prompt tools.

## Safety

- **PathGuard** — confines file operations to the workspace
- **CommandGuard** — blocks destructive shell commands (`sudo`, `rm -rf /`, `mkfs`, ...)
- **HITL** — approval prompts for risky actions, with `always` / `auto` / `never` modes
- **AuditLog** — every sensitive action appended to `~/.vibecli/audit.jsonl`

## Project layout

```
src/vibecli/
  agent/         ReAct agent, Plan-and-Execute, multi-agent orchestrator
  llm/           OpenAI-compatible streaming client + provider factory
  tools/         Tool registry, base classes, built-ins, executor
  mcp/           MCP client, server, config writer (stdio / HTTP)
  lsp/           Post-write Python syntax diagnostics
  plan/          Planner + task DAG models
  policy/        PathGuard, CommandGuard, AuditLog
  memory/        SQLite long-term memory manager
  prompt/        System-prompt assembler
  rag/           SQLite local code index
  render/        Rich and plain renderers
  runtime/       HTTP Runtime API + durable task queue
  skill/         Skill registry and loading
  snapshot/      pre-turn / post-turn snapshots and restore
  image/         Image input preprocessing
  web/           Web search and fetch helpers
  entrypoints/   CLI entrypoint and REPL
```

## Development

```bash
uv sync --extra dev
uv run --extra dev ruff check .
uv run --extra dev ruff format .
uv build
uv run vibecli --help
```

## Notes

- Project memory files: `VIBE.md`, `.vibecli/VIBE.md`, and their `.local.md` variants.
- The Java implementation ships a private WeChat iLink channel; the Python port
  intentionally does not, since it needs private credentials and protocol details.

## License

MIT
