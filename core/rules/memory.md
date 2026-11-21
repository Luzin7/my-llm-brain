# Memory

Notes live in {{SIDE}}/memory. The always-loaded index is {{SIDE}}/memory/MEMORY.md; keep it under 3500 bytes.

## Layout
- Index: one line per note, under 150 characters, linking the file. No rules, dates or quotes in the index. A note is listed in exactly one index; a large domain gets its own `index_<domain>.md` linked from MEMORY.md.
- Note: file `<type>_<topic>.md`, frontmatter `name` (the file stem), `description` (one line for recall), `metadata.type` (user, feedback, project or reference). One fact per note, then **Why:** and **How to apply:** for feedback and project notes. Absolute dates only. Link notes by file stem.
- Method lessons shared across sides live in {{CORE}}/lessons; they are data-free.
- Never store secrets; note where they live.

## Rules
- A rule has one canonical home: the rules files. Notes hold facts and history, never a second wording of a rule. A new correction edits the rule line first; the note gets at most one dated example.
- Update an existing note before creating one. Fix or delete notes that became wrong.
- Project notes carry Status, Next and Sunset lines and move to `memory/archive/` at sunset.
- After every memory write run `{{PY}} "{{CORE}}/bin/memory-lint" "{{SIDE}}/memory"`; a non-zero exit blocks the commit. When {{PY}} is "none", check the layout above by hand.

## Tiers
1. Always loaded: the rules files and the memory index.
2. Loaded by trigger: skills and agent files.
3. Archive: `memory/archive/`, read only on purpose.

A situational rule moves to its skill or agent file the next time someone touches it. Review monthly: count user corrections per week, find rules that never fired, and move down a tier any rule untouched for 30 days. Track two numbers only: corrections per week and the always-loaded word count.
