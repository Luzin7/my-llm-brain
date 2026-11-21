# opencode

Tested with opencode 2.3.2. Full adapter notes: [adapters/opencode/notes.md](../../adapters/opencode/notes.md). Real-binary checks are yours to run; the checklist below is how.

## Setup

```bash
bin/brain-init ~/brain/work --harness opencode --level 2
```

Add `--level 3` for the plugins. `--config-dir <path>` overrides the default `$XDG_CONFIG_HOME/opencode`.

What it does:

- Writes the agents to `<config>/agent/`, the `task-board` skill to `<config>/skill/` and, at L3, the plugins to `<config>/plugins/`.
- Writes the rendered rules to `<config>/AGENTS.md`. It refuses if that file exists and was not written by this template.
- Installs a `maestro` primary agent with `edit` and `bash` permission denied.
- Prints a JSON snippet with `default_agent`, `instructions` (your memory index) and, at L3, `plugin` entries. It never edits your `opencode.jsonc`: merge the snippet by hand. If you already have a `plugin` array, append the two entries.

## Plugins (L3)

| Plugin | Effect |
|---|---|
| `subagent-cap.js` | Throws `FanOutCapReachedError` before dispatch number cap+1 for a session. Resuming a worker is allowed |
| `context-guard.js` | Adds a system notice when the context passes a token threshold |

Settings: `SUBAGENT_CAP` (default 25), `CONTEXT_GUARD_TOKENS` (default 100000). Both plugins fail open and log a warning.

The plugin API (`ctx.tool.hook("execute.before")`, `ctx.session.hook("context")`) was checked against the 2.3.2 binary; the older `@opencode-ai/plugin` package types a different API. Plugin loading and the shape of `ctx.session.context` messages are UNVERIFIED on your install until you run the checklist.

Run the plugin tests (quote the glob; `node --test plugins/` fails on recent Node):

```bash
cd adapters/opencode && node --test 'plugins/*.test.mjs'
```

## Verify

- [ ] `bin/brain-init ~/brain/work --verify` exits 0. It checks the snippet markers by text, so a commented-out snippet still passes: confirm the entries are live.
- [ ] After pasting the snippet, `opencode` starts with `maestro` as the main agent.
- [ ] Plugin loading (UNVERIFIED): `/plugins` lists `subagent-cap` and `context-guard`. If they are missing, the `file://` entries in `plugin` are wrong or the version does not read them: fix the paths from the printed snippet.
- [ ] Worker `mode` (UNVERIFIED): worker agents carry no `mode` key. Check the agent picker. If workers show up as selectable primary agents, add `mode: subagent` to each under `agents` in your side config and re-run `brain-init`.
- [ ] Start with `SUBAGENT_CAP=1`, ask the maestro for two dispatches: the second is blocked with the fan-out message.
- [ ] Start with `CONTEXT_GUARD_TOKENS=1000`, send a second prompt on an unrelated topic: the reply recommends a new session.
- [ ] Ask the maestro to edit a file: it dispatches a worker instead of editing.
