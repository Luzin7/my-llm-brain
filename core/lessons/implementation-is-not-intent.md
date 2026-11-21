---
name: implementation-is-not-intent
description: The current implementation proves what exists, never what was intended; check the docs and recorded decisions before prescribing a change
type: lesson
---
A gate in code (a required field, a disabled button, a manual step) may be an unfinished state, a workaround or a leftover. Reading it as a design choice inverts the requirement.
**Why:** the prescription is judged on a premise nobody agreed to, then implemented and undone later at the cost of a redesign. Only docs and recorded decisions carry intent.
**How to apply:** before prescribing a change, check in order: the product docs for that surface; the user's dated decisions; whether the behaviour is described as interim or a known gap. If a prescription would make the user build something they never wanted, correct the document first, then the code.
