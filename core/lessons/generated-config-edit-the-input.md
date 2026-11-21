---
name: generated-config-edit-the-input
description: When a generator renders a file from templates and settings, edits to the rendered file are reverted on the next run
type: lesson
---
A rendered file is temporary by construction: the next generator run silently reverts any hand edit, including a fix verified minutes earlier.
**Why:** the regression then looks like a new bug instead of the consequence of where the edit was made.
**How to apply:** change the generator's input, never its output: the template for structure and prompt text, the settings source for model, limits and permissions. Before editing inside a generated tree, look for the generator's manifest; a listed file is disposable. Signal: a verified change disappears and the file's mtime matches a generator run.
