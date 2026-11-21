# Customization

Everything below lives in your side or in the examples, except tiers and agents (see below). You never edit `core/` to configure your own setup.

## Preferences

`<side>/rules/preferences.md` holds how replies are written: language, length, status format, git text. Pick a starting point from `examples/preferences/` and copy it over your side's file:

```bash
cp examples/preferences/opinionated.md ~/my-brain/rules/preferences.md
```

- `opinionated`: answer first, 5-line replies, 1-3 line status, end-user language, no AI attribution in git text.
- `minimal`: three placeholders (reply language, length, commit language).

Edit the copy. Replace every `{placeholder}`. The install never rewrites this file.

## Standards packs

A standards pack is your code conventions: always-loaded rules plus a reference loaded on demand by a skill. The example is `examples/standards/layered-ts-go`.

Copy the pack by hand:

```bash
mkdir -p ~/my-brain/standards
cp examples/standards/layered-ts-go/reference.md ~/my-brain/standards/
cat examples/standards/layered-ts-go/rules.md >> ~/my-brain/rules/side.md
```

Then copy `skills/code-standards/` into your harness's skills directory (Claude Code: `<config>/skills/`). To write your own, copy the folder, keep the shape (`rules.md`, `reference.md`, `skills/<name>/SKILL.md`) and change the content. The core guardrails say a deviation needs a stated reason; the pack defines what the standard is.

## Side rules

`<side>/rules/side.md` is the place for what is true only for you:

- **Scope**: what the agents work on and what they must not touch.
- **Closed topics**: decisions already made, so agents do not reopen them without new evidence.
- **Approvals table**: what runs without asking and what needs your ok.
- **Asking**: the format of a question.
- **Communication**: where reports go and how long they are.

Example approvals table:

| Action | Rule |
|---|---|
| Read-only checks, local edits, tests | do |
| Push a branch, open a pull request | do |
| Merge, deploy, delete data, spend money, message other people | ask |

Agents ask only for rows marked ask and for real decisions. Write the rule once, here; notes in memory hold facts, not a second wording.

## Tiers and models

Agent models, tiers and the maestro agent are inputs of `tools/dist.config.json`. They are applied when `dist/` is built, so changing them is a contributor step: edit the file, run `python3 tools/build-dist`, commit `dist/`. After a `git pull` that changes `dist/`, run the update step of [INSTALL.md](../INSTALL.md). Keys marked UNVERIFIED in [the Claude Code guide](harness/claude-code.md) may be ignored by your Claude Code version.

## Adding an agent

1. Create `core/agents/<name>.md` with frontmatter `name` and `description`, then the prompt. Use `{{SIDE}}` and `{{CORE}}` for paths. No vendor, model or language names in core.
2. Add it to `agents` in `tools/dist.config.json` with a tier or model.
3. Run `python3 tools/build-dist`, then `python3 tools/build-dist --check`, then the update step of [INSTALL.md](../INSTALL.md).

An agent that is only yours belongs in your own harness agents directory, not in core.

## Adding a skill

1. Create `core/skills/<name>/SKILL.md` with frontmatter `name` and `description` (when to use it). Write the body as instructions for a worker, not the maestro.
2. Run `python3 tools/build-dist` and update the install. Skills are copied only for Codex and opencode; Claude Code reads them from the plugin.

Third-party skills: see [skills.md](skills.md).

## Word budgets

The always-loaded text costs attention on every request, so it has a ceiling.

| Target | Budget (words) |
|---|---|
| Claude Code always-loaded (`dist/claude-code/BRAIN.md` plus your side rules and memory index) | 2500 |
| Single-file `AGENTS.md` | 4000 |

The budgets apply to the defaults. Adding a standards pack and the opinionated preferences brings Claude Code to about 2756 words, over the budget on purpose: the conventions you added are yours to weigh. Check any time:

```bash
cat dist/claude-code/BRAIN.md ~/my-brain/rules/*.md ~/my-brain/memory/MEMORY.md | wc -w
```

If you add rules and the count climbs, move situational ones into a skill or an agent file.
