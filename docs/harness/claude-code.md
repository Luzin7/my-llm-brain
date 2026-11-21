# Claude Code

Tested with Claude Code 2.1.330. Full adapter notes: [adapters/claude-code/notes.md](../../adapters/claude-code/notes.md).

## Setup

```bash
bin/brain-init ~/brain/work --harness claude-code --level 2
```

Add `--level 3` for hooks, `--config-dir <path>` for a config directory other than `~/.claude` (also read from `CLAUDE_CONFIG_DIR`), `--dry-run` to preview, `--no-modify-config` to write only the side and rendered files.

What it does:

- Renders the rules into `<side>/.generated/CLAUDE.md` and adds one `@<side>/.generated/CLAUDE.md` line to `<config>/CLAUDE.md` (created, or appended once with a timestamped backup).
- Writes the 12 agents to `<config>/agents/` and the `task-board` skill to `<config>/skills/`.
- Sets `autoMemoryDirectory` in `<config>/settings.json` to `<side>/memory` only if it is unset; otherwise it warns and keeps yours.
- At L3, merges the hook entries that are absent (backup, atomic write) and writes `<config>/maestro-guard.paths` and `maestro-guard.grep-paths`.

The main session is the maestro; its prompt is `core/maestro/maestro.md`, loaded through the rendered rules. It is not installed as a subagent.

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
- Each hook command is `test ! -f <script> || python3 <script>`: if the core is moved or deleted the hook is skipped instead of blocking every call. `--verify` reports the dead path.
- A core path containing `"`, `$` or a backtick breaks the hook command. Clone the repo to a plain path.
- On a version whose subagent hook input lacks `agent_id`, workers look like the main session and the guard would block them. The Verify check below catches it.

## UNVERIFIED frontmatter keys

The example side config emits `autoCompactWindow`, `omitClaudeMd` and `effort` in agent frontmatter. They are not confirmed against the docs for the tested version, and an unknown key may be ignored silently. Check with `claude agents` or by dispatching one agent, and delete from your side config any key that has no effect.

## Verify

Run each and tick it off.

- [ ] `bin/brain-init ~/brain/work --verify` prints `ok: claude-code level N` and exits 0.
- [ ] `wc -w ~/brain/work/.generated/CLAUDE.md` is at most 2500.
- [ ] `claude agents` lists the 12 agents.
- [ ] A new `claude` session in a project shows your memory index (ask: "which notes are in memory?").
- [ ] At L3, ask the main session to edit a file outside the side: it is blocked with the guard message and dispatches a worker instead.
- [ ] At L3, start with `SUBAGENT_CAP=1 claude` and ask for two dispatches: the cap fires on the second dispatch with the cap message.
- [ ] At L3, dispatch a worker and have it Write a file outside the side: it succeeds (confirms `agent_id` reaches the hook).
- [ ] Moving the checkout makes `--verify` exit 1 and name the dead hook path.
- [ ] Note which of `autoCompactWindow`, `omitClaudeMd`, `effort` your version honors.
