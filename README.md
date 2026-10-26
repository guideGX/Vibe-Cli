# VibeCLI (Python)

[![CI](https://github.com/guideGX/Vibe-Cli/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/guideGX/Vibe-Cli/actions/workflows/ci.yml)
![version](https://img.shields.io/badge/version-0.1.0-blue)
![python](https://img.shields.io/badge/python-3.11%2B-3776AB)
![tests](https://img.shields.io/badge/tests-97%20passed-brightgreen)
![license](https://img.shields.io/badge/license-MIT-green)

[English](README.en.md) · [架构文档](docs/architecture.md) · [对齐矩阵](docs/parity.md) · [变更日志](CHANGELOG.md)

运行在终端里的 AI Agent CLI，面向真实项目开发场景：读写文件、搜索代码、执行命令、联网检索、调用 MCP 工具、保存长期记忆、生成快照并恢复现场，并通过 Runtime API 对外提供线程、turn、事件和后台任务能力。

这个仓库是 VibeCLI 的 Python 版本。它不是空壳 Demo，而是按真实 CLI 产品的标准来做：核心路径有测试覆盖（97 个用例，见[开发与测试](#开发与测试)），CI 跑 lint + 测试 + 冒烟 + 构建，安全策略和失败路径都有明确的实现位置。

![VibeCLI 终端输出](docs/images/terminal-demo.svg)

## 功能特性

- 交互式终端 Agent，Rich + prompt-toolkit 渲染，底部实时显示模型、上下文占用、cwd、工具/MCP/skill 计数
- 单次 prompt 模式（`-p`），适合脚本、管道和自动化调用
- OpenAI-compatible 流式 LLM 客户端，默认面向 DeepSeek，支持 GLM / Kimi / Step / 本地 OpenAI-compatible 服务
- ReAct 工具调用循环：文本增量、thinking 增量、流式 tool call 参数拼接、多工具批量执行、usage 统计
- Plan-and-Execute：独立 Planner 生成任务 DAG，按依赖批次串行/并行执行，失败任务不阻塞无关分支
- Multi-Agent：Planner / Worker / Reviewer 三角色编排，共享消息总线、依赖调度、review 驳回与有限重试
- 15 个内置工具：文件、Shell、grep、glob、记忆、skill 加载、代码搜索、快照回滚
- 四层安全：路径限制、命令黑名单 + 破坏性命令正则、HITL 人工确认、JSONL 审计日志（自动脱敏）
- MCP client：stdio 与 Streamable HTTP 双传输，远端工具动态注册为 `mcp__<server>__<tool>`
- VibeCLI 自身也能作为 MCP server 暴露内置工具（stdio / HTTP）
- Chrome DevTools MCP 配置助手，一条命令写好人人都配不对的那段 JSON
- Skill 系统：内置 / 用户级 / 项目级三层，支持启用禁用与 `load_skill` 一次性注入
- Runtime API：线程、turn、SSE 事件流、SQLite 持久化后台任务队列
- SQLite 长期记忆 + 本地代码索引（零外部依赖的 RAG 兜底）
- Agent run 前后自动快照，`/restore` 一键回到上一轮之前
- 图片输入：本地路径 / `file://` / 远程 URL，自动缩放压缩、透明底铺白、按模型能力降级
- 写 `.py` 文件后自动跑 `py_compile` 语法诊断，把错误在模型下一次思考前就还给它

## 环境要求

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)（推荐）或 pip
- 可选：`rg`，用于更快的本地搜索
- 可选：Chrome DevTools MCP 需要 Node.js LTS、`npm`/`npx` 和 Chrome

## 安装

```bash
git clone https://github.com/guideGX/Vibe-Cli.git
cd Vibe-Cli
uv sync                 # 运行依赖
uv sync --extra dev     # 加上 ruff 和 pytest
uv run vibecli --help
```

用 pip 也可以：

```bash
pip install -e .
pip install -e ".[dev]"
```

## 快速开始

```bash
# 1. 提供 API Key（默认 provider 是 DeepSeek）
export VIBECLI_API_KEY="sk-..."        # macOS / Linux
set VIBECLI_API_KEY=sk-...             # Windows cmd
$env:VIBECLI_API_KEY="sk-..."          # Windows PowerShell

# 2. 自检：Python / uv / node / npx / rg / key / 配置文件路径
uv run vibecli doctor

# 3. 进入交互模式
uv run vibecli

# 4. 或者非交互跑一条
uv run vibecli -p "summarize src/vibecli/agent/agent.py"
```

`vibecli doctor` 的真实输出（字段固定，方便贴进 issue）：

```json
{
  "python": "3.11.2",
  "uv": "C:\\Users\\gx\\.local\\bin\\uv.EXE",
  "node": "v22.22.2",
  "npx": "C:\\Users\\gx\\.workbuddy\\binaries\\node\\versions\\22.22.2-6\\npx.CMD",
  "rg": "missing",
  "api_key": "missing",
  "provider": "deepseek",
  "model": "deepseek-v4-flash",
  "cwd": "C:\\Users\\gx\\Desktop\\python\\VibeCLI-Python\\VibeCLI-Python",
  "config_paths": [
    "C:\\Users\\gx\\.vibecli\\config.json",
    "C:\\Users\\gx\\Desktop\\python\\VibeCLI-Python\\VibeCLI-Python\\.vibecli\\config.json"
  ]
}
```

## CLI

| 命令 | 说明 |
| --- | --- |
| `vibecli` | 启动交互 REPL |
| `vibecli -p, --prompt <text>` | 单次执行模式，跑完退出 |
| `vibecli -m, --model <name>` | 临时覆盖模型 |
| `vibecli --provider <name>` | 临时覆盖 provider |
| `vibecli --plain` | 纯文本渲染（无 Rich UI） |
| `vibecli --cwd <path>` | 指定工作目录 |
| `vibecli --version` | 打印版本 |
| `vibecli doctor` | 输出环境与配置体检报告（JSON） |
| `vibecli serve --http --port <port>` | 启动 Runtime API |
| `vibecli serve --api-key <key>` | 显式指定 Runtime API Key |
| `vibecli mcp list` | 列出已配置的 MCP server |
| `vibecli mcp serve --transport stdio\|http` | 把内置工具暴露成 MCP server |
| `vibecli mcp init-chrome` | 写 Chrome DevTools MCP 配置 |

## 配置

配置按层叠加，后面的覆盖前面的：

1. 内置默认值
2. 用户级 `~/.vibecli/config.json`
3. 项目级 `<project>/.vibecli/config.json`
4. 项目 `.env`
5. CLI 参数（`--provider`、`--model`、`--plain`）
6. 进程环境变量

写进项目 `.env` 最省事：

```dotenv
VIBECLI_PROVIDER=deepseek
VIBECLI_MODEL=deepseek-v4-flash
DEEPSEEK_API_KEY=your_key_here
```

或者用通用 Key：

```dotenv
VIBECLI_API_KEY=your_key_here
```

### 环境变量

| 变量 | 作用 |
| --- | --- |
| `VIBECLI_API_KEY` | 通用 API Key |
| `VIBECLI_PROVIDER` | provider 名（`deepseek` / `glm` / `kimi` / `step` / `openai-compatible`） |
| `VIBECLI_MODEL` | 模型名 |
| `VIBECLI_BASE_URL` | 覆盖 API base URL |
| `VIBECLI_MAX_TOKENS` | 单次最大输出 token |
| `VIBECLI_TEMPERATURE` | 采样温度 |
| `VIBECLI_RENDER_MODE` / `VIBECLI_RENDERER` | `plain` 或 `inline` |
| `VIBECLI_TUI` | 设为 `true` 强制 inline 渲染 |
| `VIBECLI_MCP` / `VIBECLI_SKILL` / `VIBECLI_MEMORY` | `true` / `false` 功能开关 |
| `VIBECLI_HITL` | 人工确认模式：`always` / `auto` / `never` |
| `VIBECLI_RUNTIME_API_KEY` | `vibecli serve` 必需 |

`VIBECLI_API_KEY` 未设置时，会按 provider 回落到专属 Key：`DEEPSEEK_API_KEY`、`GLM_API_KEY`、`STEP_API_KEY`、`KIMI_API_KEY`、`FREELLMAPI_API_KEY`、`XFYUN_API_KEY`、`AGNES_API_KEY`。同理，`<PROVIDER>_MODEL` 和 `<PROVIDER>_BASE_URL` 也生效。

连接本地 OpenAI-compatible 服务：

```bash
VIBECLI_PROVIDER=openai-compatible \
VIBECLI_BASE_URL=http://127.0.0.1:11434/v1 \
VIBECLI_MODEL=qwen2.5-coder \
uv run vibecli -p "解释这个仓库"
```

### 状态文件

| 路径 | 内容 |
| --- | --- |
| `~/.vibecli/config.json` | 用户配置 |
| `~/.vibecli/mcp.json` | 用户级 MCP server 配置 |
| `~/.vibecli/memory.db` | SQLite 长期记忆 |
| `~/.vibecli/audit.jsonl` | JSONL 审计日志 |
| `~/.vibecli/skills.json` | skill 禁用状态 |
| `~/.vibecli/skills/` | 用户级 skill |
| `~/.vibecli/snapshots/<项目哈希>/` | 项目快照与 `index.jsonl` |
| `~/.vibecli/tasks/tasks.db` | 持久化后台任务队列 |
| `~/.vibecli/runtime/runtime.db` | Runtime API 的线程与事件 |
| `~/.vibecli/history/prompt_history.txt` | REPL 输入历史 |
| `<project>/.vibecli/config.json` | 项目级配置 |
| `<project>/.vibecli/mcp.json` | 项目级 MCP server 配置 |
| `<project>/.vibecli/skills/` | 项目级 skill |
| `<project>/.vibecli/code_index.sqlite3` | 本地代码索引 |

## REPL 斜杠命令

```
/help    /exit    /clear   /context  /memory  /save    /config
/tools   /hitl    /policy  /audit    /index   /search  /plan
/team    /model   /skill   /mcp      /task    /snapshot /restore
```

| 命令 | 用法与行为 |
| --- | --- |
| `/help` | 打印命令列表 |
| `/exit`（别名 `/quit`） | 退出 |
| `/clear` | 清空对话历史与屏幕 |
| `/context` | 当前 cwd、模型、上下文窗口、渲染模式、记忆条数、工具数 |
| `/memory` | 列出当前项目记忆 |
| `/memory search <query>` | 按词检索（要求所有词命中） |
| `/memory clear` | 清空当前项目记忆 |
| `/save <fact>` | 写入一条长期记忆 |
| `/config` | 打印当前配置（API Key 已脱敏为 `***`） |
| `/tools` | 列出已注册工具 |
| `/hitl on\|off\|always\|auto\|never` | 切换人工确认模式（`on`=`always`，`off`=`never`） |
| `/policy` | 打印策略配置（HITL 模式、路径限制、命令黑名单、审计路径） |
| `/audit [N]` | 查看最近 N 条审计记录 |
| `/index [path]` | 重建本地代码索引 |
| `/search <query>` | 在索引里搜代码（`path:line: snippet`） |
| `/plan <task>` | 用 Plan-and-Execute 执行 |
| `/team <task>` | 用多 Agent 编排执行 |
| `/model [provider] [model]` | 查看或修改模型（新客户端生效，重开 REPL 重建当前 client） |
| `/skill [list\|show <name>\|on <name>\|off <name>\|reload]` | skill 管理 |
| `/mcp` | 提示如何把内置工具暴露为 MCP server |
| `/task [add <task>\|cancel <id>\|log <id>]` | 后台任务队列 |
| `/snapshot [clean]` | 列出/清理快照 |
| `/restore <id-or-index>` | 恢复到指定快照 |

## 内置工具

| 工具 | 读/写 | 危险级别 | 说明 |
| --- | --- | --- | --- |
| `read_file` | 读 | safe | 按行号输出，支持 `offset` / `limit` |
| `write_file` | 写 | medium | 写 UTF-8 文本，可选 `append`，5MB 上限，写完自动语法诊断 |
| `list_dir` | 读 | safe | 列目录 |
| `glob` / `glob_files` | 读 | safe | 按模式找文件 |
| `grep` / `grep_code` | 读 | safe | 文本/正则搜索 |
| `bash` / `execute_command` | 写 | high | 需要 HITL 确认；先过命令策略 |
| `web_search` | 读 | safe | DuckDuckGo HTML 搜索，返回标题/URL/摘要 |
| `web_fetch` | 读 | safe | 抓取公开页面并提取正文，拒绝内网/回环/`file://` |
| `save_memory` | 写 | medium | 写长期记忆 |
| `load_skill` | 读 | safe | 懒加载 skill，内容在下一次模型调用时一次性注入 |
| `search_code` | 读 | safe | 查本地代码索引 |
| `revert_turn` | 写 | high | 回滚到指定快照，需要 HITL 确认 |

只读且并发安全的工具会被批量并行执行（默认并发 4），写操作严格串行、保持声明顺序。

## MCP

VibeCLI 可以连接 MCP server，并把远端工具动态注册成：

```text
mcp__<server-name>__<tool-name>
```

除了 server 自己的工具，每个连上的 server 还会额外挂上 4 个虚拟工具：

```text
mcp__<server>__list_resources    mcp__<server>__read_resource
mcp__<server>__list_prompts      mcp__<server>__get_prompt
```

### 配置来源

`~/.vibecli/mcp.json`（用户级）与 `<project>/.vibecli/mcp.json`（项目级）合并，项目级同名覆盖。支持 `${PROJECT_DIR}`、`${HOME}` 和环境变量占位符。

```json
{
  "mcpServers": {
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "${PROJECT_DIR}"],
      "env": {},
      "timeout": 30
    },
    "remote": {
      "type": "streamable_http",
      "url": "https://example.com/mcp",
      "headers": { "authorization": "Bearer ${MCP_TOKEN}" }
    }
  }
}
```

不写 `type` 时：有 `url` 视为 `streamable_http`，否则视为 `stdio`。

### Chrome DevTools MCP

```bash
# 写项目级配置（默认 scope=project）
uv run vibecli mcp init-chrome

# 写用户级配置
uv run vibecli mcp init-chrome --scope user

# 接已有 remote-debugging 的 Chrome
uv run vibecli mcp init-chrome --browser-url http://127.0.0.1:9222

# 无头 / slim 模式
uv run vibecli mcp init-chrome --headless --slim

uv run vibecli mcp list
```

写入内容形如：

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest", "--no-usage-statistics"]
    }
  }
}
```

默认带上 `--no-usage-statistics`。`mcp list` 的真实输出：

```text
chrome-devtools	stdio	npx -y chrome-devtools-mcp@latest --no-usage-statistics
```

> Chrome DevTools MCP 会把浏览器页面和登录态暴露给 Agent。不要把含个人账号、生产后台的 Chrome 会话随手授权出去。

### 把 VibeCLI 变成 MCP server

```bash
uv run vibecli mcp serve --transport stdio
uv run vibecli mcp serve --transport http --port 3000
```

HTTP 冒烟：

```bash
curl -sS -X POST http://127.0.0.1:3000 \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Runtime API

内置轻量 HTTP Runtime API，适合外部系统（Web 后端、定时任务、IM 机器人）接入。服务只绑定 `127.0.0.1`，所有请求需要 API Key（`x-api-key` 或 `Authorization: Bearer`）。

```bash
VIBECLI_RUNTIME_API_KEY=dev-key \
uv run vibecli serve --http --port 8080
```

### 端点

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/v1/threads` | 创建线程，返回 `{ "id": "thread_..." }` |
| `POST` | `/v1/threads/{id}/turns` | 提交一轮输入，同步返回最终文本 |
| `GET` | `/v1/threads/{id}/events` | 以 SSE 回放该线程全部事件 |
| `POST` | `/v1/tasks` | 入队后台任务，返回 `{ "id", "status": "queued" }` |
| `GET` | `/v1/tasks` | 列出任务 |
| `GET` | `/v1/tasks/{id}` | 查单个任务 |
| `POST` | `/v1/tasks/{id}/cancel` | 取消任务 |

### curl 示例

```bash
# 创建线程
curl -sS -X POST http://127.0.0.1:8080/v1/threads \
  -H 'x-api-key: dev-key'

# 跑一轮
curl -sS -X POST http://127.0.0.1:8080/v1/threads/<thread_id>/turns \
  -H 'content-type: application/json' \
  -H 'x-api-key: dev-key' \
  -d '{"message":"总结这个项目"}'

# 读事件流
curl -sS http://127.0.0.1:8080/v1/threads/<thread_id>/events \
  -H 'x-api-key: dev-key'

# 后台任务
curl -sS -X POST http://127.0.0.1:8080/v1/tasks \
  -H 'content-type: application/json' \
  -H 'x-api-key: dev-key' \
  -d '{"message":"后台总结这个仓库"}'

curl -sS http://127.0.0.1:8080/v1/tasks -H 'x-api-key: dev-key'
```

### 事件类型

线程事件按写入顺序回放，`data` 是一行 JSON：

| 事件 | 触发时机 |
| --- | --- |
| `thread.created` | 线程创建 |
| `turn.started` | 一轮开始 |
| `message.delta` | 模型输出增量 |
| `tool_call` / `tool_result` | 工具调用与结果 |
| `error` | 出错 |
| `turn.completed` | 一轮结束，带最终文本（含 `done`） |

### 任务队列

后台任务落 SQLite（`~/.vibecli/tasks/tasks.db`），进程重启后仍在。`serve` 默认起 2 个 worker 线程，从队列原子认领任务执行。任务执行需要可用的 LLM Key，缺失时会 fail 并把原因写进任务的 `error` 字段，而不是静默丢弃。

## 图片输入

在 prompt 里用 `@image:` 引用图片：

```text
分析这张截图 @image:./screenshots/page.png
解释这张图 @image:/Users/me/Desktop/diagram.png
看看这个 @image:file:///Users/me/Desktop/diagram.png
参考这个设计 @image:https://example.com/image.png
```

处理规则：

- 本地图片最长边缩到 1568px，转 JPEG（质量 85）后编码成 data URL
- `RGBA` / `LA` 透明图先铺白底再编码，避免模型看到一片黑
- 本地路径必须落在当前工作目录内，越界直接报错
- 远程 URL 原样透传，不代下载
- 一个 prompt 可以混排多段文字和多张图，按出现顺序切分成 `text` / `image_url` parts

## 快照

每次 Agent run 都会尽力建两份快照：

- `pre-turn` — 本轮开始前
- `post-turn` — 本轮结束后（含模型写下的改动）

快照存在 `~/.vibecli/snapshots/<项目路径哈希>/`，不进项目 `.git`，自动跳过 `.git`、`.venv`、`node_modules`、`dist`、`build`、`target`、`__pycache__`。

```text
/snapshot            # 列出最近 20 个（带序号）
/restore 1           # 按序号恢复
/restore pre-turn_20261026...   # 按 id 恢复
/snapshot clean      # 清空快照
```

恢复前会自动先建一份 `pre-restore` 快照 —— 回滚本身也能回滚。模型侧还有一个 `revert_turn` 工具，走同一套逻辑但需要 HITL 确认。

## SDK

不需要 REPL 也能编程接入：

```python
from vibecli.sdk import create_default_engine

engine = create_default_engine(cwd=".")

# 同步
result = engine.ask_complete("解释这个项目")
print(result.text, result.total_tokens, result.turns)

plan_result = engine.plan_complete("先读 README，再总结项目结构")
team_result = engine.team_complete("让多个 Agent 并行检查核心模块")

# 异步 / 流式
async for event in engine.ask("看看 src/vibecli 有多少个模块"):
    if event["type"] == "text_delta":
        print(event["text"], end="")
```

`create_default_engine` 会按标准分层加载配置、装配内置工具 + MCP 工具、拼好 system prompt。想要自定义工具集就自己 `ToolRegistry` + `QueryEngine`，参考 `src/vibecli/sdk.py`。

## 联网工具

- `web_search`：走 DuckDuckGo HTML 端点，返回标题、URL、摘要。不需要 Key，但可能被限流。
- `web_fetch`：抓公开 HTTP/HTTPS 页面并做基础正文提取。会拒绝 `file://`、loopback、私有网段和内网地址，降低 SSRF 风险。

需要登录态、浏览器状态或 JS 渲染的页面，本机工具做不了 —— 用 Chrome DevTools MCP，别硬糊。

## 安全

| 层 | 实现 | 拦什么 |
| --- | --- | --- |
| 路径 | `PathGuard` | 文件工具越出工作目录（`../`、绝对路径逃逸） |
| 命令 | `CommandGuard` | 黑名单子串 + 破坏性命令正则（`sudo`、`rm -rf /`、`mkfs`、`dd if=/dev/zero`、fork bomb、`find /` …） |
| 人 | `HITL` | `bash`、`revert_turn` 等高风险动作要人点头；非 TTY 环境默认拒绝 |
| 事后 | `AuditLog` | 所有非只读工具调用写 `~/.vibecli/audit.jsonl`，`token/key/password/secret/authorization/bearer` 字段自动脱敏为 `***` |

HITL 三档：

- `always` — 每次工具调用都问
- `auto`（默认）— 只问标记了 `requires_approval` 的工具
- `never` — 不问（只建议在容器/沙箱里用）

## 架构

一句话：**事件流的 ReAct 循环坐在工具执行器和 LLM 客户端之间，安全策略包住工具执行，持久化能力（记忆/索引/快照/队列）都挂在循环外面，随时可插拔。**

```text
CLI / REPL / Runtime API / SDK
            │
      QueryEngine  ── PromptAssembler（system prompt + 项目记忆 + skill 索引）
            │
      Agent / PlanExecute / Orchestrator
            │
        query()  ← ReAct 循环，逐事件 yield
        ├── LlmClient（OpenAI-compatible 流式）
        └── ToolExecutor（只读并行 / 写串行）
              ├── ToolRegistry（15 内置 + MCP 动态）
              └── PathGuard / CommandGuard / HITL / AuditLog
```

完整拆解见 [docs/architecture.md](docs/architecture.md)：一次 turn 的生命周期、事件表、Plan 的批次调度、多 Agent 的消息总线、以及每个模块为什么这么切。

## 项目结构

```text
src/vibecli/
  agent/         ReAct 循环、Plan-and-Execute、多 Agent 编排、QueryEngine
  llm/           OpenAI-compatible 流式客户端 + provider 工厂
  tools/         工具基类、注册表、15 个内置工具、执行器
  mcp/           MCP client、server、配置读写（stdio / HTTP）
  lsp/           写文件后的 Python 语法诊断
  plan/          Planner 与任务 DAG 模型
  policy/        PathGuard、CommandGuard、AuditLog
  memory/        SQLite 长期记忆
  prompt/        system prompt 装配
  rag/           SQLite 本地代码索引
  render/        Rich 渲染器与纯文本渲染器
  runtime/       HTTP Runtime API + 持久化任务队列
  skill/         skill 注册表、懒加载注入、状态存储
  snapshot/      pre/post-turn 快照与恢复
  image/         图片输入解析与预处理
  web/           联网搜索与抓取
  entrypoints/   CLI 与 REPL
tests/           97 个用例（配置/策略/工具/ReAct/快照/Runtime API/MCP/CLI）
examples/        配置模板、自定义 skill、prompt 示例
```

## 开发与测试

```bash
uv sync --extra dev

uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev pytest        # 97 passed

uv build
uv run vibecli --help
```

测试不需要联网、不需要 API Key：LLM 边界由一个回放预设事件的 `ScriptedLlm` 替身顶上，`Path.home()` 在 fixture 里重定向到临时目录，所以不会污染真实的 `~/.vibecli`。

常用冒烟：

```bash
uv run vibecli --version
uv run vibecli --help
uv run vibecli doctor --cwd .
uv run vibecli mcp list --cwd .
```

## 和 Java / TypeScript 版本的关系

Python 版覆盖了 Java / TypeScript 版本里公开、开放协议相关的主要 Agent CLI 能力：CLI、REPL、ReAct、Plan-and-Execute、Multi-Agent、Skill、SDK、工具调用、MCP、Runtime API、记忆、快照、联网工具和图片输入。

Java 版本里还有一个私有的微信 iLink 通道。Python 仓库没有内置它，因为它依赖账号、扫码登录和协议凭证 —— 用假实现冒充一个"我接通了"的通道，比不做更糟。

逐项对齐情况见 [docs/parity.md](docs/parity.md)。

## 设计取舍

**为什么用 Python 重写一遍？** 原版是 Java / TypeScript。Python 的生态让「读源码搞懂 Agent 到底怎么跑」这件事的门槛低一个数量级：类型标注够用、asyncio 流式够顺手，而且面试时能当场跑给人看。移植不是翻译，事件模型和工具边界都重新设计过。

**为什么不引入 LangChain / LlamaIndex？** 这一层的价值就在于把循环、工具分发、策略钩子写清楚。套框架等于把要讲的东西藏起来。

**为什么 Runtime API 只绑 127.0.0.1？** 它会给调用方完整的工具执行权（含 shell）。默认回环 + API Key 是「先能跑」和「别裸奔」之间的最小妥协；要对外就把反代和 TLS 那一层加上，那是部署问题不是代码问题。

**为什么快照不做增量？** 全量 copytree 在中小项目里几十毫秒，换来的是恢复时不用做任何一致性推导。增量快照的复杂度应该由真实需求推动，不是由想象力推动。

**为什么本地代码索引是 SQLite 全文 LIKE 而不是向量检索？** 代码搜索里精确符号命中的召回质量比语义相似度稳，而且零依赖、零模型下载。要上向量检索，接口在 `rag/` 里留着。

## Roadmap

- [ ] 会话级 token 预算与上下文压缩（`memory.compression_threshold` 已有配置位，逻辑待接）
- [ ] 快照增量化 + 大仓库下的忽略规则可配置
- [ ] Runtime API 的 SSE 增量订阅（当前是回放）
- [ ] 更多 provider 的原生适配（目前统一走 OpenAI-compatible）

## License

MIT，见 [LICENSE](LICENSE)。
