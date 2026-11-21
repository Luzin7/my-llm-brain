<!-- Example standards reference (layered, TypeScript and Go): detail behind rules.md. Swap with your own conventions. -->
# Code standards reference

Read only the section you need.

- [Layer 0 details](#layer-0-details)
- [Layer 1: vertical slices](#layer-1-vertical-slices-default)
- [Layer 2: rich domain](#layer-2-rich-domain-only-when-justified)
- [Go](#go)
- [Frontend](#frontend)
- [Tests](#tests)
- [Naming](#naming)
- [Anti-patterns](#anti-patterns)
- [How much to apply](#how-much-to-apply)

## Layer 0 details
- Complexity: extract grouped conditions into a named predicate (`canPublish`); replace positional same-type arguments with a named object.
- Guard clauses:
  ```ts
  const invoice = await this.invoiceRepository.findById(request.invoiceId);
  if (!invoice) return left(new InvoiceNotFoundError());
  if (invoice.accountId !== request.accountId) return left(new UnauthorizedError());
  ```
- Named errors:
  ```ts
  export class InvalidTransferError extends BusinessRuleError {
    constructor(reason: string) { super(`Invalid transfer: ${reason}`) }
  }
  ```
  ```go
  func ErrNotFound(ctx string) *ServiceError { return New(ctx+" not found", 404) }
  ```
- Dependencies: `private readonly` in TypeScript, `NewX(...)` returning a pointer in Go. No hidden singletons, no concrete imports in business rules.

## Layer 1: vertical slices (default)
Horizontal layering for its own sake is cost without return. Test: a feature is findable in one place.
- Feature slice or module slice, depending on whether the domain has invariants. A domain without invariants stays a module slice; do not promote it.
- Suggested layout: `modules/<domain>/{entities,errors,repositories/contracts,presenters,features/<feature>/<feature>.{controller,service,dto}.ts}`.
- Domain-wide items live at domain level; cross-domain items go to `shared/`. A domain never imports another domain.
- Repository pattern: the contract lives in the domain, the implementation in infra.
- One use case per class with one entry point (`execute()`). No bucket services.
- Controller is thin: validate, call the service, translate the result. Presenter turns an entity into the response; the controller never serializes by hand.
- DTO per feature: schema, inferred type and validation pipe in one file.
- No extra field, variable or config to carry a value already fixed where it is read.

## Layer 2: rich domain (only when justified)
Use when real invariants exist (money, balances, states that cannot be invalid).
- Either (`left`/`right`): services return, never throw; the edge maps results to the transport.
- An entity cannot be born invalid: private constructor plus `static create()` returning an Either; every `left` carries a named error.
- Value objects for concepts without identity.
- Money is an integer in minor units (`bigint`); convert only in the presenter. Never float.

## Go
- `cmd/<binary>/main.go` is the only wiring point; the rest lives under `internal/`.
- Vertical slices per domain, with `shared/` as the only bridge.
- Idiomatic `(value, error)`: a typed named error, checked immediately with an early return.
- Hand-written SQL plus a generator; migrations are plain DDL; never edit generated files; no ORM hiding queries.
- Small interface in the domain, implementation in infra.

## Frontend
- `src/{components/{ui,layout,features},hooks,lib,stores,types,config}`; hooks are kebab-case with a `use-` prefix.
- One central HTTP client; components never call raw `fetch`.

## Tests
- Colocated: `x.spec.ts` beside `x.ts`, `x_test.go` beside the code. No parallel test tree.
- Factory fixture with overrides in the same file.
- Nested `describe` per method; one behavior per test.
- Mock the contract, never the implementation.
- No logic, no elaborate setup, no narrative titles.

## Naming
TypeScript class files PascalCase; feature files kebab-case with a role suffix (`toggle-status.service.ts`); hooks `use-thing.ts`; Go files snake_case.

## Anti-patterns
Chained `else` where early return fits; `throw` as flow control in an Either service; `left(new Error('text'))`; an entity built with `new`; a controller serializing by hand; a domain importing a domain; business rules in controller or repository; float for money; comments outside the allowed set; deep relative imports; editing generated files; mocking an implementation.

## How much to apply
| Project | Layer 0 | Vertical slices | Repository contract | Either | Rich entity | Presenter |
|---|---|---|---|---|---|---|
| Script or spike | yes | - | - | - | - | - |
| Small CLI or worker | yes | if several domains | yes | optional | - | - |
| Simple CRUD API | yes | yes | yes | yes | - | yes |
| API with business rules | yes | yes | yes | yes | yes | yes |
| Money, balance or state | yes | yes | yes | yes | invariants in entity | yes |

Layer 0 never drops. When unsure between a level and the one above, stay lower: moving up later is cheap, moving down is a rewrite.
