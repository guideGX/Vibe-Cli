# Prompt recipes

Prompts that fit the tool set this CLI actually ships. The pattern in all of them: **say what
"done" looks like, and let the agent choose tools** — do not script the tool sequence yourself.

## Repository comprehension

```text
通读 src/vibecli，用 10 句话说明：每个子包负责什么、谁调用谁、哪一层最容易出 bug。
先 glob 出文件清单，再挑 5 个最关键的文件读，不要逐个读。
```

Why it works: gives a budget (10 句), a decision criterion (最关键), and a constraint (不要逐个读)
that keeps the loop from burning turns on a 50-file directory.

## Change with verification

```text
把 tools/executor.py 里 HITL 拒绝的提示语改成 denied。
改完 grep 一遍 "deny" 确认没有别处依赖旧措辞，再跑 pytest 看有没有挂。
```

Why it works: names the file, states the acceptance check (grep), and asks for the test run in the
same breath. The agent has `write_file`, `grep`, and `bash` — this is a three-tool task, not a
research project.

## Debug from a symptom

```text
vibecli doctor 输出里 api_key 是 missing，但我的 .env 里写了 DEEPSEEK_API_KEY。
按配置加载顺序排查，从最后一层往前找，告诉我值在哪一层被覆盖了。
```

Why it works: supplies the observation, supplies the mechanism (加载顺序), and forbids random
poking by naming a direction (从最后一层往前). The config chapter in the README is the map it
will use.

## Review a diff before committing

```text
看 git diff，只报三类问题：会让测试挂的、会让行为悄悄变的、和这次需求无关的改动。
没有问题就直说没问题，别凑数。
```

Why it works: bounds the output taxonomy so it does not dump a style essay, and explicitly
authorizes "no findings" — otherwise reviewers of all species invent findings.

## Plan mode for multi-file work

```text
/plan 把 tools/builtins.py 拆成 read/write/search 三个模块，保持注册表里的 15 个工具名不变，
拆完跑 ruff 和 pytest。
```

Why it works: Plan-and-Execute is for tasks with real dependency structure. "Keep the 15 tool
names stable" is the invariant that makes each subtask verifiable, and it is exactly the kind of
constraint a Planner can propagate into every task's context.

## Multi-agent for independent sweeps

```text
/team 安排三个 worker 分别审查 policy/、runtime/、mcp/ 的错误处理，最后合并成一份按严重程度排序的清单。
```

Why it works: three genuinely independent directories, one merge step. Do not use `/team` for
tasks where each step needs the previous step's output — that is a plan, not a team.

## Things that do not work well

| Prompt | Why it struggles |
| --- | --- |
| 「优化这个项目」 | No acceptance criterion; the agent will pick something arbitrary and stop. |
| 「把所有文件都读一遍」 | Burns the context window; use `grep` / `search_code` with a target instead. |
| 「你觉得哪里有问题就改」 | Combines open-ended search with unsupervised writes. Ask for a report first. |
| Long pasted logs without a question | The tool loop cannot act on it; say what to do with the log. |
