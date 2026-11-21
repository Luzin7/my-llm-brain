# AGENTS.md-only tools

For tools that read one instruction file and have no subagents: Gemini CLI, Codex CLI, Cursor, GitHub Copilot, and others. Only the text layer applies. Full notes: [adapters/agents-md/tools.md](../../adapters/agents-md/tools.md) (sources and dates per tool).

## Setup

Follow the AGENTS.md-only steps of [INSTALL.md](../../INSTALL.md): set `AGENTS_TARGET` to the file your tool reads, then run the install block. It adds one marked block to the target (a paths line with the clone's revision, then `dist/agents-md/AGENTS.md`: core rules, the sequential protocol and five condensed role cards), after a `.bak-<timestamp>` backup. Text outside the markers is never touched; rerunning replaces the block in place.

This is always level 1. The block is about 2600 words, under the 4000-word budget. Put the target where your tool walks from, usually the repository root, and keep one copy: for tools with another file name (`GEMINI.md`, `CLAUDE.md`), use the tool's file-name setting or a symlink.

The tool cannot auto-load a memory index. The block contains one line telling the agent to read `<side>/memory/MEMORY.md` at session start; that line is the whole mechanism.

## What you do not get

- No independent judge: review is a second pass in the same context, and the report says so. If the tool can start a fresh session or another model, use it for the review pass.
- No model or effort tiers, no enforced orchestrate-only, no fan-out cap, no context nudge.
- Hard limits (secrets, permissions) belong in the tool's own permission settings. User chat prompts override the file.

## Per tool

| Tool | Where the file goes |
|---|---|
| Codex CLI | prefer the [Codex guide](codex.md); a project `AGENTS.md` at the Git root also works (combined limit 32 KiB) |
| Gemini CLI | `GEMINI.md`, or add `AGENTS.md` to `context.fileName` |
| Cursor | `AGENTS.md` in the project root |
| Copilot | `.github/copilot-instructions.md` or `AGENTS.md` (which IDE surfaces read it: UNVERIFIED) |

Other tools and the exact precedence rules: see `tools.md`, where unconfirmed items are marked UNVERIFIED.

## Verify

- [ ] Run the AGENTS.md-only verify block of INSTALL.md and paste its output.
- [ ] The marked block alone is at most 4000 words: `wc -w dist/agents-md/AGENTS.md`.
- [ ] Start the tool in the project and ask: "which instruction files did you load?" The answer names your file.
- [ ] Ask for a small change: the agent restates the request, lists done-criteria, and ends its report with the self-review line ("Review was self-review...").
- [ ] Ask: "what is in the memory index?" The agent reads `<side>/memory/MEMORY.md` (if the tool cannot read outside the repo, copy the index next to the file; UNVERIFIED for Copilot).

- [ ] Memory pointer, shell: if the tool runs commands, `bin/memory-lint <side>/memory` exits 0.
