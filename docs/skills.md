# Skills

A skill is a folder with a `SKILL.md`: a name, a description of when to use it, and instructions. Agents load it when the description matches the task. This template ships one (`task-board`) and the standards-pack example. Everything else you add yourself.

## Third-party skills are linked, not vendored

This repo does not copy other people's skills. Copying freezes a version nobody maintains, mixes licences, and ships text nobody here reviewed. Instead, find the skill upstream, read it, pin it, and install it into your own skills directory.

## The pinned-SHA audit method

A skill is instructions plus sometimes scripts. Treat it like a dependency that can run code and steer your agent.

1. **Clone and pin.** Clone the upstream repo and record the exact commit: `git rev-parse HEAD`. Install from that commit, never from a moving branch.
2. **Read all of it.** Every file in the skill folder: `SKILL.md`, scripts, assets. Look for network calls, shell commands, reads outside the project, instructions that tell the agent to ignore your rules, to hide actions, or to send data anywhere.
3. **Check scripts.** Run `bin/secret-scan <skill-dir>` to catch embedded keys, and read every script line you do not understand before running it.
4. **Check licence and scope.** Confirm the licence allows your use. Confirm the description is narrow: a skill that triggers on everything competes with your rules.
5. **Install a copy.** Put it in the harness skills directory (for example `~/.claude/skills/<name>/`). Record the source URL and commit in a note in your side memory.
6. **Try it once** with a harmless task and watch which tools it calls.
7. **Re-audit on update.** To update, diff the new commit against the pinned one, read the diff, then pin the new commit. Never auto-update.

## Skills you write

Keep the description specific (when to use, not what it is), keep the body as instructions for a worker, and never put secrets or personal data in it. See [customization.md](customization.md#adding-a-skill).

Note: the install and uninstall steps only touch files carrying the `my-llm-brain generated` marker, so skills you install by hand are left alone.
