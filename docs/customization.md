# Customization

Everything below lives in your side or in the examples. You never edit `core/` to configure your own setup.

## Preferences

`<side>/rules/preferences.md` holds how replies are written: language, length, status format, git text. Pick a starting point at install time:

```bash
bin/brain-init ~/brain/work --harness claude-code --preferences opinionated
```

- `opinionated`: answer first, 5-line replies, 1-3 line status, end-user language, no AI attribution in git text.
- `minimal`: three placeholders (reply language, length, commit language).

Both are copied once into your side. Edit the copy. Replace every `{placeholder}`.

## Standards packs

A standards pack is your code conventions: always-loaded rules plus a reference loaded on demand by a skill. The example is `examples/standards/layered-ts-go`.

```bash
bin/brain-init ~/brain/work --harness claude-code --standards layered-ts-go
```

It installs to `<side>/standards` and a `code-standards` skill. Use `--standards none` for no pack. To write your own, copy the folder, keep the shape (`rules.md`, `reference.md`, `skills/<name>/SKILL.md`) and change the content. The core guardrails say a deviation needs a stated reason; the pack defines what the standard is.

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

## Side config and tiers

`<side>/brain-sync.json` (generated from `examples/sides/<harness>.json`) controls the rendered agents: which to skip, the tier of each (judge, worker, mechanical), model aliases, and extra agents. After editing it, re-run `bin/brain-init` for the same side. Keys marked UNVERIFIED in [the Claude Code guide](harness/claude-code.md) may be ignored by your Claude Code version.

## Adding an agent

1. Create `core/agents/<name>.md` with frontmatter `name` and `description`, then the prompt. Use `{{SIDE}}` and `{{CORE}}` for paths. No vendor, model or language names in core.
2. Add it to `agents` in your side config with a tier or model.
3. Re-run `bin/brain-init <side> --harness <harness>`, then `--verify`.

For an agent that is only yours, put it under `extra_agents` in the side config with a `body_from` file instead of touching core.

## Adding a skill

1. Create `core/skills/<name>/SKILL.md` with frontmatter `name` and `description` (when to use it). Write the body as instructions for a worker, not the maestro.
2. Re-run `bin/brain-init`. Skills are copied into the harness skills directory and tracked by the manifest.

Third-party skills: see [skills.md](skills.md).

## Word budgets

The always-loaded text costs attention on every request, so it has a ceiling.

| Target | Budget (words) |
|---|---|
| Claude Code always-loaded (`<side>/.generated/CLAUDE.md`) | 2500 |
| Single-file `AGENTS.md` | 4000 |

The budgets apply to the defaults. Adding a standards pack and the opinionated preferences brings Claude Code to about 2756 words, over the budget on purpose: the conventions you added are yours to weigh. Check any time:

```bash
wc -w ~/brain/work/.generated/CLAUDE.md
```

If you add rules and the count climbs, move situational ones into a skill or an agent file.
