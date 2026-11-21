# Tools that read one instruction file

Render the single file with `brain-init --harness agents-md --target <path>`: core rules, `protocol.md`, `role-cards.md`. The file stays at or under 4000 words, so it fits every limit below. Verified against official docs on 2026-11-21; anything not confirmed is marked UNVERIFIED.

Memory pointer to add to the rendered file (every tool): "At session start read {{SIDE}}/memory/MEMORY.md; open only the notes it indexes that this task needs." Tools cannot auto-load an index, so this line is the whole mechanism.

| Tool | File and location | Point it at the memory index | Source |
|---|---|---|---|
| Codex CLI | `AGENTS.md` per directory from the Git root down to the working directory; `AGENTS.override.md` wins in the same directory; global `~/.codex/AGENTS.md` (or `$CODEX_HOME`). Combined limit 32 KiB (`project_doc_max_bytes`). Other names via `project_doc_fallback_filenames` in `~/.codex/config.toml`. | The read-at-start line. No import syntax is documented. | https://learn.chatgpt.com/docs/agent-configuration/agents-md |
| Gemini CLI | `GEMINI.md`: global `~/.gemini/GEMINI.md`, project root and ancestors up to the `.git` root, and subdirectories. Setting `context.fileName` accepts a name or list (e.g. add `AGENTS.md`). | Either the read-at-start line or the import `@{{SIDE}}/memory/MEMORY.md` (the `@file.md` syntax takes relative and absolute paths; prefer a relative path). `/memory show` lists what loaded. | https://google-gemini.github.io/gemini-cli/docs/cli/gemini-md.html |
| Cursor | `AGENTS.md` in the project root or subdirectories (plain markdown, nested files combine, nearest wins), or `.cursor/rules/*.mdc` with frontmatter `alwaysApply: true`. A plain `.md` in `.cursor/rules` is ignored. | The read-at-start line in the rule body. `@file` references in a rule are read on demand, not inlined, so do not rely on them for the index. | https://cursor.com/docs/context/rules |
| GitHub Copilot | `.github/copilot-instructions.md` (repository-wide); `.github/instructions/NAME.instructions.md` with `applyTo` glob; `AGENTS.md` anywhere (nearest wins); or a single `CLAUDE.md` or `GEMINI.md` in the root. Surfaces: cloud agent, Chat on github.com, code review for the repo-wide file; path-specific only cloud agent and code review. Which IDE surfaces read `AGENTS.md`: UNVERIFIED. | The read-at-start line. Whether the agent can read files outside the repo: UNVERIFIED. | https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions |
| Aider | Reads `AGENTS.md` through `read: AGENTS.md` in `.aider.conf.yml`. Not read automatically. | Add `read:` entries for `AGENTS.md` and the memory index. | https://agents.md (page lists it; Aider's own docs not checked: UNVERIFIED) |
| Windsurf | Listed as an AGENTS.md-compatible tool on agents.md. Its own rules path (`.windsurf/rules`, global rules file): UNVERIFIED, the docs page fetched was not found. | UNVERIFIED | https://agents.md |
| Others (Jules, Devin, Zed, Warp, Amp, goose, RooCode, Kilo Code, Junie, Augment, opencode) | Listed as AGENTS.md-compatible on agents.md. Exact location and precedence per tool: UNVERIFIED. | Read-at-start line | https://agents.md |

## Notes
- Put the file where the tool walks from: the repository root. Keep a single copy; for tools with another name (`GEMINI.md`, `CLAUDE.md`), set the file-name setting where one exists, or symlink instead of duplicating.
- User chat prompts override AGENTS.md content (agents.md). Hard limits (secrets, permissions) belong in the tool's own permission settings, not in this text.
- This adapter gives text-layer gains only. See the README matrix: no independent judge, no model tiers, no enforced orchestrate-only, no fan-out cap, no context-size nudge.
