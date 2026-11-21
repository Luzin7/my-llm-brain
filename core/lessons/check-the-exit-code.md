---
name: check-the-exit-code
description: Never read a gate's success through a pipe or an echo chain; print the command's own exit code
type: lesson
---
A lint command piped into a pager returns the pager's exit code, and a chain that ends in an echo prints nothing when it fails quietly. Both led to commits with errors.
**Why:** a false green gate becomes a broken commit when nothing else runs CI.
**How to apply:** redirect output to a log, then print the command's own status (`cmd >log 2>&1; echo "exit=$?"`) and proceed only on `exit=0`. Same for typecheck and test runners.
