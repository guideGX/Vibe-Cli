# VibeCLI Python 架构

这份文档回答一个问题：**一轮对话从按下回车到屏幕上出结果，中间到底发生了什么，每一段代码为什么在那里。**

README 讲「有什么、怎么用」，这里讲「怎么连起来的、为什么这么切」。读完应该能自己加一个工具、接一个 provider、或者重写其中一层而不塌。

目录：

1. [分层与依赖方向](#1-分层与依赖方向)
2. [一次 turn 的生命周期](#2-一次-turn-的生命周期)
3. [事件契约](#3-事件契约)
4. [ReAct 循环里的三个坑](#4-react-循环里的三个坑)
5. [工具执行层](#5-工具执行层)
6. [Plan-and-Execute](#6-plan-and-execute)
7. [多 Agent 编排](#7-多-agent-编排)
8. [安全设计](#8-安全设计)
9. [状态与持久化](#9-状态与持久化)
10. [提示词装配](#10-提示词装配)
11. [扩展点](#11-扩展点)
12. [已知边界](#12-已知边界)

---

## 1. 分层与依赖方向

```text
┌──────────────────────────────────────────────────────────────┐
│ 入口层   entrypoints/cli.py · entrypoints/repl.py            │
│          runtime/api.py · sdk.py                             │
└───────────────────────────┬──────────────────────────────────┘
                            │ 只依赖 QueryEngine，不认识循环细节
┌───────────────────────────▼──────────────────────────────────┐
│ 编排层   agent/query_engine.py                               │
│          agent/agent.py（ReAct）                             │
│          agent/plan_execute.py（Plan-and-Execute）           │
│          agent/orchestrator.py（多 Agent）                   │
└───────────────────────────┬──────────────────────────────────┘
                            │ 三种模式共用同一个 query()
┌───────────────────────────▼──────────────────────────────────┐
│ 循环层   agent/query.py  ← 唯一持有「messages + while 循环」  │
└──────┬──────────────────────────────────────┬────────────────┘
       │                                      │
┌──────▼──────────────┐          ┌────────────▼───────────────┐
│ llm/                │          │ tools/                      │
│ OpenAI-compatible   │          │ registry · executor         │
│ 流式客户端           │          │ builtins（15 个）           │
└─────────────────────┘          └────────────┬───────────────┘
                                              │ 每次执行前后
┌─────────────────────────────────────────────▼───────────────┐
│ 横切层   policy/（PathGuard · CommandGuard · AuditLog）      │
│          skill/ · memory/ · rag/ · snapshot/ · image/ · web/ │
│          mcp/（把远端工具塞进 registry）                      │
└──────────────────────────────────────────────────────────────┘
```

三条规则，整个代码库都在守：

1. **依赖只往下走。** 入口层不认识 `query()`，编排层不认识 HTTP，工具不知道谁在调它。
2. **事件是唯一横向语言。** 上层消费 `dict` 事件，不直接碰 LLM 返回对象，也不读工具的返回值。
3. **横切能力不塞进循环。** 循环只有不到 170 行（`agent/query.py`），记忆、快照、索引都是旁挂。

这条边界的收益在测试上直接体现：把 LLM 换成一个回放事件的替身，`query()` 以上的所有逻辑都能离线跑（`tests/test_react_loop.py`）。

---

## 2. 一次 turn 的生命周期

以 REPL 里敲一句 `帮我看下 agent 目录` 为例。

**① 读输入（`entrypoints/repl.py::start_repl`）**

prompt-toolkit 负责输入、补全（21 个 slash command）、历史落 `~/.vibecli/history/prompt_history.txt`。以 `/` 开头走 `_handle_slash`，否则进 agent。

**② 建快照（`agent/agent.py::Agent.run` 第一行）**

```python
snapshot = SnapshotService(self.cwd)
with suppress(Exception):
    snapshot.create("pre-turn")
```

注意 `suppress(Exception)`：快照失败绝不能拖垮对话。这是刻意的 —— 快照是保险，不是前置条件。

**③ 装配消息（`agent/query.py`）**

```python
user_message = _prepend_skill_context(user_message, skill_context_buffer)
messages = [*(history or []), Message(role="user", content=parse_image_references(...))]
```

顺序很重要：先把上一轮 `load_skill` 攒下的内容前置到**用户消息**里，再做 `@image:` 解析。这样 skill 正文不会混进图片 parts，也不会污染历史。

**④ 进循环（`agent/query.py::query`）**

```python
while turn < max_turns:          # 默认 20
```

**⑤ 流式接收（`LlmClient.chat`）**

`llm/openai_compatible.py` 解析 SSE，往外吐 6 种原始事件：`text_delta`、`thinking_delta`、`tool_call_delta`、`usage`、`message_end`、`error`。

`query()` 对 `tool_call_delta` 做**增量拼接**（见第 4 节），其余直接透传给上层。

**⑥ 判断要不要用工具**

```python
if stop_reason != "tool_use" and not tool_calls:
    break
```

两个条件都要满足才退出：既没有 `tool_use` 停止原因，也没有攒出任何完整 tool call。单看其中一个会误判 —— 有的网关不返回 `stop_reason`，有的会在 `end_turn` 后继续吐 tool call。

**⑦ 执行工具（`tools/executor.py`）**

只读且并发安全的先批量并行（信号量 `tools.max_concurrent_read`，默认 4），写操作随后严格串行。每个调用先后经过：参数校验 → HITL 决策 → handler → 审计落盘。

**⑧ 结果回灌**

工具输出以 `role="tool"` 消息追加，`tool_call_id` 对齐。上层同时收到一条 `tool_result` 事件用于渲染。

**⑨ 下一轮**

回到 ⑤，messages 已经带上 assistant 的 tool_calls 和 tool 结果。直到模型不再要工具，或撞到 `max_turns`。

**⑩ 收尾（`agent/agent.py`）**

```python
if event.get("type") == "done":
    self.history = list(event.get("messages") or [])
```

历史只在 `done` 时整体回写，中途出错不留半截。`finally` 里建 `post-turn` 快照 —— 就算循环抛异常，改动也已经被记下来了。

---

## 3. 事件契约

事件是 `dict[str, Any]`，`type` 字段是判别式。三个消费方：REPL 渲染器、Runtime API 的 SSE 写入、SDK 的 `ask_complete`。

| `type` | 关键字段 | 谁产生 | 语义 |
| --- | --- | --- | --- |
| `text_delta` | `text` | LLM → `query()` | 模型输出的一个增量片段 |
| `thinking_delta` | `thinking` | LLM → `query()` | 推理模型的思考增量，只渲染不落历史 |
| `tool_call` | `name`, `input` | `query()` | 参数已拼完、即将执行 |
| `tool_result` | `name`, `result`, `is_error` | `query()` | 工具执行结果（错误也是结果，回灌给模型） |
| `usage` | `usage.input_tokens` / `output_tokens` | LLM | token 计量 |
| `turn_complete` | `turn`, `stop_reason` | `query()` | 一轮模型调用结束（不是整个任务结束） |
| `plan_task_done` | `turns`, `tokens` | `plan_execute.py` | Plan 模式下单个任务完成 |
| `error` | `error` | 任意层 | 终止信号；消费方应立即停止 |
| `done` | `total_turns`, `total_tokens`, `messages` | `query()` / 编排层 | 唯一携带完整历史的终态事件 |

两条约定：

- **`error` 之后不再有事件。** 所有实现都是 `yield error` 然后 `return`。
- **只有 `done` 带 `messages`。** 想续接对话就必须等到它；这是 history 一致性的唯一来源。

Runtime API 把内部事件映射成对外的 SSE 事件名（`message.delta` / `turn.started` / `turn.completed` …），映射点在 `runtime/api.py::_run_turn`。对外不直接暴露内部事件名，是为了以后改内部契约时不至于连累 API 版本。

---

## 4. ReAct 循环里的三个坑

### 4.1 流式 tool call 参数是碎片的

OpenAI 兼容协议里，一个 tool call 的参数会按 `{"index": 0, "function": {"arguments": "{\"pa"}`、`"th\": \"a"`、`".txt\"}"` 这样分片到达，且**只在第一片带 `id` 和 `name`**。

`query.py` 用 `dict[int, dict]` 按 index 归并：

```python
def _merge_tool_delta(tool_states, delta):
    index = int(delta.get("index") or 0)
    state = tool_states.setdefault(index, {...})
    if delta.get("id"):                      # 只覆盖非空
        state["id"] = delta["id"]
    if function.get("arguments"):
        state["function"]["arguments"] += function["arguments"]   # 字符串追加
```

用 `+=` 而不是赋值，是这段代码唯一正确的写法。测试 `test_streaming_tool_arguments_are_merged` 专门喂了三段碎片来钉住它。

### 4.2 `stop_reason` 不可靠，得和 tool_calls 交叉验证

见第 2 节 ⑥。判据是「或」关系的反面：两个都否定才停。

### 4.3 思考内容不进历史

推理模型的 thinking delta 只用于渲染，不进 messages。原因很实际：多数网关在下一轮不接受带 thinking 的历史消息，塞进去会 400。所以 `query.py` 里 thinking 只累加到局部变量，assistant 消息的 `content` 只保留正式文本。

---

## 5. 工具执行层

### 5.1 工具的声明式定义

`tools/base.py` 里 `Tool` 是一个 dataclass，行为由 5 个字段决定：

| 字段 | 作用 |
| --- | --- |
| `is_read_only` | 决定要不要写审计、能不能并行 |
| `is_concurrency_safe` | 与上一项联合决定是否进并行批次 |
| `danger_level` | `safe` / `medium` / `high`，HITL 提示用 |
| `requires_approval` | `auto` 模式下是否必须人工确认 |
| `timeout` | 单次执行超时（`asyncio.wait_for`） |

加工具基本就是填这张表，不用写分发逻辑。

### 5.2 为什么读并行、写串行

```python
if tool and tool.is_read_only and tool.is_concurrency_safe:
    read_calls.append(...)      # 并行，信号量限流
else:
    sequential_calls.append(...)  # 串行，保持声明顺序
```

- 读并行：一次 `grep` + `read_file` + `search_code` 串起来能省掉一半等待。
- 写串行：两个 `write_file` 并发打到同一个文件，谁赢取决于调度，这种不确定性在 agent 里是不可接受的调试地狱。
- **并行结果的顺序由 `asyncio.gather` 保证与调用顺序一致**，所以 messages 里的 tool 结果永远对得上 tool_call 的 id，与完成时间无关。

### 5.3 HITL 决策矩阵

`_approval_decision` 是纯函数式的四分支：

| `hitl_mode` | `requires_approval` | 有无 callback | 结果 |
| --- | --- | --- | --- |
| `never` | 任意 | 任意 | `approve` |
| `auto` | `False` | 任意 | `approve` |
| `auto` | `True` | 有 | 问 callback |
| `always` | 任意 | 有 | 问 callback |
| 任意（除 `never`） | 任意 | 无 | `deny` |

最后一行是关键：**没有 callback 就意味着没人能批准，所以默认拒绝**。非 TTY 环境（管道、CI）走这一条，不会因为没人应答而挂住。

### 5.4 工具异常必须回到模型

```python
except Exception as exc:
    return ToolResult(content=f'Tool "{name}" execution error: {exc}', is_error=True)
```

工具炸了不能抛穿循环。模型看到错误文本才能自我纠正 —— 这是 ReAct 相对一次性生成的核心优势，把异常吞掉或者中断对话都是浪费。审计里同时记一条 `outcome="error"`。

---

## 6. Plan-and-Execute

### 6.1 结构

```text
用户任务
   │
   ▼
Planner（独立 LLM 调用，返回 JSON）
   │  ExecutionPlan{ goal, tasks: {id: Task} }
   ▼
while 有可执行任务:
    executable = 依赖已全部 COMPLETED 的 PENDING 任务（按拓扑序）
    if len == 1: 串行执行
    else:        asyncio.gather 并行整批
   │
   ▼
汇总（completed / failed / stalled 三种结局）
```

`ExecutionPlan.execution_order()` 给拓扑序，`executable_tasks()` 给当前依赖已满足的集合，两者取交并按拓扑序排 —— 保证同一批里也是确定顺序，重跑结果可复现。

### 6.2 每个任务是一个完整 ReAct 循环

`_execute_task` 内部又调 `query()`，`max_turns=8`（比顶层 20 小），任务是收敛的、有界的。任务上下文里带**已完成依赖的产出预览**：

```text
Goal: ...
Current task [t2]: 汇总三个模块的职责
Completed dependency results:
- [t1] 读取 agent 目录: ...
```

这就是 DAG 的价值：后续任务不是凭空推理，而是拿到前序任务的真实产出。

### 6.3 失败语义

- 单任务失败 → 标记 `FAILED`，**不影响**无关分支继续跑（依赖它的任务会因为依赖未完成而停在 `PENDING`）
- 全部完成 → `COMPLETED`
- 有失败 → `FAILED`，输出"部分完成"
- 依赖链断裂导致没有可执行任务但也没结束 → `stalled`，明确说出来而不是静默结束

「stalled 要显式报」是我特意加的：静默退出会让人以为任务做完了。

---

## 7. 多 Agent 编排

### 7.1 角色与消息

三个角色，同一个 `SubAgent` 类，靠 `role` 切换 system prompt：

| 角色 | 有工具 | 输出契约 |
| --- | --- | --- |
| Planner | 否 | 只返回 JSON：`steps[{id, description, type, dependencies}]` |
| Worker | 是 | 执行单个 step，返回具体产出 |
| Reviewer | 否 | 只返回 JSON：`{"approved": bool, "summary": "...", "issues": []}` |

消息对象 `AgentMessage{from_agent, from_role, content, type}`，类型有 `TASK` / `RESULT` / `FEEDBACK` / `APPROVAL` / `REJECTION` / `ERROR`。这让「谁跟谁说了什么」在日志里是明文，不用猜。

### 7.2 worker pool

```python
worker_queue = asyncio.Queue()
for worker in self.workers:        # 默认 2 个
    worker_queue.put_nowait(worker)
```

每个 step 借一个 worker，跑完 `clear_history()` 再还回队列。**借还必须清历史** —— worker 是多任务复用的，带上一轮的上下文会让它把两个任务搞混。这是这类编排最容易出的 bug。

### 7.3 review 驳回与有限重试

```text
worker 产出 → reviewer 审 → approved?
                                ├─ 是 → step COMPLETED
                                └─ 否 → 把 issues 塞回 worker 重试
                                        （每步最多 2 次，超了记 FAILED）
```

重试不是无脑循环：每次重试都把 reviewer 的 `issues` 显式拼进上下文，让 worker 知道该改什么。上限 `max_retries_per_step = 2`，防止两个模型互相抬杠烧钱。

### 7.4 为什么 reviewer 每次新建

`reviewer-{step.id}` 每个 step 一个新实例，审完即弃。理由同上：审查要独立视角，看过上一步的审查记录会让它产生「上一版过了这版应该也行」的偏置。

---

## 8. 安全设计

四层，从内到外，顺序不是随便排的：

```text
      用户/模型
         │
         ▼
① PathGuard   ── handler 内部，管「能碰哪个文件」
         │
         ▼
② CommandGuard ── bash handler 内部，管「能跑什么命令」
         │
         ▼
③ HITL        ── executor 里，管「要不要人点头」
         │
         ▼
④ AuditLog    ── executor 里，管「事后能不能查」
```

### 8.1 为什么 PathGuard 在 handler 里，不在 executor 里

因为「路径」的含义是工具私有的。`read_file` 的 `path`、`glob` 的 `pattern`、`grep` 的 `path` 语义都不同，executor 层没法统一校验。所以每个 handler 走 `_resolve_path(context, value)`：

```python
if context.config.policy.path_guard_enabled:
    return PathGuard(context.cwd).validate(value)
```

`PathGuard.validate` 做 `resolve()` 后再 `relative_to(root)` —— **必须先 resolve**，否则 `link/../../../etc/passwd` 这种符号链接加相对路径的组合能绕过。

### 8.2 为什么命令要黑名单 + 正则双保险

- 黑名单（`sudo`、`mkfs`、`curl | sh`…）可配置，来自 `policy.command_blacklist`，用户能加自己公司禁的命令。
- 正则管形态：`rm -rf /` 有一百种写法（`rm  -rf   /`、`rm -r -f /`），纯字符串匹配靠不住，所以先做 `" ".join(split())` 归一化，再过正则。

两者都不完备，所以 HITL 还在后面兜。安全策略的定位是「提高作恶成本」，不是「证明安全」—— 把这话说清楚比假装完备更专业。

### 8.3 审计脱敏

```python
SENSITIVE_KEYS = ("token", "key", "password", "secret", "authorization", "bearer")
```

递归遍历输入 dict（含嵌套和数组），键名命中就替换成 `***`。审计日志的价值在于可查，但一份带着 API Key 的日志本身就是事故。

### 8.4 Runtime API 的边界

- 只绑 `127.0.0.1`，不监听 `0.0.0.0`
- 每个请求校验 `x-api-key` 或 `Authorization: Bearer`，不匹配直接 401，不进业务分支
- 缺 LLM Key 时 `turn` 返回 500 并说清原因，而不是静默返回空字符串

---

## 9. 状态与持久化

| 存储 | 写入者 | 时机 | 丢了会怎样 |
| --- | --- | --- | --- |
| `~/.vibecli/config.json` | 用户 | 手动 | 回落到默认配置，可用 |
| `~/.vibecli/memory.db` | `MemoryManager` | `/save`、`save_memory` | 没有长期记忆，对话仍正常 |
| `~/.vibecli/audit.jsonl` | `AuditLog` | 每次非只读工具执行 | 无法事后追溯，这是最不该丢的 |
| `~/.vibecli/snapshots/` | `SnapshotService` | 每轮前后 | 不能回滚，但代码本身还在 |
| `~/.vibecli/tasks/tasks.db` | `DurableTaskManager` | 入队/认领/完成 | 后台任务丢失 |
| `~/.vibecli/runtime/runtime.db` | `RuntimeApiServer` | 线程与事件写入 | 事件流不可回放 |
| `.vibecli/code_index.sqlite3` | `CodeIndex` | `/index` | `/search` 无结果，重建即可 |
| `~/.vibecli/skills.json` | `SkillStateStore` | `/skill on\|off` | skill 全部回到默认启用 |

三个设计约束：

1. **全部在 `~` 下或用项目内 `.vibecli/`。** 唯一写进项目目录的是代码索引（可随时删）和 `mcp.json`/`skills/`（属于项目配置）。
2. **快照按项目路径哈希分目录。** `sha256(project_root)[:16]`，同一个 `~/.vibecli` 服务多个项目不串。
3. **SQLite 而不是 JSON 文件存记忆/任务。** 原子认领需要 `UPDATE ... WHERE status='queued'` 这种语句，JSON 文件做不到并发安全。

---

## 10. 提示词装配

`PromptAssembler.build()` 输出 6 段，顺序固定：

```text
1. 身份      You are VibeCLI, a powerful AI coding assistant...
2. 环境      当前时间 / 工作目录 / 模型 / provider
3. 工具清单  Available tools: read_file, write_file, ...
4. 行为准则  5 条（简洁、先查证、用 write_file、保留 URL、只在有风险时提问）
5. 项目记忆  VIBE.md / .vibecli/VIBE.md / *.local.md + 长期记忆 top 8
6. skill 索引  Name: description 一行一个（不塞正文）
```

两个刻意的取舍：

**为什么工具清单要显式列名字？** 工具的 JSON schema 已经通过 `tools` 参数传了，但两者在模型注意力里的权重不一样：schema 是结构化约束，提示词里的清单是「你现在能做什么」的自然语言提示。列一遍几乎没有成本，而漏一个工具的名字，模型就可能去猜一个不存在的名字，白烧一轮。

**为什么 skill 只给索引，正文靠 `load_skill` 懒加载？** 一个 skill 正文几千 token，塞满 20 个就把上下文吃光了。索引一行一个，模型判断需要时再 `load_skill`，正文进 `SkillContextBuffer`（最多缓存 3 个），在下一次 `query()` 开始时一次性注入用户消息 —— 用完即清，不会在后续轮次里反复烧 token。

项目记忆有 8000 字符上限、单个文件 4000 上限。有上限是为了让「读不到」变成可预期的行为，而不是等模型因上下文溢出报错。

---

## 11. 扩展点

### 加一个工具

```python
# src/vibecli/tools/builtins.py
Tool(
    name="count_lines",
    description="Count lines in a workspace file.",
    parameters=object_schema({"path": {"type": "string"}}, ["path"]),
    required_keys=["path"],
    handler=count_lines,          # async def handler(payload, context) -> ToolResult
    is_read_only=True,            # 只读 → 自动进并行批次
)
```

然后在 `tests/test_tools.py::EXPECTED_TOOLS` 里加名字，测试会帮你守住注册表。

### 接一个 provider

`llm/factory.py::create_llm_client` 里加 base_url 映射即可，只要对端说 OpenAI 兼容协议 —— 请求体、流式解析、tool call 合并都能复用：

```python
PROVIDER_BASE_URLS = {"yourprovider": "https://api.yourprovider.com/v1", ...}
```

非兼容协议（如 Anthropic 原生格式）需要单独实现 `LlmClient` 协议里的 `chat()`，只要吐同样 6 种事件，上层无感。

### 加一个 skill

`<project>/.vibecli/skills/<name>/SKILL.md`，带 frontmatter：

```markdown
---
name: release-notes
description: 把 git log 整理成发布说明
---

正文（模型调用 load_skill 后才会看到）
```

不用改代码，`SkillRegistry` 启动时扫目录。完整示例见 `examples/skills/release-notes/SKILL.md`。

### 加一个 API 路由

`runtime/api.py::_handle` 是显式 `if/elif` 分派，加一个分支就行。分派顺序无副作用，不用考虑路由表冲突。

---

## 12. 已知边界

诚实列出来，比等别人发现好：

| 边界 | 现状 | 如果要补 |
| --- | --- | --- |
| 上下文压缩 | 配置项 `memory.compression_threshold` 在，压缩逻辑未接 | 在 `query()` 每轮前判断 token 占比，超阈值时摘要早期消息 |
| 快照增量 | 每轮全量 copytree | 大仓库下换成 rsync 式差量或 git stash 式方案 |
| SSE 实时订阅 | `/events` 是回放，不是长连接推送 | 加 `threading.Event` + 游标即可 |
| 微信 iLink | 不实现（私有协议） | 不会用假实现糊 —— 见 parity.md |
| 向量检索 | 只有 SQLite LIKE 全文索引 | `rag/` 接口留着，换后端不影响调用方 |
| Windows 信号处理 | Ctrl+C 走 asyncio 默认行为，任务可能不优雅退出 | 加 `signal` 处理 + 任务取消传播 |

---

相关文档：[README](../README.md) · [对齐矩阵](parity.md) · [变更日志](../CHANGELOG.md)
