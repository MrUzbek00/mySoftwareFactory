# Schema Index

`my-software-factory/schemas/` holds one JSON Schema per artifact. Every stage that produces an
artifact validates it against the schema named here, and `completion-report`
validates all of them again at the end.

This document is the index. It says which stage writes each schema and which
stage consumes what that schema describes.

Sixteen of these schemas are pipeline artifact contracts. One,
`factory-map-state.schema.json`, is the output contract of a tool rather than
of a stage, and is listed separately at the end.

## Intake Artifacts

Produced only when the input is a project-level specification. These live in
`.factory/` in the repository being built.

| Schema | Written by | Read by |
| --- | --- | --- |
| `project-context.schema.json` | `clarify-project` | `decompose-spec`, `prepare-task` |
| `requirements-index.schema.json` | `ingest-requirements` | `decompose-spec`, `prepare-task` |
| `project-backlog.schema.json` | `decompose-spec` | `prepare-task` |
| `task-handoff.schema.json` | `prepare-task` | every engineering stage |

## Task Artifacts

Produced once per task, in pipeline order.

| Schema | Written by | Read by |
| --- | --- | --- |
| `repository-context.schema.json` | `inspect-repository` | `plan-change` |
| `change-plan.schema.json` | `plan-change` | `implement-change` |
| `workspace-result.schema.json` | `isolate-task` | `implement-change` |
| `implementation-result.schema.json` | `implement-change` | `validate-change` |
| `validation-report.schema.json` | `validate-change` | `create-pull-request` |
| `before-after-report.schema.json` | `before-after` | `create-pull-request` |
| `security-review.schema.json` | `security-review` | `create-pull-request` |
| `documentation-update.schema.json` | `update-documentation` | `create-pull-request` |
| `pull-request-result.schema.json` | `create-pull-request` | `review-pull-request`, `revise-pull-request` |
| `pull-request-review.schema.json` | `review-pull-request` | `revise-pull-request` |
| `revision-result.schema.json` | `revise-pull-request` | `completion-report` |
| `completion-report.schema.json` | `completion-report` | the human who owns the merge |

`start-from-spec` is the one stage with no schema of its own. It routes, and
the artifacts it points at belong to the stages that write them.

## Tooling

| Schema | Written by | Read by |
| --- | --- | --- |
| `factory-map-state.schema.json` | `tools/factory-map/scripts/build_state.py` | the map page, and `tests/test_build_state.py` |

This one is not a pipeline artifact. No stage produces it, `completion-report`
never validates it, and its presence in `my-software-factory/schemas/` is a convenience rather than
a claim that the map is part of the pipeline.

## The Audit Pass

`my-software-factory/stages/engineering/completion-report/scripts/build_report.py` maps a stage name to a schema
filename and revalidates every artifact it is given:

```bash
python my-software-factory/stages/engineering/completion-report/scripts/build_report.py \
  --task-id TASK-123 \
  --schemas-dir schemas \
  --artifact plan-change=/artifacts/TASK-123/change-plan.json \
  --artifact validate-change=/artifacts/TASK-123/validation-report.json
```

The script takes the schema directory as an argument and resolves each schema
by filename. Schema filenames are therefore an interface, not an
implementation detail: renaming one breaks the audit pass at runtime, not at
import time. They are also referenced by name from the `SKILL.md` of the stage
that writes them, and from `tests/test_json_schemas.py`.

## Conventions

Every schema declares `$schema` as Draft 2020-12 and an `$id` of the form:

```text
https://example.com/my-software-factory/<artifact-name>.schema.json
```

The identifier is not resolved over the network. It exists so that a schema
stays identifiable once an artifact has been copied away from this repository.
The final path segment matches the filename, which is what keeps the two
coherent.

Schemas reject unknown values rather than ignoring them. A readiness state, a
risk level, a severity, and a quality criterion are all closed enumerations, so
a stage cannot invent `ALMOST_READY` or grade a finding as `NITPICK` to get
past a gate. `tests/test_json_schemas.py` asserts those refusals directly.
