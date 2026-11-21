---
name: task-board
description: Track your own work on the local task board (one file per task, generated BOARD.md). Use when a request spans sessions, waits on someone or something, or when asked what is open, in progress or done.
---
Worker: brain-keeper. The maestro never runs this skill itself; it names it in a brief.

# Task board

The board directory is `{{SIDE}}/tasks`. Tools: `{{CORE}}/bin/tasks {{SIDE}}/tasks new "<title>"` and `{{CORE}}/bin/tasks {{SIDE}}/tasks board`.

## When to create a task
- The work will not finish in this session, depends on someone else, or needs a later check (deploy, merge, external run).
- Not for one-shot questions, or work finished and verified in the same session.

## Task file
Frontmatter: `id`, `title`, `status` (todo, doing, review, blocked, done), `created`, `updated`, `proof` (list of verifiable references: pull request URL, issue, commit, execution id, query). Body: Goal, Done criteria (checkable), Log (dated one-liners, newest last).

## Rules
1. Status comes from reality. Before reporting or changing a status, check each `proof` (the pull request state, the execution, the data). If reality disagrees with the file, fix the file first and log it.
2. `done` only when the done criteria were verified; log how.
3. `blocked` names who or what it waits on, in the log.
4. After any change to task files, run the `board` command. Never edit BOARD.md by hand.
5. Keep entries short; detail belongs in the pull request or issue the proof points to. Never store secrets; point to where they live.
