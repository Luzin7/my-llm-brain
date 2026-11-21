# Concepts

## The loop

The main session is the **maestro**. It plans, dispatches, judges and reports. It does not edit files, run tests or write to git; workers do.

1. **Triage.** A conversational question gets an answer. Anything that needs code, data, files or the web is dispatched.
2. **Plan.** Multi-step work goes to `architect`, which returns tasks with files, done-criteria (a command that proves it) and dependencies. A single obvious change skips this.
3. **Dispatch.** Independent tasks run in parallel, each to the narrowest worker. `scout` finds the exact files first so implementers do not explore.
4. **Judge.** One `reviewer` pass per batch, on the combined diff. Changes that can break or duplicate production data (migration, job, queue, webhook, CI, deploy, external API) also go to `edge-auditor`. After two failed rounds on a real decision, the maestro stops and asks the user.
5. **Verify.** The maestro reads the evidence (commands and outputs) and re-reads the original request item by item.
6. **Report.** Outcome first, what was verified and how, then each risk as fixed, tracked on the task board, or put to you as a decision.

Workers start with no conversation history. Every brief is self-contained: goal, paths, constraints, done-criteria and what to return.

The full text is in `core/rules/orchestration.md`; the maestro's own prompt is `core/maestro/maestro.md`.

## Workers and judges

| Role | Job |
|---|---|
| `architect` | Plans multi-step work; names blocking and assumable gaps |
| `scout` | Finds files and symbols; read-only |
| `backend-dev`, `frontend-dev` | Implement, test first |
| `test-engineer` | Writes the failing test or end-to-end check first |
| `debugger` | Finds the root cause before any fix |
| `researcher` | Looks things up, cites sources |
| `reviewer` | Independent judge of a diff |
| `edge-auditor` | Judge for production-touching changes: six edge questions |
| `scribe` | Commit, push, pull request text; never merges |
| `brain-keeper` | Memory, task board, notes |
| `operator` | Browser and external-UI work |

A judge is independent only if it has a fresh context. That needs a harness with subagents. On a single-file tool the reviewer is a second pass in the same context and is labelled weaker.

## Memory tiers

1. **Always loaded**: the rules files and the memory index (`memory/MEMORY.md`). Kept short by a word budget.
2. **Loaded by trigger**: skills and agent files.
3. **Archive** (`memory/archive/`): read only on purpose.

A note is one fact. The index has one line per note, under 150 characters. A rule has one canonical home, the rules files; notes hold facts and history, never a second wording of a rule. `bin/memory-lint <memory-dir>` checks the layout and exits non-zero on a violation; run it after every memory write.

A situational rule moves down a tier the next time someone touches it. Review monthly: count your corrections per week, find rules that never fired, move down anything untouched for 30 days.

## Task board

Work that outlives a session becomes a task file in `<side>/tasks`: frontmatter (`id`, `title`, `status`, `proof`) and a body with Goal, Done criteria and Log. Statuses: todo, doing, review, blocked, done.

```bash
bin/tasks ~/brain/work/tasks new "Short title"
bin/tasks ~/brain/work/tasks board
```

`BOARD.md` is generated; never edit it by hand. Status comes from reality: check each `proof` (the pull request state, the run, the data) before changing it. The `task-board` skill tells `brain-keeper` how.

## Side versus core

| | Core | Side |
|---|---|---|
| Lives in | this repo (`core/`) | a folder you choose, outside the repo |
| Holds | method: rules, agents, skills, lessons | your scope, approvals, preferences, memory, tasks |
| Updated by | `git pull` (and the update step of INSTALL.md for copies) | you |
| Private data | never | yes |

Core files use `{{CORE}}`, `{{SIDE}}` and `{{PY}}` tokens. They stay literal in the built `dist/`; the install writes one paths line (`my-llm-brain paths: ...`) that tells the agent what each token means. Claude Code plugins substitute them natively. An unknown token aborts `tools/build-dist` before any write.

`dist/` is generated: never edit it. Edit the input (the core file, your side rules, `tools/dist.config.json`) and rebuild.

## Leak gate

The core must stay free of private data, including its history. `tools/leak-gate/leak-gate` runs gitleaks, a pattern list (home paths, e-mail addresses, private IPs, internal hosts) and your private denylist of terms. It exits 0 clean, 1 findings, 2 could not run. The denylist lives outside the repo and the gate prints only `denylist #N`, never the term. A pre-push hook runs it on the full history. Details: [CONTRIBUTING.md](../CONTRIBUTING.md#leak-gate).

Your side is private and is not subject to the gate. Do not push it anywhere public.
