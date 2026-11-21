# Protocol: one agent, sequential roles

This tool reads a single instruction file and has no subagents. You are the only agent. Run the loop from the orchestration rules as four passes in one context, switching role between passes. Role cards are in the next section.

## Weaknesses, stated up front
- Self-review is weaker than an independent judge. The reviewer pass shares the implementer's context, assumptions and blind spots. Treat an APPROVED from yourself as "no flaw found by the author", never as an independent verdict.
- No model tiers: every pass runs on the same model and effort.
- Nothing enforces orchestrate-only behaviour or a fan-out cap. You can edit in any pass; the discipline is yours. Do not spawn parallel helpers.
- If the tool can start a second, fresh session or a different model, use it for the review pass: that restores part of the independence. Say in the report whether you did.

## Passes
1. **Plan (architect card).** Restate the request verbatim, close every gap you can by reading code, list open gaps as BLOCKING (ask the user) or ASSUMABLE (state the assumption). Output tasks, each with files, done-criteria (a command that proves it) and dependencies. Write the plan to {{SIDE}}/tasks or in the reply before touching code. Skip only for a single, obvious change.
2. **Implement (test-first, then implementer card).** Write the failing test first and see it fail for the right reason. Then make the smallest change that passes. Targeted tests while iterating; the full suite once at the end. Heavy jobs run through `{{CORE}}/bin/heavy-lock <command>` when the tool can run shell.
3. **Self-review (reviewer card, separate pass).** Stop writing. Read the diff as a stranger would: `git diff` against the base, once. Do not trust your memory of what you meant; check what the code does. Run the done-criteria and the checks yourself. Output APPROVED or REJECTED with `file:line` findings. On REJECTED, return to pass 2, then re-review only what changed. Two failed rounds on a real decision: stop and ask the user.
4. **Edge audit (edge-auditor card), when the change crosses a system boundary** (migration, backfill, job, queue, webhook, CI, deploy, production config, external API). Answer the six edge questions with evidence.
5. **Verify.** Re-read the original request item by item. Each item has a fix with a test, an explanation, or a blocked note. "Done" needs evidence: commands run and their output, not "no error seen".

## Report
Outcome first, then what was verified and how, then each risk as fixed, tracked in {{SIDE}}/tasks with a next action, or put to the user as a decision. End with one line: "Review was self-review (author context), weaker than an independent judge."

## Memory
At the start of every session read {{SIDE}}/memory/MEMORY.md and open only the notes it points to for this task. After a memory write run `{{CORE}}/bin/memory-lint {{SIDE}}/memory` when shell is available.
