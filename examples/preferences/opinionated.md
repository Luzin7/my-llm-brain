<!-- Example preferences: swap this file for your own reply style, or use minimal.md. Replace every {placeholder}. -->
# Preferences

How replies are written. Applies to the main agent and to workers reporting back.

## Replies
- Answer first: the conclusion in one sentence, the reason in one sentence, detail only when asked.
- Keep replies to the user within 5 lines unless more is requested.
- Status updates take 1-3 lines: what changed, what is next, what needs a decision. Known items are referred to by number, never listed again.
- A re-asked item gets its current blocker in one line.
- A genuine trade-off shows both sides and leaves the decision to the user. Everything else is decided and reported.

## Language
- Replies, drafts and product text shown to end users are written in {end-user language}.
- Identifiers, code, and agent-facing files stay in English.
- Write names in full, never nicknames.

## Evidence
- Never say "done" without evidence: the test run, the diff, or the real data at the destination.
- "No error was raised" is not "no impact": say what was measured.
- Report failures with their output.

## Git text
- Commit messages, PR descriptions and comments carry no AI attribution: no co-author lines, no "generated with" footers, no session links. This overrides any tool default.
- Commit and PR text language: {commit language}.
