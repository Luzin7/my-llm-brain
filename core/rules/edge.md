# Edge rules: integrations and production changes

Rigor must reach the glue: workflow automations, jobs and schedules, queues, webhooks, CI configuration, migrations, backfills, deploys and runtime config. Costly incidents start there, not inside services.

Before proposing, enabling or merging anything that crosses systems or touches real data, answer these six in a short table ("n/a" with a reason is fine, blank is not):
1. **Runs twice or stops halfway?** The destination is idempotent through a unique constraint or idempotency key in the data store, not only a cache or a lock. Retry only idempotent operations.
2. **Still true when acting?** Recheck state at the moment of action, not only at entry. Prefer state rebuilt each cycle over state that needs cleanup at the end.
3. **How old is this data, and who notices if it stops?** Know the source cadence and size the window by it. Measure freshness by the source's own load marker, not by a derived table's date.
4. **Timeout, and what happens when it fires?** Every external call has an explicit timeout; a job's ceiling sits below its executor's ceiling; know the API rate limit.
5. **How do I tell "nothing" from "broken"?** Errors alert (every trigger has an error path). Empty and error are distinct states in UI and logs. Scheduled jobs and CI fail loudly: non-zero exits, `set -euo pipefail`, fail-on-HTTP-error flags.
6. **Where does it really run, and did I test there?** Real timezone, schema and version. Dates carry an explicit timezone, and the suite also runs with `TZ=UTC`. A local schema, repo migrations and compose files prove nothing about production. Migration and backfill audits run against real data before deploy, with the result pasted.

- Never report "no impact" from "no run errored": say what was measured. If the system cannot tell nothing from broken, impact is unknown. A failure's log line is its alert text: step, error, input class, caller.
- Production console commands stay readable: no encoded or compressed blobs; use a readable URL or plain chunks.
- After shipping, "deployed" is not "works". Check the data at the destination or the real executions, and read one row through the production read path. Only then "done".
- When it breaks, write a one-page blameless postmortem: timeline, cause, why it was not caught, which of the six questions would have caught it, action. A question number that repeats is where to study.
- Where failure-first testing applies, the bad-scenario test (run twice, late source, `TZ=UTC`, dependency not answering) is written and seen failing before the fix.

Anti-patterns: retry on create; duplicates blocked only by a cache; scheduled HTTP calls that ignore error status; a trigger without an error path; a UI showing "empty" when the API failed; a date formatted without a timezone; a query window shorter than the source cadence; a migration adding a constraint without auditing real data.
