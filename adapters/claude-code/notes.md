# Claude Code adapter notes

Harness-only lines that the neutral core rules leave out.

## Orchestration

- Resuming a worker is `SendMessage` to the existing agent; it does not count toward the fan-out cap.
- Start a fresh session with `/clear`. Compact with `/compact <focus line>`.
- The fan-out cap is enforced by the L3 `subagent-cap` PreToolUse hook (matcher `Agent|Task`, main session only). Without L3 the cap is a rule the maestro follows.
- The main session is held to orchestrating only by the L3 `maestro-guard` hook. Without it, the rule is text only.
- Model and effort tiers come from `tools/dist.config.json` (agent frontmatter `model`, `effort`); the cheap tiers may hit a separate usage quota.
- `omitClaudeMd: true` (UNVERIFIED, see below) in the side config is meant to keep subagents from loading the project instructions file twice; each agent file already carries its rules.

## Always-loaded budget

Posture, orchestration and memory together stay at or under 2500 words as built into `dist/claude-code/BRAIN.md` plus your side rules and memory index. Edge and guardrails travel inside the agent files that need them, not in the main session.

## Maestro

The main session is the maestro. Its body is `core/maestro/maestro.md`; it is not installed as a subagent on this harness. It lives outside `core/agents/` because every file there is built as a subagent definition.

## Hooks (level 3)

The hooks ship as the `brain-guards` plugin in `adapters/claude-code/guards/`: stdlib Python scripts in `hooks/`, wired by `hooks/hooks.json` in exec form (no shell), each entry with `timeout: 10` and `onFailure: "continue"`. The plugin options are `side` (default `~/my-brain`) and `python` (default `python3`). A session start line `brain-guards active (python X.Y)` shows the guards are alive.

- `maestro-guard` receives `--side <dir>` from `hooks.json`. Writes are allowed under `<side>/memory`, `<side>/tasks` and `<side>/specs`; Grep also under any `--core <dir>`. Paths are normalized (backslashes, `~`, symlinks, case on Windows).
- `try_lock` is duplicated in `guards/hooks/subagent_cap.py` and `bin/lib/portablelock.py` on purpose: a plugin cannot import from `bin/`.
- Create `<config>/maestro-guard.off` to disable `maestro-guard`. The config directory is `CLAUDE_CONFIG_DIR`, default `~/.claude`.
- In the main session every `mcp__*` tool is blocked. Bash is limited to read-only git (`status`, `diff`, `log`, `show`) and `ls`, `wc`, `head`, `cat`, `jq`, with no shell metacharacters.
- Hooks also fire inside subagents. The input carries `agent_id` only there, so the guards allow any call that has it and the cap counts only calls without it.
- `subagent-cap`: `SUBAGENT_CAP` (default 25; invalid or negative falls back to it); call cap+1 exits 2. One counter file per session under `${CLAUDE_PLUGIN_DATA}/subagent-cap/` (fallback `<config>/state/subagent-cap/`), guarded by a cross-platform file lock; files older than 7 days are pruned. A corrupt counter is reset and the call allowed. Blocked calls are not counted.
- `context-guard`: `CONTEXT_GUARD_TOKENS` (default 100000; invalid falls back to it).
- Fail open: any internal error exits 0 with a stderr line naming step, error and input class. Only a clean exit 2 blocks.
- The cap matches the dispatch tool as `Agent|Task` (matcher and script), since the name has varied; re-check it when upgrading Claude Code.
- Each hook runs as `${user_config.python} -I <script>` with no shell, so PowerShell and POSIX behave the same.

## UNVERIFIED frontmatter keys

`tools/dist.config.json` emits these keys; they are not confirmed against the Claude Code docs for the tested version (2.1.330):
- `autoCompactWindow` (per tier): UNVERIFIED. Check that a subagent file accepts it, or whether the compact window is set only in settings; an unknown key may be ignored silently.
- `omitClaudeMd`: UNVERIFIED. Check that it is a supported agent frontmatter key and that it actually stops the project instructions file loading into the subagent.
- `effort`: UNVERIFIED for the same reason; check the accepted values.
Verify by running `claude agents` or dispatching one agent and inspecting its effective settings; drop any key the harness ignores.
