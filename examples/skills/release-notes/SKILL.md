---
name: release-notes
description: Turn a range of git commits into grouped, user-facing release notes.
version: 1.0.0
tags: [release, git, writing]
---

# Release notes

Produce release notes that a user of the library can read without opening the diff.

## Steps

1. Read the commit list for the requested range. If the user did not give a range, use the last
   20 commits on the current branch.
2. Drop noise: merge commits, version bumps, formatting-only changes, revert-of-revert.
3. Group what remains into exactly these sections, omitting any that end up empty:
   - **Added** — new capability
   - **Changed** — behaviour change users can notice
   - **Fixed** — bug fixes, with the symptom described
   - **Breaking** — anything requiring an action from the user
4. Write one line per item, past tense, no commit hashes, no author names.
5. If a change is breaking, add one sentence on what the user must do.

## Rules

- Never invent an item. If a commit's intent is unclear from its message, read the diff before
  writing about it.
- Never describe internal refactors as fixes; put them under Changed or leave them out.
- Keep the whole output under 40 lines unless the user asks for detail.
