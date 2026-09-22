# Factory Map

An interactive map of the pipeline this repository defines, served from a local
HTTP server. It draws the seventeen stages, the edges between them, and the
seven gates, and it colours each stage by what the files on disk actually say.

This is tooling, not a skill. It carries no `SKILL.md`, because a skill is a
procedure an agent follows and this is a viewer a person runs. The rule is
enforced rather than remembered: `tests/test_skill_metadata.py` asserts the
exact list of seventeen skill directories, so an eighteenth directory with a
`SKILL.md` fails the suite.

## Running It

```bash
python factory-map/scripts/serve_map.py --port 8787
```

It prints `http://127.0.0.1:8787` and serves the map there. The server binds
the loopback interface explicitly and never any other. It reads the repository
and the factory directory, writes to neither, runs no subprocess, and executes
no pipeline stage.

| Option | Effect |
| --- | --- |
| `--port N` | Port on 127.0.0.1. Default 8787. `--port 0` picks a free one. |
| `--repo PATH` | Repository root. Default the working directory. |
| `--factory PATH` | Run-state directory. Default `<repo>/.factory`. |
| `--open` | Open the map in a browser once the server is up. |
| `--once --out FILE` | Write a self-contained HTML snapshot instead of serving. |

A snapshot inlines the state into the page, so it opens from the filesystem
with no server and no network. It is a photograph rather than a live view, and
the header says so.

Three routes exist and everything else is a 404:

| Route | Serves |
| --- | --- |
| `/` | the page |
| `/api/state` | the whole state as JSON, with the fingerprint as an `ETag` |
| `/api/skill/<name>` | one stage, where `<name>` is checked against the known stage list |

The name in `/api/skill/<name>` is compared against the seventeen known stages
and is never used to build a filesystem path, so there is nothing for a
traversal attempt to reach.

`scripts/build_state.py` does the scanning and can be run on its own:

```bash
python factory-map/scripts/build_state.py --repo . --out state.json
```

Its output is validated by `schemas/factory-map-state.schema.json`. That schema
describes tooling output; it is not a pipeline artifact contract like the other
sixteen.

## The Two State Sources

The map has two independent state sources and always shows both.

**Repository mode** describes how completely each stage is built. It is
available always, because it only needs this repository.

**Run mode** describes where a task has actually got to. It needs a `.factory`
directory. Without one the header says so and the map shows build status alone,
rather than an empty run that could be mistaken for a failed one.

Everything is derived from the filesystem when the request arrives. No status
is written into the page. The pipeline topology - which stages exist, in what
order, with gates where - is the one declared thing, taken from `AGENTS.md` and
`README.md`, and even that is checked: a skill directory the map does not place
is reported as a warning rather than dropped.

## Build Status

| Status | Means |
| --- | --- |
| `built` | everything below is present |
| `partial` | the stage exists but something below is missing, and the panel names it |
| `missing` | no `SKILL.md` |

A stage is `built` when it has a `SKILL.md` whose frontmatter parses and whose
`name` matches its directory, at least one `references/*.md`, its output schema
where its Output Contract names one, and, for each script it has, a test that
builds a path to that script.

That last rule is stricter than it looks, on purpose. A test counts only when
it reaches the script as a path, the way `tests/test_quality_review.py` does
with `ROOT / "validate-change" / "scripts" / "run_validation.py"`. Naming a
script inside a string does not count, and `tests/test_repository_structure.py`
is excluded entirely, because it lists every script path to assert the file
exists - which is not the same as running it.

Applied honestly, that rule reports `review-pull-request` as `partial` today:
nothing in `tests/` exercises `fetch_pull_request.py`. The map is meant to
surface that, not to round it up.

## Run Status

| Status | Means |
| --- | --- |
| `passed` | the artifact exists, satisfies its schema, and its fields say the stage succeeded |
| `blocked` | the artifact exists and a field says it did not succeed, or a gate condition failed |
| `invalid` | the artifact exists but is unreadable or does not satisfy its schema |
| `active` | no artifact yet, and every stage feeding this one is complete |
| `pending` | no artifact yet |
| `skipped` | an optional stage with no artifact while a later stage has one |
| `not_applicable` | an intake stage in a run that began from a scoped ticket |

`invalid` exists because a malformed artifact is not a passing stage. A file
that is present but does not satisfy its contract tells you less than no file
at all, and the map says so rather than counting the file.

## Which Field Decides What

Every status traces to a file and a field, shown in the detail panel and in the
Checkpoints view. These are the fields the schemas actually declare.

| Stage | Artifact | Decided by |
| --- | --- | --- |
| `start-from-spec` | none | whether any intake artifact exists |
| `ingest-requirements` | `requirements.json` | `unknowns[].status`, `conflicts[].status` |
| `clarify-project` | `project.json` | `status` is `confirmed` |
| `decompose-spec` | `backlog.json` | `status` is `approved` |
| `prepare-task` | `task-handoff.json` | present and schema-valid |
| `inspect-repository` | `context.json` | present and schema-valid |
| `plan-change` | `plan.json` | `ready_for_isolation`, and `approval_reason` when `risk_level` is HIGH or CRITICAL |
| `isolate-task` | `workspace.json` | `status` is `created` |
| `implement-change` | `implementation.json` | `status` is `implemented` |
| `validate-change` | `validation.json` | `status`, `ready_for_pull_request`, `code_quality.counts.BLOCKING` |
| `before-after` | `before-after.json` | `status` is `captured` |
| `security-review` | `security.json` | `counts.CRITICAL` is 0 |
| `update-documentation` | `documentation.json` | `status` is `updated` or `no_change_required` |
| `create-pull-request` | `pull-request.json` | `status` is `created` |
| `review-pull-request` | `review.json` | `status` is `reviewed` |
| `revise-pull-request` | `revision.json` | `status` is `revised` |
| `completion-report` | `completion.json` | `status` is `complete` and `inconsistencies` is empty |

The seven gates read the same files:

| Gate | Reads |
| --- | --- |
| CONTEXT CONFIRMED | `project.json:status` |
| BACKLOG APPROVED | `backlog.json:status` |
| READY | `task-handoff.json:readiness` |
| PLAN APPROVED | `plan.json:ready_for_isolation` |
| VALIDATION PASSED | `validation.json:status` |
| NO CRITICAL | `security.json:counts.CRITICAL` |
| HUMAN MERGE | nothing; it never passes automatically |

The READY gate is a special case worth knowing. `task-handoff.schema.json`
declares `readiness` as `{"const": "READY"}`, so a handoff for a task that is
not READY cannot satisfy its own contract. The gate is enforced by the schema,
and the map reports what the schema already decided.

## Where the Artifacts Are Looked For

Project artifacts are read from `<factory>/project.json`, `requirements.json`
and `backlog.json`, which `start-from-spec/SKILL.md` documents. Task artifacts
are read from `<factory>/tasks/<TASK-ID>/`, which `prepare-task/SKILL.md`
documents for `task-handoff.json`.

The nine per-stage filenames come from
`completion-report/references/audit-trail.md`, which lists them under a generic
artifact root and says to keep them outside the repository being changed. The
repository does not state that they live under `.factory/tasks/<TASK-ID>/`, so
that is this map reading an implication, and `--factory` exists to point it
somewhere else.

Three stages have no documented artifact filename anywhere in the repository:
`review-pull-request`, `revise-pull-request` and `completion-report`. The map
uses `review.json`, `revision.json` and `completion.json`, and the Artifacts
view labels those rows `factory-map` rather than `repository` so the difference
stays visible.

## The Page

One HTML file with its markup, styles, and script inline. No build step, no
package manager, no bundler, and nothing fetched from a network - the only
absolute URL in the file is the SVG namespace, which is an identifier and is
never requested. The graph is drawn as inline SVG paths; the cards are HTML,
because SVG cannot wrap a line of text.

| Interaction | Effect |
| --- | --- |
| click a node | detail panel: description, purpose, artifact, evidence, failure and escalation conditions |
| hover a node | dim everything else, keep its edges lit |
| drag | pan |
| scroll | zoom, with a zoom-to-fit control |
| `/` | filter nodes by name or description |
| Esc | close the panel, the filter, or the shortcut list |
| `?` | the shortcut list |
| click a side-menu row | focus the matching node on the canvas |

The page polls `/api/state` every three seconds with the previous `ETag`. An
unchanged repository answers `304` and nothing re-renders. The LIVE indicator
carries the time of the last change it saw.

State is never signalled by colour alone. A blocked card takes a rose border
and its tag chip changes text, so the state survives being read without colour.
