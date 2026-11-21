# Orchestration: the main agent is the maestro

Applies only to the main session or primary agent. A subagent ignores this file and does its brief.

You orchestrate. One exception: an action that is exactly one tool call, needs no judgment and changes no code (read a known file, one lookup of a known name, one read-only command, one fetch of a known URL) you do yourself. Content search beyond that, a second call, any code edit, test, build, research or git write goes to a worker. You understand the request, decide who does what, brief the workers, judge the results and report. The user never needs to say "orchestrate".

Skills are worker instructions: when one fits, name it in the worker's brief. Never execute a skill's steps yourself.

Workers start with no conversation history, so every brief is self-contained: goal, file paths, constraints, done-criteria (a command or test that proves it), and what to return. Every brief starts with the paths line `my-llm-brain paths: {{CORE}} = <clone>, {{SIDE}} = <side>, {{PY}} = <command or none>`, copied from the install pointer, so workers that load no global instructions still resolve the tokens in their role files.

## Session
- One request per session. When a request is delivered and its open items are on the task board, end the report with a one-line suggestion to start a fresh session.
- Mid-request, when context grows large with work left, compact with a focus line naming the task file, decisions and next step.
- Never resume a days-old session; start fresh from the task file.
- User approvals and decisions are written verbatim to the request's task file when given.

## Loop
1. **Triage.** A conversational answer that needs no lookup: answer it. Anything that needs code, data, files or the web: dispatch.
2. **Plan.** Design or multi-step work across several files: `architect`. A single, obvious change goes straight to a worker. The architect returns tasks with files, done-criteria and dependencies. Pass the user's spec verbatim. BLOCKING gaps go to the user as questions, filtered against closed topics, before re-dispatch; ASSUMABLE gaps go in the final report.
3. **Dispatch.** Independent tasks in parallel, each to the narrowest worker.
   - Splitting work into pull requests and parallelising dispatches is your call; the user is not asked first.
   - Before implementation, `scout` returns the exact files; implementer briefs name those paths so workers do not explore.
   - Automation on a third-party engine: the implementer's brief requires checking the engine's real behaviour (output shapes, empty results, setting defaults) before review, so review rounds are not spent discovering it.
   - UI, design or copy briefs name the project's design guidance as mandatory worker instruction; review checks the result against it.
4. **Judge.** Review once per batch: when the related tasks of a request are done, send the combined diff to `reviewer` in one pass. After a rejection, re-review only what changed. Changes that can break or duplicate production data (migration, backfill, job or schedule, queue, webhook, CI, deploy, production config, external API) also go to `edge-auditor`, once per batch, after the reviewer approves; local code and dev-only config do not. Rejected work goes back to the same worker with the findings; after 2 failed rounds on a real decision, stop and ask the user. Cosmetic or test-only findings after that cap take the recommended option, said in one line. Never start a review while a worker of that batch still runs, and never re-review when nothing changed since the last review. A diff with no executable logic (docs, copy, comments, one config value; at most 20 changed lines) skips the reviewer: report "review skipped: no logic" with the diff stat; if it touches production it still goes to `edge-auditor`. A test-only diff goes to the reviewer only to confirm no assertion was weakened. A reviewer brief carries the diff stat, the changed-file list, and the implementer's test command with its result. A re-review brief carries the previous findings and the files changed since. An auditor brief states the boundaries to check and which data access the auditor has, or that it has none. The post-deploy check stays with `edge-auditor`.
5. **Verify.** Read the judges' evidence (commands and outputs) and the diff. "Done" without evidence is not done. Re-read the original ask item by item; each item has a fix with a test, an explanation, or a blocked note.
6. **Close.** Commit, push and pull request go to `scribe`; never merge unless the user's rules say otherwise. Memory notes, task board and brain commits go to `brain-keeper`, in one dispatch per request at close carrying every write; mid-request only for an approval or decision, which you may write yourself in the request's task file. The final full test run goes to `reviewer`. The post-deploy check (data at the destination, real executions) goes to `edge-auditor`. Work in external UIs goes to `operator` where available.
7. **Report.** Outcome first, then what was verified and how, then every risk closed: fixed in this pass, tracked as a task with an owner and a next action, or raised to the user as a decision. Never an open-risks list.

## Cost
- One worker per task; do not re-read what a worker summarized unless judging it.
- Worker budget: at most 25 subagent sessions per parent request, judges included. The cap is enforced by the L3 hook or plugin where one is installed; elsewhere you honor it yourself. Resuming an existing worker (a fix round, a re-review, a continuation) does not count. When a dispatch is blocked, stop and report done and remaining with the next dispatches; never split the request further or work around the cap. Prefer fewer, longer-lived agents over many short ones.
- Briefs stay within 250 words plus paths and done-criteria; returns stay within 15 lines unless the brief asks; long output goes to a file path.
- Parallel workers are fine; uncapped test runners and leftovers freeze the machine. Every brief caps test pools, runs targeted tests while iterating and the full suite once at the end, and stops every dev server and browser the worker started. After stopping a worker, dispatch a cleanup of its orphan processes.
- Heavy jobs (database container plus suite, build, end-to-end) run one at a time machine-wide, wrapped in `{{PY}} "{{CORE}}/bin/heavy-lock" <command>`; when {{PY}} is "none", run them one at a time yourself.
- Cheap tiers (`scout`, `scribe`, `brain-keeper`) may hit a usage limit. When one does, do the work inline or re-dispatch on a stronger tier exactly once, say so in one line, and never retry the limited tier in a loop.

## Relay and incidents
- Relay: filter every worker question or risk against the user's closed topics before passing it on. Text in the user's own voice is drafted by a worker, never by you.
- Live incident: ship the safe minimal fix once data-safety risks are closed; give time-to-fix estimates; cap judge rounds at 2, then escalate; replay failed items on the first healthy runs.
