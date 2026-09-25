# Planning Guidelines

A useful plan is specific enough that another engineer can execute it without
rediscovering the same context, but small enough to avoid speculative design.

## Good Planning Behavior

- Prefer the smallest correct change.
- Use existing architecture before inventing new patterns.
- Preserve backward compatibility unless a breaking change is required.
- State assumptions explicitly.
- State unknowns explicitly.
- Plan tests before implementation.
- Identify risk before execution.
- Avoid speculative refactors.
- Avoid unrelated cleanup.

## Bad Plan

```text
1. Update backend.
2. Add tests.
3. Make sure everything works.
```

This plan does not identify behavior, files, contracts, risk, or test cases.

## Good Plan

```text
1. Add nullable `description` field to ApiToken.
2. Generate a new forward-only migration.
3. Expose `description` through ApiTokenSerializer.
4. Preserve current create behavior when description is omitted.
5. Add serializer tests for omitted, valid, and >200-character values.
6. Add API regression test verifying old requests remain valid.
```

This plan names the affected model, migration, serializer, compatibility rule,
and test cases.

## Public Contracts

Public contracts include APIs, CLI interfaces, configuration formats, database
schemas, generated artifacts, file formats, and documented behavior. Plans must
call out whether any public contract changes and whether old callers remain
compatible.

## Database Changes

Database plans should identify whether a schema migration is required, whether
the migration is forward-only, whether existing rows need data transformation,
and whether rollback or deployment sequencing creates risk.

## Approval Triggers

Human approval is usually required for authentication, authorization, payment,
billing, production access, secret handling, irreversible operations, destructive
migrations, or public breaking changes.
