# FAQ

## Do I get the same results on every tool and model?

No. The text rules travel everywhere. Independent review, model tiers, orchestrate-only and the fan-out cap need harness features. See the matrix in the [README](../README.md#gain-by-harness).

## Which level should I pick?

L2 on Claude Code or opencode. L1 on tools that read one instruction file. Add L3 when the maestro keeps doing work itself or dispatches too many workers.

## Will it overwrite my existing configuration?

No. `brain-init` adds one import line to your Claude Code `CLAUDE.md` (with a timestamped backup), merges only absent hook entries (backup, atomic write) and sets `autoMemoryDirectory` only if unset, with a warning otherwise. It refuses to overwrite a hand-written opencode `AGENTS.md` and never edits `opencode.jsonc`. Preview anything with `--dry-run`.

## How do I undo an install?

Run `bin/brain-init <side> --uninstall` (add `--dry-run` to preview). It removes the files listed in the manifests, the import line in `CLAUDE.md`, this template's hook entries, `maestro-guard.paths`, `maestro-guard.grep-paths`, the `state/subagent-cap` counters, and `autoMemoryDirectory` only if it still points at this side's memory. Your other edits stay, and your side folder is untouched. Any removed file whose content differs from what the core renders (or every removed file when the core can no longer render them) is first copied to `<side>/.generated/uninstall-backups/<timestamp>/` and the path is printed. If `CLAUDE.md` held only our import line and is a symlink or lives outside the config dir, it is emptied instead of deleted. It works even if the repo was moved. For agents-md there is no manifest: the AGENTS.md target is simply deleted.

## I moved the repo. Now what?

`bin/brain-init <side> --verify` exits 1 and names the dead path. Moving the repo means uninstall, then install: run `bin/brain-init <side> --uninstall` from the new location (it works without the old path), then re-run `brain-init` with the same arguments.

## Why does the maestro refuse to edit files?

By design: the main session plans and judges, workers edit. With L3 a hook enforces it. If you want a quick change done in the main session, say so in the request or create `maestro-guard.off` in the Claude Code config directory (see the [Claude Code guide](harness/claude-code.md)).

## A dispatch was blocked with a fan-out message.

The cap (default 25 workers per session) stopped it. The maestro should report what is done and what remains. Raise it with `SUBAGENT_CAP=40` in the environment if the request truly needs more. Resuming an existing worker does not count.

## Can I use a different language for replies?

Yes. Set it in `preferences.md`. Agent-facing files stay in English; replies and end-user text follow your preference.

## Does it work on Windows?

Through WSL only.

## Where do my notes go, and are they private?

In your side folder, outside this repo. Never push it to a public place. `bin/secret-scan <path>` flags secrets in notes; store where a secret lives, never the value.

## Can I add skills from other people?

Yes, link and audit them; see [skills.md](skills.md).

## Does the template phone home?

No. The scripts use the standard library and make no network calls.

## How do I contribute?

Read [CONTRIBUTING.md](../CONTRIBUTING.md): tests, the leak gate, review.
