# Observable Evidence

Validation answers "does it still work." Before-and-after answers "what is
different now." They are different questions and they need different commands.

## A Probe Is Not a Test

A test asserts. A probe observes. The probe does not know what the right answer
is — it runs the same command on both commits and records both results, and the
difference is the evidence.

That is why a probe must run on the base commit too. A command that only exists
after the change produces `not_run` on the before side, and a one-sided result
demonstrates nothing.

## Choosing a Probe

Good probes are:

- **Deterministic** — same input, same output, every run.
- **Fast** — seconds, not minutes.
- **Offline** — no network, no production service, no credentials.
- **Narrow** — they exercise the behavior the plan changed, not the whole app.

Examples that work well:

```text
--probe reset-expiry="python -m demo reset --token expired"
--probe exit-code="python -m demo validate bad-input.json"
--probe help-text="mytool --help"
--probe single-test="pytest tests/test_auth.py::test_expired_token -q"
```

## Sources of False Differences

A probe whose output embeds any of these will report `changed: true` on every
run, including runs where nothing changed:

- timestamps, durations, or dates
- absolute paths — and the two sides run in different directories, so paths
  differ by construction
- random IDs, UUIDs, ports, PIDs
- hash values derived from paths or times
- iteration order of an unordered collection
- log lines with sequence numbers

If a probe must produce such output, filter it in the command itself rather than
explaining the noise afterwards.

## Reading the Result

| Probe targets | `changed` | Reading |
| --- | --- | --- |
| behavior the plan changed | `true` | expected — this is the evidence |
| behavior the plan changed | `false` | the change may not work; investigate |
| behavior the plan did not touch | `true` | possible regression; investigate |
| behavior the plan did not touch | `false` | expected |

A refactor is the useful inversion: for a refactor, `changed: false` on the
targeted probes is exactly the evidence you want, and `changed: true` is the
problem.

## The Scratch Worktree

The script creates a detached worktree at the base commit, uses it, and removes
it. Two consequences worth knowing:

- The base side runs against a **clean checkout of the base commit** — it has no
  build output, no installed dependencies, and no local configuration. A probe
  that needs those will report `not_run` or fail on the before side only. Prefer
  probes that run against source.
- Removal only touches the detached worktree the script created. It checks that
  HEAD is detached before removing, so a worktree attached to a branch is never
  deleted by this stage.

## When to Skip This Stage

Skip, and record that you skipped, when the change has no observable behavior to
probe: an internal refactor with identical outputs and no exercised path worth
demonstrating, a documentation-only change, or a comment or type-annotation
change.

Skipping is a decision to state, not a step to quietly omit.
