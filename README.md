# my-llm-brain

A template for a shared "brain" that guides LLM coding agents: rules, role agents, skills, memory and a task board, kept outside any single project and installed into the tool you already use.

Português: [README.pt-BR.md](README.pt-BR.md) (English is canonical).

## What it is

Three parts, each replaceable:

- **Core** (`core/`): neutral rules (posture, orchestration, edge cases, guardrails, memory), 12 role agents, a task-board skill, a spec template and a few method lessons. Nothing in it names a company, a language or a model vendor.
- **Side** (a folder you own, outside this repo): your scope, approvals table, preferences, memory and tasks. Created from `templates/side/` by the install.
- **Adapters** (`adapters/`): how one harness loads the core. Claude Code, Codex, opencode, or a single `AGENTS.md` for tools that read only that. `dist/` holds the generated output of each; `python3 tools/build-dist` rebuilds it.

## Why it works

Most agent failures are process failures: the agent starts coding before the request is clear, says "done" without evidence, reviews its own work, or forgets yesterday. The brain fixes the process, not the model.

- One **maestro** plans and dispatches; narrow **workers** implement; independent **judges** review with a fresh context. See [docs/concepts.md](docs/concepts.md).
- "Done" needs evidence: a test run, a diff, real data.
- Memory is a short index that is always loaded; details load on demand.
- Work that outlives a session lives on a task board, not in chat.
- Limits that matter (orchestrate-only, fan-out cap) are enforced in code where the harness allows it, and stated as text where it does not.

## Gain by harness

The text layer travels everywhere. Enforcement and independence depend on what the tool can do. There is no parity across tools or models: pick the column you need.

| Gain | Claude Code | Codex | opencode | AGENTS.md-only (Gemini CLI, Cursor, Copilot) |
|---|---|---|---|---|
| Posture, guardrails, edge questions, done-criteria (text) | yes | yes | yes | yes |
| Memory index always loaded | `autoMemoryDirectory` and `@` imports | read-at-start line | `instructions` | read-at-start line |
| Task board, memory-lint, heavy-lock, secret-scan (scripts) | yes | if the tool runs shell | yes | if the tool runs shell |
| Role prompts | subagents | custom agents (TOML) | subagents | sequential modes, one context |
| Independent judge (fresh context) | yes | yes | yes | no: self-review, labelled weaker |
| Per-role model/effort tiers | yes | effort per agent | model only | no |
| Main session orchestrates only | `maestro-guard` hook (L3) | no | `maestro` agent permission deny (L3) | no |
| Fan-out cap | hook (L3) | no | plugin (L3) | n/a |
| Context-size nudge | hook (L3) | no | plugin (L3) | no |
| Skills on demand | plugin | yes | yes | tool-dependent |

Results also vary with the model behind the harness. Small models follow long rule files less reliably; keep the word budgets in [docs/customization.md](docs/customization.md).

## Install

Requirements: git. Python 3.9+ is optional and only turns on the L3 guards. Linux, macOS and Windows (opencode on Windows runs in WSL).

```bash
git clone https://github.com/Luzin7/my-llm-brain.git
cd my-llm-brain
```

There is one checklist, [INSTALL.md](INSTALL.md), and two ways to run it.

### Let your AI install it

Open your harness inside the clone and paste this prompt. The agent follows INSTALL.md, shows you the plan, waits for your "yes", applies it, records it and verifies:

```text
Install the my-llm-brain "brain" for me from this clone.

1. Read INSTALL.md in the repository root and follow it exactly, step by step. Run only the commands written there; use the PowerShell blocks on Windows and the POSIX blocks elsewhere.
2. Detect which harness you are running in (Claude Code, Codex, opencode or an AGENTS.md-only tool). Install only that one, unless I ask for others.
3. Before writing anything, print the plan from step 3: every file you will create or edit, every backup, the side folder, the Python you found. Then stop and wait for me to answer "yes".
4. After my yes, apply the steps in order. On any line starting with STOP, stop and tell me. Never edit text outside the my-llm-brain markers, never overwrite an existing side, back every edited file up first.
5. Record what you did in the side's .install-record.md, run the verify blocks and the harness-side checks for my harness, and paste their output. Do not say "done" without that output.
```

### Install by hand

Open [INSTALL.md](INSTALL.md) and run its POSIX or PowerShell blocks in order, in one terminal, from the clone. You make the same choices the agent would: the side path, the harness, the yes to the plan.

### Claude Code marketplace

Claude Code can also take the plugins straight from the marketplace; the rules block and the side still come from INSTALL.md:

```text
/plugin marketplace add Luzin7/my-llm-brain
/plugin install brain --marketplace Luzin7/my-llm-brain
```

### Coming from v1

v1 (the `brain-init` installer) is tag `v1`. The v2 install detects v1 manifests and stops. Uninstall v1 from that tag first, following its README, then start INSTALL.md.

## Levels

| Level | Adds | Use it when |
|---|---|---|
| L1 | Rules, memory index, task board. Works in any tool. | You want the method with no agents. Default for AGENTS.md-only tools. |
| L2 (default) | Role agents and skills. | You use Claude Code, Codex or opencode. |
| L3 | Hooks, plugins, permissions (needs Python for Claude Code). | You want orchestrate-only and the fan-out cap enforced. |

L3 changes your tool settings. See the harness guides.

## Harness guides

- [Claude Code](docs/harness/claude-code.md)
- [Codex](docs/harness/codex.md)
- [opencode](docs/harness/opencode.md)
- [AGENTS.md-only tools](docs/harness/agents-md.md)

## Next steps

1. Edit `rules/side.md` (scope, closed topics, approvals) and `rules/preferences.md` in your side. Both are yours; the core never overwrites them.
2. Pick preferences and standards: [docs/customization.md](docs/customization.md).
3. Learn the loop and the memory tiers: [docs/concepts.md](docs/concepts.md).
4. Add skills from others, safely: [docs/skills.md](docs/skills.md).
5. Questions: [docs/faq.md](docs/faq.md). Changing the template itself: [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT, see [LICENSE](LICENSE).
