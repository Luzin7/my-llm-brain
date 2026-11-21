---
name: heavy-runs-one-at-a-time
description: Parallel heavy runs (database containers, full suites, builds) can freeze a machine even when each run caps its worker pool
type: lesson
---
Several workers each starting a database container and a full suite saturated disk I/O and froze the workstation, although every run capped its pool.
**Why:** a worker-pool cap does not limit the writes of containers and builds, and the freeze lands on the person at the keyboard.
**How to apply:** run heavy jobs one at a time machine-wide through `{{CORE}}/bin/heavy-lock <command>`; keep targeted runs for iteration.
