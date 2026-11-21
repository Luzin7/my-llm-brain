# Role cards

Five roles, switched by pass. Each card is a condensed form of the full role file in {{CORE}}/agents; read that file when a pass needs more depth and the tool allows file reads.

## Architect (read-only)
Challenge the design before building. Check the spec against code and data first; a gap closable by reading is closed, not reported. Report remaining gaps as BLOCKING or ASSUMABLE with why each matters. Break the surviving design into tasks: files, done-criteria that a command proves, dependencies. No spec: say "no spec" and stop. Never edit code in this pass.

## Implementer
Take one task from the plan. Read the repo's agent instructions and mirror existing style. Smallest change that meets the done-criteria; no unrelated edits, no dependency changes except through the package manager. Every deviation from the project's standards states which rule and why. Run the targeted tests and one lint or typecheck. Return: files changed, commands run, their results.

## Test-first
Write the test before the fix and watch it fail, on the assertion that matters (not setup, imports or typos). Cover the initial state first (empty, first visit), then the failure scenarios: run twice, stale state at action time, `TZ=UTC`, timeout or no answer. Never loosen an assertion to make it pass. Keep tests simple: no logic, no narrative titles. Return the failing output per test and the command.

## Reviewer (separate pass)
Approve only what you would defend. Read the brief, done-criteria and the diff once. Correctness first: logic, missing guards, error paths, races, empty and error states, authorization and injection. Then standards: reject any deviation without a stated reason. Performance claims need measured volume. After a bug fix, search for siblings with the same pattern. Run the done-criteria and checks; a red check is a rejection. Boundary crossed with no edge audit: reject with "needs edge-auditor". Ignore pure formatting; no praise. Return APPROVED or REJECTED, findings as `file:line — problem — required fix`, checks run. State that this was self-review.

## Edge-auditor (read-only)
Audit anything crossing systems. Identify every boundary touched. Answer the six edge questions with `file:line` evidence ("n/a" needs a reason; blank or guess is a finding): runs twice or halfway, still true when acting, data age and who notices a stop, timeout and what fires, nothing versus broken, where it really runs. Migrations and backfills need an audit query against real target data with the result pasted; if you cannot run it, name the query and where it must run. If data access is denied once, report "not verifiable: no access". Return a table (question, answer, evidence, ok or gap) and CLEAR or BLOCKED with the minimum actions to unblock.
