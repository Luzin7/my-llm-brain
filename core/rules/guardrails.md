# Guardrails

Method rules that hold for every project. Language- and stack-specific standards live in an optional standards pack, not here.

1. Every deviation from the project's code standards needs a stated reason (which rule, why) in the pull request body or the worker report. An unjustified deviation is a defect the reviewer rejects, never a style preference.
2. Failing test first, seen failing for the right reason (on the assertion that matters, not on setup or a typo). A test is never loosened to pass; a changed contract gets an equally exact assertion.
3. Docs written for agents are self-contained: state the convention itself, never point to a person's private rules or files.
4. Security mechanisms follow the industry standard for that mechanism. Fix races inside the standard; never drop one of its properties.
5. Dependency manifests and lockfiles are changed only through the package manager. If a fix seems to need a manual edit, stop and report it.
6. A worker never works around a permission denial: no splitting the action, no alternate route. It reports the denial.
7. Git text carries no AI attribution unless the user's preferences ask for it.
8. Never store secrets in notes, tasks or memory. Record where the secret lives instead.
