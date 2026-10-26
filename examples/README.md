# VibeCLI examples

Copy-paste starting points. Nothing here is loaded automatically — that is the point: each
example shows where a file has to live for VibeCLI to pick it up.

| Path | Copy to | Purpose |
| --- | --- | --- |
| `config/project-config.json` | `<project>/.vibecli/config.json` | Project-level config with a tight safety posture |
| `skills/release-notes/SKILL.md` | `<project>/.vibecli/skills/release-notes/SKILL.md` | Custom skill the agent loads on demand |
| `prompts.md` | — | Prompt recipes that work well with the current tool set |

## Try the skill

```bash
mkdir -p .vibecli/skills/release-notes
cp examples/skills/release-notes/SKILL.md .vibecli/skills/release-notes/

uv run vibecli
# then inside the REPL:
/skill                     # release-notes should be listed
/skill show release-notes
把最近 10 个 commit 整理成发布说明   # the agent calls load_skill on its own
```

## Try the config

```bash
mkdir -p .vibecli
cp examples/config/project-config.json .vibecli/config.json
uv run vibecli doctor --cwd .
```

Then verify from inside the REPL with `/policy` and `/config`.

### Two things to know before you edit it

**Lists replace, they do not append.** A `command_blacklist` in project config overwrites the
default list entirely. The example file copies every default entry and then adds
`git push --force` — start from the defaults, do not write a three-item list and assume the other
eight still apply.

**The example sets `hitl_mode` to `always`.** That means every tool call waits for a yes. It is
the right default when you are first pointing an agent at an unfamiliar repo, and the wrong one
for scripted runs — use `never` only inside a container or a throwaway checkout.
