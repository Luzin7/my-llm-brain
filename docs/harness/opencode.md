# opencode

Tested with opencode 2.3.2. Full adapter notes: [adapters/opencode/notes.md](../../adapters/opencode/notes.md). Real-binary checks are yours to run; the checklist below is how.

## Setup

Follow the opencode steps of [INSTALL.md](../../INSTALL.md) (POSIX blocks; on Windows run them in WSL). It does this:

- Copies the 13 agents (the `maestro` primary agent plus 12 workers) from `dist/opencode/agents/` to `<config>/agents/`, skipping any same-name file it did not generate.
- Creates an empty `<config>/AGENTS.md` if absent, so opencode does not fall back to `~/.claude/CLAUDE.md`.
- Creates `<config>/opencode.json` with `default_agent`, `instructions` (the built `BRAIN.md`, the side rules and the memory index) and `skills.paths`, only if neither `opencode.json` nor `opencode.jsonc` exists. Otherwise it prints the entries and you merge them behind a backup.
- The `maestro` agent has `edit` and `bash` permission denied.

`<config>` is `$XDG_CONFIG_HOME/opencode`, default `~/.config/opencode`.

## Plugins (L3)

| Plugin | Effect |
|---|---|
| `subagent-cap` | Throws `FanOutCapReachedError` before dispatch number cap+1 for a session. Resuming a worker is allowed |
| `context-guard` | Adds a system notice when the context passes a token threshold |

Settings: `SUBAGENT_CAP` (default 25), `CONTEXT_GUARD_TOKENS` (default 100000). Both plugins fail open and log a warning.

The plugin API (`ctx.tool.hook("execute.before")`, `ctx.session.hook("context")`) was checked against the 2.3.2 binary; the older `@opencode-ai/plugin` package types a different API. Add the L3 plugins by hand: append `file://<clone>/adapters/opencode/plugins/subagent-cap` and `.../context-guard` to the `plugin` array. Plugin loading and the shape of `ctx.session.context` messages are UNVERIFIED on your install until you run the checklist.

Run the plugin tests (quote the glob; `node --test plugins/` fails on recent Node):

```bash
cd adapters/opencode && node --test 'plugins/*.test.mjs'
```

## Verify

Files first: run the opencode verify block of INSTALL.md and paste its output. Then, on the real binary:

- [ ] `opencode debug agents` lists `maestro` plus the 12 workers.
- [ ] `opencode debug config` shows `default_agent`, the four `instructions` and `skills.paths` (the `skills.paths` key shape is UNVERIFIED: if it is missing, fix it per the opencode docs).
- [ ] `opencode` starts with `maestro` as the main agent.
- [ ] Plugin loading (UNVERIFIED): `/plugins` lists `subagent-cap` and `context-guard`. If missing, the `file://` entries are wrong or the version does not read them.
- [ ] Worker `mode` (UNVERIFIED): workers carry `mode: subagent`; if they show as selectable primary agents, report it.
- [ ] Start with `SUBAGENT_CAP=1`, ask the maestro for two dispatches: the second is blocked with the fan-out message.
- [ ] Start with `CONTEXT_GUARD_TOKENS=1000`, send a second prompt on an unrelated topic: the reply recommends a new session.
- [ ] Ask the maestro to edit a file: it dispatches a worker instead of editing.
