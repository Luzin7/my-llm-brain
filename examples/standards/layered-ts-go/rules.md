<!-- Example standards (layered, TypeScript and Go): always-loaded rules. Swap this folder for your own conventions, or use none. -->
# Code standards

Code outside these standards is a defect. A deviation needs a stated reason (which rule, why) in the PR body or worker report; an unjustified deviation is rejected in review, never treated as taste.

Layer 0 applies to every language and size. Layers 1-2, Go and anti-patterns live in the `code-standards` skill and its reference; load them when writing or reviewing code. Skipping a layer is a deliberate decision, never an oversight.

## Layer 0
1. Early return. `else` is rare; the error path exits first and the happy path stays unindented. An `else` usually means a missing function.
2. Guard clauses at the top: validate input, authorization and existence before any I/O or object construction.
3. Errors are named types, never loose strings: one class per case extending a base error (TypeScript), or a named factory carrying a status (Go).
4. Dependencies enter through the constructor. Wiring happens in one place: the entry point or root module.
5. No comments in code, except a tool directive, a license header, or a one-line external constraint with a link. If code needs explaining, fix the code.
6. Names reveal intent; the role is a suffix (`CreateInvoiceService`, `InvoicePresenter`).
7. Complexity cap: more than 3-5 conditionals in a function means extracting a named check; more than 2-3 parameters means a named object.
8. Identifiers in English. Text shown to end users follows the project's end-user language ({end-user language}).
9. Imports use path aliases, never long relative chains.
10. Tests sit next to the code, use factory fixtures with overrides, and mock contracts, never implementations. Tests stay simple. A test is never loosened to pass. Write the failing test first and see it fail for the right reason.
11. Git text carries no AI attribution.
12. Agent-facing repo docs are in English and self-contained: they state the convention instead of pointing at personal files.
13. Security mechanisms follow the industry standard; fix a race inside the standard, never by dropping a property.
14. Dependency manifests and lockfiles are changed only through the package manager. If a fix seems to need a manual edit, stop and report it.
