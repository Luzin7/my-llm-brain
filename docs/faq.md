# FAQ

## Do I get the same results on every tool and model?

No. The text rules travel everywhere. Independent review, model tiers, orchestrate-only and the fan-out cap need harness features. See the matrix in the [README](../README.md#gain-by-harness).

## Which level should I pick?

L2 on Claude Code or opencode. L1 on tools that read one instruction file. Add L3 when the maestro keeps doing work itself or dispatches too many workers.

## Will it overwrite my existing configuration?

No. The install adds one marked block (`my-llm-brain:start` to `my-llm-brain:end`) to your instruction file, backs the file up first as `<file>.bak-<timestamp>`, and never edits text outside the markers. It sets `autoMemoryDirectory` only if the key is absent, creates `opencode.json` only if you have none, and skips a file of the same name that it did not generate. Ask for the plan first: step 3 of [INSTALL.md](../INSTALL.md) lists every file and backup before anything is written.

## How do I undo an install?

Run the uninstall section of [INSTALL.md](../INSTALL.md). Ownership is proven per file at removal time: a marked block is cut out, a copy is deleted only if it still equals the clone's `dist/` file and carries the generated marker, and an edited copy is renamed to `.bak-<timestamp>`, never deleted. Your side folder is never touched.

## I moved the repo. Now what?

Claude Code reads the clone in place, and the Codex, opencode and AGENTS.md paths are written into the files at install time, so a moved clone leaves dead paths. From the new location, run the install blocks again (paths and the Codex `rev` are refreshed) and then the verify blocks, which name any dead path.

## I installed v1. What now?

v1 is tag `v1`. The install detects its manifests and stops with `STOP`; uninstall v1 from that tag first (its README), then start [INSTALL.md](../INSTALL.md).

## Why does the maestro refuse to edit files?

By design: the main session plans and judges, workers edit. With L3 a hook enforces it. If you want a quick change done in the main session, say so in the request or create `maestro-guard.off` in the Claude Code config directory (see the [Claude Code guide](harness/claude-code.md)).

## A dispatch was blocked with a fan-out message.

The cap (default 25 workers per session) stopped it. The maestro should report what is done and what remains. Raise it with `SUBAGENT_CAP=40` in the environment if the request truly needs more. Resuming an existing worker does not count.

## Can I use a different language for replies?

Yes. Set it in `preferences.md`. Agent-facing files stay in English; replies and end-user text follow your preference.

## Does it work on Windows?

Claude Code, Codex and AGENTS.md-only tools run natively with the PowerShell blocks of INSTALL.md. opencode runs through WSL with the POSIX blocks.

## Where do my notes go, and are they private?

In your side folder, outside this repo. Never push it to a public place. `bin/secret-scan <path>` flags secrets in notes; store where a secret lives, never the value.

## Can I add skills from other people?

Yes, link and audit them; see [skills.md](skills.md).

## Does the template phone home?

No. The scripts use the standard library and make no network calls.

## How do I contribute?

Read [CONTRIBUTING.md](../CONTRIBUTING.md): tests, the leak gate, review.
