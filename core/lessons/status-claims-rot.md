---
name: status-claims-rot
description: A doc that states a status rots silently the moment the work ships; audit surviving docs and board columns against the source of truth
type: lesson
---
A line such as "pending", "not implemented" or "phase 1 of 3" is written once and read much later by someone with no reason to doubt it. A detailed document makes its stale claim more convincing, not less.
**Why:** after work ships or docs are purged, the survivors still assert the old status, and a reader schedules shipped work as pending or re-specifies it. A task board column is only what the last writer believed.
**How to apply:** grep survivors for status words (pending, not implemented, TBD, planned, awaiting) and check each against the code, the release or the pull request state, never against another doc. Prefer status that expires visibly (a date, an issue link). Strike the stale claim instead of appending a correction below it.
