# VibeCLI Python Parity

This file tracks the Python port against the existing Java and TypeScript implementations.

## Implemented

- CLI:
  - `vibecli`
  - `vibecli -p`
  - `--provider`
  - `--model`
  - `--plain`
  - `--cwd`
  - `vibecli doctor`
  - `vibecli serve --http --port <port>`
- REPL:
  - `/help`
  - `/clear`
  - `/context`
  - `/memory`
  - `/save`
  - `/config`
  - `/tools`
  - `/hitl`
  - `/policy`
  - `/audit`
  - `/index`
  - `/search`
  - `/plan`
  - `/team`
  - `/task`
  - `/snapshot`
  - `/restore`
  - `/skill`
  - `/mcp`
  - `/exit`
- Agent:
  - OpenAI-compatible streaming LLM client
  - DeepSeek default
  - ReAct loop with text/thinking/tool-call/tool-result/done events
  - Plan-and-Execute agent with Planner-generated DAG, dependency ordering, and parallel executable batches
  - Multi-Agent orchestrator with Planner, Worker, Reviewer, dependency scheduling, parallel workers, review approval parsing, and bounded retry
  - SDK entrypoint with ReAct, Plan-and-Execute, and Multi-Agent methods
  - pre/post side-history snapshots around Agent runs
- Configuration:
  - defaults
  - user config
  - project config
  - project `.env`
  - CLI overrides