# Validation Evidence

Validation exists to replace claims with evidence. The distinction that matters
is between "the tests pass" and "here is the command, the exit code, and the
output tail."

## Why a Script Runs the Checks

An agent that runs a test suite and then summarizes it from memory can be wrong
in two directions: it can miss a failure, and it can report a pass that never
happened. Neither is detectable afterwards from the summary alone.

`scripts/run_validation.py` removes that gap. It records:

- the exact command string
- the real exit code
- the wall-clock duration
- the last lines of real combined output

The report is the evidence. If the script did not record it, it did not happen.

## Choosing Checks

Prefer, in order:

1. Commands the repository documents — in `README`, `AGENTS.md`, or
   `CONTRIBUTING`.
2. Commands the repository's CI configuration runs.
3. Detected commands from manifests that exist.

Detection is deliberately conservative. It proposes `ruff` only when
`pyproject.toml` mentions `ruff`, and `npm run lint` only when `package.json`
declares a `lint` script. It never proposes a tool because the language usually
has one.

## The `not_run` Status

When an executable is missing from `PATH`, the check is recorded as `not_run`
with the missing binary named. This is not a pass and must never be reported as
one.

`not_run` usually means one of:

- the project's dependencies were never installed in this worktree
- the tool runs through a runner the command did not use
- the environment genuinely cannot run this check

The first two are fixable. Fix them and re-run rather than accepting a gap.

## The Built-In Clean Tree Check

Every run includes a `working-tree-clean` check. Uncommitted changes mean the
evidence does not describe any particular commit, so the report would not be
reproducible. A dirty tree fails validation by design.

## Reading a Failure

A failing check is information, not an obstacle to route around. Attribute it:

| Symptom | Likely cause | Next stage |
| --- | --- | --- |
| New test fails on the new behavior | implementation is wrong | `implement-change` |
| Existing test fails on untouched behavior | regression | `implement-change` |
| Test asserts behavior the plan contradicts | plan was wrong | `plan-change` |
| Tool errors before running any test | check misconfigured | report, do not drop |

State which one you concluded and why. "Flaky" is a claim that needs evidence
too: re-run it and record both runs.

## Timeouts

The default per-check timeout is 900 seconds. A timeout is recorded as
`timeout`, not as a failure of the code, because the two have different fixes.
Raise `--timeout` for genuinely slow suites rather than narrowing the suite.
