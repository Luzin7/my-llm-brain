# Claude Code

Tested with Claude Code 2.1.330. Full adapter notes: [adapters/claude-code/notes.md](../../adapters/claude-code/notes.md).

## Setup

Follow the Claude Code steps of [INSTALL.md](../../INSTALL.md) (or paste the README prompt). It does this:

- Creates the side from `templates/side/` if it is absent.
- Adds one marked block to `<config>/CLAUDE.md` (paths line plus four `@` imports: `dist/claude-code/BRAIN.md`, the side's `rules/side.md`, `rules/preferences.md` and `memory/MEMORY.md`), after a `.bak-<timestamp>` backup. `<config>` is `CLAUDE_CONFIG_DIR`, default `~/.claude`.
- Sets `autoMemoryDirectory` in `<config>/settings.json` to `<side>/memory` only if you have no `settings.json`; with one, it tells you to merge the key yourself.
- Registers the local marketplace and installs the `brain` plugin (12 agents, `task-board` skill, read in place from the clone) and, with Python available, `brain-guards` (L3).

The main session is the maestro; its prompt is `core/maestro/maestro.md`, built into `BRAIN.md`. It is not installed as a subagent. Updating is `git pull`; restart the session or run `/reload-plugins`.

## Hooks (L3)

| Hook | Event | Effect |
|---|---|---|
| `maestro-guard` | PreToolUse, all tools | Main session may write only under the `.paths` directories (your side's memory, tasks, specs), Grep only under `.grep-paths`, no `mcp__*` tools, Bash limited to read-only git and a few read commands |
| `subagent-cap` | PreToolUse, matcher `Agent\|Task` | Blocks dispatch number cap+1 per session (exit 2). Resuming an existing worker does not count |
| `context-guard` | UserPromptSubmit | Adds a nudge to start a fresh session past a token threshold |

Facts worth knowing:

- Hooks also fire inside subagents. Only there the input carries `agent_id`, so the guards allow any call that has it and the cap counts only calls without it.
- Settings: `SUBAGENT_CAP` (default 25), `CONTEXT_GUARD_TOKENS` (default 100000). Invalid values fall back to the default.
- Fail open: bad input, a missing session id or an unwritable state directory allows the call. Only a clean exit 2 blocks.
- To switch the guard off, create `<config>/maestro-guard.off`.
- Each hook entry has `timeout: 10`. The cap matches the dispatch tool as `Agent|Task` because the tool name has changed between versions; re-check it when you upgrade Claude Code.
- Hooks run in exec form (no shell): the interpreter is the plugin option `python`, so a path with spaces or quotes is safe.
- On a version whose subagent hook input lacks `agent_id`, workers look like the main session and the guard would block them. The Verify check below catches it.

## UNVERIFIED frontmatter keys

`tools/dist.config.json` emits `autoCompactWindow`, `omitClaudeMd` and `effort` in agent frontmatter. They are not confirmed against the docs for the tested version, and an unknown key may be ignored silently. Check with `claude agents` or by dispatching one agent, and remove from `tools/dist.config.json` (and rebuild) any key that has no effect.

## Verify

Files first: run the Claude Code verify block of INSTALL.md and paste its output. Then, on the real binary:

- [ ] `claude plugin list` shows `brain` and, if installed, `brain-guards`, both enabled.
- [ ] `/memory` shows 4 imports (BRAIN.md, side.md, preferences.md, MEMORY.md).
- [ ] Dispatch `brain:reviewer` on a small diff: it answers APPROVED or REJECTED with findings.
- [ ] A new session shows your memory index (ask: "which notes are in memory?").
- [ ] A session start line says `brain-guards active (python X.Y)`.
- [ ] At L3, ask the main session to edit a file outside the side: it is blocked with the guard message and dispatches a worker instead.
- [ ] At L3, start with `SUBAGENT_CAP=1 claude` and ask for two dispatches: the cap fires on the second.
- [ ] At L3, dispatch a worker and have it Write a file outside the side: it succeeds (confirms `agent_id` reaches the hook).
- [ ] Note which of `autoCompactWindow`, `omitClaudeMd`, `effort` your version honors.
