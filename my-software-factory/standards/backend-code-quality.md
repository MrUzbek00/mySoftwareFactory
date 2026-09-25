# Backend Code Quality Standard

Backend code the factory produces must be understandable by another developer
without reverse-engineering the author's intent.

A developer should understand the public contract of a class or function from:

1. its name,
2. its parameter names,
3. its parameter types,
4. its return type,
5. concise documentation where necessary,

without first reading the implementation. That is the self-explanatory code
principle, and every criterion below serves it.

This standard is consumed by `implement-change`, which applies it while writing
code, and by `validate-change`, which reviews changed backend files against it.
`review-pull-request` uses the same criteria and the same severity split.

## Order of Preference

Readability comes from design before it comes from prose:

1. good architecture
2. good naming
3. strong native typing
4. clear function signatures
5. small cohesive functions
6. documentation where useful
7. inline comments only where the reasoning is not obvious

More comments is not better code. A comment that restates the line above it
subtracts value, because a reader must now check whether the two still agree.

## Precedence

These rules do not outrank the target repository.

1. The framework's required conventions win.
2. The repository's established architecture and conventions win next.
3. The domain language of the project's requirements wins next.
4. This standard fills what remains.

Never rename a framework-required method, restructure an existing architecture,
or introduce a pattern the repository does not use, in order to satisfy a rule
here.

## Criteria

Each criterion has a slug. Findings cite the slug so they can be counted and
compared across tasks.

### `naming` — human-readable names

Names describe what a value represents, not its data type.

Avoid `data`, `info`, `item`, `obj`, `tmp`, `val`, `res`, `result`, `x`, `y`,
`foo`, `bar` unless the meaning is genuinely obvious in a very small local
scope.

```php
// Avoid
$u = User::find($id);
$result = $service->run($data);
$array = [];

// Prefer
$assignedSpecialist = User::find($specialistId);
$createdContract = $contractService->createContract($contractData);
$contractItems = [];
```

Loop variables get meaningful names where practical:

```php
// Avoid
foreach ($items as $i)

// Prefer
foreach ($contractItems as $contractItem)
```

Short conventional names remain correct where they aid readability: `$i` in a
small numeric loop, `$e` for a caught exception where the language convention
expects it, and any name the framework establishes. Do not lengthen a name that
is already unambiguous.

### `function-names` — action-oriented method names

A method name states what it does.

```text
createPurchaseApplication()
assignApplicationToSpecialist()
approveContract()
calculateContractTotal()
findAvailableSpecialists()
generatePurchaseApplicationPdf()
```

Avoid `execute()`, `run()`, `process()`, `perform()`, `manage()`, `handle()`
unless an interface or framework requires that exact name.

### `class-names` — names that state a responsibility

```text
PurchaseApplicationService
ContractApprovalService
PurchaseApplicationRepository
ContractPdfGenerator
ContractStatusTransitionValidator
```

Avoid `Helper`, `Manager`, `Processor`, `Utility`, `CommonService` unless that
term is already an architectural concept in this repository. Do not create a
class solely to satisfy a naming rule.

### `parameter-names` — business meaning in the signature

```php
// Avoid
function approve($id, $data, $user)

// Prefer
function approveContract(
    int $contractId,
    ApprovalData $approvalData,
    User $approver
): Contract
```

A caller should know what to pass from the signature alone.

### `input-types` — explicit parameter types

Use the language's native type system first. Use annotations only where native
types cannot express enough.

```php
public function assignApplication(
    PurchaseApplication $application,
    User $specialist
): PurchaseApplication
```

```python
def assign_application(
    application: PurchaseApplication,
    specialist: User,
) -> PurchaseApplication:
```

Where a DTO would be excessive, an array is acceptable if its shape is
documented:

```php
public function createContract(array $contractData): Contract
```

### `return-types` — explicit return types

```php
public function calculateTotal(): float
public function findContract(int $contractId): ?Contract
public function archiveContract(Contract $contract): void
```

```python
def calculate_total(items: list[ContractItem]) -> Decimal: ...
def archive_contract(contract: Contract) -> None: ...
```

Do not omit a return type without a concrete reason. Where several return shapes
are genuinely possible, express that with the language's own mechanism — a union
type, a result object, or a documented exception — not by leaving it unstated.

### `nullability` — explicit optional values

```php
public function findContract(int $contractId): ?Contract
```

A method whose contract implies a value must not return null unexpectedly.
Nullable behavior is visible from the type declaration, the documented contract,
or documented exception behavior — one of the three, always.

### `collection-types` — what is inside the collection

```php
/**
 * @return array<int, Contract>
 */

/**
 * @return Collection<int, Contract>
 */
```

```python
list[Contract]
dict[int, Contract]
```

A bare `@return array` or an untyped list leaves the caller guessing.

### `structured-inputs` — structure where structure is justified

Prefer a DTO, request object, or value object over a large array whose shape is
undocumented:

```php
// Avoid, when $data carries many unrelated fields
createContract(array $data)

// Prefer
createContract(CreateContractData $contractData)
```

Judgment applies. Weigh complexity, reuse, validation needs, parameter count,
and what the repository already does. Do not introduce a DTO for every trivial
function.

### `documentation` — contract, not repetition

Public or non-obvious functions and classes get documentation where the language
and project convention support it. Documentation explains the contract:

```php
/**
 * Assigns an accepted purchase application to a procurement specialist.
 *
 * @param PurchaseApplication $application Application being assigned.
 * @param User $specialist User who will become responsible for the application.
 *
 * @return PurchaseApplication Updated application containing the assignment.
 *
 * @throws InvalidApplicationStatusException
 *     When the application cannot be assigned from its current status.
 */
```

```python
def assign_application(
    application: PurchaseApplication,
    specialist: User,
) -> PurchaseApplication:
    """Assign an accepted purchase application to a procurement specialist.

    Args:
        application: Application being assigned.
        specialist: User who will become responsible for the application.

    Returns:
        The updated purchase application.

    Raises:
        InvalidApplicationStatusError: If the application cannot be assigned
            from its current status.
    """
```

Cover what the signature cannot: purpose, meaning of arguments and options,
important side effects, important exceptions, and significant business
constraints.

Do not restate a signature that already says everything. For an obvious private
method, a docblock adds nothing:

```php
private function calculateTotal(Collection $contractItems): Money
```

That signature is the documentation. A block repeating it is noise.

### `variadic-contract` — variable and keyword arguments

Where variadic parameters, option maps, or configuration dictionaries are used,
their contract must be documented: accepted values, expected types, meaning of
supported keys, defaults, and return behavior.

```python
def create_report(
    report_type: ReportType,
    *filters: ReportFilter,
    include_archived: bool = False,
    **export_options: ExportOption,
) -> Report:
```

Do not reach for `*args`, `**kwargs`, `$options`, or a generic map to avoid
designing an API. Prefer explicit parameters when the API is known.

### `boolean-names` — names that read as conditions

```text
$isApproved
$canEditContract
$hasActiveAssignment
$shouldNotifyManager
```

Not `$status`, `$flag`, `$check`, `$value`. Apply the equivalent convention in
other languages.

### `constants-enums` — no unexplained magic values

```php
// Avoid
if ($contract->status === 3)
if ($contract->status === 'a')

// Prefer
if ($contract->status === ContractStatus::APPROVED)
```

Use enums, constants, or value objects where the language version and the
repository's architecture justify them. Do not introduce one for a single local
literal.

### `comments` — why, not what

Names, types, and structure explain *what*. Comments explain *why*.

```php
// Noise
// Increase counter by one
$count++;

// Get user
$user = User::find($userId);

// Useful
// Keep rejected contracts in the statistics because management reports
// measure all purchasing activity, not only completed contracts.
```

Comment noise introduced by a change is itself a finding.

### `cohesion` — one clear responsibility

A method that validates input, queries several unrelated models, mutates
multiple entities, generates a PDF, sends notifications, writes logs, and
computes statistics is doing seven things. Decompose it.

There is no line limit. Cohesion and readability decide, not a number.

### `side-effects` — visible from the API

A function with important side effects makes them visible through its name, its
API design, or its documentation.

```text
sendContractApprovalNotification()   clear
processNotification()                not
```

Important side effects include database writes, external API calls, messages and
emails, file creation or deletion, queued jobs, and status transitions.

### `error-behavior` — predictable failure

A function must not silently swallow exceptions, return `false` in some failure
cases and throw in others without a stated reason, return unrelated types
depending on how it failed, or hide a critical external-service failure.

Document or type important error behavior. Follow the repository's existing
error-handling conventions.

### `domain-language` — the project's own vocabulary

Where the requirements call something a Purchase Application, the code says
`PurchaseApplication`, `PurchaseApplicationStatus`, `PurchaseApplicationService`
— not `OrderRequest`, `RequestDocument`, or `ProcurementTicket`.

For spec-driven projects, the requirement statements travel with the task in the
handoff. They are the vocabulary. The exception is a repository that has already
established a different canonical term; the existing codebase wins, and the
divergence is worth noting rather than silently mixing both.

### `framework-conventions` — the framework wins

Framework-required and conventional names stay as the framework defines them,
even when they look generic in isolation. In Laravel that includes `handle()`,
`rules()`, `authorize()`, `up()`, `down()`. Equivalents exist in every
framework.

Renaming a convention-bound method to satisfy a rule here is a defect, not a
fix.

## Language-Aware Application

Apply the strongest mechanism the target language actually offers.

| Language | Use |
| --- | --- |
| PHP | native parameter and return types, typed properties, enums where the version supports them, PHPDoc for array shapes and generics |
| Python | type hints, return annotations, docstrings, `TypedDict`, dataclasses, or Pydantic models where appropriate |
| TypeScript | interfaces and type aliases, explicit return types on exported functions, descriptive parameter names |
| Java, C# | native type contracts, nullability annotations, language-standard documentation |
| Go | explicit types, named returns only where they aid clarity, doc comments on exported identifiers |

Do not apply a PHP-specific rule to a Python file, or demand a mechanism the
target language or its version does not have.

## Severity

Only two levels, because only one of them stops a change.

| Severity | Meaning |
| --- | --- |
| `BLOCKING` | The contract cannot be understood or can be used incorrectly. |
| `ADVISORY` | A real improvement that does not endanger correct use. |

Blocking, for example:

- a public function whose contract cannot be understood from its signature
- missing types that make the API's behavior ambiguous
- a function that returns unrelated types depending on how it failed
- nullable behavior that is undocumented and can surprise a caller
- a parameter contract so ambiguous that a caller can reasonably get it wrong
- a name that actively misleads about what the code does
- an undocumented option map or variadic contract on a public API

Advisory, for example:

- a local variable name that could be marginally better
- docblock wording that could be clearer
- a harmless style preference
- a private helper whose name is adequate but not ideal

A subjective naming preference is never blocking. Turning taste into a failed
validation trains everyone to ignore the check, which costs more than the
preference was worth.

## Automated Tooling

Use the static analysis the target repository already has: PHPStan, Psalm, or
Laravel Pint for PHP; mypy, pyright, or ruff for Python; `tsc` and ESLint for
TypeScript.

Do not add a new analysis dependency to an application repository to enforce
this standard. A new dependency is a change like any other: it needs a plan, a
risk classification, and approval.

Tooling does not replace this review. A linter can prove a return type is
present. It cannot tell whether `createPurchaseApplication` is a more honest
name than `process`.

## Worked Example

Before:

```php
public function process($data)
{
    $res = Contract::create($data);

    return $res;
}
```

The name states nothing, the parameter has no type or meaning, the return type
is unstated, and `$res` describes its own mechanism rather than its content.

After:

```php
/**
 * Creates a contract from validated contract input.
 */
public function createContract(CreateContractData $contractData): Contract
{
    $createdContract = Contract::create($contractData->toArray());

    return $createdContract;
}
```

And the counter-example that matters just as much — this needs no docblock at
all:

```php
private function calculateTotal(Collection $contractItems): Money
```

The fix for unclear code is a clearer signature. Documentation is what remains
when the signature has done all it can.
