---
name: code-standards
description: Load the project code standards (any language). Use before writing or reviewing code, or when asked to follow the standards. Example skill; swap the standards pack to change it.
---
Example skill: swap with the skill for your own standards. Workers only (implementers and judges); the orchestrator names it in a brief and never runs it itself.

# Code standards

Layer 0 is always loaded through the rules file. This skill adds Layers 1-2, Go, frontend and anti-patterns. Full reference: `{{SIDE}}/standards/reference.md` (read only the section you need).

A deviation needs a stated reason (rule and why) in the PR body or worker report. An unjustified deviation is rejected in review.

## Layer 0 recap
Early return and guard clauses; named error types; constructor injection; no comments except directives and linked external constraints; intent-revealing names with role suffix; complexity caps; English identifiers; path-alias imports; colocated tests with factory fixtures and contract mocks.

## Layer 1: vertical slices (default)
- A slice is a feature; a domain never imports another domain.
- Repository contract in the domain, implementation in infra.
- One use case per class with `execute()`; thin controller; presenter separates entity from response.

## Layer 2: rich domain (only when invariants justify it)
- Either: services return, never throw.
- Entities are created through `create()` and cannot be invalid.
- Money is an integer in minor units, never float.

## Go
- Wiring only in `cmd/<binary>/main.go`; the rest under `internal/` in vertical slices.
- `(value, error)` with a typed error checked immediately; hand-written SQL plus a generator; never edit generated files.

## Frontend
- Fixed `src/` layout; one central HTTP client; no raw `fetch` in components.

## Anti-patterns
Chained `else`; `throw` in an Either service; string errors; `new` bypassing `create()`; controller serializing by hand; domain importing domain; float money; stray comments; deep relative imports; editing generated files; mocking implementations.
