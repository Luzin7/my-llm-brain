# opencode adapter notes

Tested with opencode 2.3.2. This adapter installs two plugins and prints a config snippet. Nothing edits your `opencode.jsonc`: you paste the snippet yourself.

## Gains this adapter gives

| Gain | Level | How |
|---|---|---|
| Fan-out cap | L3 | `plugins/subagent-cap.js` throws `FanOutCapReachedError` before the cap-plus-one subagent dispatch |
| Context-size nudge | L3 | `plugins/context-guard.js` adds a system notice when the context passes a token threshold |
| Main session orchestrates only | L3 | `maestro` agent with `edit`/`bash` permission deny (from `examples/sides/opencode.json`), not a plugin |
| Memory index always loaded | L1+ | `instructions` entry in the snippet |
| Main agent is the orchestrator | L2+ | `default_agent` entry in the snippet |
| Per-role model tiers | L2+ | model only; opencode has no per-agent effort setting here |

Everything else (posture, guardrails, scripts, role prompts, independent judge, skills) comes from the core and works the same as on other harnesses.

## Snippet

`opencode.snippet.jsonc` has three keys. Merge them into your own config:

- `default_agent`: the orchestrator agent name.
- `instructions`: path to the side's memory index, so it is always loaded.
- `plugin`: file entries for the two plugins. Replace `{{SIDE}}` and `{{CONFIG_DIR}}` with your real paths (`brain-init` prints them filled in). If you already have a `plugin` array, append the two entries.

## Settings

| Env var | Default | Effect |
|---|---|---|
| `SUBAGENT_CAP` | 25 | Max child sessions per session. Invalid or negative values fall back to 25 |
| `CONTEXT_GUARD_TOKENS` | 100000 | Context size that triggers the nudge. Invalid values disable it |
| `SUBAGENT_GUARD_TIMEOUT_MS` | 5000 | Timeout for `session.list` and `session.context`; on expiry the call is allowed (the cap logs a warning). Invalid values fall back to 5000 |

Both plugins fail open: if the session list or context read fails, the call is allowed (the cap logs a warning).

## API facts (opencode 2.3.2)

The plugin shape is `export default { id, setup(ctx) }`. Hooks used:

- `ctx.tool.hook("execute.before", fn)`: event `{ tool, sessionID, agent, messageID, id, input }`; throwing blocks the call. The built-in subagent tool is named `subagent`; resuming passes `input.sessionID`.
- `ctx.tool.hook("execute.after", fn)`: event carries the same `tool` and `id`.
- `ctx.session.list({ parentID, limit })`: returns `{ data: [{ id }] }`.
- `ctx.session.hook("context", fn)`: event `{ sessionID, system }`; push `{ type: "text", text }` onto `system`. `ctx.session.context({ sessionID })` returns messages with `type` and `tokens`.

The `@opencode-ai/plugin` npm package installed next to 1.x configs still types the older `tool.execute.before` API, so it does not describe these hooks. They were checked against the 2.3.2 binary. Run the checklist below on your install.

## Verify

1. Start opencode and run `/plugins`: `subagent-cap` and `context-guard` are listed.
2. Start with `SUBAGENT_CAP=1`, ask the orchestrator for two subagent dispatches: the second is blocked with the fan-out message.
3. Start with `CONTEXT_GUARD_TOKENS=1000`, send a second prompt on an unrelated topic: the reply recommends a new session.

## Tests

```
cd adapters/opencode && node --test 'plugins/*.test.mjs'
```

Quote the glob: on recent Node versions `node --test plugins/` treats the directory as a module path and fails.

## Maestro agent (core text)

`core/maestro/maestro.md` is the body of the `maestro` primary agent, declared under `extra_agents.maestro` in `examples/sides/opencode.json` with `edit` and `bash` permission deny. It sits outside `core/agents/` because `brain-sync` parses every file there as a worker agent. Resuming a worker is passing its existing session id to the subagent tool; it does not count toward the fan-out cap. Start a fresh session with a new opencode session.
