# Codex

Instruction file, custom agents and one skill, all copied by [INSTALL.md](../../INSTALL.md). Codex has no import syntax and no agents inside plugins, so unlike Claude Code these are copies: the Codex steps record the clone's `git rev-parse --short HEAD` in the paths line, and verify fails when the clone has moved on (run the update step).

## Setup

Follow the Codex steps of INSTALL.md (or paste the README prompt). It does this:

- Creates the side from `templates/side/` if it is absent.
- Adds one marked block to `$CODEX_HOME/AGENTS.md` (default `~/.codex/AGENTS.md`), after a `.bak-<timestamp>` backup: the paths line (with `rev`), `dist/codex/AGENTS.block.md` and a line telling the agent to read `<side>/memory/MEMORY.md` at session start.
- Copies the 12 `brain-*.toml` agents to `$CODEX_HOME/agents/`, skipping any same-name file it did not generate.
- Copies the `task-board` skill to `~/.agents/skills/task-board/`. That user-level skills path is UNVERIFIED for your Codex version: if the skill is not listed, move the copy to `$CODEX_HOME/skills/`.
- Never edits `config.toml`.

Update: `git pull`, then rerun the Codex install blocks and the verify blocks.

## What you get

Text rules, 12 role agents with their own instructions (and reasoning effort), a fresh-context reviewer and the task-board skill. There is no orchestrate-only enforcement, no fan-out cap and no context nudge: those need hooks Codex does not offer here.

## Verify

Files first: run the Codex verify block of INSTALL.md and paste its output. Then, on the real binary:

- [ ] Ask "what are the my-llm-brain paths": the answer quotes the paths line with the current `rev`.
- [ ] `/agents` lists the `brain-*` roles.
- [ ] The `task-board` skill is listed (UNVERIFIED path, see Setup).
- [ ] Spawn `brain-reviewer` on a small diff: it answers APPROVED or REJECTED, and it does not see the parent conversation.
