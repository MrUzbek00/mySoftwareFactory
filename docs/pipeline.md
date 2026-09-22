# The Pipeline

This is the canonical stage-by-stage description of the pipeline: what each
stage reads, what it produces, and what it refuses to let past.

`AGENTS.md` is the normative document. It states the rules an agent must
follow, and this document does not restate them in different words. What
follows explains the shape the rules produce, and why each gate is where it is.

## Two Entry Points

The pipeline has two entry points, and `AGENTS.md` decides which one an input
takes. A project-level document — a specification, a BRD, an SRS — enters at
the intake layer and is decomposed before anything is implemented. A single
task, ticket, or bug report enters the engineering workflow directly and never
touches intake.

The intake layer exists because a specification is not a unit of work. It
contains dozens of requirements at different levels of certainty, and some of
them contradict each other. Handing that to an implementation stage produces a
change nobody can review. Decomposition makes each unit small enough that its
plan, its diff, and its evidence can be read in one sitting.

## Stages

Specification intake. Runs only for project-level input.

| Stage | Reads | Produces | Gate |
| --- | --- | --- | --- |
| `start-from-spec` | the source document, existing `.factory/` state | a routing decision: new, resume, or amendment | none |
| `ingest-requirements` | the source document | a requirements index with source coordinates, unknowns, and conflicts | refuses a document it could not open |
| `clarify-project` | the requirements index | a confirmed project context | the user confirms the intake summary |
| `decompose-spec` | project context, requirements index | epics, features, and tasks with dependencies and readiness | the user approves the backlog |
| `prepare-task` | project context, requirements index, backlog | one task handoff | the task's readiness is `READY` |

Engineering. Runs for every task, whatever the entry point.

| Stage | Reads | Produces | Gate |
| --- | --- | --- | --- |
| `inspect-repository` | the target repository | repository context: relevant files, tests, contracts, risks | none |
| `plan-change` | task, repository context | a structured change plan with a risk level | human approval when the risk level is `HIGH` or `CRITICAL` |
| `isolate-task` | task, base branch | a branch and a Git worktree | refuses a dirty tree, an existing branch, or a protected base |
| `implement-change` | the approved plan | a commit inside the task worktree | writes nothing the plan does not name |
| `validate-change` | the worktree | commands, exit codes, output, and a code quality review | every check passes and no `BLOCKING` quality finding stands |
| `before-after` | base commit and task head | the same probes run on both sides | none |
| `security-review` | added lines only | secrets, dangerous sinks, and new dependencies | no `CRITICAL` finding stands |
| `update-documentation` | the change | documentation corrections | none |
| `create-pull-request` | the validated branch | one pull request | refuses a protected head branch and refuses to force push |
| `review-pull-request` | an open pull request | findings | read-only: cannot approve, merge, or comment |
| `revise-pull-request` | review feedback | fast-forward commits | refuses a diverged branch, never rewrites history |
| `completion-report` | every stage artifact | a validated report and the contradictions between artifacts | reports contradictions rather than resolving them |

## The Gates

A gate is a point where the pipeline stops rather than continues. Each one
exists because the alternative is a change that looks finished and is not.

**Project confirmation.** Intake asks its questions in one batch and presents a
summary. Nothing proceeds until the user confirms it, because every task
generated afterwards inherits whatever the summary got wrong.

**Backlog approval.** The decomposition is presented before anything is built.
A backlog that decomposes the wrong specification is cheap to discard and
expensive to discover three tasks later.

**Readiness.** Only a `READY` task is handed to the engineering workflow. A task
that is `AMBIGUOUS` or `BLOCKED` is a question wearing a task's clothes, and
implementing it means inventing the answer.

**Plan approval.** A `HIGH` or `CRITICAL` risk level requires a human decision
before isolation. Risk is classified by a model; the consequence of that
classification is enforced by the workflow.

**Validation.** A check reports pass only with a recorded exit code of zero.
This is why validation is a script rather than a prompt: a model can be
convinced that tests passed, and a process cannot.

**Code quality.** `validate-change` reviews changed backend files against
`standards/backend-code-quality.md`. A `BLOCKING` finding fails validation and
blocks publication. An `ADVISORY` finding is recorded and changes nothing.

**Security.** The scan reads added lines only, and redacts secret material on
match rather than reproducing it. A `CRITICAL` finding blocks publication.

## Where the Pipeline Stops

These are deliberately unimplemented, and are decisions rather than gaps:

- merging or approving a pull request
- enabling auto-merge or dismissing reviews
- deploying, releasing, or touching production
- modifying branch protection or repository settings

Each is a judgement about consequences outside the change itself. The pipeline
assembles the evidence for that judgement and hands it to a human.
