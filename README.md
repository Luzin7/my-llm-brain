# my-llm-brain

A template for a shared "brain" that guides LLM coding agents: rules, role agents, skills, memory and a task board, kept outside any single project and installed into the tool you already use.

Português: [README.pt-BR.md](README.pt-BR.md) (English is canonical).

## What it is

Three parts, each replaceable:

- **Core** (`core/`): neutral rules (posture, orchestration, edge cases, guardrails, memory), 12 role agents, a task-board skill, a spec template and a few method lessons. Nothing in it names a company, a language or a model vendor.
- **Side** (a folder you own, outside this repo): your scope, approvals table, preferences, memory and tasks. `bin/brain-init` creates it from `templates/side/`.
- **Adapters** (`adapters/`): how one harness loads the core. Claude Code, opencode, or a single `AGENTS.md` for tools that read only that.

## Why it works

Most agent failures are process failures: the agent starts coding before the request is clear, says "done" without evidence, reviews its own work, or forgets yesterday. The brain fixes the process, not the model.

- One **maestro** plans and dispatches; narrow **workers** implement; independent **judges** review with a fresh context. See [docs/concepts.md](docs/concepts.md).
- "Done" needs evidence: a test run, a diff, real data.
- Memory is a short index that is always loaded; details load on demand.
- Work that outlives a session lives on a task board, not in chat.
- Limits that matter (orchestrate-only, fan-out cap) are enforced in code where the harness allows it, and stated as text where it does not.

## Gain by harness

The text layer travels everywhere. Enforcement and independence depend on what the tool can do. There is no parity across tools or models: pick the row you need.

| Gain | Claude Code | opencode | AGENTS.md-only (Codex CLI, Gemini CLI, Cursor, Copilot) |
|---|---|---|---|
| Posture, guardrails, edge questions, done-criteria (text) | yes | yes | yes |
| Memory index always loaded | `autoMemoryDirectory` | `instructions` snippet | read-at-start line |
| Task board, memory-lint, heavy-lock, secret-scan (scripts) | yes | yes | if the tool runs shell |
| Role prompts | subagents | subagents | sequential modes, one context |
| Independent judge (fresh context) | yes | yes | no: self-review, labelled weaker |
| Per-role model/effort tiers | yes | model only | no |
| Main session orchestrates only | `maestro-guard` hook (L3) | `maestro` agent permission deny (L3) | no |
| Fan-out cap | hook (L3) | plugin (L3) | n/a |
| Context-size nudge | hook (L3) | plugin (L3) | no |
| Skills on demand | yes | yes | tool-dependent |

Results also vary with the model behind the harness. Small models follow long rule files less reliably; keep the word budgets in [docs/customization.md](docs/customization.md).

## Quickstart

Requirements: Linux or macOS (Windows via WSL), Python 3.9+, git. Nothing to install: the scripts use the standard library only.

```bash
git clone <repo-url> my-llm-brain
cd my-llm-brain
```

Install for Claude Code at level 2 into a new side at `~/brain/work`:

<!-- quickstart:start -->
```bash
bin/brain-init ~/brain/work --harness claude-code --level 2
bin/brain-init ~/brain/work --verify
bin/tasks ~/brain/work/tasks new "First task"
bin/memory-lint ~/brain/work/memory
```
<!-- quickstart:end -->

What happened:

- `~/brain/work` now holds `rules/side.md`, `rules/preferences.md`, `memory/MEMORY.md`, `tasks/` and `specs/`. Fill the placeholders in the two rules files.
- Rendered rules went to `~/brain/work/.generated/CLAUDE.md`; your `~/.claude/CLAUDE.md` got one `@` import line (a timestamped backup is kept if the file existed).
- 12 agents and the `task-board` skill were written under `~/.claude/`.
- `--verify` exits 0 when everything is wired; a moved checkout is reported with the dead path.

Then start `claude` in any project. Ask for something small and watch for the loop: plan, dispatch, review, report. Preview any install with `--dry-run`. For opencode or a single `AGENTS.md`, use the harness guides below.

## Levels

| Level | Adds | Use it when |
|---|---|---|
| L1 | Rules, memory index, task board. Works in any tool. | You want the method with no agents. Default for `agents-md`. |
| L2 (default) | Role agents and skills. | You use Claude Code or opencode. |
| L3 | Hooks, plugins, permissions (`--level 3`, opt-in). | You want orchestrate-only and the fan-out cap enforced. |

L3 changes your tool settings. `brain-init` merges only absent entries, backs up first and never edits opencode JSONC. See the harness guides.

## Harness guides

- [Claude Code](docs/harness/claude-code.md)
- [opencode](docs/harness/opencode.md)
- [AGENTS.md-only tools](docs/harness/agents-md.md)

## Next steps

1. Edit `rules/side.md` (scope, closed topics, approvals) and `rules/preferences.md`. Both are yours; the core never overwrites them.
2. Pick preferences and standards: [docs/customization.md](docs/customization.md).
3. Learn the loop and the memory tiers: [docs/concepts.md](docs/concepts.md).
4. Add skills from others, safely: [docs/skills.md](docs/skills.md).
5. Questions: [docs/faq.md](docs/faq.md). Changing the template itself: [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT, see [LICENSE](LICENSE).
