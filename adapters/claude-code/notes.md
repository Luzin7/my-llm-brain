# Claude Code adapter notes

Harness-only lines that the neutral core rules leave out.

## Orchestration

- Resuming a worker is `SendMessage` to the existing agent; it does not count toward the fan-out cap.
- Start a fresh session with `/clear`. Compact with `/compact <focus line>`.
- The fan-out cap is enforced by the L3 `subagent-cap` PreToolUse hook (matcher `Agent|Task`, main session only). Without L3 the cap is a rule the maestro follows.
- The main session is held to orchestrating only by the L3 `maestro-guard` hook. Without it, the rule is text only.
- Model and effort tiers come from `examples/sides/claude-code.json` (agent frontmatter `model`, `effort`); the cheap tiers may hit a separate usage quota.
- `omitClaudeMd: true` (UNVERIFIED, see below) in the side config is meant to keep subagents from loading the project instructions file twice; each agent file already carries its rules.

## Always-loaded budget

Posture, orchestration and memory together stay at or under 2500 words as rendered into `<side>/.generated/CLAUDE.md`. Edge and guardrails travel inside the agent files that need them, not in the main session.

## Maestro

The main session is the maestro. Its body is `core/maestro/maestro.md`; it is not installed as a subagent on this harness. It lives outside `core/agents/` because `brain-sync` parses every file there as a subagent definition.

## Hooks (level 3)

Hook scripts are stdlib Python in `adapters/claude-code/hooks/`; `settings.hooks.json` wires them, each entry with `timeout: 10`.

- `brain-init` renders `{{CORE}}` in the commands, merges an entry only if absent (backup, atomic write), and writes `<config>/maestro-guard.paths` and `<config>/maestro-guard.grep-paths` (one directory per line; `~` allowed). The config directory is `CLAUDE_CONFIG_DIR`, default `~/.claude`.
- `maestro-guard`: main-session writes are allowed only under the `.paths` directories, Grep only under the `.grep-paths` directories (missing file means blocked). Create `<config>/maestro-guard.off` to disable it.
- In the main session every `mcp__*` tool is blocked. Bash is limited to read-only git (`status`, `diff`, `log`, `show`) and `ls`, `wc`, `head`, `cat`, `jq`, with no shell metacharacters.
- Hooks also fire inside subagents. The input carries `agent_id` only there, so the guards allow any call that has it and the cap counts only calls without it.
- `subagent-cap`: `SUBAGENT_CAP` (default 25; invalid or negative falls back to it); call cap+1 exits 2. One flock-guarded counter file per session in `<config>/state/subagent-cap/`, files older than 7 days pruned. Blocked calls are not counted.
- `context-guard`: `CONTEXT_GUARD_TOKENS` (default 100000; invalid falls back to it).
- Fail open: bad input, a missing `session_id` or `transcript_path`, or an unwritable state directory allows the call (warning on stderr where the hook warns). Only a clean exit 2 blocks.
- The cap matches the dispatch tool as `Agent|Task` (matcher and script), since the name has varied; re-check it when upgrading Claude Code.
- Each command is `test ! -f <script> || python3 <script>`, so a moved core skips the hook instead of blocking every call.

## UNVERIFIED frontmatter keys

`examples/sides/claude-code.json` emits these keys; they are not confirmed against the Claude Code docs for the tested version (2.1.330):
- `autoCompactWindow` (per tier): UNVERIFIED. Check that a subagent file accepts it, or whether the compact window is set only in settings; an unknown key may be ignored silently.
- `omitClaudeMd`: UNVERIFIED. Check that it is a supported agent frontmatter key and that it actually stops the project instructions file loading into the subagent.
- `effort`: UNVERIFIED for the same reason; check the accepted values.
Verify by running `claude agents` or dispatching one agent and inspecting its effective settings; drop any key the harness ignores.
